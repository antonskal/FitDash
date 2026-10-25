# FitDash

Local-first Garmin Connect dashboard. Syncs health and workout telemetry into SQLite (WAL), then visualizes it as a Grafana-dark, high-density React dashboard — including a GitHub-style 52-week activity heatmap and a monthly habit matrix.

Tokens stay in `./.garmin_tokens`. The database lives in `./data/fitdash.db`. Nothing is sent anywhere except Garmin Connect.

## Stack

- **Backend:** Python 3.11+ / FastAPI, `garminconnect` + `garth`, `fitparse`, SQLite
- **Frontend:** React 18 + TypeScript + Vite + Tailwind + ECharts + Leaflet

## Run

```bash
# API (from repo root)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python run.py

# UI (second terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. On first launch, sign in to Garmin (MFA supported). Choose a lookback window (default 90 days, up to 3 years). Later launches — and **Sync Now** — only fetch from the watermark through today.

### Offline demo (no Garmin account)

```bash
cd backend && source .venv/bin/activate
python run.py --demo            # seed 365 days if the DB is empty
python run.py --demo --reset    # wipe and regenerate
```

Then start the Vite UI as above.

Production-style single process: `cd frontend && npm run build`, then `python run.py` serves `frontend/dist` from `:8000`.

## Sync model

| Mode | When | Window |
| --- | --- | --- |
| Initial | `sync_metadata` is empty | Configurable lookback (default 90d) |
| Delta | Subsequent launches / Sync Now | `last_synced_date − 1 day` → today |
| Manual | Custom range in the API | Caller-specified |

Writes are idempotent upserts. Activity `.fit` files download only for new `activity_id`s. Progress streams over SSE at `/api/sync/events`.

## Environment

All settings use the `FITDASH_` prefix (see `backend/app/config.py`), e.g. `FITDASH_LOOKBACK_DAYS=365`.
