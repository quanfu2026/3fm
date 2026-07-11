"""
test_rag_from_word.py
─────────────────────────────────────────────────────────────────────
自動化批量評測腳本
流程：
  1. 從 product_specs.txt 建立 BM25 + BGE 雙層索引（課本）
  2. 從 .docx 問答集解析出所有「客戶提問」與「Ground Truth」（考卷）
  3. 每一題送進 RAG 管線 → BM25 → BGE → RRF → Reranker → Qwen2.5
  4. 計算六大評估指標並輸出 JSON / CSV 報告

用法：
  python test_rag_from_word.py

環境變數（寫在 .env 或直接改下方 CONFIG）：
  LM_STUDIO_URL   = http://localhost:1234/v1
  LM_STUDIO_MODEL = qwen2.5-7b-instruct
  KNOWLEDGE_BASE_PATH = ./knowledge_base
"""

import os
import re
import sys
import json
import time
import math
import logging
import pickle
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

# ══════════════════════════════════════════
# 0.  設定區（在這裡改就好）
# ══════════════════════════════════════════
CONFIG = {
    # 知識庫（課本）
    "knowledge_txt":  "knowledge_base/docs/product_specs.txt",

    # 考卷（任選一個 .docx）
    "eval_docx":      "knowledge_base/evaluation/電商客服問答集.docx",

    # LM Studio / vLLM / Ollama（OpenAI 相容 API）
    "lm_base_url":    os.getenv("LM_STUDIO_URL",   "http://localhost:1234/v1"),
    "lm_model":       os.getenv("LM_STUDIO_MODEL", "qwen2.5-7b-instruct"),
    "lm_api_key":     os.getenv("LM_STUDIO_KEY",   "lm-studio"),   # LM Studio 不驗 key

    # 檢索參數
    "bm25_top_k":     10,
    "bge_top_k":      10,
    "rrf_top_k":      10,
    "rerank_top_k":   5,
    "final_top_k":    5,     # 送給 LLM 的 context 數量
    "rrf_k":          60,

    # BGE 模型（本地 HuggingFace，可改為 BAAI/bge-m3）
    "bge_model":      os.getenv("BGE_MODEL", "BAAI/bge-m3"),

    # 輸出目錄
    "output_dir":     "evaluation_results",

    # 是否啟用 Reranker（關掉可省記憶體）
    "use_reranker":   False,

    # 是否跳過 LLM（只評估檢索指標，速度快 10 倍）
    "skip_llm":       False,

    # 每次評測最多幾題（None = 全部）
    "max_questions":  None,
}

# ══════════════════════════════════════════
# 1.  日誌設定
# ══════════════════════════════════════════
Path(CONFIG["output_dir"]).mkdir(exist_ok=True)
log_file = Path(CONFIG["output_dir"]) / f"eval_{datetime.now():%Y%m%d_%H%M%S}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════
# 2.  知識庫解析（課本）
# ══════════════════════════════════════════
def load_knowledge_chunks(txt_path: str) -> list[dict]:
    """
    讀取 product_specs.txt，每個 === 產品知識資料編號 N === 區塊視為一個 chunk
    回傳 [{"id": str, "content": str, "source": str, "type": str}]
    """
    path = Path(txt_path)
    if not path.exists():
        log.error(f"找不到知識庫檔案：{txt_path}")
        log.error("請先執行 build_knowledge_base_multi.py 產生課本")
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    # 依分隔符切割
    blocks = re.split(r"=== 產品知識資料編號 \d+ ===", text)
    chunks = []
    for i, block in enumerate(blocks):
        content = block.strip()
        if not content:
            continue
        chunks.append({
            "id":      f"chunk_{i:04d}",
            "content": content,
            "source":  txt_path,
            "type":    "product_spec",
        })

    log.info(f"知識庫載入：{len(chunks)} 個 chunks（來源：{txt_path}）")
    return chunks


# ══════════════════════════════════════════
# 3.  評測資料集解析（考卷）
# ══════════════════════════════════════════
def parse_eval_docx(docx_path: str) -> list[dict]:
    """
    解析 .docx 問答集，回傳：
    [{"sample_id": int, "question": str, "ground_truth": str}]
    """
    from docx import Document

    path = Path(docx_path)
    if not path.exists():
        log.error(f"找不到評測檔案：{docx_path}")
        sys.exit(1)

    doc = Document(str(path))
    samples = []
    current = {}
    state   = None   # "question" | "answer"

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue

        # 新樣本起始
        m = re.match(r"樣本\s*ID[:：]\s*(\d+)", text)
        if m:
            if current.get("question") and current.get("ground_truth"):
                samples.append(current)
            current = {"sample_id": int(m.group(1)), "question": "", "ground_truth": ""}
            state   = None
            continue

        # 客戶提問區段
        if "【客戶提問" in text:
            state = "question"
            inline = re.sub(r"【客戶提問[^】]*】", "", text).strip()
            if inline:
                current["question"] = inline
            continue

        # 標準回答區段
        if "【標準客服回答" in text:
            state = "answer"
            inline = re.sub(r"【標準客服回答[^】]*】", "", text).strip()
            if inline:
                current["ground_truth"] = inline
            continue

        # 分隔線
        if text.startswith("─") or text.startswith("—") or text.startswith("━"):
            continue

        # 累積內容
        if state == "question":
            current["question"] += ("\n" if current["question"] else "") + text
        elif state == "answer":
            current["ground_truth"] += ("\n" if current["ground_truth"] else "") + text

    # 最後一筆
    if current.get("question") and current.get("ground_truth"):
        samples.append(current)

    log.info(f"評測資料集：{len(samples)} 筆（來源：{docx_path}）")
    return samples


# ══════════════════════════════════════════
# 4.  BM25 檢索器（內嵌版，不依賴外部檔案）
# ══════════════════════════════════════════
class BM25Retriever:
    def __init__(self):
        self.bm25 = None
        self.docs = []

    def build(self, docs: list[dict]):
        import jieba
        from rank_bm25 import BM25Okapi
        self.docs = docs
        tokenized = [list(jieba.cut_for_search(d["content"])) for d in docs]
        self.bm25 = BM25Okapi(tokenized)
        log.info(f"BM25 索引建立完成：{len(docs)} 筆")

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        import jieba
        if not self.bm25:
            return []
        tokens = list(jieba.cut_for_search(query))
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for rank, (idx, score) in enumerate(ranked, 1):
            if score > 0:
                doc = dict(self.docs[idx])
                doc["score"]     = float(score)
                doc["rank_bm25"] = rank
                results.append(doc)
        return results


# ══════════════════════════════════════════
# 5.  BGE 向量檢索器（內嵌版）
# ══════════════════════════════════════════
class BGERetriever:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model      = None
        self.docs       = []
        self.vectors    = None

    def _load_model(self):
        if self.model:
            return
        log.info(f"載入 BGE 模型：{self.model_name}（首次較慢）")
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(self.model_name)
        log.info("BGE 模型載入完成")

    def build(self, docs: list[dict]):
        self._load_model()
        import numpy as np
        self.docs = docs
        contents  = [d["content"] for d in docs]
        log.info(f"BGE 向量編碼中（{len(contents)} 筆）...")
        self.vectors = self.model.encode(
            contents,
            batch_size=8,
            show_progress_bar=True,
            normalize_embeddings=True,
        )
        log.info("BGE 向量索引建立完成")

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        import numpy as np
        if self.vectors is None or not self.model:
            return []
        q_vec  = self.model.encode([query], normalize_embeddings=True)[0]
        scores = self.vectors @ q_vec
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for rank, (idx, score) in enumerate(ranked, 1):
            doc = dict(self.docs[idx])
            doc["score"]   = float(score)
            doc["rank_bge"] = rank
            results.append(doc)
        return results


# ══════════════════════════════════════════
# 6.  RRF 融合（內嵌版）
# ══════════════════════════════════════════
class RRFFusion:
    def __init__(self, k: int = 60):
        self.k = k

    def fuse(self, bm25_results: list, bge_results: list, top_k: int = 10) -> list:
        from collections import defaultdict
        doc_map    = {}
        rrf_scores = defaultdict(float)

        for rank, doc in enumerate(bm25_results, 1):
            doc_id = doc["id"]
            doc_map[doc_id]     = doc
            rrf_scores[doc_id] += 1.0 / (self.k + rank)

        for rank, doc in enumerate(bge_results, 1):
            doc_id = doc["id"]
            if doc_id not in doc_map:
                doc_map[doc_id] = doc
            rrf_scores[doc_id] += 1.0 / (self.k + rank)

        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:top_k]
        results = []
        for new_rank, doc_id in enumerate(sorted_ids, 1):
            doc = dict(doc_map[doc_id])
            doc["rrf_score"] = round(rrf_scores[doc_id], 6)
            doc["rank"]      = new_rank
            results.append(doc)
        return results


# ══════════════════════════════════════════
# 7.  LLM 介面（LM Studio / Ollama / vLLM）
# ══════════════════════════════════════════
SYSTEM_PROMPT = """你是一位專業的電商客服助理。
請根據以下提供的知識片段回答客戶問題。
規則：
1. 只能根據知識片段中的資訊回答，不可自行編造
2. 若知識片段中找不到答案，請告知「很抱歉，我目前沒有這個問題的相關資料，建議您聯繫客服人員」
3. 回答需簡潔、友善、專業
4. 若涉及價格、政策，請務必引用知識片段中的確切資訊"""

def call_llm(query: str, context: str, cfg: dict) -> tuple[str, float]:
    """
    呼叫 LLM，回傳 (answer, latency_ms)
    相容 LM Studio / vLLM / Ollama（OpenAI 格式）
    """
    from openai import OpenAI
    client = OpenAI(
        api_key  = cfg["lm_api_key"],
        base_url = cfg["lm_base_url"],
    )
    prompt = f"""【知識庫內容】
{context}

【客戶問題】
{query}

請根據以上知識庫內容，給出專業、友善的回答："""

    t0 = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model    = cfg["lm_model"],
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature = 0.1,
            max_tokens  = 512,
        )
        answer  = resp.choices[0].message.content.strip()
        latency = (time.perf_counter() - t0) * 1000
        return answer, latency
    except Exception as e:
        latency = (time.perf_counter() - t0) * 1000
        log.warning(f"LLM 呼叫失敗：{e}")
        return f"[LLM 錯誤] {e}", latency


# ══════════════════════════════════════════
# 8.  評估指標計算
# ══════════════════════════════════════════
def tokenize_zh(text: str) -> set[str]:
    """中文字元級別 tokenize（用於 BERTScore 簡化版）"""
    import jieba
    return set(jieba.cut(text))

def compute_hit_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int = 5) -> float:
    """Hit@K：前 K 個結果中是否有相關文件"""
    return 1.0 if any(rid in relevant_ids for rid in retrieved_ids[:k]) else 0.0

def compute_mrr(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """Mean Reciprocal Rank"""
    for rank, rid in enumerate(retrieved_ids, 1):
        if rid in relevant_ids:
            return 1.0 / rank
    return 0.0

def compute_ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int = 5) -> float:
    """NDCG@K（binary relevance）"""
    dcg  = sum(
        1.0 / math.log2(rank + 1)
        for rank, rid in enumerate(retrieved_ids[:k], 1)
        if rid in relevant_ids
    )
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(relevant_ids), k) + 1))
    return dcg / idcg if idcg > 0 else 0.0

def compute_bge_cosine(answer: str, ground_truth: str, model) -> float:
    """
    用 BGE 模型計算答案與 GT 的語意相似度
    （論文中的生成品質指標）
    """
    if model is None or not answer or not ground_truth:
        return 0.0
    try:
        import numpy as np
        vecs = model.encode([answer, ground_truth], normalize_embeddings=True)
        return float(vecs[0] @ vecs[1])
    except Exception:
        return 0.0

def compute_hallucination_rate(answer: str, context: str) -> float:
    """
    簡化版幻覺率：
    用 jieba 分詞，計算答案中有多少關鍵詞不在 context 中出現
    （論文中使用更嚴謹的 NLI 模型，這裡用詞彙覆蓋率近似）
    """
    import jieba
    answer_tokens  = set(w for w in jieba.cut(answer)  if len(w) > 1)
    context_tokens = set(w for w in jieba.cut(context) if len(w) > 1)
    if not answer_tokens:
        return 0.0
    not_covered = answer_tokens - context_tokens
    return len(not_covered) / len(answer_tokens)

def find_relevant_chunks(ground_truth: str, chunks: list[dict], threshold: float = 0.3) -> set[str]:
    """
    找出與 ground_truth 語意最相近的 chunk IDs（作為「正確答案來源」）
    用於計算 Hit@K、MRR、NDCG
    策略：詞彙重疊度 > threshold 的視為相關
    """
    import jieba
    gt_tokens = set(w for w in jieba.cut(ground_truth) if len(w) > 1)
    relevant  = set()
    for chunk in chunks:
        c_tokens = set(w for w in jieba.cut(chunk["content"]) if len(w) > 1)
        if not gt_tokens or not c_tokens:
            continue
        overlap = len(gt_tokens & c_tokens) / len(gt_tokens)
        if overlap >= threshold:
            relevant.add(chunk["id"])
    # 至少保留最高相似度的那一個
    if not relevant:
        best = max(
            chunks,
            key=lambda c: len(set(jieba.cut(c["content"])) & gt_tokens),
            default=None,
        )
        if best:
            relevant.add(best["id"])
    return relevant


# ══════════════════════════════════════════
# 9.  主評測流程
# ══════════════════════════════════════════
def build_index(chunks: list[dict], cfg: dict):
    """建立 BM25 + BGE 雙層索引"""
    bm25 = BM25Retriever()
    bm25.build(chunks)

    bge = BGERetriever(cfg["bge_model"])
    bge.build(chunks)

    rrf = RRFFusion(k=cfg["rrf_k"])
    return bm25, bge, rrf

def run_single_query(
    query:    str,
    chunks:   list[dict],
    bm25:     BM25Retriever,
    bge:      BGERetriever,
    rrf:      RRFFusion,
    cfg:      dict,
) -> dict:
    """
    對單一問題執行完整 RAG 管線
    回傳詳細的中間結果與最終答案
    """
    t_total_start = time.perf_counter()

    # ── Stage 1：BM25 ──
    t0 = time.perf_counter()
    bm25_results = bm25.search(query, top_k=cfg["bm25_top_k"])
    t_bm25 = (time.perf_counter() - t0) * 1000

    # ── Stage 2：BGE ──
    t0 = time.perf_counter()
    bge_results = bge.search(query, top_k=cfg["bge_top_k"])
    t_bge = (time.perf_counter() - t0) * 1000

    # ── Stage 3：RRF 融合 ──
    t0 = time.perf_counter()
    fused = rrf.fuse(bm25_results, bge_results, top_k=cfg["rrf_top_k"])
    t_rrf = (time.perf_counter() - t0) * 1000

    # ── Stage 4：Reranker（可選）──
    reranked = fused
    t_rerank = 0.0
    if cfg["use_reranker"]:
        try:
            from bge_reranker import BGEReranker
            reranker = BGEReranker()
            t0 = time.perf_counter()
            reranked = reranker.rerank(query, fused, top_k=cfg["rerank_top_k"])
            t_rerank = (time.perf_counter() - t0) * 1000
        except Exception as e:
            log.warning(f"Reranker 失敗（跳過）：{e}")

    # ── Stage 5：組合 Context ──
    top_docs = reranked[:cfg["final_top_k"]]
    context  = "\n\n".join(
        f"[知識片段 {i+1}]\n{d['content']}"
        for i, d in enumerate(top_docs)
    )

    # ── Stage 6：LLM 生成 ──
    answer  = "[SKIP]"
    t_llm   = 0.0
    if not cfg["skip_llm"]:
        answer, t_llm = call_llm(query, context, cfg)

    t_total = (time.perf_counter() - t_total_start) * 1000

    return {
        "retrieved_ids":  [d["id"] for d in reranked],
        "top_docs":        top_docs,
        "context":         context,
        "answer":          answer,
        "latency": {
            "bm25_ms":   round(t_bm25,   2),
            "bge_ms":    round(t_bge,    2),
            "rrf_ms":    round(t_rrf,    2),
            "rerank_ms": round(t_rerank, 2),
            "llm_ms":    round(t_llm,    2),
            "total_ms":  round(t_total,  2),
        },
    }

def evaluate(cfg: dict):
    log.info("=" * 60)
    log.info("🚀  RAG 自動化批量評測啟動")
    log.info("=" * 60)

    # ── 載入課本 & 考卷 ──
    chunks  = load_knowledge_chunks(cfg["knowledge_txt"])
    samples = parse_eval_docx(cfg["eval_docx"])

    if cfg["max_questions"]:
        samples = samples[:cfg["max_questions"]]
        log.info(f"限制評測題數：{len(samples)} 題")

    # ── 建立索引 ──
    log.info("建立 BM25 + BGE 雙層索引...")
    bm25, bge, rrf = build_index(chunks, cfg)

    # ── 逐題評測 ──
    results     = []
    all_hit5    = []
    all_mrr     = []
    all_ndcg5   = []
    all_cosine  = []
    all_halluc  = []
    all_latency = []

    log.info(f"\n開始批量評測（共 {len(samples)} 題）\n{'─'*60}")

    for i, sample in enumerate(samples, 1):
        sid   = sample["sample_id"]
        query = sample["question"]
        gt    = sample["ground_truth"]

        log.info(f"\n[{i:3d}/{len(samples)}] 樣本 ID={sid}")
        log.info(f"  問題：{query[:60]}...")

        # RAG 推論
        result = run_single_query(query, chunks, bm25, bge, rrf, cfg)

        # 找出與 GT 相關的 chunk IDs
        relevant_ids = find_relevant_chunks(gt, chunks)

        # 計算檢索指標
        retrieved = result["retrieved_ids"]
        hit5   = compute_hit_at_k(retrieved, relevant_ids, k=5)
        mrr    = compute_mrr(retrieved, relevant_ids)
        ndcg5  = compute_ndcg_at_k(retrieved, relevant_ids, k=5)

        # 計算生成指標
        cosine = compute_bge_cosine(result["answer"], gt, bge.model)
        halluc = compute_hallucination_rate(result["answer"], result["context"])

        lat = result["latency"]["total_ms"]

        all_hit5.append(hit5)
        all_mrr.append(mrr)
        all_ndcg5.append(ndcg5)
        all_cosine.append(cosine)
        all_halluc.append(halluc)
        all_latency.append(lat)

        log.info(
            f"  Hit@5={hit5:.2f}  MRR={mrr:.3f}  NDCG@5={ndcg5:.3f}  "
            f"Cosine={cosine:.3f}  Halluc={halluc:.3f}  Latency={lat:.0f}ms"
        )
        if result["answer"] != "[SKIP]":
            log.info(f"  回答：{result['answer'][:80]}...")

        results.append({
            "sample_id":    sid,
            "question":     query,
            "ground_truth": gt,
            "answer":       result["answer"],
            "metrics": {
                "hit_at_5":         round(hit5,   4),
                "mrr":              round(mrr,    4),
                "ndcg_at_5":        round(ndcg5,  4),
                "bge_cosine":       round(cosine, 4),
                "hallucination":    round(halluc, 4),
                "latency_ms":       round(lat,    2),
            },
            "retrieval": {
                "retrieved_ids":    retrieved[:5],
                "relevant_ids":     list(relevant_ids),
            },
            "latency_breakdown":    result["latency"],
        })

    # ── 彙總統計 ──
    n = len(results)
    summary = {
        "eval_file":        cfg["eval_docx"],
        "knowledge_file":   cfg["knowledge_txt"],
        "total_questions":  n,
        "model":            cfg["lm_model"],
        "use_reranker":     cfg["use_reranker"],
        "timestamp":        datetime.now().isoformat(),
        "metrics_avg": {
            "hit_at_5":         round(sum(all_hit5)   / n, 4),
            "mrr":              round(sum(all_mrr)    / n, 4),
            "ndcg_at_5":        round(sum(all_ndcg5)  / n, 4),
            "bge_cosine":       round(sum(all_cosine) / n, 4),
            "hallucination":    round(sum(all_halluc) / n, 4),
            "latency_ms_avg":   round(sum(all_latency)/ n, 2),
            "latency_ms_p95":   round(sorted(all_latency)[int(n*0.95)], 2) if n > 1 else 0,
        },
    }

    # ── 輸出報告 ──
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    reranker_tag = "with_reranker" if cfg["use_reranker"] else "no_reranker"

    # JSON 詳細報告
    json_path = Path(cfg["output_dir"]) / f"eval_detail_{reranker_tag}_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)

    # CSV 摘要（方便貼入 Excel / 簡報）
    import csv
    csv_path = Path(cfg["output_dir"]) / f"eval_summary_{reranker_tag}_{ts}.csv"
    fieldnames = ["sample_id", "question", "hit_at_5", "mrr", "ndcg_at_5",
                  "bge_cosine", "hallucination", "latency_ms", "answer"]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "sample_id":    r["sample_id"],
                "question":     r["question"][:50],
                "answer":       r["answer"][:80],
                **r["metrics"],
            })

    # ── 終端漂亮輸出 ──
    m = summary["metrics_avg"]
    print("\n" + "═" * 60)
    print(f"📊  評測結果總覽（{n} 題）")
    print("─" * 60)
    print(f"  檢索品質")
    print(f"    Hit@5        = {m['hit_at_5']:.4f}")
    print(f"    MRR          = {m['mrr']:.4f}")
    print(f"    NDCG@5       = {m['ndcg_at_5']:.4f}")
    print(f"  生成品質")
    print(f"    BGE Cosine   = {m['bge_cosine']:.4f}")
    print(f"    幻覺率       = {m['hallucination']:.4f}")
    print(f"  系統效率")
    print(f"    平均延遲     = {m['latency_ms_avg']:.1f} ms")
    print(f"    P95 延遲     = {m['latency_ms_p95']:.1f} ms")
    print("─" * 60)
    print(f"  詳細 JSON：{json_path}")
    print(f"  摘要 CSV ：{csv_path}")
    print("═" * 60)

    return summary, results


# ══════════════════════════════════════════
# 10. 執行入口
# ══════════════════════════════════════════
if __name__ == "__main__":
    # ── 可在這裡切換不同考卷 ──
    CONFIG["eval_docx"] = "knowledge_base/evaluation/電商客服問答集.docx"

    # ── 實驗組切換（對應論文四組對照）──
    import argparse
    parser = argparse.ArgumentParser(description="RAG 自動化評測")
    parser.add_argument("--docx",        default=CONFIG["eval_docx"],    help="考卷 .docx 路徑")
    parser.add_argument("--knowledge",   default=CONFIG["knowledge_txt"], help="知識庫 .txt 路徑")
    parser.add_argument("--reranker",    action="store_true",             help="啟用 Reranker")
    parser.add_argument("--skip-llm",    action="store_true",             help="跳過 LLM（只評估檢索）")
    parser.add_argument("--max-q",       type=int, default=None,         help="最多評測幾題")
    parser.add_argument("--model",       default=CONFIG["lm_model"],     help="LLM 模型名稱")
    parser.add_argument("--base-url",    default=CONFIG["lm_base_url"],  help="LM Studio base URL")
    args = parser.parse_args()

    CONFIG.update({
        "eval_docx":      args.docx,
        "knowledge_txt":  args.knowledge,
        "use_reranker":   args.reranker,
        "skip_llm":       args.skip_llm,
        "max_questions":  args.max_q,
        "lm_model":       args.model,
        "lm_base_url":    args.base_url,
    })

    evaluate(CONFIG)
