"""Quản lý chi tiêu cá nhân: Flask, Jinja2, PostgreSQL."""
import os
import secrets
from datetime import date
from functools import wraps

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
DATABASE_URL = os.environ["DATABASE_URL"]
STUDENT_ID = os.environ.get("STUDENT_ID", "")
STUDENT_NAME = os.environ.get("STUDENT_NAME", "")
CATEGORIES = ["Ăn uống", "Đi lại", "Học tập", "Giải trí", "Khác"]


def db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


@app.context_processor
def common():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return {"csrf_token": session["csrf_token"], "student_id": STUDENT_ID, "student_name": STUDENT_NAME}


@app.before_request
def protect_post():
    if request.method == "POST" and not secrets.compare_digest(
        session.get("csrf_token", ""), request.form.get("csrf_token", "")
    ):
        abort(400)


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not (3 <= len(username) <= 50) or len(password) < 8:
            flash("Tên đăng nhập 3–50 ký tự, mật khẩu ít nhất 8 ký tự.")
        else:
            try:
                with db() as conn:
                    conn.execute(
                        "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                        (username, generate_password_hash(password)),
                    )
                flash("Đăng ký thành công. Hãy đăng nhập.")
                return redirect(url_for("login"))
            except psycopg.errors.UniqueViolation:
                flash("Tên đăng nhập đã tồn tại.")
    return render_template("auth.html", title="Đăng ký", action="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        with db() as conn:
            user = conn.execute(
                "SELECT id, username, password_hash FROM users WHERE username = %s",
                (request.form.get("username", "").strip(),),
            ).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Đăng nhập thành công.")
            return redirect(url_for("index"))
        flash("Sai tên đăng nhập hoặc mật khẩu.")
    return render_template("auth.html", title="Đăng nhập", action="login")


@app.post("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@login_required
def index():
    uid = session["user_id"]
    with db() as conn:
        rows = conn.execute(
            "SELECT id, amount, category, note, spent_on FROM expenses "
            "WHERE user_id = %s ORDER BY spent_on DESC, id DESC", (uid,)).fetchall()
        month_total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS t FROM expenses "
            "WHERE user_id = %s AND date_trunc('month', spent_on) = date_trunc('month', CURRENT_DATE)",
            (uid,)).fetchone()["t"]
        by_cat = conn.execute(
            "SELECT category, SUM(amount) AS t FROM expenses WHERE user_id = %s "
            "AND date_trunc('month', spent_on) = date_trunc('month', CURRENT_DATE) "
            "GROUP BY category ORDER BY t DESC", (uid,)).fetchall()
    return render_template("index.html", rows=rows, month_total=month_total, by_cat=by_cat)


def parse_form():
    """Trả về (dữ liệu, lỗi)."""
    category = request.form.get("category", "")
    note = request.form.get("note", "").strip()[:200]
    try:
        amount = int(request.form.get("amount", ""))
        spent_on = date.fromisoformat(request.form.get("spent_on", ""))
    except ValueError:
        return None, "Số tiền (số nguyên) và ngày chi không hợp lệ."
    if amount <= 0 or category not in CATEGORIES:
        return None, "Số tiền phải lớn hơn 0 và chọn đúng danh mục."
    return {"amount": amount, "category": category, "note": note, "spent_on": spent_on}, None


def own_expense(eid):
    with db() as conn:
        row = conn.execute(
            "SELECT id, amount, category, note, spent_on FROM expenses WHERE id = %s AND user_id = %s",
            (eid, session["user_id"])).fetchone()
    if row is None:
        abort(404)
    return row


@app.route("/expenses/new", methods=["GET", "POST"])
@login_required
def create():
    item = {"spent_on": date.today()}
    if request.method == "POST":
        data, err = parse_form()
        if err:
            flash(err)
            item = request.form
        else:
            with db() as conn:
                conn.execute(
                    "INSERT INTO expenses (user_id, amount, category, note, spent_on) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (session["user_id"], data["amount"], data["category"], data["note"], data["spent_on"]))
            flash("Đã thêm khoản chi.")
            return redirect(url_for("index"))
    return render_template("form.html", title="Thêm khoản chi", item=item, categories=CATEGORIES)


@app.route("/expenses/<int:eid>/edit", methods=["GET", "POST"])
@login_required
def edit(eid):
    item = own_expense(eid)
    if request.method == "POST":
        data, err = parse_form()
        if err:
            flash(err)
            item = request.form
        else:
            with db() as conn:
                conn.execute(
                    "UPDATE expenses SET amount=%s, category=%s, note=%s, spent_on=%s "
                    "WHERE id=%s AND user_id=%s",
                    (data["amount"], data["category"], data["note"], data["spent_on"], eid, session["user_id"]))
            flash("Đã sửa khoản chi.")
            return redirect(url_for("index"))
    return render_template("form.html", title="Sửa khoản chi", item=item, categories=CATEGORIES)


@app.post("/expenses/<int:eid>/delete")
@login_required
def delete(eid):
    own_expense(eid)
    with db() as conn:
        conn.execute("DELETE FROM expenses WHERE id=%s AND user_id=%s", (eid, session["user_id"]))
    flash("Đã xóa khoản chi.")
    return redirect(url_for("index"))
