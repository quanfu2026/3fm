"""
BM25 稀疏檢索器 — 第一階段（求準）
使用 rank-bm25 套件，對中文文本進行結巴分詞後建立倒排索引
"""
import os
import pickle
import jieba
import logging
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

INDEX_PATH = os.path.join(
    os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge_base"),
    "bm25_index.pkl"
)


class BM25Retriever:

    def __init__(self):
        self.bm25   = None
        self.docs   = []   # [{"id", "content", "source", "type"}]

    # ── 建立索引 ──────────────────────────────────────
    def build(self, docs: list):
        """
        docs: list of {"id": str, "content": str, "source": str, "type": str}
        """
        self.docs = docs
        tokenized = [self._tokenize(d["content"]) for d in docs]
        self.bm25 = BM25Okapi(tokenized)
        self._save()
        logger.info(f"BM25 索引建立完成：{len(docs)} 筆")

    # ── 檢索 ──────────────────────────────────────────
    def search(self, query: str, top_k: int = 10) -> list:
        if self.bm25 is None:
            logger.warning("BM25 索引未載入")
            return []

        tokens = self._tokenize(query)
        scores = self.bm25.get_scores(tokens)

        ranked = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )[:top_k]

        results = []
        for idx, score in ranked:
            if score > 0:
                doc = dict(self.docs[idx])
                doc["score"]    = float(score)
                doc["rank_bm25"] = len(results) + 1
                results.append(doc)

        return results

    # ── 持久化 ────────────────────────────────────────
    def _save(self):
        os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
        with open(INDEX_PATH, "wb") as f:
            pickle.dump({"bm25": self.bm25, "docs": self.docs}, f)

    def load(self):
        with open(INDEX_PATH, "rb") as f:
            data = pickle.load(f)
        self.bm25 = data["bm25"]
        self.docs = data["docs"]
        logger.info(f"BM25 索引載入：{len(self.docs)} 筆")

    # ── 中文分詞 ──────────────────────────────────────
    @staticmethod
    def _tokenize(text: str) -> list:
        """結巴分詞，同時保留英數字"""
        return list(jieba.cut_for_search(text))
