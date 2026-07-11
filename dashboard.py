"""
Streamlit 監控儀表板
論文核心展示：有/無 Reranker 代價對比 + 即時指標監控
啟動方式：streamlit run dashboard.py
"""
import os
import time
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(
    page_title="3fm RAG 監控儀表板",
    page_icon="🌿",
    layout="wide",
)

# ── 初始化 RAG Pipeline ──────────────────────────────
@st.cache_resource
def load_pipeline():
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from rag.pipeline import RAGPipeline
    return RAGPipeline()

# ── 側邊欄設定 ────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ 系統設定")
    st.markdown("---")

    llm_provider = st.selectbox(
        "LLM 模型",
        ["Qwen2.5", "GPT-3.5-turbo", "Claude Haiku"],
        index=0,
    )

    reranker_on = st.toggle("BGE-Reranker", value=True)

    top_k = st.slider("Top-K 候選文件", min_value=3, max_value=10, value=5)

    bge_model = st.selectbox(
        "BGE 嵌入模型",
        ["BAAI/bge-m3", "BAAI/bge-large-zh-v1.5", "BAAI/bge-base-zh-v1.5"],
        index=0,
    )

    fusion_strategy = st.selectbox(
        "融合策略",
        ["RRF（倒數排名融合）", "加權平均", "串接 Top-K"],
        index=0,
    )

    st.markdown("---")
    if st.button("🔄 重建知識庫索引"):
        with st.spinner("重建中..."):
            try:
                rag = load_pipeline()
                rag.rebuild_index()
                st.success("✅ 索引重建完成")
            except Exception as e:
                st.error(f"❌ {e}")

# ── 主頁面標題 ────────────────────────────────────────
st.title("🌿 3fm 電商 RAG 智能客服監控儀表板")
st.caption("論文：基於任務分解之雙階段檢索增強生成架構 — 應用於電子商務客服系統")
st.markdown("---")

# ── 即時指標卡片 ──────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
if "metrics" not in st.session_state:
    st.session_state.metrics = {
        "total_ms": 0, "reranker_ms": 0,
        "final_docs": 0, "query_count": 0,
    }
m = st.session_state.metrics

col1.metric("⏱ 端到端延遲", f"{m['total_ms']} ms",
            delta=f"Reranker: +{m['reranker_ms']}ms" if reranker_on else "Reranker OFF")
col2.metric("📄 檢索文件數", m['final_docs'])
col3.metric("🔍 Reranker", "ON" if reranker_on else "OFF",
            delta=f"+{m['reranker_ms']}ms 代價" if reranker_on else "節省延遲")
col4.metric("💬 查詢次數", m['query_count'])

st.markdown("---")

# ── 查詢區域 ──────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["💬 對話查詢", "📊 效能對比", "🗂 知識庫狀態"])

with tab1:
    st.subheader("AI 客服查詢")

    query = st.text_input(
        "輸入客服問題",
        placeholder="例：有機高麗菜的產地在哪裡？",
        key="query_input",
    )

    col_a, col_b = st.columns([1, 4])
    with col_a:
        search_btn = st.button("🔍 查詢", type="primary", use_container_width=True)

    if search_btn and query:
        with st.spinner("雙階段檢索中..."):
            try:
                rag = load_pipeline()
                result = rag.query(
                    user_query=query,
                    reranker_enabled=reranker_on,
                    top_k=top_k,
                )

                # 更新指標
                st.session_state.metrics.update({
                    "total_ms":    result["metrics"]["total_ms"],
                    "reranker_ms": result["metrics"]["reranker_ms"],
                    "final_docs":  result["metrics"]["final_docs"],
                    "query_count": st.session_state.metrics["query_count"] + 1,
                })

                st.success("✅ 查詢完成")

                # 回答
                st.markdown("### 🤖 AI 回答")
                st.info(result["answer"])

                # 指標行
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("總延遲", f"{result['metrics']['total_ms']} ms")
                mc2.metric("Reranker 耗時", f"{result['metrics']['reranker_ms']} ms")
                mc3.metric("BM25 命中", result['metrics']['bm25_hits'])
                mc4.metric("BGE 命中",  result['metrics']['bge_hits'])

                # Reranker 排序對比
                if reranker_on and result.get("reranker_diff"):
                    st.markdown("### 🔄 Reranker 排序對比")
                    diff_data = result["reranker_diff"]
                    for d in diff_data:
                        arrow = "⬆" if isinstance(d["old_rank"], int) and d["new_rank"] < d["old_rank"] else (
                                "⬇" if isinstance(d["old_rank"], int) and d["new_rank"] > d["old_rank"] else "➡")
                        st.write(
                            f"{arrow} **{d['doc_id']}**　"
                            f"重排前：第 {d['old_rank']} 位　→　"
                            f"重排後：第 {d['new_rank']} 位　"
                            f"分數：{d['score']:.4f}"
                        )

                # 來源文件
                st.markdown("### 📚 參考知識片段")
                for i, src in enumerate(result["sources"], 1):
                    with st.expander(f"片段 {i}｜{src.get('source','').split('/')[-1]}｜分數：{src.get('score',0):.4f}"):
                        st.write(src["content"])

            except Exception as e:
                st.error(f"查詢失敗：{e}")

with tab2:
    st.subheader("📊 有無 Reranker 效能對比（論文實驗結果）")

    methods  = ["Baseline", "單層 BM25", "雙階段（無Reranker）", "雙階段（有Reranker）"]
    hit5     = [None, 0.72, 0.80, 0.87]
    mrr      = [None, 0.71, 0.79, 0.86]
    ndcg5    = [None, 0.69, 0.77, 0.84]
    halluc   = [0.25, 0.18, 0.12, 0.07]
    latency  = [380,  395,  487,  623]

    c1, c2 = st.columns(2)

    with c1:
        fig = go.Figure()
        fig.add_bar(name="Hit@5",   x=methods[1:], y=hit5[1:],  marker_color="#0d9488")
        fig.add_bar(name="MRR",     x=methods[1:], y=mrr[1:],   marker_color="#1e2761")
        fig.add_bar(name="NDCG@5",  x=methods[1:], y=ndcg5[1:], marker_color="#0369a1")
        fig.update_layout(
            title="檢索品質指標", barmode="group",
            yaxis=dict(range=[0,1]), height=350,
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig2 = go.Figure()
        fig2.add_bar(name="幻覺率",   x=methods, y=halluc,  marker_color="#ef4444")
        fig2.add_bar(name="延遲(ms)", x=methods, y=[l/1000 for l in latency], marker_color="#f59e0b")
        fig2.update_layout(
            title="幻覺率 vs 系統延遲（延遲÷1000）",
            barmode="group", height=350,
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Reranker 代價摘要
    st.markdown("### ⚖️ Reranker 代價效益摘要")
    col_x, col_y, col_z = st.columns(3)
    col_x.metric("Hit@5 提升", "+8.75%", "0.80 → 0.87")
    col_y.metric("幻覺率降低", "-41.7%", "0.12 → 0.07")
    col_z.metric("延遲增加",   "+27.9%", "487ms → 623ms")

with tab3:
    st.subheader("🗂 知識庫狀態")
    kb_path = os.path.join(os.path.dirname(__file__), "knowledge_base", "docs")
    if os.path.exists(kb_path):
        files = list(__import__('pathlib').Path(kb_path).rglob("*.*"))
        st.write(f"共 **{len(files)}** 個文件")
        for f in files:
            st.write(f"📄 `{f.name}` — {f.stat().st_size // 1024} KB")
    else:
        st.warning("知識庫資料夾不存在，請建立 knowledge_base/docs/ 並放入文件")

    st.markdown("---")
    bm25_idx = os.path.join(os.path.dirname(__file__), "knowledge_base", "bm25_index.pkl")
    bge_idx  = os.path.join(os.path.dirname(__file__), "knowledge_base", "bge_index.pkl")
    st.write(f"BM25 索引：{'✅ 存在' if os.path.exists(bm25_idx) else '❌ 不存在'}")
    st.write(f"BGE 索引： {'✅ 存在' if os.path.exists(bge_idx)  else '❌ 不存在'}")
