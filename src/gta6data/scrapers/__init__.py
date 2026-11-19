"""Scraper framework. Each scraper: fetch a source, parse to models, store in SQLite.

Launch-week sources are deliberately stubbed: real URLs and parsing rules can
only be written once the game ships and community sources stabilize (Nov 19+).
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel

from .. import db
from ..models import Location, Mission, Vehicle

log = logging.getLogger(__name__)

USER_AGENT = "gta6-data/0.1 (+https://github.com/crlsmartnruiz/gta6-data; community data project)"
RETRY_DELAYS = (1, 2, 5, 10)


class Scraper(ABC):
    name: str
    dataset: str  # key in db.DATASETS
    source_url: str | None = None  # set per scraper; None until launch week pins it

    def fetch(self, url: str | None = None, **kwargs: Any) -> str:
        """GET with retries + polite backoff. Returns response text."""
        target = url or self.source_url
        if not target:
            raise ValueError(f"{self.name}: no source URL configured yet")
        headers = {"User-Agent": USER_AGENT}
        last_exc: Exception | None = None
        for delay in (0, *RETRY_DELAYS):
            if delay:
                time.sleep(delay)
            try:
                resp = httpx.get(target, headers=headers, timeout=30, follow_redirects=True,
                                 **kwargs)
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPError as exc:
                log.warning("%s: fetch failed (%s), retrying...", self.name, exc)
                last_exc = exc
        raise RuntimeError(f"{self.name}: all fetch attempts failed") from last_exc

    @abstractmethod
    def parse(self, raw: str) -> list[BaseModel]:
        """Turn raw response into domain models. Implemented per scraper."""

    def run(self, conn=None) -> int:
        raw = self.fetch()
        items = self.parse(raw)
        conn = conn or db.connect()
        written = db.upsert(conn, self.dataset, items)
        log.info("%s: wrote %d records to %s", self.name, written, self.dataset)
        return written


# vehicles-stub / locations-stub retired: real scrapers (gta6intel.com) live in
# vehicles_intel.py / locations_intel.py.


# missions-stub retired: real scraper (gta6intel.com) lives in missions_intel.py.

# Imported last (but before REGISTRY): the real scrapers do
# `from . import Scraper`, which requires the base class to exist when their
# module initializes (avoids a cycle).
from .locations_intel import LocationsIntelScraper  # noqa: E402
from .missions_intel import MissionsIntelScraper  # noqa: E402
from .vehicles_intel import VehiclesIntelScraper  # noqa: E402

REGISTRY: dict[str, type[Scraper]] = {
    s.name: s for s in (
        VehiclesIntelScraper,
        LocationsIntelScraper,
        MissionsIntelScraper,
    )
}
