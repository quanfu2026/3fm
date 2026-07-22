"""
Chat Blueprint — AI 客服 API 端點
"""

from flask import Blueprint, request, jsonify, current_app, session

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/api", methods=["POST"])
def chat_api():
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()

    if not query:
        return jsonify({"error": "query 不能為空"}), 400

    reranker_enabled = data.get("reranker", None)
    top_k = int(data.get("top_k", 5))

    try:
        result = current_app.rag.query(
            user_query=query,
            reranker_enabled=reranker_enabled,
            top_k=top_k,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    history = session.get("chat_history", [])
    history.append({"role": "user", "content": query})
    history.append({
        "role": "assistant",
        "content": result["answer"],
        "metrics": result["metrics"],
    })
    session["chat_history"] = history[-20:]

    return jsonify(result)


@chat_bp.route("/history", methods=["GET"])
def chat_history():
    return jsonify(session.get("chat_history", []))


@chat_bp.route("/history/clear", methods=["POST"])
def clear_history():
    session.pop("chat_history", None)
    return jsonify({"status": "ok"})


@chat_bp.route("/evaluate", methods=["GET"])
def evaluate_rag():
    import json
    import os
    from pathlib import Path

    results_dir = Path("evaluation_results")

    # 預設固定顯示論文正式引用的那組結果，避免之後隨手跑的非正式測試
    # 不小心把儀表板上顯示的數字換掉。若要更新成新的正式結果，改
    # .env 的 EVAL_OFFICIAL_RESULT_FILE 即可，不需要動程式碼。
    official_filename = os.getenv(
        "EVAL_OFFICIAL_RESULT_FILE",
        "eval_detail_no_reranker_20260629_091539.json",
    )
    target_file = results_dir / official_filename

    used_fallback = False

    if not target_file.exists():
        # 官方結果檔案找不到（例如換了一台機器、檔案被搬動），
        # 才退回使用資料夾中最新的一份，而不是直接回傳 404。
        candidates = sorted(
            results_dir.glob("eval_detail_no_reranker_*.json")
        )
        if not candidates:
            return jsonify({
                "error": f"找不到檔案：{target_file}，且 {results_dir} 內也沒有任何可用的評測結果"
            }), 404

        target_file = candidates[-1]
        used_fallback = True

    with open(target_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data["summary"]
    metrics = summary["metrics_avg"]

    result = {
        "total_questions": summary.get("total_questions", 0),
        "model": summary.get("model", ""),
        "use_reranker": summary.get("use_reranker", False),
        "source_file": str(target_file),
        "used_fallback": used_fallback,

        "Hit@5": round(metrics.get("hit_at_5", 0), 4),
        "MRR": round(metrics.get("mrr", 0), 4),
        "NDCG@5": round(metrics.get("ndcg_at_5", 0), 4),
        "BGE Cosine": round(metrics.get("bge_cosine", 0), 4),
        "Coverage Proxy": round(metrics.get("hallucination", 0), 4),
        "平均延遲(ms)": round(metrics.get("latency_ms_avg", 0), 2),
        "P95延遲(ms)": round(metrics.get("latency_ms_p95", 0), 2),
    }

    from flask import Response

    return Response(
        json.dumps(result, ensure_ascii=False, indent=4),
        mimetype="application/json"
    )