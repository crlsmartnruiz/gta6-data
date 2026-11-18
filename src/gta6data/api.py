"""Read-only public API. Serves whatever the scrapers have collected."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request

from . import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One shared sqlite connection for the whole process: opened once at
    # startup, closed at shutdown. Async endpoints keep every access on the
    # event-loop thread, so no check_same_thread handling is needed.
    app.state.conn = db.connect(Path(os.environ.get("GTA6_DB", db.DEFAULT_DB)))
    yield
    app.state.conn.close()


app = FastAPI(
    title="gta6-data API",
    version="0.1.0",
    description=(
        "Community-run, structured GTA VI data. Free and open. "
        "Not affiliated with Rockstar Games or Take-Two Interactive."
    ),
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/{dataset}")
async def list_records(
    request: Request, dataset: str, limit: int = Query(default=500, le=5000)
):
    model = db.DATASETS.get(dataset)
    if model is None:
        raise HTTPException(status_code=404, detail=f"unknown dataset '{dataset}'")
    records = db.list_dataset(request.app.state.conn, dataset)
    return {"dataset": dataset, "count": len(records), "records": records[:limit]}


@app.get("/api/v1/{dataset}/{record_id}")
async def get_record(request: Request, dataset: str, record_id: str):
    if dataset not in db.DATASETS:
        raise HTTPException(status_code=404, detail=f"unknown dataset '{dataset}'")
    record = db.get_record(request.app.state.conn, dataset, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"no record '{record_id}' in '{dataset}'")
    return record
