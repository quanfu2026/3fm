"""
環境相容性修補工具。

背景：
    sentence-transformers 與 FlagEmbedding 在 import 階段都會連帶匯入
    `datasets` 套件（用來產生 model card / 讀取訓練資料集），但本專案
    完全沒有使用到 datasets 的任何實際功能，純粹是上游套件的被動依賴。

    在部分電腦上（例如受 Windows 應用程式控制原則 / WDAC 管制的機器），
    `datasets` 依賴的原生元件 `_xxhash` 會被系統擋下，導致
    `import sentence_transformers` / `import FlagEmbedding` 直接失敗，
    連帶讓 BGE 語意檢索與 Reranker 都無法使用。

    這個模組會先嘗試正常 import datasets；如果失敗，就用一個「行為盡量
    貼近正常模組」的空殼頂替：
      - 只有本專案上游套件實際會用到的少數幾個名稱（Dataset、DatasetDict、
        Value 等）才回傳假物件，其餘一律拋出 AttributeError（正常模組
        本來就該有的行為），避免誤觸發其他套件內部的「功能探測」邏輯。
      - 附上正常的 __spec__，讓 importlib.util.find_spec() 等標準檢查
        不會因為 __spec__ 是 None 而直接報錯。
"""

import sys
import types
import logging
import importlib.machinery

logger = logging.getLogger(__name__)

_PATCHED = False

# 目前已知本專案的上游套件（sentence-transformers / FlagEmbedding）
# 在 import 階段會用到的名稱，僅對這些名稱回傳假物件。
_KNOWN_STUB_NAMES = {
    "Dataset",
    "DatasetDict",
    "IterableDataset",
    "Value",
    "Features",
    "Sequence",
    "load_dataset",
}

_KNOWN_STUB_VALUES = {
    "__version__": "0.0.0-stub",
}


class _DummyDatasetsClass:
    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "此環境的 `datasets` 套件已被替換為空殼模組（因系統原則封鎖其"
            "原生元件 xxhash），無法執行真正的資料集操作。若你確實需要"
            "使用 datasets 的功能，請先排除 xxhash 的載入問題。"
        )


class _DatasetsStubModule(types.ModuleType):
    def __getattr__(self, name):
        if name in _KNOWN_STUB_VALUES:
            return _KNOWN_STUB_VALUES[name]

        if name in _KNOWN_STUB_NAMES:
            return _DummyDatasetsClass

        # 其餘一律視為「沒有這個屬性」，讓 hasattr()/getattr(..., default)
        # 這類檢查行為跟正常模組一致，不要誤觸發其他套件的功能探測。
        raise AttributeError(
            f"module 'datasets' (stub) has no attribute {name!r}"
        )


def ensure_datasets_importable():
    """確保 `import datasets` 這個動作不會讓呼叫方連帶掛掉。
    能正常載入就用真的 datasets；不能的話就用空殼頂替。
    """
    global _PATCHED

    if _PATCHED or "datasets" in sys.modules:
        return

    try:
        import datasets  # noqa: F401

        logger.info("datasets 套件正常載入")

    except Exception as exc:
        logger.warning(
            "datasets 套件載入失敗（%s），本專案未使用其功能，"
            "改用空殼模組頂替以繞過此依賴。",
            exc,
        )
        stub = _DatasetsStubModule("datasets")
        stub.__spec__ = importlib.machinery.ModuleSpec("datasets", loader=None)
        stub.__path__ = []  # 讓它看起來像個 package，避免部分檢查誤判
        sys.modules["datasets"] = stub

    finally:
        _PATCHED = True
