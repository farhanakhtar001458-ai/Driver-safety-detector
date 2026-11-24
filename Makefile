# SafeWay AI - common tasks.
#
# Requirements: Python 3.11+, Node 20+ (or the .venv created below).
# Use `make help` to list targets.

SHELL := /bin/bash
PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
VENV ?= .venv

.DEFAULT_GOAL := help
.PHONY: help setup backend frontend dev test test-backend test-frontend lint build migrate seed smoke contracts docker clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup: ## Create the Python venv and install backend dependencies
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt
	cd frontend && npm install

backend: ## Start the FastAPI backend on :8000 (SQLite + demo seed)
	cd backend && ../$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

frontend: ## Start the Next.js dev server on :3000
	cd frontend && npm run dev

dev: ## Start backend and frontend together (two terminals recommended)
	@echo "Run 'make backend' and 'make frontend' in separate terminals."

test: test-backend test-frontend ## Run every automated test

test-backend: ## Run the pytest suite (60 tests)
	cd backend && ../$(PYTHON) -m pytest -q

test-frontend: ## Run the vitest suite
	cd frontend && npm run test

lint: ## Type-check the frontend
	cd frontend && npx tsc --noEmit

build: ## Production build of the frontend
	cd frontend && npm run build

migrate: ## Apply database migrations (uses DATABASE_URL from backend/.env)
	cd backend && ../$(VENV)/bin/alembic upgrade head

migrate-new: ## Autogenerate a migration after model changes (review before committing)
	cd backend && ../$(VENV)/bin/alembic revision --autogenerate -m "$(m)"

seed: ## Re-create the demo database (destructive: deletes the SQLite file)
	@echo "This deletes data/safeway.db and reseeds the demo organisation. Continue? [y/N]" ; read ans ; [ "$$ans" = "y" ] || exit 1
	rm -f data/safeway.db
	cd backend && ../$(PYTHON) -c "from app.db.init_db import init_db; init_db()"

API_URL ?= http://127.0.0.1:8000

smoke: ## Run the API smoke test against a running backend
	$(PYTHON) scripts/smoke_api.py --base-url $(API_URL)

contracts: ## Verify every page's data contract against a running backend
	$(PYTHON) scripts/verify_page_contracts.py --base-url $(API_URL)

docker: ## Build and start the full stack on http://localhost:8080
	docker compose up --build

clean: ## Remove build artefacts and local databases
	rm -rf frontend/.next frontend/tsconfig.tsbuildinfo data/*.db backend/data/*.db
	find . -type d -name "__pycache__" -not -path "./.venv/*" -not -path "./frontend/node_modules/*" -exec rm -rf {} +
