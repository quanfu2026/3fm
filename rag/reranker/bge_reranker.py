import os, logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class BGEReranker:

    def __init__(self):
        self.model   = None
        self.enabled = False   # 強制關閉，節省記憶體
        logger.info('BGEReranker：已停用（記憶體保護模式）')

    def rerank(self, query: str, docs: List[dict], top_k: int = 5) -> List[dict]:
        return docs[:top_k]
