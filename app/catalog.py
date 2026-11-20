from flask import Blueprint, request, jsonify, g

from .db import get_db
from .security import login_required

bp = Blueprint("catalog", __name__)


@bp.get("/api/books")
def list_books():
    q, genre = request.args.get("q", "").strip(), request.args.get("genre", "").strip()
    try:
        lo = float(request.args["min"]) if request.args.get("min") else None
        hi = float(request.args["max"]) if request.args.get("max") else None
    except ValueError:
        return jsonify(error="Invalid price range"), 400
    if lo is not None and hi is not None and lo > hi:
        return jsonify(error="Invalid price range"), 400
    sql, args = "SELECT * FROM books WHERE 1=1", []
    if q:
        sql += " AND (LOWER(title) LIKE ? OR LOWER(author) LIKE ?)"
        args += [f"%{q.lower()}%"] * 2
    if genre:
        sql += " AND genre=?"
        args.append(genre)
    if lo is not None:
        sql += " AND price>=?"
        args.append(lo)
    if hi is not None:
        sql += " AND price<=?"
        args.append(hi)
    rows = [dict(r) for r in get_db().execute(sql + " ORDER BY book_id", args)]
    return jsonify(books=rows, message="" if rows else "No books found")


@bp.get("/api/books/<int:bid>")
def book(bid):
    db = get_db()
    b = db.execute("SELECT * FROM books WHERE book_id=?", (bid,)).fetchone()
    if not b:
        return jsonify(error="Book not found"), 404
    revs = [dict(r) for r in db.execute(
        "SELECT r.rating,r.comment,u.name FROM reviews r JOIN users u USING(user_id) WHERE book_id=?", (bid,))]
    avg = round(sum(r["rating"] for r in revs) / len(revs), 2) if revs else None
    return jsonify(**dict(b), in_stock=b["stock"] > 0, average_rating=avg, reviews=revs)


@bp.post("/api/books/<int:bid>/reviews")
@login_required()
def review(bid):
    d = request.get_json(silent=True) or {}
    r = d.get("rating")
    if not isinstance(r, int) or not 1 <= r <= 5:
        return jsonify(error="Rating must be between 1 and 5"), 400
    db = get_db()
    if not db.execute("SELECT 1 FROM books WHERE book_id=?", (bid,)).fetchone():
        return jsonify(error="Book not found"), 404
    db.execute("INSERT INTO reviews(book_id,user_id,rating,comment) VALUES(?,?,?,?)",
               (bid, g.user["user_id"], r, d.get("comment", "")))
    db.commit()
    return jsonify(message="Review added"), 201
