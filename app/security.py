"""Password hashing, session tokens and role decorators."""
import re
import secrets
import time
from functools import wraps

import bcrypt
from flask import request, jsonify, g

from .db import get_db

SESSION_TTL = 3600


def hash_password(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=4)).decode()


def check_password(pw, h):
    return bcrypt.checkpw(pw.encode(), h.encode())


def valid_email(e):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e or ""))


def strong_password(p):
    return bool(p) and len(p) >= 8 and any(c.isdigit() for c in p) and any(not c.isalnum() for c in p)


def new_session(user_id):
    token = secrets.token_urlsafe(24)
    db = get_db()
    db.execute("INSERT INTO sessions VALUES(?,?,?)", (token, user_id, time.time() + SESSION_TTL))
    db.commit()
    return token


def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            auth = request.headers.get("Authorization", "")
            token = auth[7:] if auth.startswith("Bearer ") else ""
            row = get_db().execute(
                "SELECT u.*, s.expires FROM sessions s JOIN users u ON u.user_id=s.user_id WHERE s.token=?",
                (token,)).fetchone()
            if row is None or row["expires"] < time.time():
                return jsonify(error="Authentication required"), 401
            if role and row["role"] != role:
                return jsonify(error="Forbidden"), 403
            g.user = row
            g.token = token
            return fn(*a, **kw)
        return wrapper
    return deco
