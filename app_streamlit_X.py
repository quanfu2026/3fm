import streamlit as st
from rag.pipeline import RAGPipeline

st.set_page_config(page_title="Offline RAG Demo", layout="wide")

@st.cache_resource
def load_rag():
    return RAGPipeline()

rag = load_rag()

st.title("🔎 完全離線版 RAG Demo")
st.caption("BM25 + BGE + RRF + Ollama，本機執行，不需要 OpenAI / Gemini API Token")

query = st.text_input("請輸入問題")

reranker_enabled = st.checkbox("啟用 Reranker", value=False)

if st.button("查詢") and query:
    result = rag.query(query, reranker_enabled=reranker_enabled)

    st.subheader("📌 生成回答")
    st.write(result["answer"])

    st.subheader("📚 Top-K 檢索結果")
    for i, doc in enumerate(result["sources"], 1):
        st.markdown(f"### Top {i}")
        st.write(doc.get("content", ""))
        st.json({
            "id": doc.get("id"),
            "score": doc.get("score"),
        })

    st.subheader("📊 系統指標")
    st.json(result["metrics"])
    st.divider()
    st.subheader("📊 自動評測結果")

if st.button("執行自動評測"):
    with st.spinner("正在跑測試集，請稍候..."):
        eval_result = rag.evaluate("data/eval_questions.json", top_k=5)

    st.write(f"評測題數：{eval_result['total_questions']} 題")
    st.metric("Hit@5", eval_result["Hit@5"])
    st.metric("MRR", eval_result["MRR"])
    st.metric("NDCG@5", eval_result["NDCG@5"])
    st.metric("平均延遲 ms", eval_result["avg_latency_ms"])