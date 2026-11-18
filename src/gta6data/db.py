"""SQLite storage. Keep it dead simple: JSON blobs per dataset + indexed lookups."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .models import Location, Mission, PricePoint, Vehicle

DEFAULT_DB = Path("data/gta6.sqlite3")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    dataset TEXT NOT NULL,          -- 'vehicles' | 'locations' | 'missions' | 'prices'
    id       TEXT NOT NULL,
    data     TEXT NOT NULL,         -- full model JSON
    updated_at TEXT NOT NULL,
    PRIMARY KEY (dataset, id)
);
CREATE INDEX IF NOT EXISTS idx_records_dataset ON records(dataset);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def upsert(conn: sqlite3.Connection, dataset: str, items: list[BaseModel]) -> int:
    """Insert or replace records by (dataset, id). Returns number of records written."""
    written = 0
    with conn:
        for item in items:
            record_id = getattr(item, "id", None)
            if record_id is None:
                raise ValueError(f"{type(item).__name__} requires an 'id' field")
            payload = item.model_dump(mode="json")
            conn.execute(
                "INSERT INTO records (dataset, id, data, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(dataset, id) DO UPDATE SET data=excluded.data, "
                "updated_at=excluded.updated_at",
                (dataset, record_id, json.dumps(payload), payload.get("updated_at")),
            )
            written += 1
    return written


def export_json(conn: sqlite3.Connection, dataset: str, path: Path) -> int:
    """Write `dataset` to `path` as a JSON array sorted by id (committed state
    of truth: per-dataset JSON files, diffable and mergeable in git)."""
    records = list_dataset(conn, dataset)  # already ordered by id
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2) + "\n")
    return len(records)


def import_json(conn: sqlite3.Connection, path: Path, dataset: str) -> int:
    """Read a JSON array from `path`, validate every record against the
    dataset model in DATASETS, and upsert it. Returns records written."""
    model = DATASETS.get(dataset)
    if model is None:
        raise ValueError(f"unknown dataset '{dataset}'")
    records = json.loads(Path(path).read_text())
    if not isinstance(records, list):
        raise ValueError(f"{path}: expected a JSON array of '{dataset}' records")
    items = [model.model_validate(record) for record in records]
    return upsert(conn, dataset, items)


def list_dataset(conn: sqlite3.Connection, dataset: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT data FROM records WHERE dataset = ? ORDER BY id", (dataset,)
    ).fetchall()
    return [json.loads(r["data"]) for r in rows]


def get_record(conn: sqlite3.Connection, dataset: str, record_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT data FROM records WHERE dataset = ? AND id = ?", (dataset, record_id)
    ).fetchone()
    return json.loads(row["data"]) if row else None


DATASETS: dict[str, type[BaseModel]] = {
    "vehicles": Vehicle,
    "locations": Location,
    "missions": Mission,
    "prices": PricePoint,
}
