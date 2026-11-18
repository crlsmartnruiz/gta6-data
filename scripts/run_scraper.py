"""CLI: run one scraper or all of them. Usage:

    python -m scripts.run_scraper --list
    python -m scripts.run_scraper --name vehicles-stub
    python -m scripts.run_scraper --all
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gta6data import db  # noqa: E402
from gta6data.scrapers import REGISTRY  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="list registered scrapers")
    group.add_argument("--name", help="run one scraper")
    group.add_argument("--all", action="store_true", help="run every scraper")
    args = parser.parse_args()

    if args.list:
        for name, cls in sorted(REGISTRY.items()):
            print(f"{name:20s} dataset={cls.dataset:10s} source={cls.source_url or 'TODO'}")
        return 0

    names = list(REGISTRY) if args.all else [args.name]
    failed = []
    # Scrape into a throwaway SQLite DB in TMPDIR. The committed state of
    # truth is the per-dataset JSON exported below — never a binary DB file.
    with tempfile.TemporaryDirectory(prefix="gta6-scrape-") as tmp:
        conn = db.connect(Path(tmp) / "scrape.sqlite3")
        try:
            for name in names:
                cls = REGISTRY.get(name)
                if cls is None:
                    print(f"unknown scraper: {name}", file=sys.stderr)
                    return 2
                try:
                    written = cls().run(conn)
                    print(f"{name}: wrote {written} records")
                except (RuntimeError, ValueError) as exc:
                    logging.error("%s failed: %s", name, exc)
                    failed.append(name)
            data_dir = Path("data")
            data_dir.mkdir(parents=True, exist_ok=True)
            for dataset in db.DATASETS:
                out = data_dir / f"{dataset}.json"
                count = db.export_json(conn, dataset, out)
                print(f"{dataset}: exported {count} records -> {out}")
        finally:
            conn.close()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
