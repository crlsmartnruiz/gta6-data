import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gta6data import api, db
from gta6data.models import Vehicle


@pytest.fixture()
def client(tmp_path: Path, monkeypatch) -> TestClient:
    conn = db.connect(tmp_path / "api.sqlite3")
    db.upsert(conn, "vehicles", [Vehicle(id="alpha", name="Alpha", source="test")])
    conn.close()
    monkeypatch.setenv("GTA6_DB", str(tmp_path / "api.sqlite3"))
    # re-import to pick up env var on fresh connection
    monkeypatch.setattr(api, "_conn", lambda: db.connect(Path(os.environ["GTA6_DB"])))
    return TestClient(api.app)


def test_health(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}


def test_list_vehicles(client: TestClient):
    r = client.get("/api/v1/vehicles")
    body = r.json()
    assert r.status_code == 200
    assert body["count"] == 1
    assert body["records"][0]["id"] == "alpha"


def test_get_record(client: TestClient):
    r = client.get("/api/v1/vehicles/alpha")
    assert r.status_code == 200
    assert r.json()["name"] == "Alpha"


def test_unknown_dataset_is_404(client: TestClient):
    assert client.get("/api/v1/spaceships").status_code == 404


def test_missing_record_is_404(client: TestClient):
    assert client.get("/api/v1/vehicles/does-not-exist").status_code == 404
