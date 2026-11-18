# gta6-data

Community-run, structured data for GTA VI — served through a **free, open API**.
We compete with wikis on structured data and API access, not on SEO content.

> **Not affiliated with Rockstar Games or Take-Two Interactive.** We store game
> *facts* (names, classes, locations), never copyrighted assets.

## Base URL

```
https://gta6data.xyz
```

Interactive docs: [`https://gta6data.xyz/docs`](https://gta6data.xyz/docs) (OpenAPI/Swagger).

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Service health check |
| GET | `/api/v1/{dataset}?limit=N` | List records. `limit` default 500, max 5000 |
| GET | `/api/v1/{dataset}/{record_id}` | One record by id |

**Datasets:**

| Dataset | Records | Notes |
|---|---|---|
| `vehicles` | 321 | Vehicles seen in trailers/gameplay |
| `locations` | 108 | Cities, landmarks and other map locations |
| `missions` | 0 | Populates during launch week |
| `prices` | 0 | Populates during launch week |

## Quickstart

```bash
# Health check
curl https://gta6data.xyz/health
# {"status":"ok"}

# First 3 vehicles (total count always returned)
curl "https://gta6data.xyz/api/v1/vehicles?limit=3"
# {"dataset":"vehicles","count":321,"records":[ ... ]}

# One vehicle by id
curl https://gta6data.xyz/api/v1/vehicles/55-vapid-stanier

# Unknown datasets and records return 404
curl https://gta6data.xyz/api/v1/spells
# {"detail":"unknown dataset 'spells'"}  (HTTP 404)
```

## Record shape

Every record carries a `source` URL (where the fact came from) and `updated_at`.
Optional fields are `null` until the data exists in-game.

**Vehicle:**

```json
{
  "id": "55-vapid-stanier",
  "name": "'55 Vapid Stanier",
  "manufacturer": "Vapid",
  "vehicle_class": "Sedan",
  "price": null,
  "notes": "A sedan, spotted in Trailer 1.",
  "stats": {},
  "source": "https://gta6intel.com/vehicles/55-vapid-stanier",
  "updated_at": "2026-11-18T16:40:38.710652Z"
}
```

**Location:**

```json
{
  "id": "alligator-creek",
  "name": "Alligator Creek",
  "area": null,
  "kind": "Landmark",
  "lat": null,
  "lon": null,
  "notes": null,
  "source": "https://gta6intel.com/locations/alligator-creek",
  "updated_at": "2026-11-18T16:45:20.946160Z"
}
```

## Data provenance & attribution

Data is scraped hourly from public fan sources — currently
[gta6intel.com](https://gta6intel.com) — and refreshed into this API
automatically. Every record carries its `source` URL so any fact can be
checked against the original page. If you use this API, credit the upstream
sources too.

This project is not affiliated with Rockstar Games or Take-Two Interactive.

## Self-hosting

The API is a small FastAPI service. An Ansible playbook deploys it to a VPS
(systemd + Caddy) — see [`ansible/playbook.yml`](ansible/playbook.yml).

## Contributing

Found an error, or missing data? The datasets live in
[`data/*.json`](data/) — fix or extend the JSON and open a PR. Contributions
welcome under the [MIT license](LICENSE).
