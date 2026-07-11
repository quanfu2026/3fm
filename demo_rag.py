"""
RAG Pipeline 一鍵 Demo
用法：python demo_rag.py
或互動模式：python demo_rag.py --interactive
"""
import sys
import os
import logging
import argparse

# 設定 log 等級（減少 HuggingFace 噪音）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def banner():
    print("=" * 60)
    print("  3FM RAG Pipeline Demo")
    print("=" * 60)


def check_env():
    """檢查必要環境變數"""
    provider = os.getenv("LLM_PROVIDER", "qwen").lower()
    key_map = {
        "qwen":   "QWEN_API_KEY",
        "gpt":    "OPENAI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
    }
    key_name = key_map.get(provider, "QWEN_API_KEY")
    key_val  = os.getenv(key_name, "")

    print(f"\n[設定] LLM Provider : {provider}")
    print(f"[設定] API Key ({key_name}): {'已設定 ✓' if key_val else '未設定 ✗ (將使用 fallback)'}")
    print(f"[設定] Reranker     : {os.getenv('RERANKER_ENABLED', 'true')}")
    print()


def build_pipeline():
    """載入 RAG Pipeline（若 index 不存在則自動 build）"""
    print("[1/3] 載入 RAG Pipeline...")
    try:
        from rag.pipeline import RAGPipeline
        pipeline = RAGPipeline()
        print("[1/3] Pipeline 載入完成 ✓\n")
        return pipeline
    except Exception as e:
        print(f"[ERROR] Pipeline 載入失敗：{e}")
        print("\n請確認：")
        print("  1. 已啟動 venv：venv\\Scripts\\Activate.ps1")
        print("  2. 已安裝套件：pip install jieba rank-bm25 sentence-transformers FlagEmbedding")
        print("  3. knowledge_base/faq.md 存在且有內容")
        sys.exit(1)


def run_query(pipeline, query: str, verbose: bool = False):
    """執行單次查詢並印出結果"""
    print(f"[查詢] {query}")
    print("-" * 60)

    result = pipeline.query(query)

    print(f"\n[回答]\n{result['answer']}\n")

    if verbose:
        m = result["metrics"]
        print(f"[效能] 總耗時={m['total_ms']}ms | Reranker={m['reranker_ms']}ms")
        print(f"[命中] BM25={m['bm25_hits']} | BGE={m['bge_hits']} | 最終={m['final_docs']}")
        print("\n[來源文件]")
        for i, src in enumerate(result["sources"], 1):
            score = src.get("reranker_score", src.get("score", 0))
            print(f"  {i}. [{src.get('source','?')}] score={score:.4f}")
            print(f"     {src['content'][:100]}...")

        if result.get("reranker_diff"):
            print("\n[Reranker 排序變化]")
            for d in result["reranker_diff"]:
                arrow = "→" if d["old_rank"] != d["new_rank"] else "="
                print(f"  #{d['old_rank']} {arrow} #{d['new_rank']}  id={d['doc_id']}  score={d['score']}")

    print("=" * 60)


def demo_mode(pipeline):
    """執行預設示範問題"""
    demo_questions = [
        "你們有什麼產品？",
        "如何退換貨？",
        "運費怎麼計算？",
    ]

    print("[2/3] 執行示範查詢...\n")
    for q in demo_questions:
        run_query(pipeline, q, verbose=True)
        print()

    print("[3/3] Demo 完成 ✓")


def interactive_mode(pipeline):
    """互動問答模式"""
    print("[互動模式] 輸入問題後按 Enter，輸入 'q' 離開\n")
    while True:
        try:
            query = input("問題> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再見！")
            break

        if not query:
            continue
        if query.lower() in ("q", "quit", "exit"):
            print("再見！")
            break

        run_query(pipeline, query, verbose=True)
        print()


def main():
    parser = argparse.ArgumentParser(description="3FM RAG Pipeline Demo")
    parser.add_argument("--interactive", "-i", action="store_true", help="互動問答模式")
    parser.add_argument("--rebuild", "-r", action="store_true", help="強制重建 index")
    parser.add_argument("--query", "-q", type=str, help="執行單一查詢後退出")
    args = parser.parse_args()

    banner()
    check_env()

    # 載入 .env（若存在）
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("[設定] .env 已載入\n")
    except ImportError:
        pass

    pipeline = build_pipeline()

    if args.rebuild:
        print("[重建] 重新建立 index...")
        pipeline.rebuild_index()
        print("[重建] 完成 ✓\n")

    if args.query:
        run_query(pipeline, args.query, verbose=True)
    elif args.interactive:
        interactive_mode(pipeline)
    else:
        demo_mode(pipeline)


if __name__ == "__main__":
    main()