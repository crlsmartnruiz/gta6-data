"""Frontend/API parity guards — every dataset the API serves must be visible.

Regression guards for the launch-day incident (Nov 19, 2026): the SPA
fetched and rendered only vehicles and locations, so missions (137 real
records live in the API) were invisible on gta6data.xyz, and the per-view
count chain left every newer dataset's badge stuck at "0".
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from gta6data import db
from gta6data.scrapers import REGISTRY

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_JS = (REPO_ROOT / "web" / "app.js").read_text(encoding="utf-8")
INDEX_HTML = (REPO_ROOT / "web" / "index.html").read_text(encoding="utf-8")


def _js_views() -> list[str]:
    match = re.search(r"const VIEWS = \[(.*?)\]", APP_JS, re.S)
    assert match, "web/app.js must define a VIEWS array"
    return re.findall(r'"([^"]+)"', match.group(1))


def _js_renderers() -> dict[str, str]:
    match = re.search(r"const ROW_RENDERERS = \{(.*?)\}", APP_JS, re.S)
    assert match, "web/app.js must define a ROW_RENDERERS map"
    return dict(re.findall(r"(\w+):\s*(\w+)", match.group(1)))


def test_js_views_cover_every_api_dataset() -> None:
    """A dataset added to db.DATASETS without a frontend view is invisible."""
    views = _js_views()
    for dataset in db.DATASETS:
        assert dataset in views, (
            f"dataset '{dataset}' is served by the API but has no view in "
            "web/app.js VIEWS — users would never see its records"
        )


def test_load_data_fetches_every_view() -> None:
    """loadData must fetch from VIEWS, not a hardcoded two-dataset list."""
    assert "VIEWS.map(async (ds)" in APP_JS, (
        "web/app.js loadData() must fetch every VIEWS dataset; a hardcoded "
        "fetch list silently drops newer datasets"
    )


def test_counts_are_generic_not_per_dataset_chain() -> None:
    """setCounts must derive counts from state generically."""
    assert "state[el.dataset.count]" in APP_JS, (
        "web/app.js setCounts() must use state[el.dataset.count]; the old "
        "per-dataset if/chain left newer dataset badges stuck at 0"
    )


def test_dataset_with_records_has_a_renderer() -> None:
    """Any dataset whose committed JSON has rows must render rows, not the
    coming-soon placeholder. ROW_RENDERERS maps dataset -> renderer fn."""
    renderers = _js_renderers()
    for dataset in db.DATASETS:
        records = json.loads((REPO_ROOT / "data" / f"{dataset}.json").read_text())
        if records:
            assert dataset in renderers, (
                f"dataset '{dataset}' has {len(records)} committed records "
                f"but no entry in web/app.js ROW_RENDERERS — users would "
                "see the coming-soon placeholder instead of real rows"
            )


def test_every_scraper_dataset_is_a_real_model_dataset() -> None:
    """A scraper wired to a nonexistent/renamed dataset would silently drop
    its records on export (run_scraper exports via REGISTRY[n].dataset)."""
    for name, cls in REGISTRY.items():
        assert cls.dataset in db.DATASETS, (
            f"scraper '{name}' targets dataset '{cls.dataset}' which does "
            "not exist in db.DATASETS"
        )


def test_caddy_routes_health_to_the_api() -> None:
    """/health must reach FastAPI, not try_files -> index.html. The old
    matcher served the SPA HTML for /health, so monitoring saw 200 HTML."""
    caddyfile = (REPO_ROOT / "ansible" / "templates" / "Caddyfile.j2").read_text()
    assert "@api path /api/* /health" in caddyfile, (
        "Caddyfile.j2 @api matcher must include /health so the health "
        "endpoint returns the API's JSON status instead of index.html"
    )


def test_noscript_links_cover_every_api_dataset() -> None:
    for dataset in db.DATASETS:
        assert f"/api/v1/{dataset}" in INDEX_HTML, (
            f"web/index.html noscript fallback must link /api/v1/{dataset}"
        )
