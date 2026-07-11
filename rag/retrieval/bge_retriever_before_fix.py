import os, pickle, logging
import numpy as np

logger = logging.getLogger(__name__)

INDEX_PATH = os.path.join(
    os.getenv('KNOWLEDGE_BASE_PATH', './knowledge_base'),
    'bge_index.pkl'
)
MODEL_NAME = os.getenv('BGE_MODEL', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')


class BGERetriever:

    def __init__(self):
        self.model   = None   # 懶載入，不在 __init__ 載入
        self.docs    = []
        self.vectors = None

    def _ensure_model(self):
        if self.model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(MODEL_NAME)
            logger.info(f'BGE 模型載入成功：{MODEL_NAME}')
        except Exception as e:
            logger.warning(f'BGE 模型載入失敗：{e}')
            self.model = None

    def build(self, docs: list):
        self._ensure_model()
        if self.model is None:
            logger.error('BGE 模型未載入，跳過向量索引建立')
            self.docs = docs
            self.vectors = np.zeros((len(docs), 1))
            return
        self.docs = docs
        contents  = [d['content'] for d in docs]
        logger.info(f'編碼 {len(contents)} 筆文件..')
        self.vectors = self.model.encode(
            contents, batch_size=16,
            show_progress_bar=True,
            normalize_embeddings=True,
        )
        self._save()
        logger.info('BGE 向量索引建立完成')

    def search(self, query: str, top_k: int = 10) -> list:
        if self.vectors is None or len(self.docs) == 0:
            return []
        if self.model is None:
            return []
        self._ensure_model()
        q_vec  = self.model.encode([query], normalize_embeddings=True)[0]
        scores = self.vectors @ q_vec
        ranked = np.argsort(scores)[::-1][:top_k]
        results = []
        for rank, idx in enumerate(ranked, 1):
            doc = dict(self.docs[idx])
            doc['score']    = float(scores[idx])
            doc['rank_bge'] = rank
            results.append(doc)
        return results

    def _save(self):
        os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
        with open(INDEX_PATH, 'wb') as f:
            pickle.dump({'docs': self.docs, 'vectors': self.vectors}, f)

    def load(self):
        with open(INDEX_PATH, 'rb') as f:
            data = pickle.load(f)
        self.docs    = data['docs']
        self.vectors = data['vectors']
        logger.info(f'BGE 索引載入：{len(self.docs)} 筆')
