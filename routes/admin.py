import os
from flask import Blueprint, render_template, session, redirect, url_for, request, current_app, jsonify
from werkzeug.utils import secure_filename

admin_bp = Blueprint("admin", __name__)

ALLOWED_EXTENSIONS = {"md", "txt", "pdf", "docx", "xlsx", "pptx", "jpg", "jpeg", "png", "webp"}
DOCS_PATH = os.path.join("knowledge_base", "docs")

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
    filename = secure_filename(file.filename)
    file.save(os.path.join(DOCS_PATH, filename))
    return jsonify({"status": "ok", "message": f"{filename} 上傳成功"})

@admin_bp.route("/delete", methods=["POST"])
@require_admin
def delete():
    filename = request.json.get("filename", "")
    filepath = os.path.join(DOCS_PATH, secure_filename(filename))
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "檔案不存在"}), 404

@admin_bp.route("/rebuild-index", methods=["POST"])
@require_admin
def rebuild_index():
    current_app.rag.rebuild_index()
    return jsonify({"status": "ok", "message": "索引重建完成"})