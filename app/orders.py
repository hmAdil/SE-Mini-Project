from flask import Blueprint, request, jsonify, g

from .db import get_db
from .security import login_required
from . import payment

bp = Blueprint("orders", __name__)


def cart_view(uid):
    rows = [dict(r) for r in get_db().execute(
        "SELECT c.cart_item_id,c.book_id,b.title,b.price,c.quantity,b.price*c.quantity AS line_total "
        "FROM cart_items c JOIN books b USING(book_id) WHERE c.user_id=?", (uid,))]
    return {"items": rows, "total": round(sum(r["line_total"] for r in rows), 2)}


@bp.route("/api/cart", methods=["GET", "POST"])
@login_required()
def cart():
    db, uid = get_db(), g.user["user_id"]
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        qty = d.get("quantity", 1)
        b = db.execute("SELECT * FROM books WHERE book_id=?", (d.get("book_id"),)).fetchone()
        if not b:
            return jsonify(error="Book not found"), 404
        if not isinstance(qty, int) or qty < 1:
            return jsonify(error="Quantity must be at least 1"), 400
        existing = db.execute("SELECT * FROM cart_items WHERE user_id=? AND book_id=?",
                              (uid, b["book_id"])).fetchone()
        new_qty = qty + (existing["quantity"] if existing else 0)
        if new_qty > b["stock"]:
            return jsonify(error=f"Only {b['stock']} copies available"), 400
        if existing:
            db.execute("UPDATE cart_items SET quantity=? WHERE cart_item_id=?", (new_qty, existing["cart_item_id"]))
        else:
            db.execute("INSERT INTO cart_items(user_id,book_id,quantity) VALUES(?,?,?)", (uid, b["book_id"], qty))
        db.commit()
    return jsonify(cart_view(uid))


@bp.route("/api/cart/<int:iid>", methods=["PUT", "DELETE"])
@login_required()
def cart_item(iid):
    db, uid = get_db(), g.user["user_id"]
    row = db.execute("SELECT c.*,b.stock FROM cart_items c JOIN books b USING(book_id) "
                     "WHERE cart_item_id=? AND user_id=?", (iid, uid)).fetchone()
    if not row:
        return jsonify(error="Cart item not found"), 404
    if request.method == "DELETE":
        db.execute("DELETE FROM cart_items WHERE cart_item_id=?", (iid,))
    else:
        qty = (request.get_json(silent=True) or {}).get("quantity")
        if not isinstance(qty, int) or qty < 1:
            return jsonify(error="Quantity must be at least 1"), 400
        if qty > row["stock"]:
            return jsonify(error=f"Only {row['stock']} copies available"), 400
        db.execute("UPDATE cart_items SET quantity=? WHERE cart_item_id=?", (qty, iid))
    db.commit()
    return jsonify(cart_view(uid))


@bp.post("/api/orders")
@login_required()
def checkout():
    """Create order, decrement stock and clear cart in one transaction, then charge.
    On payment failure the transaction is rolled back so stock is restored."""
    db, uid = get_db(), g.user["user_id"]
    card = (request.get_json(silent=True) or {}).get("card")
    view = cart_view(uid)
    if not view["items"]:
        return jsonify(error="Your cart is empty"), 400
    for it in view["items"]:
        stock = db.execute("SELECT stock FROM books WHERE book_id=?", (it["book_id"],)).fetchone()["stock"]
        if it["quantity"] > stock:
            return jsonify(error=f"Insufficient stock for {it['title']}"), 400
    ok, ref = payment.gateway.charge(card, view["total"])
    if not ok:
        # nothing was changed: the order is recorded as Pending with a Failed payment
        oid = db.execute("INSERT INTO orders(user_id,total,status) VALUES(?,?,'Pending')",
                         (uid, view["total"])).lastrowid
        db.execute("INSERT INTO payments(order_id,amount,status) VALUES(?,?,'Failed')", (oid, view["total"]))
        db.commit()
        return jsonify(error="Payment failed", order_id=oid, status="Pending"), 402
    oid = db.execute("INSERT INTO orders(user_id,total,status) VALUES(?,?,'Confirmed')",
                     (uid, view["total"])).lastrowid
    for it in view["items"]:
        db.execute("INSERT INTO order_items(order_id,book_id,quantity,unit_price) VALUES(?,?,?,?)",
                   (oid, it["book_id"], it["quantity"], it["price"]))
        db.execute("UPDATE books SET stock=stock-? WHERE book_id=?", (it["quantity"], it["book_id"]))
    db.execute("DELETE FROM cart_items WHERE user_id=?", (uid,))
    db.execute("INSERT INTO payments(order_id,amount,status,txn_ref) VALUES(?,?,'Success',?)",
               (oid, view["total"], ref))
    db.commit()
    return jsonify(order_id=oid, total=view["total"], status="Confirmed", txn_ref=ref), 201


@bp.get("/api/orders")
@login_required()
def history():
    db = get_db()
    out = []
    for o in db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY order_id DESC", (g.user["user_id"],)):
        items = [dict(i) for i in db.execute(
            "SELECT b.title,i.quantity,i.unit_price FROM order_items i LEFT JOIN books b USING(book_id) "
            "WHERE order_id=?", (o["order_id"],))]
        out.append({**dict(o), "items": items})
    return jsonify(orders=out)


@bp.post("/api/orders/<int:oid>/cancel")
@login_required()
def cancel(oid):
    db = get_db()
    o = db.execute("SELECT * FROM orders WHERE order_id=? AND user_id=?", (oid, g.user["user_id"])).fetchone()
    if not o:
        return jsonify(error="Order not found"), 404
    if o["status"] in ("Shipped", "Delivered"):
        return jsonify(error="Shipped orders cannot be cancelled"), 400
    if o["status"] == "Cancelled":
        return jsonify(error="Order already cancelled"), 400
    for i in db.execute("SELECT * FROM order_items WHERE order_id=?", (oid,)).fetchall():
        db.execute("UPDATE books SET stock=stock+? WHERE book_id=?", (i["quantity"], i["book_id"]))
    db.execute("UPDATE orders SET status='Cancelled' WHERE order_id=?", (oid,))
    db.commit()
    return jsonify(message="Order cancelled", status="Cancelled")
