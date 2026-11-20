"""Cart and Orders module tests (UT_17-UT_23, IT_03, IT_04, ST_03)."""
from conftest import GOOD_CARD, BAD_CARD


def stock(client, bid):
    return client.get(f"/api/books/{bid}").get_json()["stock"]


def add(client, h, bid, qty=1):
    return client.post("/api/cart", json={"book_id": bid, "quantity": qty}, headers=h)


def pay(client, h, card=GOOD_CARD):
    return client.post("/api/orders", json={"card": card}, headers=h)


def test_UT_17_add_to_cart(client, cust):
    d = add(client, cust, 3).get_json()
    assert len(d["items"]) == 1 and d["total"] == 350


def test_UT_18_add_more_than_stock(client, cust, admin):
    client.put("/api/admin/books/3", json={"stock": 2}, headers=admin)
    r = add(client, cust, 3, 5)
    assert r.status_code == 400 and r.get_json()["error"] == "Only 2 copies available"
    assert client.get("/api/cart", headers=cust).get_json()["items"] == []


def test_UT_19_update_quantity(client, cust):
    iid = add(client, cust, 3).get_json()["items"][0]["cart_item_id"]
    d = client.put(f"/api/cart/{iid}", json={"quantity": 3}, headers=cust).get_json()
    assert d["items"][0]["line_total"] == 1050 and d["total"] == 1050


def test_UT_20_cart_total_multiple(client, cust, admin):
    client.put("/api/admin/books/3", json={"price": 300}, headers=admin)
    client.put("/api/admin/books/5", json={"price": 250}, headers=admin)
    add(client, cust, 3)
    assert add(client, cust, 5).get_json()["total"] == 550


def test_UT_21_remove_item(client, cust):
    iid = add(client, cust, 3).get_json()["items"][0]["cart_item_id"]
    d = client.delete(f"/api/cart/{iid}", headers=cust).get_json()
    assert d["items"] == [] and d["total"] == 0


def test_UT_22_checkout_empty_cart(client, cust):
    r = pay(client, cust)
    assert r.status_code == 400 and r.get_json()["error"] == "Your cart is empty"
    assert client.get("/api/orders", headers=cust).get_json()["orders"] == []


def test_IT_03_order_reduces_stock(client, cust):
    before = stock(client, 3)
    add(client, cust, 3, 2)
    r = pay(client, cust)
    assert r.status_code == 201 and r.get_json()["status"] == "Confirmed"
    assert stock(client, 3) == before - 2
    assert client.get("/api/cart", headers=cust).get_json()["items"] == []


def test_UT_23_cancel_shipped_order(client, cust, admin):
    add(client, cust, 3)
    oid = pay(client, cust).get_json()["order_id"]
    client.put(f"/api/admin/orders/{oid}/status", json={"status": "Shipped"}, headers=admin)
    r = client.post(f"/api/orders/{oid}/cancel", headers=cust)
    assert r.status_code == 400 and r.get_json()["error"] == "Shipped orders cannot be cancelled"
    assert client.get("/api/orders", headers=cust).get_json()["orders"][0]["status"] == "Shipped"


def test_IT_04_cancel_restores_stock(client, cust):
    before = stock(client, 3)
    add(client, cust, 3, 2)
    oid = pay(client, cust).get_json()["order_id"]
    assert stock(client, 3) == before - 2
    assert client.post(f"/api/orders/{oid}/cancel", headers=cust).get_json()["status"] == "Cancelled"
    assert stock(client, 3) == before
    assert client.post(f"/api/orders/{oid}/cancel", headers=cust).status_code == 400  # already cancelled


def test_cart_edge_cases(client, cust):
    assert add(client, cust, 999).status_code == 404
    assert add(client, cust, 3, 0).status_code == 400
    iid = add(client, cust, 3, 2).get_json()["items"][0]["cart_item_id"]
    assert add(client, cust, 3, 1).get_json()["items"][0]["quantity"] == 3  # merges with existing line
    assert client.put(f"/api/cart/{iid}", json={"quantity": 0}, headers=cust).status_code == 400
    assert client.put(f"/api/cart/{iid}", json={"quantity": 999}, headers=cust).status_code == 400
    assert client.put("/api/cart/9999", json={"quantity": 1}, headers=cust).status_code == 404
    assert client.get("/api/cart").status_code == 401


def test_checkout_insufficient_stock(client, cust, admin):
    add(client, cust, 3, 5)
    client.put("/api/admin/books/3", json={"stock": 2}, headers=admin)
    r = pay(client, cust)
    assert r.status_code == 400 and "Insufficient stock" in r.get_json()["error"]


def test_failed_payment_keeps_stock_and_cart(client, cust):
    before = stock(client, 3)
    add(client, cust, 3, 2)
    r = pay(client, cust, BAD_CARD)
    assert r.status_code == 402
    assert stock(client, 3) == before
    assert len(client.get("/api/cart", headers=cust).get_json()["items"]) == 1


def test_cancel_unknown_order(client, cust):
    assert client.post("/api/orders/999/cancel", headers=cust).status_code == 404


def test_ST_03_browse_add_pay_history(client, cust):
    bid = client.get("/api/books?q=sapiens").get_json()["books"][0]["book_id"]
    add(client, cust, bid)
    pay(client, cust)
    o = client.get("/api/orders", headers=cust).get_json()["orders"][0]
    assert o["status"] == "Confirmed" and o["total"] == 499 and o["items"][0]["title"] == "Sapiens"


def test_order_history_newest_first(client, cust):
    for bid in (3, 4):
        add(client, cust, bid)
        pay(client, cust)
    ids = [o["order_id"] for o in client.get("/api/orders", headers=cust).get_json()["orders"]]
    assert ids == sorted(ids, reverse=True) and len(ids) == 2
