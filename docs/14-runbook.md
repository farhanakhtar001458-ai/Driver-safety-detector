# 14 — Runbook

Operational procedures for SafeWay AI. Replace placeholders with your environment's values.

## 1. Service inventory

| Service | Port | Health check | Depends on |
| --- | --- | --- | --- |
| nginx | 80/443 (host 8080 in Compose) | `curl -f localhost:8080/` | frontend, backend |
| frontend (Next.js) | 3000 | `curl -f localhost:3000/login` | — |
| backend (FastAPI) | 8000 | `curl -f localhost:8000/api/v1/health` | database, optional Redis |
| PostgreSQL | 5432 | `pg_isready` | — |
| Redis | 6379 | `redis-cli ping` | — |

## 2. Daily checks

```bash
curl -fsS http://localhost:8000/api/v1/health | jq .
curl -fsS http://localhost:8000/api/v1/health/ready | jq .
curl -fsS http://localhost:8000/api/v1/health/details | jq .
```

Then in the UI: Overview KPIs load, live map shows vehicles, notifications badge populates.

## 3. Common incidents

### 3.1 Live map empty / "Polling fallback"
1. `curl -fsS localhost:8000/api/v1/gps/live` — if empty, the simulator is off or no telemetry arrived.
2. Check `DEMO_MODE` / `SIMULATOR_ENABLED`.
3. If WebSocket fails but REST works, check nginx `location /api/v1/ws/` upgrade headers and that no proxy
   buffers WebSocket frames.
4. Restart: `docker compose restart backend`.

### 3.2 Login returns 401 for a valid user
1. Confirm the user exists: `psql -c "select email, is_active from users where email='…'"`.
2. `is_active=false` → reactivate via an org admin or SQL.
3. Password unknown → use `/auth/change-password` with the current password, or set a bcrypt hash directly.
4. Check `SECRET_KEY` has not changed since the token was issued (all tokens invalidate on rotation).

### 3.3 Dashboard 500
1. Read the traceback in the backend logs.
2. Most likely causes: a missing column after a code change (run migrations), or a corrupt JSON cell.
3. `alembic current` vs `alembic heads` will reveal an unmigrated schema.
4. Roll back the deployment if the error started with a release.

### 3.4 Reports fail to generate
1. Check `data/reports/` is writable by the service user.
2. Check disk space (`df -h`).
3. Report generation is synchronous — large ranges can hit the request timeout; reduce the date window.
4. `reports.status` and `reports.error_message` record the failure reason.

### 3.5 WebSocket disconnects every few minutes
1. nginx `proxy_read_timeout` must exceed the idle interval (set to 3600 s).
2. Load balancers often cut idle connections at 60 s — enable ping/pong or reduce the interval.
3. The frontend falls back to polling, so data keeps flowing, but fix the proxy to restore the stream.

### 3.6 Simulator stopped
`DEMO_MODE=false` disables it by design. Re-enable only in a demo environment.

## 4. Deployment procedure

```bash
git pull
cd backend && ../.venv/bin/alembic upgrade head      # 1. migrate
cd ../frontend && npm ci && npm run build            # 2. build web
cd .. && docker compose up -d --build backend frontend nginx
curl -fsS localhost:8000/api/v1/health/ready           # 3. verify
cd . && .venv/bin/python scripts/smoke_api.py         # 4. smoke
```

Rollback: redeploy the previous image tag, then `alembic downgrade -1` **only if** the migration is
backward-compatible. Prefer forward fixes for data migrations.

## 5. Backup and restore

```bash
# Postgres
pg_dump -Fc -h db -U safeway safeway > backup-$(date +%F).dump

# Restore into a scratch database
createdb safeway_restore
pg_restore -d safeway_restore backup-YYYY-MM-DD.dump
DATABASE_URL=postgresql+psycopg://safeway:…@db:5432/safeway_restore \
  alembic current
```

Verify a restore by starting the API against it with `SEED_DEMO_DATA=false` and calling `/dashboard`.

## 6. On-call triage for a safety incident

SafeWay AI does not dispatch emergency services. If a customer reports a real emergency:

1. Confirm they have contacted local emergency services themselves — the platform is not an emergency channel.
2. Do not assert that the platform detected or predicted the event.
3. Preserve the incident record and audit log; do not edit timestamps.
4. Escalate to the accountable safety officer named in the customer's organisation.

## 7. Data subject requests

| Request | Procedure |
| --- | --- |
| Access | Export the driver's scores, events and profile via reporting or SQL; PII is decrypted server-side only |
| Correction | Update via `PATCH /drivers/{id}`; licence/phone re-encrypt automatically |
| Deletion | Deactivate the driver; purge telemetry within the retention policy; keep audit entries (legal obligation) |
| Objection to monitoring | Disable the organisation's monitoring or deactivate the driver record; document the decision |

## 8. Log locations

| Source | Where |
| --- | --- |
| Backend stdout | `docker compose logs -f backend` |
| nginx access/error | `/var/log/nginx/` inside the container, or the platform log driver |
| Application audit | `audit_logs` table (`GET /audit-logs`) |
| Report generation | `reports` table + files under `data/reports/` |

## 9. Useful commands

```bash
make test            # backend + frontend suites
make smoke           # 67-check API contract test
make migrate         # alembic upgrade head
make seed            # recreate the demo database (destructive)
make clean           # remove build artefacts and local databases
```
