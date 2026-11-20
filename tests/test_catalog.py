"""Catalog module tests (UT_09-UT_16, IT_02, ST_02)."""


def titles(r):
    return [b["title"] for b in r.get_json()["books"]]


def test_UT_09_list_all_books(client):
    bs = client.get("/api/books").get_json()["books"]
    assert len(bs) == 10 and all({"title", "author", "price"} <= set(b) for b in bs)


def test_UT_10_search_title_match(client):
    assert "Clean Code" in titles(client.get("/api/books?q=clean"))
    assert "Harper Lee" in [b["author"] for b in client.get("/api/books?q=HARPER").get_json()["books"]]


def test_UT_11_search_no_match(client):
    d = client.get("/api/books?q=zzzzqq").get_json()
    assert d["books"] == [] and d["message"] == "No books found"


def test_UT_12_filter_genre(client):
    bs = client.get("/api/books?genre=Fiction").get_json()["books"]
    assert bs and {b["genre"] for b in bs} == {"Fiction"}


def test_UT_13_filter_price_range(client):
    bs = client.get("/api/books?min=200&max=500").get_json()["books"]
    assert bs and all(200 <= b["price"] <= 500 for b in bs)


def test_UT_14_combined_filters(client):
    bs = client.get("/api/books?genre=Fiction&min=200&max=300").get_json()["books"]
    assert {b["title"] for b in bs} == {"To Kill a Mockingbird", "1984"}


def test_filter_invalid_range(client):
    assert client.get("/api/books?min=500&max=100").status_code == 400
    assert client.get("/api/books?min=abc").status_code == 400
    assert client.get("/api/books?min=300").status_code == 200


def test_UT_15_review_valid(client, cust):
    r = client.post("/api/books/1/reviews", json={"rating": 4, "comment": "Great read"}, headers=cust)
    assert r.status_code == 201
    d = client.get("/api/books/1").get_json()
    assert d["average_rating"] == 4 and d["reviews"][0]["comment"] == "Great read"


def test_UT_16_review_invalid_rating(client, cust):
    for bad in (7, 0, "5", None):
        r = client.post("/api/books/1/reviews", json={"rating": bad}, headers=cust)
        assert r.status_code == 400 and r.get_json()["error"] == "Rating must be between 1 and 5"
    assert client.get("/api/books/1").get_json()["reviews"] == []


def test_review_requires_login_and_existing_book(client, cust):
    assert client.post("/api/books/1/reviews", json={"rating": 3}).status_code == 401
    assert client.post("/api/books/999/reviews", json={"rating": 3}, headers=cust).status_code == 404


def test_book_not_found(client):
    assert client.get("/api/books/999").status_code == 404


def test_IT_02_details_reflect_admin_edit(client, admin):
    client.put("/api/admin/books/3", json={"price": 399}, headers=admin)
    assert client.get("/api/books/3").get_json()["price"] == 399


def test_ST_02_search_open_review(client, cust):
    bid = client.get("/api/books?q=clean").get_json()["books"][0]["book_id"]
    assert client.get(f"/api/books/{bid}").get_json()["in_stock"] is True
    client.post(f"/api/books/{bid}/reviews", json={"rating": 5, "comment": "Superb"}, headers=cust)
    client.post(f"/api/books/{bid}/reviews", json={"rating": 4}, headers=cust)
    d = client.get(f"/api/books/{bid}").get_json()
    assert d["average_rating"] == 4.5 and len(d["reviews"]) == 2
