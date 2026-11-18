"""Tests for the locations-intel scraper (gta6intel.com) — no network access.

Fixtures are copies of real pages saved during launch-week probing (see
tests/fixtures/): the full 108-entry listing (combined from 5 live pages into
one ItemList) and the Downtown Vice City detail page. All tests run offline
against those files.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from gta6data import db
from gta6data.models import Location
from gta6data.scrapers.locations_intel import (
    POLITE_DELAY,
    LocationsIntelScraper,
    parse_detail,
    parse_facts,
    parse_listing,
)

FIXTURES = Path(__file__).parent / "fixtures"
LISTING_HTML = (FIXTURES / "intel-locations-listing.html").read_text(encoding="utf-8")
DETAIL_HTML = (FIXTURES / "intel-location-downtown.html").read_text(encoding="utf-8")


@pytest.fixture()
def scraper() -> LocationsIntelScraper:
    return LocationsIntelScraper()


def test_parse_listing_fixture_108_urls() -> None:
    urls, next_url = parse_listing(LISTING_HTML)
    assert len(urls) == 108
    assert len(set(urls)) == 108
    assert urls[0] == "https://gta6intel.com/locations/downtown-vice-city"
    assert urls[-1] == "https://gta6intel.com/locations/state-of-gloriana"
    # Sorted by JSON-LD position: downtown (1) before megamundo (2).
    assert urls.index("https://gta6intel.com/locations/downtown-vice-city") < urls.index(
        "https://gta6intel.com/locations/megamundo-building"
    )
    # Fixture combines all pages: no load-more link remains.
    assert next_url is None


def test_parse_detail_fixture_location_fields() -> None:
    location = parse_detail(DETAIL_HTML)
    assert location is not None
    assert location.id == "downtown-vice-city"
    assert location.name == "Downtown Vice City"
    # "Level" fact maps to kind; description (Thing node) maps to notes.
    assert location.kind == "Landmark"
    assert location.notes is not None
    assert location.notes.startswith("Vice City's downtown waterfront")
    # No geo/area data anywhere on the real detail page.
    assert location.area is None
    assert location.lat is None
    assert location.lon is None
    assert location.source == "https://gta6intel.com/locations/downtown-vice-city"


def test_parse_facts_fixture() -> None:
    facts = parse_facts(DETAIL_HTML)
    assert facts["Level"] == "Landmark"
    assert facts["Real-life inspiration"] == "Downtown Miami"


def test_parse_abc_contract_returns_list() -> None:
    scraper = LocationsIntelScraper()
    result = scraper.parse(DETAIL_HTML)
    assert len(result) == 1
    assert isinstance(result[0], Location)
    assert scraper.parse("<html><body>garbage</body></html>") == []


def test_run_end_to_end_offline(
    scraper: LocationsIntelScraper, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full run() flow: listing + all 108 details, entirely from fixtures."""

    def fake_fetch(url: str | None = None, **_: object) -> str:
        target = url or scraper.source_url or ""
        if target and target.rstrip("/").endswith("/locations"):
            return LISTING_HTML
        # Rebrand the downtown fixture per requested slug so ids stay unique.
        slug = target.rstrip("/").rsplit("/", 1)[-1]
        return DETAIL_HTML.replace("locations/downtown-vice-city", f"locations/{slug}")

    monkeypatch.setattr(scraper, "fetch", fake_fetch)
    conn = db.connect(tmp_path / "test.sqlite3")
    written = scraper.run(conn)
    assert written == 108
    records = db.list_dataset(conn, "locations")
    assert len(records) == 108
    downtown = next(r for r in records if r["id"] == "downtown-vice-city")
    assert downtown["name"] == "Downtown Vice City"
    assert downtown["kind"] == "Landmark"
    assert downtown["source"] == "https://gta6intel.com/locations/downtown-vice-city"


def test_politeness_delay_between_requests(
    scraper: LocationsIntelScraper,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every extra request is separated by the 0.75s polite sleep."""
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

    def fake_fetch(url: str | None = None, **_: object) -> str:
        target = url or scraper.source_url or ""
        if target and target.rstrip("/").endswith("/locations"):
            return LISTING_HTML
        return DETAIL_HTML

    monkeypatch.setattr(scraper, "fetch", fake_fetch)
    scraper.run(db.connect(tmp_path / "test.sqlite3"))
    # 1 listing page + 108 details (sleep before all but the first detail).
    assert sleeps.count(POLITE_DELAY) == 107
    assert all(0 < s <= 1 for s in sleeps)  # max politeness delay is 1s
