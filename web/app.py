from pathlib import Path

from flask import Flask
from flask_session import Session

from rag.pipeline import RAGPipeline
from routes.admin import admin_bp
from routes.auth import auth_bp
from routes.cart import cart_bp
from routes.chat import chat_bp
from routes.checkout import checkout_bp
from routes.main import main_bp
from routes.shop import shop_bp


def create_app():
    root = Path(__file__).resolve().parent.parent

    app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
    )

    session_dir = root / "data" / "flask_session"
    session_dir.mkdir(parents=True, exist_ok=True)

    app.config.update(
        SECRET_KEY="3fm-local-secret-key",
        SESSION_TYPE="filesystem",
        SESSION_PERMANENT=False,
        SESSION_FILE_DIR=str(session_dir),
    )

    Session(app)

    app.rag = RAGPipeline()

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(shop_bp, url_prefix="/shop")
    app.register_blueprint(cart_bp, url_prefix="/cart")
    app.register_blueprint(checkout_bp, url_prefix="/checkout")
    app.register_blueprint(chat_bp, url_prefix="/chat")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    return app

