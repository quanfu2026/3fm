"""
RAG Pipeline — 雙階段檢索增強生成核心流程
階段1: BM25 求準 → 階段2: BGE-M3 求廣 → RRF 融合 → (可選) BGE-Reranker → Ollama 本地模型生成
"""
import os
import time
import json
import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    完整 RAG 處理流程：
      1. BM25 第一階段（求準）
      2. BGE-M3 第二階段（求廣）
      3. RRF 排序融合
      4. BGE-Reranker 重排序（可選）
      5. Prompt 組合
      6. Ollama 本地 LLM 生成回答
      7. 自動評測 Hit@5 / MRR / NDCG@5 / 平均延遲
    """

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
        self.llm = OllamaInterface(model="llama3:latest")
        self.builder = KnowledgeBuilder()

        self._ensure_index()

    # ── 知識庫初始化 ──────────────────────────────────
    def _ensure_index(self):
        """若索引不存在則自動建立。"""
        try:
            self.bm25.load()
            self.bge.load()
            logger.info("✅ 索引載入成功")
        except FileNotFoundError:
            logger.warning("⚠️ 索引不存在，開始自動建立...")
            self.rebuild_index()

    def rebuild_index(self):
        """重新建立 BM25 + BGE 向量索引。"""
        docs = self.builder.load_all_documents()
        self.bm25.build(docs)
        self.bge.build(docs)
        logger.info(f"✅ 索引建立完成，共 {len(docs)} 筆文件")

    # ── 主查詢入口 ────────────────────────────────────
    def query(
        self,
        user_query: str,
        reranker_enabled: Optional[bool] = None,
        top_k: int = 5,
        bm25_top_k: int = 10,
    ) -> dict:
        """
        完整 RAG 查詢流程。

        Returns:
            {
                answer: str,
                sources: list,
                metrics: dict,
                reranker_diff: list
            }
        """
        t_start = time.time()

        use_reranker = reranker_enabled
        if use_reranker is None:
            use_reranker = os.getenv("RERANKER_ENABLED", "true").lower() == "true"

        # 階段 1：BM25 求準
        bm25_results = self.bm25.search(user_query, top_k=bm25_top_k)

        # 階段 2：BGE-M3 求廣
        bge_results = self.bge.search(user_query, top_k=bm25_top_k)

        # RRF 排序融合
        fused = self.rrf.fuse(bm25_results, bge_results, top_k=top_k * 2)

        reranker_ms = 0
        reranker_diff = []

        # BGE-Reranker 重排序（可選）
        if use_reranker:
            t_rerank = time.time()
            before_ids = [d["id"] for d in fused[:top_k]]
            fused = self.reranker.rerank(user_query, fused, top_k=top_k)
            after_ids = [d["id"] for d in fused]
            reranker_ms = int((time.time() - t_rerank) * 1000)
            reranker_diff = self._build_diff(before_ids, after_ids, fused)
        else:
            fused = fused[:top_k]

        # Prompt 組合 + LLM 生成
        context = self._build_context(fused)
        answer = self.llm.generate(user_query, context)

        total_ms = int((time.time() - t_start) * 1000)

        return {
            "answer": answer,
            "sources": fused,
            "metrics": {
                "total_ms": total_ms,
                "reranker_ms": reranker_ms,
                "reranker_enabled": use_reranker,
                "bm25_hits": len(bm25_results),
                "bge_hits": len(bge_results),
                "final_docs": len(fused),
            },
            "reranker_diff": reranker_diff,
        }

    # ── 自動評測入口 ───────────────────────────────────
    def evaluate(self, eval_path="data/eval_questions.json", top_k=5, bm25_top_k=10) -> dict:
        """
        讀取測試題 JSON，自動計算 Hit@5 / MRR / NDCG@5 / 平均延遲。

        eval_questions.json 建議格式：
        [
          {"question": "iPhone 15 有保固嗎？", "answer_doc_id": "faq_001"}
        ]
        """
        if not os.path.exists(eval_path):
            return {
                "error": f"找不到評測檔案：{eval_path}",
                "hint": "請先建立 data/eval_questions.json，內容需包含 question 與 answer_doc_id。",
                "total_questions": 0,
                "Hit@5": 0,
                "MRR": 0,
                "NDCG@5": 0,
                "avg_latency_ms": 0,
            }

        with open(eval_path, "r", encoding="utf-8") as f:
            eval_data = json.load(f)

        if not eval_data:
            return {
                "error": "評測檔案是空的。",
                "total_questions": 0,
                "Hit@5": 0,
                "MRR": 0,
                "NDCG@5": 0,
                "avg_latency_ms": 0,
            }

        hit_count = 0
        mrr_total = 0.0
        ndcg_total = 0.0
        latency_total = 0.0
        total = len(eval_data)

        for item in eval_data:
            question = item.get("question", "")
            answer_doc_id = item.get("answer_doc_id") or item.get("gt_doc_id") or item.get("doc_id")

            if not question or not answer_doc_id:
                continue

            start = time.time()

            bm25_results = self.bm25.search(question, top_k=bm25_top_k)
            bge_results = self.bge.search(question, top_k=bm25_top_k)
            fused = self.rrf.fuse(bm25_results, bge_results, top_k=top_k)

            latency_ms = (time.time() - start) * 1000
            latency_total += latency_ms

            retrieved_ids = [str(doc.get("id")) for doc in fused]
            answer_doc_id = str(answer_doc_id)

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

    # ── 輔助方法 ──────────────────────────────────────
    def _build_context(self, docs: list) -> str:
        parts = []
        for i, d in enumerate(docs, 1):
            parts.append(f"[知識片段 {i}]\n{d['content']}")
        return "\n\n".join(parts)

    def _build_diff(self, before: list, after: list, docs: list) -> list:
        """建立重排前後對比列表。"""
        diff = []
        score_map = {d["id"]: round(d.get("score", 0), 4) for d in docs}
        for new_rank, doc_id in enumerate(after, 1):
            old_rank = (before.index(doc_id) + 1) if doc_id in before else ">"
            diff.append({
                "doc_id": doc_id,
                "old_rank": old_rank,
                "new_rank": new_rank,
                "score": score_map.get(doc_id, 0),
            })
        return diff
