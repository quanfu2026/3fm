"""
3fm — 電商智能客服系統
論文：基於任務分解之雙階段檢索增強生成架構：應用於電子商務客服系統
"""
import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv(override=True)  # 強制在最前端把 .env 的內容載入並覆蓋系統變數

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

    # ── 初始化 RAG 系統（掛載到 app context）──
    from rag.pipeline import RAGPipeline
    app.rag = RAGPipeline()

    # ── 註冊 Blueprints ──
    from routes.main    import main_bp
    from routes.auth    import auth_bp
    from routes.shop    import shop_bp
    from routes.cart    import cart_bp
    from routes.chat    import chat_bp
    from routes.admin   import admin_bp
    from routes.checkout import checkout_bp
 
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp,  url_prefix="/auth")
    app.register_blueprint(shop_bp,  url_prefix="/shop")
    app.register_blueprint(cart_bp,  url_prefix="/cart")
    app.register_blueprint(chat_bp,  url_prefix="/chat")
    print(app.url_map)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    
    app.register_blueprint(checkout_bp, url_prefix="/checkout")

    return app


if __name__ == "__main__":
    app = create_app()
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=5000)

    app.run(debug=debug, host="0.0.0.0", port=5000)
