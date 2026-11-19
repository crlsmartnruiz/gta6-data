"""Tests for scripts/run_scraper.py export behavior — no network access.

Regression guard for the data-wipe bug found on Nov 19, 2026: a per-scraper
run (`--name X`) must export ONLY the datasets it touched. The old behavior
exported every dataset from a throwaway DB that only contained X's records,
clobbering the other datasets' committed JSON with empty arrays on every
hourly data-refresh (locations.json was silently wiped to 0 records).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from gta6data import db
from gta6data.models import Mission
from gta6data.scrapers import Scraper

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import run_scraper  # noqa: E402


class FakeMissionsScraper(Scraper):
    name = "fake-missions"
    dataset = "missions"
    source_url = "https://example.test/missions"

    def parse(self, raw: str) -> list:
        return []

    def run(self, conn=None) -> int:  # bypass fetch entirely
        mission = Mission(id="prologue", name="Prologue",
                          source="https://example.test/missions")
        written = db.upsert(conn or db.connect(), self.dataset, [mission])
        return written


class ExplodingScraper(Scraper):
    name = "fake-exploding"
    dataset = "vehicles"
    source_url = "https://example.test/vehicles"

    def parse(self, raw: str) -> list:
        return []

    def run(self, conn=None) -> int:
        raise RuntimeError("simulated source outage")


@pytest.fixture()
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run the CLI in a scratch cwd with a sentinel vehicles.json on disk."""
    monkeypatch.chdir(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    sentinel = [{"id": "sentinel-vehicle", "name": "Sentinel"}]
    (data / "vehicles.json").write_text(json.dumps(sentinel), encoding="utf-8")
    monkeypatch.setattr(
        run_scraper,
        "REGISTRY",
        {"fake-missions": FakeMissionsScraper, "fake-exploding": ExplodingScraper},
    )
    return tmp_path


def _run_cli(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["run_scraper.py", *args])
    return run_scraper.main()


def test_single_scraper_run_exports_only_its_dataset(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exit_code = _run_cli(monkeypatch, "--name", "fake-missions")
    assert exit_code == 0
    missions = json.loads((workspace / "data" / "missions.json").read_text())
    assert [m["id"] for m in missions] == ["prologue"]
    # The other dataset file must keep its previous content, untouched.
    vehicles = json.loads((workspace / "data" / "vehicles.json").read_text())
    assert [v["id"] for v in vehicles] == ["sentinel-vehicle"]


def test_failed_scraper_exports_nothing_and_keeps_previous_data(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exit_code = _run_cli(monkeypatch, "--name", "fake-exploding")
    assert exit_code == 1
    vehicles = json.loads((workspace / "data" / "vehicles.json").read_text())
    # No clobbering with an empty array: the file stays exactly as it was.
    assert [v["id"] for v in vehicles] == ["sentinel-vehicle"]


def test_list_subcommand_still_works(
    workspace: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    assert _run_cli(monkeypatch, "--list") == 0
    out = capsys.readouterr().out
    assert "fake-missions" in out
