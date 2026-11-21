import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import seed  # noqa: E402
from app.main import app  # noqa: E402

PW = seed.DEMO_PASSWORD


@pytest.fixture(scope="session")
def client():
    seed.main(reset=True)
    return TestClient(app)


def login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session")
def h(client):
    return {
        "admin": login(client, "admin@srk.demo"),
        "tpo": login(client, "tpo@srk.demo"),
        "esm": login(client, "coord.esm@srk.demo"),
        "cp": login(client, "coord.cp@srk.demo"),
        "it": login(client, "hr@vindhyainfotech.demo"),
        "pharma": login(client, "hr@satnapharma.demo"),
        "student": login(client, "student001@srk.demo"),
    }
