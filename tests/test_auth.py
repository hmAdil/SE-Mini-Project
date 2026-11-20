"""Authentication module tests (UT_01-UT_08, IT_01, ST_01) plus extra negative paths."""
import sqlite3

from app.auth import RESET_OUTBOX
from conftest import login


def reg(client, **kw):
    d = {"name": "Ravi", "email": "ravi@test.com", "password": "Pass@1234"}
    d.update(kw)
    return client.post("/api/auth/register", json=d)


def test_UT_01_register_valid(client):
    r = reg(client, name="New", email="new@test.com")
    assert r.status_code == 201 and r.get_json()["message"] == "Account created"


def test_UT_02_register_duplicate_email(client):
    r = reg(client, email="asha@test.com")
    assert r.status_code == 409 and r.get_json()["error"] == "Email already registered"


def test_UT_03_register_weak_password(client):
    for pw in ("123", "password", "Password1", ""):
        r = reg(client, password=pw)
        assert r.status_code == 400
        assert "at least 8 characters" in r.get_json()["error"]


def test_UT_04_register_invalid_email(client):
    r = reg(client, email="ravi@test")
    assert r.status_code == 400 and r.get_json()["error"] == "Enter a valid email address"


def test_UT_04b_register_missing_name(client):
    assert reg(client, name="").status_code == 400


def test_UT_05_login_valid(client):
    r = client.post("/api/auth/login", json={"email": "asha@test.com", "password": "Pass@1234"})
    assert r.status_code == 200 and r.get_json()["token"] and r.get_json()["role"] == "customer"


def test_UT_06_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"email": "asha@test.com", "password": "wrong123"})
    assert r.status_code == 401 and r.get_json()["error"] == "Invalid email or password"
    r2 = client.post("/api/auth/login", json={"email": "nobody@test.com", "password": "x"})
    assert r2.get_json()["error"] == "Invalid email or password"  # same message, no user enumeration


def test_UT_07_password_stored_hashed(client, tmp_path):
    path = client.application.config["DATABASE"]
    h = sqlite3.connect(path).execute("SELECT password_hash FROM users WHERE email='asha@test.com'").fetchone()[0]
    assert h != "Pass@1234" and h.startswith("$2")


def test_UT_08_password_reset(client):
    RESET_OUTBOX.clear()
    r = client.post("/api/auth/reset", json={"email": "asha@test.com"})
    assert r.status_code == 200 and RESET_OUTBOX == ["asha@test.com"]
    client.post("/api/auth/reset", json={"email": "ghost@test.com"})  # neutral message, no email
    assert RESET_OUTBOX == ["asha@test.com"]


def test_IT_01_customer_cannot_open_admin_route(client, cust):
    r = client.get("/api/admin/reports/sales", headers=cust)
    assert r.status_code == 403 and "total_revenue" not in r.get_json()


def test_protected_route_requires_token(client):
    assert client.get("/api/users/me").status_code == 401
    assert client.get("/api/users/me", headers={"Authorization": "Bearer bogus"}).status_code == 401


def test_expired_session_rejected(client, cust):
    sqlite3.connect(client.application.config["DATABASE"]).execute("UPDATE sessions SET expires=0").connection.commit()
    assert client.get("/api/users/me", headers=cust).status_code == 401


def test_logout_ends_session(client, cust):
    assert client.post("/api/auth/logout", headers=cust).status_code == 200
    assert client.get("/api/users/me", headers=cust).status_code == 401


def test_profile_empty_name_rejected(client, cust):
    assert client.put("/api/users/me", json={"name": "  "}, headers=cust).status_code == 400


def test_ST_01_register_login_profile_logout(client):
    assert reg(client).status_code == 201
    h = login(client, "ravi@test.com")
    assert client.put("/api/users/me", json={"address": "12 MG Road, Bengaluru"}, headers=h).status_code == 200
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    h2 = login(client, "ravi@test.com")
    assert client.get("/api/users/me", headers=h2).get_json()["address"] == "12 MG Road, Bengaluru"
