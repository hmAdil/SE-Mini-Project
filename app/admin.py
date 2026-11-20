import sqlite3

from flask import Blueprint, request, jsonify

from .db import get_db
from .security import login_required

bp = Blueprint("admin", __name__)
LOW_STOCK = 5
NEXT = {"Pending": "Confirmed", "Confirmed": "Shipped", "Shipped": "Delivered"}


def _validate(d, partial=False):
    if not partial:
        for f in ("title", "author", "genre", "isbn"):
            if not d.get(f):
                return f"{f} is required"
        if "price" not in d or "stock" not in d:
            return "price and stock are required"
    if "price" in d and (not isinstance(d["price"], (int, float)) or d["price"] <= 0):
        return "Price must be positive"
    if "stock" in d and (not isinstance(d["stock"], int) or d["stock"] < 0):
        return "Stock cannot be negative"
    return None


@bp.post("/api/admin/books")
@login_required("admin")
def add_book():
    d = request.get_json(silent=True) or {}
    err = _validate(d)
    if err:
        return jsonify(error=err), 400
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO books(title,author,genre,isbn,price,stock,description) VALUES(?,?,?,?,?,?,?)",
            (d["title"], d["author"], d["genre"], d["isbn"], d["price"], d["stock"], d.get("description", "")))
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(error="ISBN already exists"), 409
    return jsonify(book_id=cur.lastrowid), 201


@bp.route("/api/admin/books/<int:bid>", methods=["PUT", "DELETE"])
@login_required("admin")
def edit_book(bid):
    db = get_db()
    if not db.execute("SELECT 1 FROM books WHERE book_id=?", (bid,)).fetchone():
        return jsonify(error="Book not found"), 404
    if request.method == "DELETE":
        db.execute("DELETE FROM books WHERE book_id=?", (bid,))
        db.commit()
        return jsonify(message="Book deleted")
    d = request.get_json(silent=True) or {}
    err = _validate(d, partial=True)
    if err:
        return jsonify(error=err), 400
    for f in ("title", "author", "genre", "price", "stock", "description"):
        if f in d:
            db.execute(f"UPDATE books SET {f}=? WHERE book_id=?", (d[f], bid))
    db.commit()
    return jsonify(message="Book updated")


@bp.get("/api/admin/low-stock")
@login_required("admin")
def low_stock():
    rows = get_db().execute("SELECT book_id,title,stock FROM books WHERE stock<? ORDER BY stock", (LOW_STOCK,))
    return jsonify(threshold=LOW_STOCK, books=[dict(r) for r in rows])


@bp.put("/api/admin/orders/<int:oid>/status")
@login_required("admin")
def order_status(oid):
    db = get_db()
    o = db.execute("SELECT * FROM orders WHERE order_id=?", (oid,)).fetchone()
    if not o:
        return jsonify(error="Order not found"), 404
    want = (request.get_json(silent=True) or {}).get("status")
    if NEXT.get(o["status"]) != want:
        return jsonify(error=f"Cannot move from {o['status']} to {want}"), 400
    db.execute("UPDATE orders SET status=? WHERE order_id=?", (want, oid))
    db.commit()
    return jsonify(order_id=oid, status=want)


@bp.get("/api/admin/reports/sales")
@login_required("admin")
def sales():
    db = get_db()
    start, end = request.args.get("from", "0000-01-01"), request.args.get("to", "9999-12-31")
    rev = db.execute(
        "SELECT COALESCE(SUM(total),0) FROM orders WHERE status NOT IN ('Cancelled','Pending') "
        "AND date(created_at) BETWEEN ? AND ?", (start, end)).fetchone()[0]
    top = db.execute(
        "SELECT b.title, SUM(i.quantity) AS sold FROM order_items i JOIN orders o USING(order_id) "
        "JOIN books b USING(book_id) WHERE o.status NOT IN ('Cancelled','Pending') "
        "AND date(o.created_at) BETWEEN ? AND ? GROUP BY b.book_id ORDER BY sold DESC LIMIT 5", (start, end))
    return jsonify(total_revenue=rev, top_books=[dict(r) for r in top])
