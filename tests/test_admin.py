"""Admin and Payments module tests (UT_24-UT_30, IT_05, IT_06, ST_04)."""
import pytest

from conftest import GOOD_CARD, BAD_CARD, login

NEW = {"title": "Refactoring 2", "author": "Martin Fowler", "genre": "Technology",
       "isbn": "9780000000001", "price": 350, "stock": 20}


def order(client, h, bid=3, qty=1, card=GOOD_CARD):
    client.post("/api/cart", json={"book_id": bid, "quantity": qty}, headers=h)
    return client.post("/api/orders", json={"card": card}, headers=h)


def test_UT_24_add_book(client, admin):
    r = client.post("/api/admin/books", json=NEW, headers=admin)
    assert r.status_code == 201
    assert "Refactoring 2" in [b["title"] for b in client.get("/api/books").get_json()["books"]]


def test_UT_25_duplicate_isbn(client, admin):
    client.post("/api/admin/books", json=NEW, headers=admin)
    r = client.post("/api/admin/books", json=NEW, headers=admin)
    assert r.status_code == 409 and r.get_json()["error"] == "ISBN already exists"
    assert len(client.get("/api/books").get_json()["books"]) == 11


def test_UT_26_negative_price(client, admin):
    r = client.post("/api/admin/books", json={**NEW, "price": -50}, headers=admin)
    assert r.status_code == 400 and r.get_json()["error"] == "Price must be positive"


@pytest.mark.parametrize("patch,msg", [({"stock": -1}, "Stock cannot be negative"),
                                       ({"title": ""}, "title is required"),
                                       ({"price": None}, "Price must be positive")])
def test_add_book_validation(client, admin, patch, msg):
    d = {**NEW, **patch}
    r = client.post("/api/admin/books", json=d, headers=admin)
    assert r.status_code == 400 and r.get_json()["error"] == msg


def test_add_book_missing_price_stock(client, admin):
    d = {k: v for k, v in NEW.items() if k not in ("price", "stock")}
    assert client.post("/api/admin/books", json=d, headers=admin).status_code == 400


def test_UT_27_delete_book(client, admin):
    assert client.delete("/api/admin/books/9", headers=admin).status_code == 200
    assert client.get("/api/books/9").status_code == 404
    assert client.delete("/api/admin/books/9", headers=admin).status_code == 404


def test_edit_book_validation(client, admin):
    assert client.put("/api/admin/books/1", json={"price": -1}, headers=admin).status_code == 400
    assert client.put("/api/admin/books/999", json={"price": 5}, headers=admin).status_code == 404
    assert client.put("/api/admin/books/1", json={"stock": 50, "title": "Clean Code 2"}, headers=admin).status_code == 200
    assert client.get("/api/books/1").get_json()["title"] == "Clean Code 2"


def test_UT_28_update_order_status(client, cust, admin):
    oid = order(client, cust).get_json()["order_id"]
    r = client.put(f"/api/admin/orders/{oid}/status", json={"status": "Shipped"}, headers=admin)
    assert r.status_code == 200 and r.get_json()["status"] == "Shipped"


def test_order_status_invalid_transition(client, cust, admin):
    oid = order(client, cust).get_json()["order_id"]
    r = client.put(f"/api/admin/orders/{oid}/status", json={"status": "Delivered"}, headers=admin)
    assert r.status_code == 400
    assert client.put("/api/admin/orders/999/status", json={"status": "Shipped"}, headers=admin).status_code == 404


def test_IT_05_customer_sees_admin_status(client, cust, admin):
    oid = order(client, cust).get_json()["order_id"]
    client.put(f"/api/admin/orders/{oid}/status", json={"status": "Shipped"}, headers=admin)
    assert client.get("/api/orders", headers=cust).get_json()["orders"][0]["status"] == "Shipped"


def test_UT_29_payment_success(client, cust):
    d = order(client, cust).get_json()
    assert d["status"] == "Confirmed" and d["txn_ref"].startswith("TXN-")


def test_UT_30_payment_declined(client, cust):
    r = order(client, cust, card=BAD_CARD)
    assert r.status_code == 402 and r.get_json()["status"] == "Pending" and "Payment failed" in r.get_json()["error"]
    assert client.get("/api/orders", headers=cust).get_json()["orders"][0]["status"] == "Pending"


def test_payment_malformed_card(client, cust):
    assert order(client, cust, card="1234").status_code == 402
    assert order(client, cust, card=None).status_code == 402


def test_IT_06_low_stock_alert(client, cust, admin):
    client.put("/api/admin/books/3", json={"stock": 6}, headers=admin)
    assert 3 not in [b["book_id"] for b in client.get("/api/admin/low-stock", headers=admin).get_json()["books"]]
    order(client, cust, bid=3, qty=2)
    low = client.get("/api/admin/low-stock", headers=admin).get_json()["books"]
    assert {"book_id": 3, "title": "Refactoring", "stock": 4} in low


def test_ST_04_sales_report(client, admin):
    for i, price in enumerate((300, 450, 250)):
        bid = client.post("/api/admin/books", json={**NEW, "isbn": f"97800000{i}", "price": price, "stock": 10},
                          headers=admin).get_json()["book_id"]
        client.post("/api/auth/register", json={"name": f"U{i}", "email": f"u{i}@t.com", "password": "Pass@1234"})
        h = login(client, f"u{i}@t.com")
        order(client, h, bid=bid)
    rep = client.get("/api/admin/reports/sales", headers=admin).get_json()
    assert rep["total_revenue"] == 1000 and len(rep["top_books"]) == 3
    empty = client.get("/api/admin/reports/sales?from=2000-01-01&to=2000-12-31", headers=admin).get_json()
    assert empty["total_revenue"] == 0 and empty["top_books"] == []


def test_admin_routes_need_admin(client, cust):
    for method, url in (("post", "/api/admin/books"), ("get", "/api/admin/low-stock"),
                        ("delete", "/api/admin/books/1"), ("put", "/api/admin/orders/1/status")):
        assert getattr(client, method)(url, headers=cust).status_code == 403
        assert getattr(client, method)(url).status_code == 401


def test_index_page_served(client):
    r = client.get("/")
    assert r.status_code == 200 and b"Online Bookstore" in r.data
    r.close()
