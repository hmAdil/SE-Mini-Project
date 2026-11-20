from flask import Blueprint, request, jsonify, g

from .db import get_db
from .security import (hash_password, check_password, valid_email, strong_password,
                       new_session, login_required)

bp = Blueprint("auth", __name__)
RESET_OUTBOX = []  # stands in for the SMTP email service


@bp.post("/api/auth/register")
def register():
    d = request.get_json(silent=True) or {}
    if not d.get("name"):
        return jsonify(error="Name is required"), 400
    if not valid_email(d.get("email")):
        return jsonify(error="Enter a valid email address"), 400
    if not strong_password(d.get("password")):
        return jsonify(error="Password must be at least 8 characters with a number and a symbol"), 400
    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE email=?", (d["email"].lower(),)).fetchone():
        return jsonify(error="Email already registered"), 409
    db.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)",
               (d["name"], d["email"].lower(), hash_password(d["password"])))
    db.commit()
    return jsonify(message="Account created"), 201


@bp.post("/api/auth/login")
def login():
    d = request.get_json(silent=True) or {}
    u = get_db().execute("SELECT * FROM users WHERE email=?", ((d.get("email") or "").lower(),)).fetchone()
    if not u or not check_password(d.get("password") or "", u["password_hash"]):
        return jsonify(error="Invalid email or password"), 401
    return jsonify(token=new_session(u["user_id"]), name=u["name"], role=u["role"])


@bp.post("/api/auth/logout")
@login_required()
def logout():
    db = get_db()
    db.execute("DELETE FROM sessions WHERE token=?", (g.token,))
    db.commit()
    return jsonify(message="Logged out")


@bp.post("/api/auth/reset")
def reset():
    d = request.get_json(silent=True) or {}
    email = (d.get("email") or "").lower()
    if get_db().execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        RESET_OUTBOX.append(email)
    return jsonify(message="Reset link sent if the email is registered")


@bp.route("/api/users/me", methods=["GET", "PUT"])
@login_required()
def me():
    db = get_db()
    if request.method == "PUT":
        d = request.get_json(silent=True) or {}
        name, addr = d.get("name", g.user["name"]), d.get("address", g.user["address"])
        if not str(name).strip():
            return jsonify(error="Name cannot be empty"), 400
        db.execute("UPDATE users SET name=?, address=? WHERE user_id=?", (name, addr, g.user["user_id"]))
        db.commit()
    u = db.execute("SELECT name,email,role,address FROM users WHERE user_id=?", (g.user["user_id"],)).fetchone()
    return jsonify(dict(u))
