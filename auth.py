"""
auth.py — Flask-Login integration + auth routes.
"""
import functools
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
import database as db

auth_bp = Blueprint("auth", __name__)

SESSION_KEY = "user_id"


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if SESSION_KEY not in session:
            return redirect(url_for("auth.login", next=request.path))
        user = db.get_user_by_id(session[SESSION_KEY])
        if not user:
            session.clear()
            return redirect(url_for("auth.login"))
        g.user = user
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @functools.wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not g.user.get("is_admin"):
            flash("Доступ запрещён. Требуются права администратора.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if SESSION_KEY in session:
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.verify_password(username, password)
        if user:
            session.permanent = True
            session[SESSION_KEY] = user["id"]
            next_url = request.args.get("next") or url_for("dashboard")
            return redirect(next_url)
        error = "Неверный логин или пароль."
    return render_template("login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
