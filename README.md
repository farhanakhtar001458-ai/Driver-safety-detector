# SafeWay AI — Driving Safety Management SaaS

A complete, production-oriented driving-safety platform: live GPS tracking, explainable driver scoring,
AI risk triage, incident workflow, predictive maintenance, reporting, and a grounded AI coaching assistant.

Built as a full-stack reference implementation: **FastAPI + Next.js + SQLAlchemy + scikit-learn**, with
**62 backend tests**, **27 frontend tests**, a **67-check API smoke test**, Alembic migrations, Docker and
nginx configuration, and 18 documentation deliverables.

> **Honesty notice.** This build ships with a clearly-labelled simulated telemetry feed so the product can
> be evaluated without hardware. Nothing in this repository claims to predict or prevent accidents. Risk
> scores are triage priorities for human review. See [docs/18-limitations-and-honesty.md](docs/18-limitations-and-honesty.md).

---

## 1. What's inside

| Area | Highlights |
| --- | --- |
| **Dashboard** | 10 KPIs, live fleet map (WebSocket + polling fallback), trend, severity mix, leaderboard, vehicle health |
| **Vehicles** | CRUD, validated registration/VIN, status lifecycle, driver assignment, health, trips, events |
| **Drivers** | Profiles with encrypted PII, licence expiry, score breakdown and trend, coaching reports |
| **Live tracking** | Real-time positions, trails, geofences, roster, recent high-severity events |
| **Behaviour** | Speeding / harsh braking / acceleration / cornering / duration, patterns, configurable thresholds |
| **Risk** | Rule + gradient-boosted model with indicators, explanation, confidence, limitations, model card |
| **Incidents** | State machine (investigate → verify → resolve / false alert), notes, evidence, audit |
| **Maintenance** | Diagnostics, alerts, service schedule, records, component failure prediction |
| **Reports** | 9 report types, PDF/CSV, filters, authenticated downloads, stored parameters |
| **Notifications** | 8 types, in-app/email/SMS routing, priorities, quiet hours, read state |
| **AI assistant** | Grounded coaching chat; LLM when a key is configured, transparent local mode otherwise |
| **Road safety** | Illustrative hotspots vs live expiring hazards, hazard reporting, route risk check, labelled weather |
| **Settings** | Organisation, team with role ceilings, security, audit log |
| **Billing** | Four published plans, trials, limits enforced on write, invoice history |

Five roles: `super_admin`, `org_admin`, `fleet_manager`, `safety_officer`, `driver`.

## 2. Quickstart (local)

Requires Python 3.11+ and Node 20+.

```bash
# 1. Backend
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
cd backend && ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 2. Frontend (new terminal)
cd frontend && npm install
cp .env.local.example .env.local
npm run dev
```

Open **http://localhost:3000** and create an organisation account. API docs are at
**http://localhost:8000/api/docs**.

Demo accounts and telemetry are disabled by default. For an isolated local demo only,
set `DEMO_MODE=true`, `SEED_DEMO_DATA=true`, and `SIMULATOR_ENABLED=true` in
`backend/.env` before starting the backend. Never enable these settings for real users.
Disabling seeding does not remove accounts already present in a database.

## 3. Docker

```bash
docker compose up --build                      # local stack → http://localhost:8080
docker compose --profile postgres up -d        # with PostgreSQL + Redis
docker compose --profile postgres run --rm backend-migrate
```

nginx fronts both services so the browser only ever talks to one origin, including the WebSocket at
`/api/v1/ws/fleet`.

## 4. Configuration

Copy `backend/.env.example` → `backend/.env`. The important keys:

| Key | Purpose |
| --- | --- |
| `SECRET_KEY` | JWT signing secret (set a long random value) |
| `FIELD_ENCRYPTION_KEY` | Fernet key for PII at rest (required in production) |
| `DATABASE_URL` | SQLite default, `postgresql+psycopg://…` for production |
| `REDIS_URL` | Optional; enables multi-instance WebSocket fan-out |
| `DEMO_MODE`, `SEED_DEMO_DATA`, `SIMULATOR_ENABLED` | Set all to `false` for a real deployment |
| `LLM_API_KEY` | Server-side only; empty = local assistant mode |
| `WEATHER_API_KEY` | Empty = labelled simulated weather sample |
| `SMTP_*`, `SMS_*` | Required for real notification delivery |

The frontend uses `NEXT_PUBLIC_API_BASE` (default `/api/v1`) and a server-side `API_PROXY_URL` for
rewrites. No secret ever reaches the browser bundle.

## 5. Database and migrations

```bash
cd backend
../.venv/bin/alembic upgrade head      # apply all revisions
../.venv/bin/alembic current           # show applied revision
../.venv/bin/alembic check             # verify models match the schema
```

The initial revision creates all 30 tables. Verified: upgrade on an empty database, `alembic check`
clean, downgrade to base, re-upgrade.

## 6. Testing and verification

```bash
make test          # backend (62) + frontend (27)
make smoke         # 67 API contract checks against a running backend
make lint          # frontend type-check
make build         # production frontend build (20 routes)
```

Individually:

```bash
cd backend && ../.venv/bin/python -m pytest -q          # 62 passed
cd frontend && npm run test                             # 27 passed
cd frontend && npx tsc --noEmit                         # clean
cd frontend && npm run build                            # 20 routes
.venv/bin/python scripts/smoke_api.py --base-url http://127.0.0.1:8000
```

## 7. Architecture at a glance

```
Browser (Next.js 14 · TypeScript · Tailwind · Recharts · Leaflet)
   │  same-origin HTTPS
   ▼
nginx  ── /            → frontend:3000
        ── /api/*       → backend:8000
        ── /api/v1/ws/* → backend:8000 (WebSocket upgrade)
   │
   ▼
FastAPI (20 domain routers · RBAC · tenant scoping · audit)
   ├── rules engine → driving events
   ├── scoring service → 0-100 score + confidence
   ├── risk model (HistGradientBoosting) → triage + explanation
   ├── notifications · reports · billing · maintenance
   └── WebSocket hub + telemetry simulator
   │
   ▼
PostgreSQL / SQLite   ·   Redis (optional)   ·   report files
```

Detailed diagrams and trade-offs: [docs/03-architecture.md](docs/03-architecture.md).

## 8. Documentation

All 18 deliverables are indexed in [docs/README.md](docs/README.md). Start with:

- [02 — Product requirements](docs/02-product-requirements.md)
- [06 — AI, scoring and risk](docs/06-ai-scoring-and-risk.md) — how scores and risk levels actually work
- [09 — Testing strategy](docs/09-testing-strategy.md) — what is and is not covered
- [12 — Implementation phases](docs/12-implementation-phases.md) — 15-phase build log with status
- [18 — Limitations and honesty](docs/18-limitations-and-honesty.md) — read this before deploying

## 9. Status

| | |
| --- | --- |
| Backend tests | 62 passing |
| Frontend tests | 27 passing |
| API smoke checks | 67 passing |
| Page contract checks | 401 passing |
| API surface | 109 paths / 132 operations |
| Database | 30 tables, Alembic-managed |
| Frontend routes | 16 pages + 404 + error boundary |
| Containers | Dockerfiles, compose, nginx (build unverified — no Docker daemon in the build environment) |

**Not done / not verified:** payment processing, MFA/SSO, camera pipeline, real email/SMS delivery,
PostgreSQL and Redis execution, Docker build, browser E2E tests, load testing, LLM output evaluation.
Full list with reasoning: [docs/18-limitations-and-honesty.md](docs/18-limitations-and-honesty.md).

## 10. License

Inherits the repository's existing `LICENSE`.
