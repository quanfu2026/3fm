"""
RAG 系統快速健康檢查
用法：python check_rag.py
"""
import sys

CHECKS = []

def check(name):
    def decorator(fn):
        CHECKS.append((name, fn))
        return fn
    return decorator


@check("Python 版本")
def check_python():
    v = sys.version_info
    assert v >= (3, 9), f"需要 Python 3.9+，目前 {v.major}.{v.minor}"
    return f"{v.major}.{v.minor}.{v.micro}"


@check("jieba")
def check_jieba():
    import jieba
    result = list(jieba.cut("測試分詞"))
    assert len(result) > 0
    return "OK"


@check("rank-bm25")
def check_bm25():
    from rank_bm25 import BM25Okapi
    bm25 = BM25Okapi([["hello", "world"], ["foo", "bar"]])
    scores = bm25.get_scores(["hello"])
    assert len(scores) == 2
    return "OK"


@check("sentence-transformers")
def check_st():
    from sentence_transformers import SentenceTransformer
    return "已安裝"


@check("FlagEmbedding (reranker)")
def check_flag():
    try:
        from FlagEmbedding import FlagReranker
        return "已安裝"
    except ImportError:
        return "未安裝（reranker 將降級，不影響基本 RAG）"


@check("openai (Qwen/GPT)")
def check_openai():
    try:
        import openai
        return f"v{openai.__version__}"
    except ImportError:
        return "未安裝（若 LLM_PROVIDER=qwen 或 gpt 需要安裝）"


@check(".env 設定")
def check_env():
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    provider = os.getenv("LLM_PROVIDER", "qwen")
    key_map = {"qwen": "QWEN_API_KEY", "gpt": "OPENAI_API_KEY", "claude": "ANTHROPIC_API_KEY"}
    key = os.getenv(key_map.get(provider, "QWEN_API_KEY"), "")
    return f"provider={provider}, API Key={'已設定' if key else '未設定'}"


@check("knowledge_base/faq.md")
def check_kb():
    import os
    path = os.path.join(
        os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge_base"),
        "faq.md"
    )
    assert os.path.exists(path), f"找不到 {path}"
    size = os.path.getsize(path)
    assert size > 0, "faq.md 是空的"
    return f"{size} bytes"


@check("RAG Pipeline import")
def check_pipeline():
    from rag.pipeline import RAGPipeline
    return "import OK"


def main():
    print("=" * 55)
    print("  3FM RAG 系統健康檢查")
    print("=" * 55)

    passed = 0
    warnings = 0
    failed = 0

    for name, fn in CHECKS:
        try:
            result = fn()
            print(f"  ✓ {name:<30} {result}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {name:<30} {e}")
            failed += 1
        except Exception as e:
            print(f"  ⚠ {name:<30} {e}")
            warnings += 1

    print("=" * 55)
    print(f"  結果：{passed} 通過 / {warnings} 警告 / {failed} 失敗")
    print("=" * 55)

    if failed > 0:
        print("\n[建議] 請修復失敗項目後再執行 demo_rag.py")
        sys.exit(1)
    elif warnings > 0:
        print("\n[提示] 有警告項目，部分功能可能降級，但基本 RAG 可運行")
    else:
        print("\n[OK] 所有檢查通過，可執行：python demo_rag.py")


if __name__ == "__main__":
    main()