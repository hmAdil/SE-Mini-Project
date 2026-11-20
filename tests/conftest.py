import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app import create_app  # noqa: E402
from seed import seed  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    path = str(tmp_path / "test.db")
    seed(path)
    app = create_app({"DATABASE": path, "TESTING": True})
    return app.test_client()


def login(client, email="asha@test.com", pw="Pass@1234"):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.get_json()["token"]}


@pytest.fixture()
def cust(client):
    return login(client)


@pytest.fixture()
def admin(client):
    return login(client, "admin@bookstore.com", "Admin@1234")


GOOD_CARD = "4111111111111111"
BAD_CARD = "4000000000000002"
