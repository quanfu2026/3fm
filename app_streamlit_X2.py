import pandas as pd
import streamlit as st
from rag.pipeline import RAGPipeline

st.set_page_config(page_title="Offline RAG Demo", layout="wide")


@st.cache_resource
def load_rag():
    return RAGPipeline()


rag = load_rag()

st.title("🔎 完全離線版 RAG Demo")
st.caption("BM25 + BGE + RRF + Ollama，本機執行，不需要 OpenAI / Gemini API Token")

# =====================================================
# 模式一：單題 RAG Demo
# =====================================================
st.header("① 單題 RAG Demo")
st.info("這裡用來展示單一問題的回答、Top-K 檢索結果與即時延遲；Hit@5 / MRR / NDCG 請看下方 Benchmark。")

query = st.text_input("請輸入問題", value="iPhone 15 有保固嗎？")
reranker_enabled = st.checkbox("啟用 Reranker", value=False)

if st.button("查詢") and query:
    result = rag.query(query, reranker_enabled=reranker_enabled)

    st.subheader("📌 生成回答")
    st.write(result["answer"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("總延遲 ms", result["metrics"].get("total_ms"))
    c2.metric("BM25 Hits", result["metrics"].get("bm25_hits"))
    c3.metric("BGE Hits", result["metrics"].get("bge_hits"))
    c4.metric("Final Docs", result["metrics"].get("final_docs"))

    st.subheader("📚 Top-K 檢索結果")
    for i, doc in enumerate(result["sources"], 1):
        st.markdown(f"### Top {i}")
        st.write("**文件 ID：**", doc.get("id"))
        st.write("**Score：**", doc.get("score"))
        st.write(doc.get("content", ""))
        with st.expander("查看完整 doc 物件"):
            st.json(doc)

# =====================================================
# 模式二：整批 Benchmark Evaluation
# =====================================================
st.divider()
st.header("② Benchmark Evaluation：整批測試集自動評測")
st.info("這裡會讀取 data/eval_questions.json，逐題執行檢索，再自動計算 Hit@5、MRR、NDCG@5 與平均延遲。")

with st.expander("📄 eval_questions.json 應該長這樣"):
    st.code(
        '''[
  {
    "question": "iPhone 15 有保固嗎？",
    "answer_doc_id": "1_21"
  },
  {
    "question": "可以退貨嗎？",
    "answer_doc_ids": ["2_3", "2_4"]
  }
]''',
        language="json",
    )

col_a, col_b, col_c = st.columns([2, 1, 1])
with col_a:
    eval_path = st.text_input("評測檔案路徑", value="data/eval_questions.json")
with col_b:
    top_k = st.number_input("Top-K", min_value=1, max_value=20, value=5, step=1)
with col_c:
    eval_reranker = st.checkbox("評測時啟用 Reranker", value=False)

if st.button("執行 Benchmark 評測"):
    try:
        with st.spinner("正在跑整批測試集，請稍候..."):
            eval_result = rag.evaluate(
                eval_path=eval_path,
                top_k=int(top_k),
                reranker_enabled=eval_reranker,
            )

        st.success("Benchmark 評測完成")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("評測題數", eval_result["total_questions"])
        m2.metric(f"Hit@{eval_result['top_k']}", eval_result[f"Hit@{eval_result['top_k']}"])
        m3.metric("MRR", eval_result["MRR"])
        m4.metric(f"NDCG@{eval_result['top_k']}", eval_result[f"NDCG@{eval_result['top_k']}"])
        m5.metric("平均延遲 ms", eval_result["avg_latency_ms"])

        st.write(f"命中題數：{eval_result['hit_count']} / 未命中題數：{eval_result['miss_count']}")

        details = pd.DataFrame(eval_result["details"])
        st.subheader("逐題評測明細")
        st.dataframe(details, use_container_width=True)

    except Exception as e:
        st.error(f"評測失敗：{e}")
        st.warning("請先確認 data/eval_questions.json 是否存在，以及 answer_doc_id 是否填成 Top-K 畫面實際出現的文件 ID。")
