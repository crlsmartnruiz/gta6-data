import json
import sqlite3
from pathlib import Path

import pytest

from gta6data import db
from gta6data.models import Vehicle


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = db.connect(tmp_path / "test.sqlite3")
    yield c
    c.close()


def test_upsert_and_list(conn: sqlite3.Connection):
    items = [
        Vehicle(id="alpha", name="Alpha", source="test"),
        Vehicle(id="beta", name="Beta", source="test"),
    ]
    assert db.upsert(conn, "vehicles", items) == 2
    records = db.list_dataset(conn, "vehicles")
    assert [r["id"] for r in records] == ["alpha", "beta"]


def test_upsert_is_idempotent_and_overwrites(conn: sqlite3.Connection):
    db.upsert(conn, "vehicles", [Vehicle(id="alpha", name="Alpha", source="test")])
    db.upsert(conn, "vehicles", [Vehicle(id="alpha", name="Alpha v2", source="test")])
    records = db.list_dataset(conn, "vehicles")
    assert len(records) == 1
    assert records[0]["name"] == "Alpha v2"


def test_record_without_id_rejected(conn: sqlite3.Connection):
    with pytest.raises(ValueError):
        db.upsert(conn, "vehicles", [Vehicle.model_construct(name="NoId", source="s")])
