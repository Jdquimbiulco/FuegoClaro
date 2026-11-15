# AGENTS.md

## Project layout
- All runnable code is in `Hackaton/`; the repo root only holds a pointer README and
  a duplicate team plan. Run commands from `Hackaton/`. Canonical docs: `Hackaton/README.md`,
  `Hackaton/GUIA_DE_INICIO.md`, `Hackaton/docs/`.
- Docs, UI copy, and comments are Spanish; keep new text in Spanish.

## Commands (Windows host)
- Venv is `Hackaton/backend/.venv` with Windows layout. The `Makefile` and docs say
  `.venv/bin/...`; here use `backend\.venv\Scripts\python.exe`.
- Tests (from `Hackaton/`): `backend\.venv\Scripts\python.exe -m pytest -q`
  Single test: append `tests/backend/test_api.py` or `-k <name>`.
  `pytest.ini` sets `pythonpath=backend`, `testpaths=tests`, so do not run from the repo root.
- API dev: `cd Hackaton/backend` then `.venv\Scripts\uvicorn app.main:app --reload --port 8000`.
- Frontend (from `Hackaton/frontend`): `npm install` (node_modules is absent), `npm run dev`
  (5173), `npm run lint` (oxlint), `npm run build` (`tsc -b && vite build`). No frontend tests.
- Docker (avoids host quirks): from `Hackaton/`, `docker compose up -d --build`;
  `docker compose run --rm backend python -m pytest -q`. Override ports with
  `BACKEND_PORT` / `FRONTEND_PORT`.
- Known local failure: `test_ml_inference.py::test_train_and_predict_roundtrip` fails here
  because Windows Application Control blocks `pyarrow._csv` (`pyarrow.dataset` unavailable).
  Confirm with `make docker-test`; do not weaken the test.

## Architecture
- Backend: FastAPI routes in `backend/app/api/v1/endpoints/`, pure logic in
  `backend/app/domain/`, config in `core/config.py` (reads `backend/.env`).
- No database. `services/data_store.py` loads `data/processed/detections.csv` + `manifest.json`
  into memory at startup and falls back to `data/samples/` (`mode` = real/sample/empty).
- API errors always use `{"error": {"code", "message", "details"}}`; preserve that contract.
- ETL/ML entrypoints are standalone scripts in `scripts/`, importing `app.*` (needs backend on path).
- Frontend: React 19 + Vite, pages in `src/pages`, URL-synced filters in
  `context/FiltersContext.tsx`, HTTP in `services/api.ts` + `hooks/useApi.ts`.
  Vite dev has no proxy: it calls `http://localhost:8000/api/v1` unless `VITE_API_BASE_URL` is set.
  Only the Docker/Nginx build proxies `/api/v1`.

## Data and domain rules
- A detection ≠ confirmed fire ≠ burned area. Never compare MODIS and VIIRS counts as
  equivalent; keep raw confidence (`confidence_raw` / `confidence_level`) and don't invent scores.
- Local time: UTC-5 continental, UTC-6 Galápagos. BBox: `(-92.5, -5.5, -74.5, 2.0)`.
- `data/processed/detections.csv` and `data/raw/*.csv` are tracked in git despite the guide
  claiming otherwise. Avoid re-ingesting casually; ingestion aborts instead of publishing partial data.
  `data/processed/ml/`, `data/cache/`, and `*.joblib` are gitignored.
- `backend/.env` holds the real FIRMS key. Never print, copy, commit, or expose it to the frontend.
- ML dataset build is resumable via `data/cache/`; offline smoke test:
  `--limit-cells 100 --skip-weather --skip-dem --skip-ndvi`.
