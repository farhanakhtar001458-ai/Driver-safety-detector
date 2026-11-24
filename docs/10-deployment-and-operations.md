# 10 — Deployment and operations

## 1. Local development (what was used for this build)

Requirements: Python 3.11+, Node 20+.

```bash
# 1. Backend
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env        # adjust SECRET_KEY / FIELD_ENCRYPTION_KEY
cd backend && ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 2. Frontend (second terminal)
cd frontend && npm install && cp .env.local.example .env.local
npm run dev                                  # http://localhost:3000
```

The API seeds a demo organisation on first start when `SEED_DEMO_DATA=true`. Interactive docs:
http://localhost:8000/api/docs.

## 2. Configuration

All settings live in `backend/.env` (see `backend/.env.example` for the full annotated list).

| Variable | Default | Production guidance |
| --- | --- | --- |
| `SECRET_KEY` | insecure dev value | 48+ byte random string; rotate on suspicion |
| `FIELD_ENCRYPTION_KEY` | empty (ephemeral) | Required. Generate with `Fernet.generate_key()` |
| `DATABASE_URL` | `sqlite:///./data/safeway.db` | `postgresql+psycopg://user:pass@host:5432/safeway` |
| `REDIS_URL` | empty | `redis://redis:6379/0` for multi-instance |
| `CORS_ORIGINS` | localhost:3000 | The single public origin served by nginx |
| `DEMO_MODE` / `SEED_DEMO_DATA` / `SIMULATOR_ENABLED` | true | **false** in production |
| `LLM_API_KEY` | empty | Server-side only; empty = local assistant mode |
| `WEATHER_API_KEY` | empty | Empty = labelled simulated sample |
| `SMTP_*`, `SMS_*` | empty | Required for real email/SMS delivery |

Frontend: `NEXT_PUBLIC_API_BASE` (default `/api/v1`) and `API_PROXY_URL` (server-side rewrite target).

## 3. Docker

```bash
# Demo stack with SQLite: http://localhost:8080
docker compose up --build

# Production-like stack with PostgreSQL + Redis
docker compose --profile postgres up -d
docker compose --profile postgres run --rm backend-migrate
```

Images:
- `safeway/backend` — `python:3.11-slim`, non-root user, healthcheck on `/api/v1/health`.
- `safeway/frontend` — multi-stage `node:22-alpine`, builds with `API_PROXY_URL`, runs `next start` as non-root.
- `nginx:1.27-alpine` — routes `/` to the frontend, `/api/` to the backend, upgrades `/api/v1/ws/`.

Volumes: `backend-data` (SQLite + generated reports), `postgres-data`, `redis-data`.

### PostgreSQL switch

1. `DATABASE_URL=postgresql+psycopg://safeway:…@db:5432/safeway`
2. `docker compose --profile postgres run --rm backend-migrate` (runs `alembic upgrade head`)
3. Set `SEED_DEMO_DATA=false` for a real deployment.
4. Restart the backend.

## 4. nginx

`nginx/default.conf`:

- `location /api/v1/ws/` — `proxy_set_header Upgrade $http_upgrade`, 1-hour read timeout.
- `location /api/` — proxied with `X-Forwarded-*`, buffering off for report downloads.
- `location /_next/static/` — one-year immutable cache.
- `location /` — frontend, with WebSocket headers for HMR in staging.
- Security headers: `nosniff`, `SAMEORIGIN`, `strict-origin-when-cross-origin`.

Production checklist for the edge:
- Terminate TLS (Let's Encrypt or ACME), add HSTS.
- Add `client_max_body_size` consistent with the API (8 m).
- Add rate limiting at the edge if exposed publicly (`limit_req`).
- Enable access logs with a retention policy.

## 5. Migrations

```bash
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/alembic current
../.venv/bin/alembic check
```

Deployment order: migrate → start new app version → verify `/api/v1/health/ready`. The initial migration
creates all 30 tables and is verified to upgrade, downgrade and re-upgrade cleanly.

## 6. Backups and restore

| Data | Method | Frequency |
| --- | --- | --- |
| PostgreSQL | `pg_dump -Fc safeway` | Daily, plus WAL archiving for point-in-time |
| SQLite (dev/demo) | copy `data/safeway.db` while the API is stopped | On demand |
| Report files | `data/reports/` (or object storage in production) | Weekly |
| Secrets | Secret manager, never in backups of the repo | On rotation |

Restore drill: restore into a scratch database, run `alembic current`, start the API with
`SEED_DEMO_DATA=false`, and confirm `/dashboard` returns 200.

## 7. Observability

- Structured console logs (`app.main`, `app.services.simulator`).
- `/api/v1/health` for liveness, `/health/ready` for readiness (database ping).
- `/health/details` returns version, environment and database driver — useful for deployment verification.
- Errors return a JSON envelope with a `code`, which makes alerting on specific failures possible.

Recommended additions before production: request IDs, metrics endpoint (Prometheus), error tracking
(Sentry), and a log shipper.

## 8. Scaling notes

| Bottleneck | Signal | Action |
| --- | --- | --- |
| Single API process | CPU saturation, p95 latency | Run multiple instances behind nginx; move session checks to Redis |
| WebSocket fan-out | Memory per connection | Set `REDIS_URL`; hub switches to pub/sub |
| Report generation | Slow requests during PDF export | Move to a worker queue and object storage |
| Dashboard aggregation | Slow `/dashboard` at scale | Materialise daily aggregates; add read replicas |
| Model training at boot | ~4 s startup | Persist the model artefact and load it |

## 9. Environments

| Environment | Data | Simulator | LLM | Email/SMS |
| --- | --- | --- | --- | --- |
| Local demo | Seeded SQLite | On | Local mode | Stubs |
| Staging | Anonymised subset | Off | Real key (test) | Provider sandbox |
| Production | Real | Off | Real key | Real provider |

Never point a production build at the demo seed. `DEMO_MODE=false` disables the simulator and the
`simulated` banners remain only where genuinely simulated records exist.
