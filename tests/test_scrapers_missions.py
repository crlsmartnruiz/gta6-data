"""Tests for the missions-intel scraper (gta6intel.com) — no network access.

Fixtures are trimmed copies of real pages saved during launch-day probing
(Nov 19, 2026; see tests/fixtures/). All tests run offline against those files.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from gta6data import db
from gta6data.models import Mission
from gta6data.scrapers.missions_intel import (
    POLITE_DELAY,
    MissionsIntelScraper,
    parse_detail,
    parse_facts,
    parse_listing,
)

FIXTURES = Path(__file__).parent / "fixtures"
LISTING_HTML = (FIXTURES / "intel-missions-listing.html").read_text(encoding="utf-8")
DETAIL_HTML = (FIXTURES / "intel-mission-prologue.html").read_text(encoding="utf-8")

# Minimal "last page" listing: same ItemList shape, no load-more link.
LAST_PAGE_HTML = (
    '<script type="application/ld+json">'
    '{"@context":"https://schema.org","@type":"ItemList","name":"Missions",'
    '"numberOfItems":0,"itemListElement":[]}'
    "</script>"
)


@pytest.fixture()
def scraper() -> MissionsIntelScraper:
    return MissionsIntelScraper()


def test_parse_listing_fixture_urls_ordered() -> None:
    urls, next_url = parse_listing(LISTING_HTML)
    # Page 1 of the live site carries 24 entries (numberOfItems=137 across pages).
    assert len(urls) == 24
    assert urls[0] == "https://gta6intel.com/missions/prologue"
    # Sorted by JSON-LD position: prologue before gone-fishing.
    assert urls.index("https://gta6intel.com/missions/prologue") < urls.index(
        "https://gta6intel.com/missions/gone-fishing"
    )
    assert next_url == "https://gta6intel.com/missions?page=2"


def test_parse_listing_last_page_has_no_next() -> None:
    urls, next_url = parse_listing(LAST_PAGE_HTML)
    assert urls == []
    assert next_url is None


def test_parse_detail_fixture_mission_fields() -> None:
    mission = parse_detail(DETAIL_HTML)
    assert mission is not None
    assert mission.id == "prologue"
    assert mission.name == "Prologue"
    assert mission.notes and "Leonida Penitentiary" in mission.notes
    # Launch day: no Kind/Reward facts published yet — they stay None, never guessed.
    assert mission.kind is None
    assert mission.reward is None
    assert mission.prereq == []
    assert mission.source == "https://gta6intel.com/missions/prologue"


def test_parse_detail_maps_kind_and_reward_when_present() -> None:
    """When contributors fill in Kind/Reward facts, they map onto the model."""
    detail_with_facts = DETAIL_HTML.replace(
        '<div class="fact">',
        '<div class="fact"><dt>Kind</dt><dd>story</dd></div>'
        '<div class="fact"><dt>Reward</dt><dd>$500</dd></div>'
        '<div class="fact">',
        1,
    )
    mission = parse_detail(detail_with_facts)
    assert mission is not None
    assert mission.kind == "story"
    assert mission.reward == "$500"


def test_parse_facts_extracts_terms() -> None:
    facts = parse_facts(DETAIL_HTML)
    assert facts.get("Mission") == "1"


def test_parse_abc_contract_returns_list() -> None:
    scraper = MissionsIntelScraper()
    result = scraper.parse(DETAIL_HTML)
    assert len(result) == 1
    assert isinstance(result[0], Mission)
    assert scraper.parse("<html><body>garbage</body></html>") == []


def test_run_end_to_end_offline(
    scraper: MissionsIntelScraper, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full run() flow: listing pagination + details, entirely from fixtures."""

    def fake_fetch(url: str | None = None, **_: object) -> str:
        target = url or scraper.source_url or ""
        if target and "?page=" in target:
            return LAST_PAGE_HTML
        if target and target.rstrip("/").endswith("/missions"):
            return LISTING_HTML
        # Rebrand the prologue fixture per requested slug so ids stay unique.
        slug = target.rstrip("/").rsplit("/", 1)[-1]
        return DETAIL_HTML.replace("missions/prologue", f"missions/{slug}")

    monkeypatch.setattr(scraper, "fetch", fake_fetch)
    conn = db.connect(tmp_path / "test.sqlite3")
    written = scraper.run(conn)
    assert written == 24
    records = db.list_dataset(conn, "missions")
    assert len(records) == 24
    prologue = next(r for r in records if r["id"] == "prologue")
    assert prologue["name"] == "Prologue"
    assert prologue["source"] == "https://gta6intel.com/missions/prologue"
    # Storage contract: every record round-trips through the Mission model.
    for record in records:
        Mission.model_validate(record)


def test_politeness_delay_between_requests(
    scraper: MissionsIntelScraper,
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
        if target and target.rstrip("/").endswith("/missions"):
            return LISTING_HTML
        return DETAIL_HTML

    monkeypatch.setattr(scraper, "fetch", fake_fetch)
    scraper.run(db.connect(tmp_path / "test.sqlite3"))
    # 1 listing page (+ sleep before page 2) + 24 details (sleep before all but first).
    assert sleeps.count(POLITE_DELAY) == 1 + 23
    assert all(0 < s <= 1 for s in sleeps)  # max politeness delay is 1s
