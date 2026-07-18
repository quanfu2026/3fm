import os
import pickle
import logging

import numpy as np

logger = logging.getLogger(__name__)

INDEX_PATH = os.path.join(
    os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge_base"),
    "bge_index.pkl",
)

MODEL_NAME = os.getenv(
    "BGE_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)


class BGERetriever:

    def __init__(self):
        self.model = None
        self.docs = []
        self.vectors = None

    def _ensure_model(self):
        if self.model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(MODEL_NAME)

            logger.info(
                "語意嵌入模型載入成功：%s",
                MODEL_NAME,
            )

        except Exception as exc:
            logger.exception(
                "語意嵌入模型載入失敗：%s",
                exc,
            )
            self.model = None

    def build(self, docs: list):
        self._ensure_model()

        if self.model is None:
            raise RuntimeError(
                "語意嵌入模型未成功載入，無法建立向量索引。"
            )

        # 增量索引：沿用「id 與內容都沒變」的 chunk 既有向量，
        # 只對新增或內容有變動的 chunk 重新呼叫模型計算 embedding。
        # 這樣重建索引的耗時只跟「有變動的量」成正比，不會隨著
        # 知識庫累積的檔案越來越多而每次都全部重算。
        previous_by_id = {}
        if self.docs and self.vectors is not None and len(self.docs) == len(self.vectors):
            for document, vector in zip(self.docs, self.vectors):
                previous_by_id[document.get("id")] = (
                    document.get("content"),
                    vector,
                )

        reused_vectors: list = [None] * len(docs)
        pending_indexes = []
        pending_texts = []

        for index, document in enumerate(docs):
            content = document.get("content", "")
            cached = previous_by_id.get(document.get("id"))

            if cached is not None and cached[0] == content:
                reused_vectors[index] = cached[1]
            else:
                pending_indexes.append(index)
                pending_texts.append(content)

        reused_count = len(docs) - len(pending_texts)
        logger.info(
            "增量索引：共 %s 筆，沿用 %s 筆，重新編碼 %s 筆",
            len(docs), reused_count, len(pending_texts),
        )
        print(
            f"[BGE] 共 {len(docs)} 筆，沿用 {reused_count} 筆，"
            f"重新編碼 {len(pending_texts)} 筆（增量索引）"
        )

        if pending_texts:
            new_vectors = self.model.encode(
                pending_texts,
                batch_size=16,
                show_progress_bar=True,
                normalize_embeddings=True,
            )

            for offset, index in enumerate(pending_indexes):
                reused_vectors[index] = new_vectors[offset]

        self.docs = docs

        if docs:
            self.vectors = np.asarray(reused_vectors, dtype=np.float32)
        else:
            dimension = self.model.get_sentence_embedding_dimension()
            self.vectors = np.zeros((0, dimension), dtype=np.float32)

        self._save()

        logger.info(
            "語意向量索引建立完成，共 %s 筆",
            len(self.docs),
        )

    def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> list:
        if self.vectors is None or len(self.docs) == 0:
            logger.warning(
                "語意向量索引尚未載入或內容為空"
            )
            return []

        # 必須先載入模型，再判斷是否成功。
        self._ensure_model()

        if self.model is None:
            logger.error(
                "語意嵌入模型載入失敗，無法執行搜尋"
            )
            return []

        try:
            query_vector = self.model.encode(
                [query],
                normalize_embeddings=True,
            )[0]

            query_vector = np.asarray(
                query_vector,
                dtype=np.float32,
            )

            if self.vectors.ndim != 2:
                raise ValueError(
                    f"向量索引維度錯誤：{self.vectors.shape}"
                )

            if self.vectors.shape[1] != query_vector.shape[0]:
                raise ValueError(
                    "向量維度不一致："
                    f"index={self.vectors.shape[1]}, "
                    f"query={query_vector.shape[0]}"
                )

            scores = self.vectors @ query_vector

            ranked_indexes = np.argsort(
                scores
            )[::-1][:top_k]

            results = []

            for rank, index in enumerate(
                ranked_indexes,
                start=1,
            ):
                document = dict(self.docs[int(index)])

                document["score"] = float(
                    scores[int(index)]
                )
                document["rank_bge"] = rank

                results.append(document)

            logger.info(
                "語意檢索完成：query=%s，results=%s",
                query,
                len(results),
            )

            return results

        except Exception as exc:
            logger.exception(
                "語意檢索失敗：%s",
                exc,
            )
            return []

    def _save(self):
        directory = os.path.dirname(INDEX_PATH)

        if directory:
            os.makedirs(
                directory,
                exist_ok=True,
            )

        with open(INDEX_PATH, "wb") as file:
            pickle.dump(
                {
                    "docs": self.docs,
                    "vectors": self.vectors,
                    "model_name": MODEL_NAME,
                },
                file,
            )

    def load(self):
        with open(INDEX_PATH, "rb") as file:
            data = pickle.load(file)

        self.docs = data["docs"]
        self.vectors = np.asarray(
            data["vectors"],
            dtype=np.float32,
        )

        saved_model_name = data.get("model_name")

        if (
            saved_model_name
            and saved_model_name != MODEL_NAME
        ):
            logger.warning(
                "索引模型與目前設定不同："
                "saved=%s, current=%s",
                saved_model_name,
                MODEL_NAME,
            )

        logger.info(
            "語意向量索引載入完成：%s 筆，維度=%s",
            len(self.docs),
            self.vectors.shape,
        )