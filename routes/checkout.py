import json
from flask import Blueprint, session, render_template, request, redirect, url_for

checkout_bp = Blueprint("checkout", __name__)

def load_products():
    with open("data/products_db.json", encoding="utf-8") as f:
        return json.load(f)

@checkout_bp.route("/")
def index():
    cart  = session.get("cart", {})
    if not cart:
        return redirect(url_for("cart.index"))
    prods = {p["id"]: p for p in load_products()}
    items = []
    total = 0
    for pid, qty in cart.items():
        if pid in prods:
            p = prods[pid]
            subtotal = p["price"] * qty
            total += subtotal
            items.append({**p, "qty": qty, "subtotal": subtotal})
    shipping = 0 if total >= 699 else 60
    return render_template("checkout/index.html", items=items, total=total, shipping=shipping)

@checkout_bp.route("/confirm", methods=["POST"])
def confirm():
    session.pop("cart", None)
    return render_template("checkout/success.html")