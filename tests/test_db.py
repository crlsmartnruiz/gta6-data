import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from gta6data import db
from gta6data.models import Location, Mission, PricePoint, Vehicle


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


def test_upsert_pricepoint_roundtrip(conn: sqlite3.Connection):
    # Regression: PricePoint originally lacked `id`, which made db.upsert raise
    # ValueError and the 'prices' dataset crash on first write.
    pp = PricePoint(
        id="sprunk-can",
        item_id="sprunk-can",
        price=2,
        currency="GTA$",
        source="unit-test",
    )
    assert db.upsert(conn, "prices", [pp]) == 1
    records = db.list_dataset(conn, "prices")
    assert len(records) == 1
    record = records[0]
    assert record["id"] == "sprunk-can"
    assert record["item_id"] == "sprunk-can"
    assert record["price"] == 2
    assert record["currency"] == "GTA$"
    restored = PricePoint.model_validate(record)
    assert restored.id == "sprunk-can"
    assert restored.observed_at.tzinfo is not None


def _sample_items() -> dict[str, list]:
    return {
        "vehicles": [
            Vehicle(id="zeta", name="Zeta", source="t"),
            Vehicle(id="alpha", name="Alpha", source="t"),
        ],
        "locations": [Location(id="loc-1", name="Lobby", source="t")],
        "missions": [Mission(id="m-1", name="Heist", source="t")],
        "prices": [PricePoint(id="p-1", item_id="sprunk-can", price=2, source="t")],
    }


def test_export_import_roundtrip_all_datasets(tmp_path: Path):
    src = db.connect(tmp_path / "src.sqlite3")
    dst = db.connect(tmp_path / "dst.sqlite3")
    try:
        sample = _sample_items()
        for dataset, items in sample.items():
            assert db.upsert(src, dataset, items) == len(items)
            out = tmp_path / f"{dataset}.json"
            assert db.export_json(src, dataset, out) == len(items)
            # Exported file is a JSON array sorted by id
            exported = json.loads(out.read_text())
            ids = [r["id"] for r in exported]
            assert ids == sorted(ids)
            assert len(exported) == len(items)
            # Round-trip: import into a fresh DB yields identical records
            assert db.import_json(dst, out, dataset) == len(items)
            assert db.list_dataset(dst, dataset) == db.list_dataset(src, dataset)
    finally:
        src.close()
        dst.close()


def test_import_json_rejects_invalid_record(tmp_path: Path):
    conn = db.connect(tmp_path / "bad.sqlite3")
    try:
        bad = tmp_path / "vehicles.json"
        bad.write_text(json.dumps([{"id": "x"}]))  # missing name/source
        with pytest.raises(ValidationError):
            db.import_json(conn, bad, "vehicles")
        assert db.list_dataset(conn, "vehicles") == []
        with pytest.raises(ValueError, match="unknown dataset"):
            db.import_json(conn, tmp_path / "whatever.json", "spaceships")
    finally:
        conn.close()
