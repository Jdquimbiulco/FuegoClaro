.PHONY: install backend frontend test build ingest ml-dataset ml-train ml-predict docker-build docker-up docker-down docker-logs docker-test docker-ingest

install:
	cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
	cd frontend && npm install

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	backend/.venv/bin/python -m pytest -q

build:
	cd frontend && npm run build

ingest:
	backend/.venv/bin/python scripts/ingest_firms.py --start 2022-01-01 --end 2026-11-12 --keep-raw

ml-dataset:
	backend/.venv/bin/python scripts/build_fire_risk_dataset.py --start 2022-01-01 --end 2026-11-12

ml-train:
	backend/.venv/bin/python scripts/train_fire_risk_model.py

ml-predict:
	backend/.venv/bin/python scripts/predict_fire_risk.py --lat $(LAT) --lon $(LON) --date $(DATE) --window-days $(or $(WINDOW),7)

docker-build:
	docker compose build

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-test:
	docker compose run --rm backend python -m pytest -q

docker-ingest:
	docker compose run --rm backend python scripts/ingest_firms.py --start 2022-01-01 --end 2026-11-12 --keep-raw
	docker compose restart backend
