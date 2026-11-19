"""Tests for the vehicles-intel scraper (gta6intel.com) — no network access.

Fixtures are trimmed copies of real pages saved during launch-week probing
(see tests/fixtures/). All tests run offline against those files.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from gta6data import db
from gta6data.models import Vehicle
from gta6data.scrapers.vehicles_intel import (
    POLITE_DELAY,
    VehiclesIntelScraper,
    parse_detail,
    parse_facts,
    parse_listing,
)

FIXTURES = Path(__file__).parent / "fixtures"
LISTING_HTML = (FIXTURES / "intel-vehicles-listing.html").read_text(encoding="utf-8")
DETAIL_HTML = (FIXTURES / "intel-vehicle-blimp.html").read_text(encoding="utf-8")

# Minimal "last page" listing: same ItemList shape, no load-more link.
LAST_PAGE_HTML = (
    '<script type="application/ld+json">'
    '{"@context":"https://schema.org","@type":"ItemList","name":"Vehicles",'
    '"numberOfItems":0,"itemListElement":[]}'
    "</script>"
)


@pytest.fixture()
def scraper() -> VehiclesIntelScraper:
    return VehiclesIntelScraper()


def test_parse_listing_fixture_urls_ordered() -> None:
    urls, next_url = parse_listing(LISTING_HTML)
    # Page 1 of the live site carries 24 entries (numberOfItems=321 across pages).
    assert len(urls) == 24
    assert urls[0] == "https://gta6intel.com/vehicles/blimp"
    assert urls[-1] == "https://gta6intel.com/vehicles/amloco-ge-genesis"
    # Sorted by JSON-LD position: blimp (1) before freight-train (2).
    assert urls.index("https://gta6intel.com/vehicles/blimp") < urls.index(
        "https://gta6intel.com/vehicles/freight-train"
    )
    assert next_url == "https://gta6intel.com/vehicles?page=2"


def test_parse_listing_last_page_has_no_next() -> None:
    urls, next_url = parse_listing(LAST_PAGE_HTML)
    assert urls == []
    assert next_url is None


def test_parse_detail_fixture_vehicle_fields() -> None:
    vehicle = parse_detail(DETAIL_HTML)
    assert vehicle is not None
    assert vehicle.id == "blimp"
    assert vehicle.name == "Blimp"
    # The Class fact is "Plane" — the "Returning" fact-pill must be stripped.
    assert vehicle.vehicle_class == "Plane"
    assert "Returning" not in (vehicle.vehicle_class or "")
    # Manufacturer is shown as "Not known yet" on the real page (no dl fact).
    assert vehicle.manufacturer is None
    assert vehicle.source == "https://gta6intel.com/vehicles/blimp"


def test_parse_facts_excludes_pill_text() -> None:
    facts = parse_facts(DETAIL_HTML)
    assert facts["Class"] == "Plane"
    assert facts["Real-life inspiration"] == "Goodyear Aerospace GZ-20"
    assert all("Returning" not in v for v in facts.values())


def test_parse_price_defensive_formats() -> None:
    """Only digit-bearing Price facts become ints; prose stays None."""
    from gta6data.scrapers.vehicles_intel import parse_price

    assert parse_price("$1,250,000") == 1250000
    assert parse_price("1,250,000") == 1250000
    assert parse_price("1250000") == 1250000
    assert parse_price("Not purchasable") is None
    assert parse_price("TBA") is None


def test_parse_detail_without_price_fact_keeps_price_none() -> None:
    vehicle = parse_detail(DETAIL_HTML)
    assert vehicle is not None
    assert vehicle.price is None  # blimp fixture carries no Price fact


def test_parse_detail_maps_price_fact_when_present() -> None:
    detail_with_price = DETAIL_HTML.replace(
        '<div class="fact">',
        '<div class="fact"><dt>Price</dt><dd>$1,250,000</dd></div>'
        '<div class="fact">',
        1,
    )
    vehicle = parse_detail(detail_with_price)
    assert vehicle is not None
    assert vehicle.price == 1250000


def test_parse_abc_contract_returns_list() -> None:
    scraper = VehiclesIntelScraper()
    result = scraper.parse(DETAIL_HTML)
    assert len(result) == 1
    assert isinstance(result[0], Vehicle)
    assert scraper.parse("<html><body>garbage</body></html>") == []


def test_run_end_to_end_offline(
    scraper: VehiclesIntelScraper, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full run() flow: listing pagination + details, entirely from fixtures."""

    def fake_fetch(url: str | None = None, **_: object) -> str:
        target = url or scraper.source_url or ""
        if target and "?page=" in target:
            return LAST_PAGE_HTML
        if target and target.rstrip("/").endswith("/vehicles"):
            return LISTING_HTML
        # Rebrand the blimp fixture per requested slug so ids stay unique.
        slug = target.rstrip("/").rsplit("/", 1)[-1]
        return DETAIL_HTML.replace("vehicles/blimp", f"vehicles/{slug}")

    monkeypatch.setattr(scraper, "fetch", fake_fetch)
    conn = db.connect(tmp_path / "test.sqlite3")
    written = scraper.run(conn)
    assert written == 24
    records = db.list_dataset(conn, "vehicles")
    assert len(records) == 24
    blimp = next(r for r in records if r["id"] == "blimp")
    assert blimp["name"] == "Blimp"
    assert blimp["vehicle_class"] == "Plane"
    assert blimp["source"] == "https://gta6intel.com/vehicles/blimp"


def test_politeness_delay_between_requests(
    scraper: VehiclesIntelScraper,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every extra request is separated by the 0.75s polite sleep."""
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

    def fake_fetch(url: str | None = None, **_: object) -> str:
        target = url or scraper.source_url or ""
        if target and "?page=" in target:
            return LAST_PAGE_HTML
        if target and target.rstrip("/").endswith("/vehicles"):
            return LISTING_HTML
        return DETAIL_HTML

    monkeypatch.setattr(scraper, "fetch", fake_fetch)
    scraper.run(db.connect(tmp_path / "test.sqlite3"))
    # 1 listing page (+ sleep before page 2) + 24 details (sleep before all but first).
    assert sleeps.count(POLITE_DELAY) == 1 + 23
    assert all(0 < s <= 1 for s in sleeps)  # max politeness delay is 1s
    assert not sleeps or all(s != 0 for s in sleeps if s not in (POLITE_DELAY,))
