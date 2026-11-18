from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from gta6data import api, db
from gta6data.models import Vehicle


@pytest.fixture()
def client(tmp_path: Path, monkeypatch) -> Iterator[TestClient]:
    db_path = tmp_path / "api.sqlite3"
    conn = db.connect(db_path)
    db.upsert(conn, "vehicles", [Vehicle(id="alpha", name="Alpha", source="test")])
    conn.close()
    monkeypatch.setenv("GTA6_DB", str(db_path))
    # Context manager form so the app lifespan runs: it opens the shared
    # connection at startup (reading GTA6_DB) and closes it on shutdown.
    with TestClient(api.app) as c:
        yield c


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


def test_requests_share_one_connection(client: TestClient, monkeypatch):
    # The lifespan-opened connection in app.state is reused across requests:
    # spy on db.list_dataset and compare the conn each request received.
    seen: list[object] = []
    original = db.list_dataset
    monkeypatch.setattr(
        db, "list_dataset", lambda conn, dataset: seen.append(conn) or original(conn, dataset)
    )
    for _ in range(2):
        r = client.get("/api/v1/vehicles")
        assert r.status_code == 200
    assert len(seen) == 2
    assert seen[0] is seen[1] is api.app.state.conn
