import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# =========================================================
# 論文正式版 Streamlit v3
# 修正：
# 1. 不再呼叫 rag.pipeline.RAGPipeline.query()
# 2. 直接沿用 test_rag_from_word.py 的正式評測邏輯
# 3. 修正 reranker 參數：--reranker
# 4. st.dataframe 統一使用 use_container_width=True（width="stretch" 需
#    較新版 Streamlit 才支援，本專案鎖定 streamlit==1.37.0 尚不支援，
#    使用該字串會導致 TypeError: 'str' object cannot be interpreted as an integer）
# 5. 單題延遲分解新增時間占比、表格與進度條
# =========================================================

st.set_page_config(
    page_title="論文正式版 RAG 評測系統",
    page_icon="📊",
    layout="wide",
)

ROOT = Path(__file__).resolve().parent
EVAL_DIR = ROOT / "evaluation_results"
EVAL_DIR.mkdir(exist_ok=True)


def latest_file(pattern: str):
    files = sorted(EVAL_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


@st.cache_resource(show_spinner=False)
def load_formal_index(knowledge_path: str, bge_model: str):
    """直接使用 test_rag_from_word.py 的知識庫解析與索引建立。"""
    import test_rag_from_word as formal

    cfg = dict(formal.CONFIG)
    cfg["knowledge_txt"] = knowledge_path
    cfg["bge_model"] = bge_model
    cfg["skip_llm"] = True
    cfg["use_reranker"] = False

    chunks = formal.load_knowledge_chunks(knowledge_path)
    bm25, bge, rrf = formal.build_index(chunks, cfg)
    return formal, cfg, chunks, bm25, bge, rrf


def run_formal_single_query(query: str, knowledge_path: str, bge_model: str, skip_llm: bool, use_reranker: bool):
    formal, cfg, chunks, bm25, bge, rrf = load_formal_index(knowledge_path, bge_model)
    cfg = dict(cfg)
    cfg["skip_llm"] = skip_llm
    cfg["use_reranker"] = use_reranker
    return formal.run_single_query(query, chunks, bm25, bge, rrf, cfg)


def run_benchmark(docx_path: str, knowledge_path: str, max_q: int | None, skip_llm: bool, use_reranker: bool, bge_model: str):
    """呼叫既有 test_rag_from_word.py，讓正式評測邏輯與論文一致。"""
    cmd = [
        sys.executable,
        "test_rag_from_word.py",
        "--docx", docx_path,
        "--knowledge", knowledge_path,
    ]

    if max_q is not None and max_q > 0:
        cmd += ["--max-q", str(max_q)]
    if skip_llm:
        cmd += ["--skip-llm"]
    if use_reranker:
        cmd += ["--reranker"]

    # 透過環境變數指定 BGE 模型
    env = dict(**__import__("os").environ)
    env["BGE_MODEL"] = bge_model
    env["PYTHONIOENCODING"] = "utf-8"

    before_json = set(EVAL_DIR.glob("eval_detail_*.json"))
    before_csv = set(EVAL_DIR.glob("eval_summary_*.csv"))

    process = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    after_json = set(EVAL_DIR.glob("eval_detail_*.json"))
    after_csv = set(EVAL_DIR.glob("eval_summary_*.csv"))

    new_json = sorted(after_json - before_json, key=lambda p: p.stat().st_mtime, reverse=True)
    new_csv = sorted(after_csv - before_csv, key=lambda p: p.stat().st_mtime, reverse=True)

    json_path = new_json[0] if new_json else latest_file("eval_detail_*.json")
    csv_path = new_csv[0] if new_csv else latest_file("eval_summary_*.csv")

    return process, json_path, csv_path


def load_report(json_path: Path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_latency_breakdown(latency: dict):
    """顯示單題延遲分解：時間、占比、進度條，方便口試說明效能瓶頸。"""
    if not latency:
        st.info("目前沒有延遲資料。")
        return

    total = float(latency.get("total_ms", 0) or 0)
    safe_total = max(total, 0.0001)

    items = [
        ("BM25 檢索", float(latency.get("bm25_ms", 0) or 0), "傳統關鍵字檢索，速度通常最快"),
        ("BGE 向量檢索", float(latency.get("bge_ms", 0) or 0), "Transformer 向量編碼與相似度計算，通常是主要瓶頸"),
        ("RRF 融合", float(latency.get("rrf_ms", 0) or 0), "只做排名融合，成本通常很低"),
        ("Reranker", float(latency.get("rerank_ms", 0) or 0), "若未啟用則為 0 ms"),
        ("LLM 生成", float(latency.get("llm_ms", 0) or 0), "skip LLM 模式下為 0 ms"),
    ]

    rows = []
    for name, ms, note in items:
        rows.append({
            "模組": name,
            "時間(ms)": round(ms, 2),
            "占比(%)": round(ms / safe_total * 100, 1),
            "說明": note,
        })

    df = pd.DataFrame(rows)

    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("總延遲", f"{total:.2f} ms")
    with c2:
        if rows:
            bottleneck = max(rows, key=lambda r: r["時間(ms)"])
            st.metric("主要瓶頸", f"{bottleneck['模組']}（{bottleneck['占比(%)']}%）")

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("**各模組耗時占比**")
    for row in rows:
        pct = max(0.0, min(float(row["占比(%)"]), 100.0))
        st.write(f"{row['模組']}：{row['時間(ms)']:.2f} ms（{row['占比(%)']:.1f}%）")
        st.progress(int(round(pct)))

    with st.expander("查看原始 latency JSON"):
        st.json(latency)


st.title("📊 論文正式版 RAG 評測系統")
st.caption("單題展示 + 批量 Benchmark；評測數據由 test_rag_from_word.py 自動計算，不再使用寫死數值。")

with st.sidebar:
    st.header("⚙️ 評測設定")

    default_docx = "knowledge_base/evaluation/電商客服問答集.docx"
    default_knowledge = "knowledge_base/docs/product_specs.txt"

    docx_path = st.text_input("評測 DOCX", value=default_docx)
    knowledge_path = st.text_input("知識庫 TXT", value=default_knowledge)
    bge_model = st.text_input("BGE 模型", value="BAAI/bge-m3")

    max_q_option = st.selectbox(
        "評測題數",
        options=["快速測試 5 題", "快速測試 10 題", "快速測試 20 題", "全部題目"],
        index=1,
    )
    max_q = {
        "快速測試 5 題": 5,
        "快速測試 10 題": 10,
        "快速測試 20 題": 20,
        "全部題目": None,
    }[max_q_option]

    skip_llm = st.checkbox("只評估檢索，不呼叫 LLM（速度快，適合口試 Demo）", value=True)
    use_reranker = st.checkbox("啟用 Reranker（較慢，記憶體需求較高）", value=False)

    st.divider()
    st.markdown("**建議口試設定**")
    st.write("先用 10 題 + skip LLM，確認能快速跑出 Hit@5 / MRR / NDCG。")


tab_demo, tab_benchmark, tab_reports, tab_explain = st.tabs([
    "🔎 單題 RAG Demo",
    "📊 論文 Benchmark",
    "📁 歷史報告",
    "🧠 指標原理",
])

with tab_demo:
    st.subheader("🔎 單題 RAG Demo")
    st.write("這一頁直接沿用正式評測程式的 BM25 + BGE + RRF 流程，不再呼叫 rag.pipeline.query()。")

    query = st.text_area(
        "請輸入電商客服問題",
        value="這種金屬外殼的隨身碟用久了會不會很燙？會不會因為過熱突然斷線讀不到？",
        height=90,
    )
    demo_skip_llm = st.checkbox("單題 Demo 只看檢索結果，不呼叫 LLM", value=True, key="demo_skip_llm")

    if st.button("執行單題查詢", type="primary") and query.strip():
        if not Path(knowledge_path).exists():
            st.error(f"找不到知識庫 TXT：{knowledge_path}")
        else:
            with st.spinner("正在執行正式 RAG 查詢，首次載入 BGE 會比較久..."):
                result = run_formal_single_query(
                    query=query,
                    knowledge_path=knowledge_path,
                    bge_model=bge_model,
                    skip_llm=demo_skip_llm,
                    use_reranker=use_reranker,
                )

            st.success("查詢完成")

            st.subheader("📌 RAG 回答")
            answer = result.get("answer", "")
            if answer == "[SKIP]":
                st.info("目前為 skip LLM 模式，因此只展示檢索結果，不產生回答。")
            else:
                st.write(answer)

            st.subheader("📚 Top-K 檢索結果")
            for i, doc in enumerate(result.get("top_docs", []), 1):
                score = doc.get("rrf_score", doc.get("score", "N/A"))
                with st.expander(f"Top {i}｜ID: {doc.get('id')}｜Score: {score}", expanded=(i == 1)):
                    st.write(doc.get("content", ""))
                    st.json(doc)

            st.subheader("⏱️ 單題延遲分析（含占比）")
            render_latency_breakdown(result.get("latency", {}))

with tab_benchmark:
    st.subheader("📊 論文 Benchmark 批量評測")
    st.write("這一頁會呼叫原本的 `test_rag_from_word.py`，從 DOCX 解析測試題與 Ground Truth，逐題跑 RAG 並自動計算平均指標。")

    col1, col2, col3 = st.columns(3)
    col1.metric("評測檔", Path(docx_path).name)
    col2.metric("題數設定", "全部" if max_q is None else f"{max_q} 題")
    col3.metric("LLM 模式", "跳過 LLM" if skip_llm else "產生回答")

    doc_ok = Path(docx_path).exists()
    knowledge_ok = Path(knowledge_path).exists()
    if not doc_ok:
        st.error(f"找不到評測 DOCX：{docx_path}")
    if not knowledge_ok:
        st.error(f"找不到知識庫 TXT：{knowledge_path}")

    if st.button("🚀 開始批量評測", type="primary", disabled=not (doc_ok and knowledge_ok)):
        with st.spinner("正在執行批量評測，首次載入 BGE 會比較久，請稍候..."):
            process, json_path, csv_path = run_benchmark(
                docx_path=docx_path,
                knowledge_path=knowledge_path,
                max_q=max_q,
                skip_llm=skip_llm,
                use_reranker=use_reranker,
                bge_model=bge_model,
            )

        if process.returncode != 0:
            st.error("批量評測失敗，請查看錯誤輸出。")
            st.code(process.stderr or process.stdout)
        elif not json_path or not json_path.exists():
            st.error("評測完成但找不到 JSON 報告。")
            st.code(process.stdout)
        else:
            data = load_report(json_path)
            summary = data.get("summary", {})
            metrics = summary.get("metrics_avg", {})

            st.success("批量評測完成")

            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("題數", summary.get("total_questions", 0))
            c2.metric("Hit@5", metrics.get("hit_at_5", 0))
            c3.metric("MRR", metrics.get("mrr", 0))
            c4.metric("NDCG@5", metrics.get("ndcg_at_5", 0))
            c5.metric("BGE Cosine", metrics.get("bge_cosine", 0))
            c6.metric("平均延遲 ms", metrics.get("latency_ms_avg", 0))

            st.subheader("📄 報告檔案")
            st.write(f"JSON：`{json_path}`")
            if csv_path:
                st.write(f"CSV：`{csv_path}`")

            results = data.get("results", [])
            if results:
                st.subheader("🔍 前 10 筆明細")
                rows = []
                for r in results[:10]:
                    m = r.get("metrics", {})
                    rows.append({
                        "sample_id": r.get("sample_id"),
                        "question": r.get("question", "")[:60],
                        "Hit@5": m.get("hit_at_5"),
                        "MRR": m.get("mrr"),
                        "NDCG@5": m.get("ndcg_at_5"),
                        "BGE Cosine": m.get("bge_cosine"),
                        "Hallucination": m.get("hallucination"),
                        "Latency ms": m.get("latency_ms"),
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

            with st.expander("查看完整終端輸出"):
                st.code(process.stdout)
                if process.stderr:
                    st.code(process.stderr)

with tab_reports:
    st.subheader("📁 歷史 JSON 報告")
    json_files = sorted(EVAL_DIR.glob("eval_detail_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not json_files:
        st.info("目前還沒有歷史報告，請先到 Benchmark 頁面執行一次評測。")
    else:
        selected = st.selectbox("選擇報告", json_files, format_func=lambda p: p.name)
        data = load_report(selected)
        summary = data.get("summary", {})
        metrics = summary.get("metrics_avg", {})

        st.write(f"報告路徑：`{selected}`")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("題數", summary.get("total_questions", 0))
        c2.metric("Hit@5", metrics.get("hit_at_5", 0))
        c3.metric("MRR", metrics.get("mrr", 0))
        c4.metric("NDCG@5", metrics.get("ndcg_at_5", 0))
        c5.metric("BGE Cosine", metrics.get("bge_cosine", 0))
        c6.metric("平均延遲 ms", metrics.get("latency_ms_avg", 0))

        results = data.get("results", [])
        if results:
            rows = []
            for r in results:
                m = r.get("metrics", {})
                rows.append({
                    "sample_id": r.get("sample_id"),
                    "question": r.get("question", "")[:80],
                    "Hit@5": m.get("hit_at_5"),
                    "MRR": m.get("mrr"),
                    "NDCG@5": m.get("ndcg_at_5"),
                    "BGE Cosine": m.get("bge_cosine"),
                    "Hallucination": m.get("hallucination"),
                    "Latency ms": m.get("latency_ms"),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

with tab_explain:
    st.subheader("🧠 口試可用說明")
    st.markdown(
        """
### 這些數據怎麼來？

本系統不是手動填入數值，而是直接呼叫 `test_rag_from_word.py` 執行批量評測。流程如下：

```text
DOCX 評測集
    ↓
解析出每一題的 客戶提問 與 標準客服回答 Ground Truth
    ↓
從 product_specs.txt 建立知識片段 chunks
    ↓
BM25 + BGE 檢索
    ↓
RRF 融合排序
    ↓
比對 Top-5 是否包含與 Ground Truth 最相關的 chunk
    ↓
自動計算 Hit@5、MRR、NDCG@5、BGE Cosine、幻覺率與延遲
```

### Hit@5
檢查正確相關文件是否出現在前五名檢索結果中。有出現記為 1，沒有出現記為 0，最後對所有測試題取平均。

### MRR
如果正確文件排第 1 名，分數是 1；排第 2 名是 1/2；排第 5 名是 1/5。最後對所有題目取平均。

### NDCG@5
衡量排序品質。正確文件越前面，分數越高。

### BGE Cosine
用 BGE embedding 計算 RAG 回答與 Ground Truth 標準答案的語意相似度。

### 幻覺率
用詞彙覆蓋率近似估計：若回答中有許多詞沒有被檢索 context 支持，幻覺率會提高。
        """
    )
