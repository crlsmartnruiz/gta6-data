"""Read-only public API. Serves whatever the scrapers have collected."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from . import db

app = FastAPI(
    title="gta6-data API",
    version="0.1.0",
    description=(
        "Community-run, structured GTA VI data. Free and open. "
        "Not affiliated with Rockstar Games or Take-Two Interactive."
    ),
)


def _conn():
    return db.connect(Path(__import__("os").environ.get("GTA6_DB", db.DEFAULT_DB)))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/{dataset}")
def list_records(dataset: str, limit: int = Query(default=500, le=5000)):
    model = db.DATASETS.get(dataset)
    if model is None:
        raise HTTPException(status_code=404, detail=f"unknown dataset '{dataset}'")
    records = db.list_dataset(_conn(), dataset)
    return {"dataset": dataset, "count": len(records), "records": records[:limit]}


@app.get("/api/v1/{dataset}/{record_id}")
def get_record(dataset: str, record_id: str):
    if dataset not in db.DATASETS:
        raise HTTPException(status_code=404, detail=f"unknown dataset '{dataset}'")
    record = db.get_record(_conn(), dataset, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"no record '{record_id}' in '{dataset}'")
    return record
