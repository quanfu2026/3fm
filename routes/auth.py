import json
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

auth_bp = Blueprint("auth", __name__)

def load_users():
    with open("data/users_db.json", encoding="utf-8") as f:
        return json.load(f)

@auth_bp.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        uname = request.form.get("username","").strip()
        pwd   = request.form.get("password","").strip()
        users = load_users()
        user  = next((u for u in users if u["username"]==uname and u["password"]==pwd), None)
        if user:
            session["user"] = user
            return redirect(url_for("main.index"))
        flash("帳號或密碼錯誤")
    return render_template("auth/login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.index"))
