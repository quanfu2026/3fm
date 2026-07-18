import os
import re
import unicodedata
from pathlib import Path
from flask import Blueprint, render_template, session, redirect, url_for, request, current_app, jsonify

admin_bp = Blueprint("admin", __name__)

ALLOWED_EXTENSIONS = {"md", "txt", "pdf", "docx", "xlsx", "pptx", "jpg", "jpeg", "png", "webp"}
DOCS_PATH = os.path.join("knowledge_base", "docs")

# Windows/常見檔案系統不允許、或有路徑意義的危險字元。
_UNSAFE_CHARS_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_filename(filename: str) -> str:
    """像 werkzeug 的 secure_filename()，但保留中文／日文／韓文等非 ASCII 字元。

    werkzeug 的 secure_filename() 只允許 ASCII 字母數字，中文檔名會被整段
    砍掉，只剩副檔名（例如「論文修訂.docx」變成「docx」，沒有副檔名的點，
    後續完全無法被正確歸類處理）。這裡改成只擋掉路徑穿越與檔案系統不允許
    的符號，中文內容原樣保留。
    """
    filename = os.path.basename(filename or "")
    filename = unicodedata.normalize("NFKC", filename)
    filename = _UNSAFE_CHARS_RE.sub("_", filename)
    # 去除頭尾空白與句點：避免 "." "..", 以及 Windows 不允許檔名以句點/空白結尾。
    filename = filename.strip().strip(".")
    return filename or "file"


def resolve_docs_path(filename: str) -> Path | None:
    """把檔名轉成 docs 資料夾底下的絕對路徑，並確認沒有跳出 docs 資料夾。"""
    base_dir = Path(DOCS_PATH).resolve()
    candidate = (base_dir / safe_filename(filename)).resolve()
    if base_dir not in candidate.parents and candidate != base_dir:
        return None
    return candidate

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def require_admin(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = session.get("user")
        if not user or user.get("role") != "admin":
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper

@admin_bp.route("/")
@require_admin
def index():
    files = os.listdir(DOCS_PATH) if os.path.exists(DOCS_PATH) else []
    return render_template("admin/index.html", files=files)

@admin_bp.route("/upload", methods=["POST"])
@require_admin
def upload():
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "沒有檔案"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "未選擇檔案"}), 400
    if not allowed_file(file.filename):
        return jsonify({"status": "error", "message": "不支援的檔案格式"}), 400
    os.makedirs(DOCS_PATH, exist_ok=True)
    filepath = resolve_docs_path(file.filename)
    if filepath is None:
        return jsonify({"status": "error", "message": "檔名不合法"}), 400
    file.save(str(filepath))
    return jsonify({"status": "ok", "message": f"{filepath.name} 上傳成功"})

@admin_bp.route("/delete", methods=["POST"])
@require_admin
def delete():
    filename = request.json.get("filename", "")
    filepath = resolve_docs_path(filename)
    if filepath is None:
        return jsonify({"status": "error", "message": "檔名不合法"}), 400
    if filepath.exists():
        filepath.unlink()
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "檔案不存在"}), 404

@admin_bp.route("/rebuild-index", methods=["POST"])
@require_admin
def rebuild_index():
    current_app.rag.rebuild_index()
    return jsonify({"status": "ok", "message": "索引重建完成"})