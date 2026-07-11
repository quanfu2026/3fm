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
