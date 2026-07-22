import os
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")


class BGEReranker:

    def __init__(self):
        self.model = None
        self._load_failed = False

    def _ensure_model(self):
        """延遲載入 Reranker 模型：第一次真正呼叫 rerank() 時才載入，
        避免每次啟動 Flask 都花時間載入模型（尤其是不一定會用到 reranker 的請求）。
        """
        if self.model is not None or self._load_failed:
            return

        try:
            from rag.utils.env_patch import ensure_datasets_importable
            ensure_datasets_importable()

            from FlagEmbedding import FlagReranker

            self.model = FlagReranker(MODEL_NAME, use_fp16=True)

            logger.info("Reranker 模型載入成功：%s", MODEL_NAME)

        except Exception as exc:
            logger.exception("Reranker 模型載入失敗，將回退為不重排序：%s", exc)
            self.model = None
            self._load_failed = True

    def rerank(
        self,
        query: str,
        docs: List[dict],
        top_k: int = 5,
    ) -> List[dict]:
        if not docs:
            return docs[:top_k]

        self._ensure_model()

        # 模型未能成功載入時，回退為原始排序（不重排序），
        # 讓上層 pipeline 仍可正常運作，只是少了重排序的效果。
        if self.model is None:
            logger.warning("Reranker 未啟用（模型未載入），回退為原始排序")
            return docs[:top_k]

        try:
            pairs = [
                [query, d.get("content", "")]
                for d in docs
            ]

            scores = self.model.compute_score(
                pairs,
                normalize=True,
            )

            # compute_score 在只有一組 pair 時會回傳 float 而非 list，統一成 list
            if isinstance(scores, float):
                scores = [scores]

            scored_docs = []
            for doc, score in zip(docs, scores):
                new_doc = dict(doc)
                new_doc["score"] = float(score)
                new_doc["rerank_score"] = float(score)
                scored_docs.append(new_doc)

            scored_docs.sort(key=lambda d: d["score"], reverse=True)

            return scored_docs[:top_k]

        except Exception as exc:
            logger.exception("Reranker 重排序失敗，回退為原始排序：%s", exc)
            return docs[:top_k]
