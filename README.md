# 3fm 電商智能客服系統

> 論文實作：**基於任務分解之雙階段檢索增強生成架構：應用於電子商務客服系統**
> 崑山科技大學 智慧機器人工程系 碩士論文 — 陳銓富

---

## 系統架構

```
用戶查詢
    ↓
【第一階段】BM25（求準）
    ↓
【第二階段】BGE-M3（求廣）
    ↓
RRF 排序融合
    ↓
BGE-Reranker-v2-m3（可選）
    ↓
Qwen2.5 生成回答
    ↓
Streamlit 儀表板監控
```

---

## 快速啟動

### 1. 環境設定

```bash
cd 3fm
cp .env.example .env
# 編輯 .env 填入你的 API Key
pip install -r requirements.txt
```

### 2. 建立知識庫索引

```bash
python -c "
from rag.pipeline import RAGPipeline
rag = RAGPipeline()
rag.rebuild_index()
print('索引建立完成')
"
```

### 3. 啟動 Flask 電商網站

```bash
python app.py
# 開啟瀏覽器：http://localhost:5000
```

### 4. 啟動 Streamlit 監控儀表板

```bash
streamlit run dashboard.py
# 開啟瀏覽器：http://localhost:8501
```

---

## 目錄結構

```
3fm/
├── app.py                  # Flask 主程式入口
├── dashboard.py            # Streamlit 監控儀表板
├── requirements.txt        # 套件需求
├── .env.example            # 環境變數範本
│
├── rag/                    # RAG 核心模組
│   ├── pipeline.py         # 完整 RAG 處理流程
│   ├── retrieval/
│   │   ├── bm25_retriever.py   # BM25 第一階段（求準）
│   │   ├── bge_retriever.py    # BGE-M3 第二階段（求廣）
│   │   └── rrf_fusion.py       # RRF 排序融合
│   ├── reranker/
│   │   └── bge_reranker.py     # BGE-Reranker 重排序
│   ├── generator/
│   │   └── llm_interface.py    # 統一 LLM 介面（Qwen/GPT/Claude）
│   └── utils/
│       └── knowledge_builder.py # 多模態知識庫建置
│
├── routes/                 # Flask Blueprint 路由
│   ├── main.py             # 首頁
│   ├── auth.py             # 登入/登出
│   ├── shop.py             # 商品館
│   ├── cart.py             # 購物車
│   ├── chat.py             # AI 客服 API
│   └── admin.py            # 管理後台
│
├── templates/              # Jinja2 HTML 模板
│   ├── base.html           # 基礎模板（含 AI 客服浮動視窗）
│   ├── main/
│   ├── auth/
│   ├── shop/
│   ├── cart/
│   └── admin/
│
├── static/
│   ├── css/main.css        # 主樣式
│   ├── css/chat.css        # 客服視窗樣式
│   └── js/chat.js          # 客服視窗邏輯
│
├── knowledge_base/
│   └── docs/               # 放入知識文件（MD/PDF/DOCX/XLSX/PPTX/圖片）
│
└── data/
    ├── users_db.json       # 使用者資料
    └── products_db.json    # 商品資料
```

---

## 環境變數說明

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `LLM_PROVIDER` | LLM 供應商 | `qwen` |
| `QWEN_API_KEY` | Qwen API Key | — |
| `RERANKER_ENABLED` | 是否啟用 Reranker | `true` |
| `BM25_TOP_K` | BM25 候選數量 | `10` |
| `BGE_MODEL` | BGE 嵌入模型 | `BAAI/bge-m3` |
| `RERANKER_MODEL` | Reranker 模型 | `BAAI/bge-reranker-v2-m3` |
| `FINAL_TOP_K` | 最終送入 LLM 的文件數 | `5` |

---

## 新增知識文件

1. 將文件放入 `knowledge_base/docs/`
2. 支援格式：`.md` `.txt` `.pdf` `.docx` `.xlsx` `.pptx` `.jpg` `.png`
3. 進入管理後台（/admin）點選「重建索引」，或執行：

```bash
python -c "from rag.pipeline import RAGPipeline; RAGPipeline().rebuild_index()"
```

---

## 測試帳號

| 帳號 | 密碼 | 角色 |
|------|------|------|
| admin | admin123 | 管理員 |
| user1 | user123 | 一般用戶 |

---

## 論文核心對比實驗

透過 Streamlit 儀表板可視覺化對比：

| 方法 | Hit@5 | MRR | 幻覺率 | 延遲 |
|------|-------|-----|--------|------|
| Baseline | — | — | 0.25 | 380ms |
| 單層 BM25 | 0.72 | 0.71 | 0.18 | 395ms |
| 雙階段（無Reranker）| 0.80 | 0.79 | 0.12 | 487ms |
| **雙階段（有Reranker）** | **0.87** | **0.86** | **0.07** | **623ms** |
---------
# Dual-Stage RAG E-Commerce Customer Service System

> A Dual-Stage Retrieval-Augmented Generation (RAG) E-Commerce Customer Service System Based on BM25, BGE-M3, RRF, BGE-Reranker and Qwen2.5

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![Streamlit](https://img.shields.io/badge/Streamlit-1.37-red)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

# 📖 Project Overview

This project implements a **Dual-Stage Retrieval-Augmented Generation (RAG)** intelligent customer service system for e-commerce applications.

The system integrates:

- BM25 Sparse Retrieval
- BGE-M3 Dense Retrieval
- Reciprocal Rank Fusion (RRF)
- BGE-Reranker-v2-m3
- Ollama Local LLM (Qwen2.5)
- Flask Web System
- Streamlit Benchmark Dashboard

The goal is to improve retrieval accuracy, response quality, and reduce LLM hallucinations under Chinese e-commerce customer service scenarios.

---

# ✨ Features

## Intelligent Customer Service

- Local LLM (Ollama)
- Chinese Q&A
- Multi-document retrieval
- Top-K Retrieval
- Optional Reranker
- Source Citation

---

## Dual-Stage Retrieval Pipeline

```
User Query
      │
      ▼
 BM25 Retrieval
      │
      ▼
 BGE-M3 Retrieval
      │
      ▼
 RRF Fusion
      │
      ▼
 Duplicate Removal
      │
      ▼
 BGE-Reranker
      │
      ▼
 Context Construction
      │
      ▼
 Qwen2.5 (Ollama)
      │
      ▼
 Final Answer
```

---

# 🏗 System Architecture

```
                +-------------------+
                |     Web Browser   |
                +---------+---------+
                          |
                    HTTP Request
                          |
                +---------v---------+
                |      Flask App    |
                +---------+---------+
                          |
         +----------------+----------------+
         |                                 |
         |                                 |
   Shopping System                  AI Customer Service
         |                                 |
         +---------------+-----------------+
                         |
                  RAG Pipeline
                         |
         +---------------+----------------+
         |                                |
      BM25                        BGE-M3
         |                                |
         +------------ RRF Fusion --------+
                         |
                   Duplicate Removal
                         |
                   BGE-Reranker
                         |
                    Ollama Qwen2.5
                         |
                    Final Response
```

---

# 📂 Project Structure

```
3fm/

├── app.py
├── app_streamlit.py
├── requirements.txt
├── README.md

├── rag/
│   ├── retrieval/
│   ├── reranker/
│   ├── generator/
│   ├── utils/
│   └── pipeline.py

├── routes/
│   ├── auth.py
│   ├── shop.py
│   ├── cart.py
│   ├── checkout.py
│   ├── chat.py
│   └── admin.py

├── templates/

├── static/

├── knowledge_base/

├── evaluation_results/

└── data/
```
https://chatgpt.com/s/m_6a52e86dab9c8191b4346f8b3ded1bee
---

# 🚀 Installation

## Clone Repository

```bash
git clone https://github.com/quanfu2026/3fm.git

cd 3fm
```

---

## Create Virtual Environment

```bash
python -m venv .venv
```

Windows

```bash
.venv\Scripts\activate
```

Linux

```bash
source .venv/bin/activate
```

---

## Install Packages

```bash
pip install -r requirements.txt
```

---

# 🤖 Install Ollama

Download

https://ollama.com

Install model

```bash
ollama pull qwen2.5:3b
```

Run

```bash
ollama serve
```

---

# ▶ Run Flask Web

```bash
python run_web.py
```

Open browser

```
http://127.0.0.1:5000
```

---

# 📊 Run Streamlit

```bash
streamlit run app_streamlit.py
```

---

# 📚 Knowledge Base

Supported formats

- Markdown
- TXT
- DOCX
- PDF
- PPTX
- XLSX

After adding documents

```
Admin Panel

↓

Rebuild Index
```

---

# 📈 Benchmark Evaluation

Quick Test

```bash
python test_rag_from_word.py --skip-llm --max-q 20
```

Full Evaluation

```bash
python test_rag_from_word.py
```

Enable Reranker

```bash
python test_rag_from_word.py --reranker
```

Run All Experiments

```bash
python run_experiments.py
```

---

# 📊 Evaluation Metrics

| Metric | Description |
|----------|-------------|
| Hit@5 | Retrieval Accuracy |
| MRR | Mean Reciprocal Rank |
| NDCG@5 | Ranking Quality |
| BGE Cosine | Semantic Similarity |
| Hallucination | Hallucination Ratio |
| Latency | End-to-End Response Time |

---

# 🛒 Web Functions

- User Login
- Product Search
- Product Detail
- Shopping Cart
- Checkout
- Order Inquiry
- AI Customer Service
- Knowledge Base Management

---

# 💻 Technologies

- Python
- Flask
- Streamlit
- BM25
- SentenceTransformers
- BGE-M3
- BGE-Reranker
- Ollama
- Qwen2.5
- Jinja2
- FAISS
- JSON

---

# 📷 Demo

Recommended screenshots

```
docs/

home.png

shop.png

chat.png

benchmark.png

admin.png
```

---

# 📄 Research

This project is developed for the master's thesis:

**A Dual-Stage Retrieval-Augmented Generation Framework for Chinese E-Commerce Customer Service**

Core Technologies

- BM25
- BGE-M3
- RRF
- BGE-Reranker
- Qwen2.5

---

# 📜 License

MIT License

---

# 👨‍💻 Author

Quan-Fu Chen

GitHub

https://github.com/quanfu2026

---

⭐ If this project helps you, please consider giving it a Star.