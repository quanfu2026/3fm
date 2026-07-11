# RAG 自動化評測系統 — 快速指南

## 檔案說明

| 檔案 | 用途 |
|------|------|
| `test_rag_from_word.py` | ⭐ 主評測腳本（課本+考卷→六大指標） |
| `run_experiments.py`    | 一鍵跑四組對照實驗並輸出比較表 |
| `run_eval.bat`          | Windows 快速啟動腳本 |

---

## 執行步驟

### 前置作業
```bash
# 1. 安裝套件
pip install rank-bm25 jieba sentence-transformers openai python-docx tqdm

# 2. 建立知識庫（課本）
python build_knowledge_base_multi.py
# → 產生 knowledge_base/docs/product_specs.txt
```

### 快速測試（不需 LLM，只看檢索指標）
```bash
python test_rag_from_word.py --skip-llm --max-q 20
```

### 完整單組評測
```bash
# 雙階段（無 Reranker）
python test_rag_from_word.py

# 雙階段（有 Reranker）
python test_rag_from_word.py --reranker

# 換考卷
python test_rag_from_word.py --docx "knowledge_base/evaluation/3C科技類客服問答集_100筆.docx"
```

### 完整四組對照實驗（論文用）
```bash
# 確認 LM Studio 已啟動後執行
python run_experiments.py
```

---

## 輸出格式

```
evaluation_results/
  ├── eval_detail_no_reranker_20250628_143022.json   ← 每題詳細結果
  ├── eval_summary_no_reranker_20250628_143022.csv   ← 可直接貼 Excel
  ├── comparison_table_20250628_150000.json          ← 四組比較表
  └── eval_20250628_143022.log                       ← 執行日誌
```

---

## 六大評估指標說明

| 指標 | 類型 | 說明 |
|------|------|------|
| Hit@5 | 檢索 | 前5個結果中是否命中相關文件 |
| MRR | 檢索 | 第一個相關文件的排名倒數 |
| NDCG@5 | 排序 | 考慮位置權重的累積增益 |
| BGE Cosine | 生成 | 回答與 Ground Truth 的語意相似度 |
| 幻覺率 | 生成 | 回答中未在知識庫出現的詞彙比例 |
| 延遲(ms) | 效率 | 端到端回答時間 |

---

## ⚠️  關於 +20.8% 的正確說法

Hit@5 的提升是相對**單層 BM25（0.72）**計算：
- (0.87 - 0.72) / 0.72 × 100% = **+20.8%**
- Baseline 無檢索，Hit@5 恆為 0，**不可作為比較基準**
- 幻覺率下降（0.25→0.07）才是相對 Baseline 的有效比較
