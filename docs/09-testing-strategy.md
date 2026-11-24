# 09 — Testing strategy

## 1. Approach

The suite favours **fast, deterministic tests against real behaviour** over snapshot-heavy tests. The
backend runs against an isolated SQLite database created for the test session, with the simulator
disabled, so results never depend on timing.

| Layer | Tool | Count | What it proves |
| --- | --- | --- | --- |
| Backend unit + integration | pytest + FastAPI `TestClient` | 62 | Auth, RBAC, tenant isolation, CRUD, validation, scoring, risk, incidents, GPS ingest, notifications, reports, billing, audit |
| Frontend unit | vitest + Testing Library | 27 | Formatters, tone maps, API client behaviour, component labelling, score bands |
| API contract smoke | `scripts/smoke_api.py` | 67 checks | Every read endpoint + write paths + negative cases against a running server |
| Static typing | `tsc --noEmit` | — | Frontend type safety against API types |
| Build | `next build` | — | 20 routes compile and pre-render |
| Migration parity | `alembic check` | — | Models match the migrated schema |

**Total automated: 89 tests + 67 smoke checks + 401 page-contract checks.**

## 2. Backend suite layout

```
backend/tests/
  conftest.py        isolated SQLite DB, seeded demo org, admin/driver/superadmin clients
  test_auth.py       register, login, refresh rotation, logout, change-password, guards
  test_fleet.py      vehicle + driver CRUD, validation, duplicate detection, PII masking
  test_safety.py     rules engine, scoring edge cases, risk metrics, incident workflow, GPS ingest
  test_platform.py   notifications, reports, assistant, maintenance, subscriptions, audit, models, intelligence
```

Run:

```bash
cd backend && ../.venv/bin/python -m pytest -q     # 62 passed in ~8 s
```

### Notable cases

| Test | Why it matters |
| --- | --- |
| `test_register_returns_tokens` | Registration must return `expires_in` — a 500 was caught here |
| `test_duplicate_registration_with_spaces_rejected` | `"MP09 AB 4211"` vs `"MP09AB4211"` bypassed the duplicate check until normalised in SQL |
| `test_seatbelt_missing_renormalises_weights` | Missing sensors must not penalise a driver; asserts `excluded_categories` contains seatbelt and weights sum to 1 |
| `test_score_below_min_distance_is_low_confidence` | Confidence behaviour is part of the product promise |
| `test_invalid_transition_rejected` | Incident state machine must refuse illegal jumps with 409 |
| `test_driver_cannot_create_vehicle` | Role guard, not just hidden UI |
| `test_cross_tenant_vehicle_returns_404` | Tenant isolation at the row level |
| `test_gps_ingest_rejects_bad_key` | Device auth path |
| `test_risk_model_metrics_are_published` | Model card must report metrics and limitations |
| `test_report_pdf_and_csv_download` | Exports are real files, not stubs |

## 3. Frontend suite layout

```
frontend/tests/
  format.test.ts        cn, number/km/score formatting, tone maps, relative time
  scoring.test.ts       score bands, missing-data handling, clamping
  api.test.ts           error normalisation, transport failure, auth header, query encoding
  components.test.tsx   simulated badges, demo banner, stat cards, severity tones
```

Run:

```bash
cd frontend && npm run test     # 27 passed in ~2.5 s
```

## 4. Smoke test

```bash
.venv/bin/python scripts/smoke_api.py --base-url http://127.0.0.1:8000
```

Covers 44 read endpoints, the vehicle/driver/incident/report/geofence write paths, and five negative
cases (401, 422, 404, 422, 401). It asserts a non-empty PDF body on download. Use `--skip-writes` against a
database you do not want mutated.

## 4b. Page contract verification

Status codes do not prove a page can render. `scripts/verify_page_contracts.py` asserts the *shape* of
every payload a page depends on — 401 checks across dashboard, tracking, fleet, behaviour, risk, incidents,
maintenance, reports, notifications, assistant, road safety, settings and billing.

```bash
.venv/bin/python scripts/verify_page_contracts.py --base-url http://127.0.0.1:8000
# 401 contract checks, 0 failure(s)
```

This script found two real bugs before release: the drivers detail card read category scores from
`history[]` (which only carries `period_start` + `overall_score`) instead of `latest`, and the maintenance
prediction endpoint returned a shape the UI did not expect (`recommendations` vs `risk_level` /
`failure_probability`). Both are fixed and now locked by the checks.

## 5. What is not automated (and why)

| Gap | Reason | Mitigation |
| --- | --- | --- |
| Browser end-to-end flows | No browser binary available in the build environment | Manual walkthrough script in [17](17-demo-script.md); Playwright config is the next step |
| Visual regression | Same | Design tokens keep changes predictable; screenshots reviewed manually |
| Load testing | No fixture generator for 10k vehicles | Documented as a pre-production task |
| LLM output quality | Local mode is deterministic; LLM mode needs a provider key and evaluation set | Assistant exposes grounding so answers are auditable |
| Field validation of thresholds | Requires real fleet data | Thresholds are configurable and audited |
| Postgres-specific behaviour | No Postgres server in the environment | Alembic migrations use batch mode; `alembic check` passes on SQLite; Postgres run is a release gate |

## 6. Release checklist

1. `cd backend && ../.venv/bin/python -m pytest -q` → 62 passed
2. `cd frontend && npm run test` → 27 passed
3. `cd frontend && npx tsc --noEmit` → clean
4. `cd frontend && npm run build` → 20 routes compiled
5. `cd backend && ../.venv/bin/alembic upgrade head` then `alembic check` → no drift
6. Start the API and run `scripts/smoke_api.py` → 0 failures
7. Run `scripts/verify_page_contracts.py` → 0 failures
8. Walk the demo script ([17](17-demo-script.md)) in a browser
8. Confirm no secret is present in `frontend/.next/static` (`grep -r "sk-" frontend/.next/static`)
