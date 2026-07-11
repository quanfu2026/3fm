"""
RAGPipeline
雙階段檢索增強生成核心流程
BM25 → BGE-M3 → RRF → 可選 Reranker → Ollama Qwen2.5 生成
"""

import os
import time
import json
import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RAGPipeline:
    def __init__(self):
        from rag.retrieval.bm25_retriever import BM25Retriever
        from rag.retrieval.bge_retriever import BGERetriever
        from rag.retrieval.rrf_fusion import RRFFusion
        from rag.reranker.bge_reranker import BGEReranker
        from rag.generator.ollama_interface import OllamaInterface
        from rag.utils.knowledge_builder import KnowledgeBuilder

        self.bm25 = BM25Retriever()
        self.bge = BGERetriever()
        self.rrf = RRFFusion()
        self.reranker = BGEReranker()
        self.llm = OllamaInterface(model="qwen2.5:3b")
        self.builder = KnowledgeBuilder()

        self._ensure_index()
    @staticmethod
    def _deduplicate_results(
        results: list,
    ) -> tuple[list, int]:
        """
        清理檢索結果：

        1. 移除完全相同內容。
        2. 移除高度相似問題。
        3. 移除高度相似答案。
        4. 移除 FAQ 編號等雜訊。
        5. 回傳清理結果與移除數量。
        """
        import re
        from difflib import SequenceMatcher

        def extract_question_answer(
            content: str,
        ) -> tuple[str, str]:
            question_match = re.search(
                r"問題\s*[：:]\s*(.+?)"
                r"(?=\n\s*答案\s*[：:]|\Z)",
                content,
                flags=re.IGNORECASE | re.DOTALL,
            )

            answer_match = re.search(
                r"答案\s*[：:]\s*(.+)",
                content,
                flags=re.IGNORECASE | re.DOTALL,
            )

            question = (
                question_match.group(1).strip()
                if question_match
                else content.strip()
            )

            answer = (
                answer_match.group(1).strip()
                if answer_match
                else ""
            )

            return question, answer

        def normalize(text: str) -> str:
            text = text or ""

            text = re.sub(
                r"#+\s*FAQ\s*\d+",
                "",
                text,
                flags=re.IGNORECASE,
            )

            text = text.lower()
            text = text.replace("臺", "台")
            text = text.replace("～", "~")
            text = text.replace("→", "")

            text = re.sub(
                r"[？?！!，,。．、：:；;"
                r"（）()\[\]【】「」『』\s~\-]+",
                "",
                text,
            )

            return text.strip()

        def similarity(
            left: str,
            right: str,
        ) -> float:
            if not left or not right:
                return 0.0

            if left == right:
                return 1.0

            if left in right or right in left:
                shorter = min(len(left), len(right))
                longer = max(len(left), len(right))

                if longer > 0 and shorter / longer >= 0.65:
                    return 0.95

            return SequenceMatcher(
                None,
                left,
                right,
            ).ratio()

        unique_results = []
        removed_count = 0

        for item in results:
            copied = dict(item)

            content = copied.get("content", "")
            question, answer = extract_question_answer(
                content
            )

            clean_question = normalize(question)
            clean_answer = normalize(answer)
            clean_content = normalize(content)

            copied["content"] = re.sub(
                r"\s*#+\s*FAQ\s*\d+\s*$",
                "",
                content,
                flags=re.IGNORECASE,
            ).strip()

            is_duplicate = False

            for accepted in unique_results:
                accepted_content = accepted.get(
                    "_clean_content",
                    "",
                )
                accepted_question = accepted.get(
                    "_clean_question",
                    "",
                )
                accepted_answer = accepted.get(
                    "_clean_answer",
                    "",
                )

                if (
                    clean_content
                    and clean_content == accepted_content
                ):
                    is_duplicate = True
                    break

                question_similarity = similarity(
                    clean_question,
                    accepted_question,
                )

                answer_similarity = similarity(
                    clean_answer,
                    accepted_answer,
                )

                if question_similarity >= 0.82:
                    is_duplicate = True
                    break

                if (
                    clean_answer
                    and accepted_answer
                    and answer_similarity >= 0.90
                ):
                    is_duplicate = True
                    break

            if is_duplicate:
                removed_count += 1
                continue

            copied["_clean_question"] = clean_question
            copied["_clean_answer"] = clean_answer
            copied["_clean_content"] = clean_content

            unique_results.append(copied)

        cleaned = []

        for item in unique_results:
            item.pop("_clean_question", None)
            item.pop("_clean_answer", None)
            item.pop("_clean_content", None)
            cleaned.append(item)

        return cleaned, removed_count
    def _ensure_index(self):
        try:
            self.bm25.load()
            self.bge.load()
            logger.info("索引載入成功")
        except FileNotFoundError:
            logger.warning("索引不存在，開始自動建立...")
            self.rebuild_index()

    def rebuild_index(self):
        docs = self.builder.load_all_documents()
        self.bm25.build(docs)
        self.bge.build(docs)
        logger.info(f"索引建立完成，共 {len(docs)} 筆文件")

    def query(
        self,
        user_query: str,
        reranker_enabled: Optional[bool] = None,
        top_k: int = 5,
        bm25_top_k: int = 10,
    ) -> dict:
        t_start = time.time()

        use_reranker = reranker_enabled
        if use_reranker is None:
            use_reranker = os.getenv("RERANKER_ENABLED", "false").lower() == "true"

        bm25_results = self.bm25.search(user_query, top_k=bm25_top_k)
        bge_results = self.bge.search(user_query, top_k=bm25_top_k)

        raw_fused = self.rrf.fuse(
            bm25_results,
            bge_results,
            top_k=max(top_k * 4, 20),
        )
        fused, removed_count = self._deduplicate_results(raw_fused)

        print(
            f"[CLEAN] 原始={len(raw_fused)} "
            f"移除={removed_count} "
            f"保留={len(fused)}"
        )

        reranker_ms = 0
        reranker_diff = []

        if use_reranker:
            try:
                t_rerank = time.time()
                before_ids = [d["id"] for d in fused[:top_k]]
                fused = self.reranker.rerank(
                    user_query,
                    fused,
                    top_k=top_k * 2,
                )
                fused, reranker_removed = self._deduplicate_results(fused)
                removed_count += reranker_removed
                fused = fused[:top_k]

                after_ids = [d["id"] for d in fused]
                reranker_ms = int((time.time() - t_rerank) * 1000)
                reranker_diff = self._build_diff(before_ids, after_ids, fused)

                print(
                    f"[CLEAN AFTER RERANKER] "
                    f"再次移除={reranker_removed} "
                    f"最終保留={len(fused)}"
                )
            except Exception as e:
                logger.warning(f"Reranker 失敗，改用融合結果：{e}")
                fused = fused[:top_k]
        else:
            fused = fused[:top_k]

        context = self._build_context(fused)

        print("=" * 60)
        print("BM25:", len(bm25_results))
        print("BGE :", len(bge_results))
        print("FUSED:", len(fused))
        print(context[:1000])
        print("=" * 60)

        answer = self.llm.generate(user_query, context)

        total_ms = int((time.time() - t_start) * 1000)

        return {
            "answer": answer,

            "sources": [
                {
                    "rank": i + 1,
                    "id": d.get("id"),
                    "source": d.get("source"),
                    "type": d.get("type"),
                    "content": d.get("content", "")[:400],
                }
                for i, d in enumerate(fused)
            ],

            "metrics": {
                "total_ms": total_ms,
                "reranker_ms": reranker_ms,
                "reranker_enabled": use_reranker,
                "bm25_hits": len(bm25_results),
                "bge_hits": len(bge_results),
                "final_docs": len(fused),
                "duplicates_removed": removed_count,
            },

            "reranker_diff": reranker_diff,
        }

    def evaluate(self, eval_path="data/eval_questions.json", top_k=5):
        with open(eval_path, "r", encoding="utf-8") as f:
            eval_data = json.load(f)

        hit_count = 0
        mrr_total = 0
        ndcg_total = 0
        latency_total = 0
        total = len(eval_data)

        for item in eval_data:
            question = item["question"]
            answer_doc_id = item["answer_doc_id"]

            start = time.time()

            bm25_results = self.bm25.search(question, top_k=10)
            bge_results = self.bge.search(question, top_k=10)
            raw_fused = self.rrf.fuse(
                bm25_results,
                bge_results,
                top_k=max(top_k * 4, 20),
            )
            fused, _ = self._deduplicate_results(raw_fused)
            fused = fused[:top_k]
            latency_ms = (time.time() - start) * 1000
            latency_total += latency_ms

            retrieved_ids = [doc["id"] for doc in fused]
            print("QUESTION:", question)
            print("ANSWER_DOC_ID:", answer_doc_id)
            print("RETRIEVED_IDS:", retrieved_ids)
            print("-" * 60)
            if answer_doc_id in retrieved_ids:
                hit_count += 1
                rank = retrieved_ids.index(answer_doc_id) + 1
                mrr_total += 1 / rank
                ndcg_total += 1 / math.log2(rank + 1)

        return {
            "total_questions": total,
            "Hit@5": round(hit_count / total, 4),
            "MRR": round(mrr_total / total, 4),
            "NDCG@5": round(ndcg_total / total, 4),
            "avg_latency_ms": round(latency_total / total, 2),
        }

    def _build_context(self, docs: list) -> str:
        parts = []
        for i, d in enumerate(docs, 1):
            parts.append(f"[知識片段 {i}]\n{d.get('content', '')}")
        return "\n\n".join(parts)

    def _build_diff(self, before: list, after: list, docs: list) -> list:
        diff = []
        score_map = {d["id"]: round(d.get("score", 0), 4) for d in docs}

        for new_rank, doc_id in enumerate(after, 1):
            old_rank = before.index(doc_id) + 1 if doc_id in before else ">"
            diff.append({
                "doc_id": doc_id,
                "old_rank": old_rank,
                "new_rank": new_rank,
                "score": score_map.get(doc_id, 0),
            })

        return diff
   