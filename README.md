# gta6-data

Community-run **data layer for GTA VI** (released Nov 19, 2026): structured game data
plus a free public API. Inspired by the [tarkov.dev](https://tarkov.dev) model —
we compete with wikis on *structured data and API access*, not on SEO content.

**Not affiliated with Rockstar Games or Take-Two Interactive.** We store game *facts*
(prices, names, locations), never copyrighted assets.

## Status: pre-launch scaffold

Everything here is scaffolding built **before launch** (Nov 12, 2026). Real sources and
parse rules can only be pinned during launch-week datamining (Nov 19–22). Items marked
`TODO(launch week)` are intentional placeholders.

## Layout

```
src/gta6data/
  models.py     Pydantic models (Vehicle, Location, Mission, PricePoint) — provisional
  db.py         SQLite storage (upsert + list + get per dataset)
  api.py        FastAPI read-only API: /api/v1/{vehicles,locations,missions,prices}
  scrapers/     Scraper base class (retries, polite UA) + stub scrapers
scripts/run_scraper.py   CLI: --list / --name X / --all
tests/         pytest suite (models, db, API)
deploy/k8s.yaml  Homelab stubs: Deployment + PVC + Service + scraper CronJob
ansible/         VPS deployment: playbook (systemd + Caddy + ufw), env-driven inventory
.github/workflows/  ci | data-refresh (scrape → PR → merge) | deploy (Ansible to VPS)
```

## Local usage

```bash
uv sync --all-extras
uv run pytest                        # tests
uv run python scripts/run_scraper.py --list
uv run uvicorn gta6data.api:app --reload
```

The API reads the SQLite db from `GTA6_DB` (default `data/gta6.sqlite3`).

## Launch-week plan (Nov 19–22)

1. **Day 0 (launch night):** identify which community sources publish first
   (wikis, datamine Discords, Reddit megathreads). Pick 1–2 per dataset.
2. **Day 1–2:** pin `source_url` per stub scraper; write real `parse()` rules;
   run the suite; start the CronJob.
3. **Day 3–4:** lock final schemas (vehicles are the first target: price + class data
   shows up immediately in-game); publish API + a minimal landing page.
4. **Later:** GTA Online data (Q1–Q3 2027 est.) — economy tracker becomes the core product.

## Autonomous pipeline

The repo runs itself on GitHub Actions; the VPS only serves the API:

1. **data-refresh** (cron every 6h, manual dispatch): runs scrapers in CI,
   commits `data/gta6.sqlite3` to a branch, opens a PR, squash-merges it.
2. **deploy** (push to main + workflow_run): test gate, then
   `ansible-playbook ansible/playbook.yml` over SSH → git checkout at the
   merged SHA, `uv sync`, restart `gta6-api` (systemd) behind Caddy.
3. **ci**: pytest on every PR and push to main.

Required repo secrets: `VPS_HOST`, `VPS_SSH_KEY` (deploy key private half),
optional `VPS_USER` (default `root`). Optional var `gta6_domain` switches
Caddy to automatic TLS. The scraped SQLite database is versioned in Git.

## Monetization (honest)

Donations + ads on a future landing page. Expected: symbolic at first. This is a
community asset, not a revenue bet.
