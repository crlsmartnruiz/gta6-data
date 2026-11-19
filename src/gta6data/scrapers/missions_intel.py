"""Real scraper for gta6intel.com — GTA 6 fan mission database (137 missions).

Source structure (probed Nov 19, 2026 — launch day):
- Listing https://gta6intel.com/missions: HTML with an application/ld+json
  ItemList block (numberOfItems=137; each page carries up to 24
  itemListElement entries) and a `data-load-more` div linking the next page
  (?page=N). As with /locations, the last page keeps a stale load-more
  pointing at an empty ?page=N+1, so pagination stops when a page yields no
  entries.
- Detail https://gta6intel.com/missions/<slug>: HTML with an ld+json @graph
  containing a `Thing` node (name/description/url) plus a facts `<dl>`
  ("Mission" -> chapter/order number, "Kind" -> kind when present,
  "Reward" -> reward when present). The order number has no model field and
  is discarded; prereq has no structured source and stays empty.

Launch-day reality: rewards/kinds are still being filled in by contributors.
Records are written with whatever is structured on the page; fields with no
payload stay None. The scraper re-runs are cheap and will pick up enriched
facts on later refreshes.

REGISTRY wiring (done in src/gta6data/scrapers/__init__.py):
    from .missions_intel import MissionsIntelScraper
    # add MissionsIntelScraper to the REGISTRY tuple
"""

from __future__ import annotations

import html
import json
import logging
import re
import time
from typing import Any

from pydantic import BaseModel

from ..models import Mission
from . import Scraper

log = logging.getLogger(__name__)

POLITE_DELAY = 0.75  # seconds between listing/detail requests (max 1s)
MAX_PAGES = 100  # safety cap against infinite pagination loops

_LDJSON_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)
_FACT_RE = re.compile(
    r'<div class="fact">\s*<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>', re.S
)
_LOAD_MORE_RE = re.compile(
    r'<div class="load-more" data-load-more>.*?href="([^"]+)"', re.S
)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(raw: str) -> str:
    return " ".join(html.unescape(_TAG_RE.sub("", raw)).split())


def _ldjson_nodes(raw: str) -> list[dict[str, Any]]:
    """All JSON objects found in ld+json script blocks (top-level or @graph)."""
    nodes: list[dict[str, Any]] = []
    for match in _LDJSON_RE.finditer(raw):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            log.warning("missions-intel: skipping unparseable ld+json block")
            continue
        for node in data.get("@graph", [data] if isinstance(data, dict) else []):
            if isinstance(node, dict):
                nodes.append(node)
    return nodes


def parse_listing(raw: str) -> tuple[list[str], str | None]:
    """Parse a listing page into (detail_urls_in_position_order, next_page_url)."""
    urls: list[str] = []
    for node in _ldjson_nodes(raw):
        if node.get("@type") != "ItemList":
            continue
        elements = sorted(node.get("itemListElement", []), key=lambda e: e.get("position", 0))
        urls = [e["url"] for e in elements if isinstance(e, dict) and e.get("url")]
    next_url = None
    match = _LOAD_MORE_RE.search(raw)
    if match:
        next_url = html.unescape(match.group(1))
    return urls, next_url


def parse_facts(raw: str) -> dict[str, str]:
    """Extract the detail page facts <dl> as {term: definition}."""
    facts: dict[str, str] = {}
    for match in _FACT_RE.finditer(raw):
        term = _clean_text(match.group(1))
        definition = _clean_text(match.group(2))
        if term and definition:
            facts[term] = definition
    return facts


def parse_detail(raw: str) -> Mission | None:
    """Parse a mission detail page into a Mission (None when no Thing node)."""
    thing = next(
        (n for n in _ldjson_nodes(raw) if n.get("@type") == "Thing" and n.get("url")),
        None,
    )
    if thing is None:
        return None
    url: str = thing["url"]
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    facts = parse_facts(raw)
    return Mission(
        id=slug,
        name=thing.get("name", slug),
        kind=facts.get("Kind"),
        reward=facts.get("Reward"),
        notes=thing.get("description"),
        source=url,
    )


class MissionsIntelScraper(Scraper):
    """Scrape the full mission catalog from gta6intel.com."""

    name = "missions-intel"
    dataset = "missions"
    source_url = "https://gta6intel.com/missions"

    def parse(self, raw: str) -> list[BaseModel]:
        """Parse a single detail page (base-class contract; run() drives flow)."""
        mission = parse_detail(raw)
        return [mission] if mission else []

    def run(self, conn=None) -> int:
        from .. import db  # local import: avoid name shadowing at module scope

        conn = conn or db.connect()
        missions: dict[str, Mission] = {}

        url = self.source_url
        detail_urls: list[str] = []
        for _ in range(MAX_PAGES):
            raw = self.fetch(url)
            page_urls, next_url = parse_listing(raw)
            detail_urls.extend(page_urls)
            if not next_url or not page_urls:
                break  # empty page or no next link: last page reached
            time.sleep(POLITE_DELAY)
            url = next_url
        else:
            log.warning("missions-intel: pagination cap (%d pages) reached", MAX_PAGES)

        for i, detail_url in enumerate(detail_urls):
            if i:
                time.sleep(POLITE_DELAY)
            mission = parse_detail(self.fetch(detail_url))
            if mission is not None:
                missions[mission.id] = mission

        items: list[BaseModel] = list(missions.values())
        written = db.upsert(conn, self.dataset, items)
        log.info("%s: wrote %d records to %s", self.name, written, self.dataset)
        return written
