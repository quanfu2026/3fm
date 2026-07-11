import json
from flask import Blueprint, render_template, request

shop_bp = Blueprint("shop", __name__)

def load_products():
    with open("data/products_db.json", encoding="utf-8") as f:
        return json.load(f)

@shop_bp.route("/")
def index():
    products = load_products()
    category = request.args.get("category","")
    if category:
        products = [p for p in products if p["category"]==category]
    return render_template("shop/index.html", products=products, category=category)

@shop_bp.route("/product/<pid>")
def product(pid):
    products = load_products()
    p = next((x for x in products if x["id"]==pid), None)
    if not p:
        return "商品不存在", 404
    return render_template("shop/product.html", product=p)
