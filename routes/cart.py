import json
from flask import Blueprint, session, request, jsonify, render_template

cart_bp = Blueprint("cart", __name__)

def load_products():
    with open("data/products_db.json", encoding="utf-8") as f:
        return json.load(f)

@cart_bp.route("/")
def index():
    cart  = session.get("cart", {})
    prods = {p["id"]: p for p in load_products()}
    items = []
    total = 0
    for pid, qty in cart.items():
        if pid in prods:
            p = prods[pid]
            subtotal = p["price"] * qty
            total += subtotal
            items.append({**p, "qty": qty, "subtotal": subtotal})
    return render_template("cart/index.html", items=items, total=total)

@cart_bp.route("/add", methods=["POST"])
def add():
    pid = request.json.get("product_id","")
    qty = int(request.json.get("qty", 1))
    cart = session.get("cart", {})
    cart[pid] = cart.get(pid, 0) + qty
    session["cart"] = cart
    return jsonify({"status":"ok","count": sum(cart.values())})

@cart_bp.route("/remove", methods=["POST"])
def remove():
    pid  = request.json.get("product_id","")
    cart = session.get("cart", {})
    cart.pop(pid, None)
    session["cart"] = cart
    return jsonify({"status":"ok"})
