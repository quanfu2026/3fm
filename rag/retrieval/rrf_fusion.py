"""
RRF（Reciprocal Rank Fusion）排序融合策略
整合 BM25 與 BGE-M3 兩階段檢索結果
公式：RRF(d) = Σ 1 / (k + rank_i(d))
"""
import os
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

RRF_K = int(os.getenv("RRF_K", "60"))


class RRFFusion:

    def __init__(self, k: int = RRF_K):
        self.k = k

    def fuse(
        self,
        bm25_results: list,
        bge_results:  list,
        top_k:        int = 10,
    ) -> list:
        """
        融合兩個排序列表，回傳按 RRF 分數排序的文件列表

        Args:
            bm25_results: BM25 檢索結果（含 rank_bm25）
            bge_results:  BGE  檢索結果（含 rank_bge）
            top_k:        回傳前 K 筆

        Returns:
            list of doc dicts，含 rrf_score 與兩源排名
        """
        doc_map   = {}   # id → doc dict
        rrf_scores = defaultdict(float)

        # ── BM25 貢獻 ──
        for rank, doc in enumerate(bm25_results, 1):
            doc_id = doc["id"]
            doc_map[doc_id]     = doc
            rrf_scores[doc_id] += 1.0 / (self.k + rank)

        # ── BGE 貢獻 ──
        for rank, doc in enumerate(bge_results, 1):
            doc_id = doc["id"]
            if doc_id not in doc_map:
                doc_map[doc_id] = doc
            rrf_scores[doc_id] += 1.0 / (self.k + rank)

        # ── 排序 ──
        sorted_ids = sorted(
            rrf_scores, key=lambda x: rrf_scores[x], reverse=True
        )[:top_k]

        results = []
        for new_rank, doc_id in enumerate(sorted_ids, 1):
            doc = dict(doc_map[doc_id])
            doc["score"]     = round(rrf_scores[doc_id], 6)
            doc["rrf_score"] = round(rrf_scores[doc_id], 6)
            doc["rank"]      = new_rank
            results.append(doc)

        logger.debug(
            f"RRF 融合：BM25={len(bm25_results)} BGE={len(bge_results)} "
            f"→ 融合後={len(results)}"
        )
        return results
