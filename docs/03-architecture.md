# 03 — Architecture

## 1. System context

```
                    ┌──────────────────────────────────────────────┐
                    │                   Browser                     │
                    │  Next.js 14 app (TypeScript, Tailwind,       │
                    │  Recharts, Leaflet)                          │
                    └───────────────┬──────────────────────────────┘
                                    │ HTTPS, same origin
                    ┌───────────────▼──────────────────────────────┐
                    │        nginx  (TLS termination, routing)     │
                    │  /            -> frontend:3000               │
                    │  /api/*       -> backend:8000                │
                    │  /api/v1/ws/* -> backend:8000 (upgrade)      │
                    └───────┬──────────────────────────┬───────────┘
                            │                          │
              ┌─────────────▼──────────┐   ┌───────────▼────────────┐
              │ Next.js server (3000)  │   │ FastAPI (8000)         │
              │ SSR + API rewrites     │   │ 20 domain routers      │
              └─────────────┬──────────┘   │ WebSocket hub          │
                            │              │ background simulator   │
                            │              │ rule + ML services     │
                            │              └───────────┬────────────┘
                            │                          │
                            │              ┌───────────▼────────────┐
                            └─────────────►│ PostgreSQL / SQLite    │
                                           │ Redis (optional)       │
                                           │ filesystem (reports)   │
                                           └────────────────────────┘
```

In development the browser talks to Next.js on `:3000`; a rewrite proxies `/api/v1/*` to the API on
`:8000`. In production nginx fronts both so everything is same-origin — the browser never needs to reach
an internal host, which is why the deployment works behind a single hostname.

## 2. Backend layers

| Layer | Path | Responsibility |
| --- | --- | --- |
| Routers | `app/api/v1/*.py` (20 routers) | HTTP parsing, dependency injection, response models, permission checks |
| Schemas | `app/schemas/*.py` | Pydantic request/response contracts, field validation |
| Services | `app/services/*.py` | Business logic: scoring, rules, risk, notifications, reports, billing, simulator |
| AI | `app/services/ai/*.py` | Rule engine, scoring, risk model, LLM coach |
| Models | `app/models/*.py` | 30 SQLAlchemy entities with JSON columns, encrypted PII |
| Core | `app/core/*.py` | Settings, JWT/bcrypt/Fernet, RBAC, tenant deps, error handlers, rate limits |
| DB | `app/db/*.py` | Engine, session, schema bootstrap and seeding |

Routers stay thin: they resolve dependencies, call a service and serialise. No router contains business
logic beyond input coercion.

## 3. Request lifecycle

```
HTTP request
  -> RateLimitMiddleware (sliding window per identity/IP)
  -> GZipMiddleware
  -> CORSMiddleware
  -> exception handlers (AppError -> JSON envelope)
  -> require_permission("resource:action")
       -> get_current_user (JWT decode, user active, session valid)
       -> get_organisation (tenant resolution)
  -> handler
  -> service
  -> SQLAlchemy session (committed in the dependency)
  -> Pydantic response model
```

`get_db` yields a session and commits on success. Any `AppError` subclass maps to a consistent JSON
envelope: `{"detail": "...", "code": "...", "status": ...}`. Validation errors from Pydantic return 422
with field-level detail.

## 4. Multi-tenancy

Every organisation-owned table carries `organisation_id` with a foreign key and index. Two helpers
enforce isolation:

- `org_filter(query, Model, user, organisation_id=None)` — super admins may pass an explicit
  `organisation_id`; everyone else is pinned to their own.
- `ensure_org_access(organisation_id, user)` — raises 403/404 when a path parameter references another
  tenant's row.

This is defence in depth: even if a router forgets `org_filter`, `ensure_org_access` on the loaded row
prevents cross-tenant reads. Tests cover both paths.

## 5. Real-time telemetry

```
GPS device / simulator
   -> POST /api/v1/gps/ingest   (X-Device-Key: sw_...)
        -> key hash lookup -> organisation -> vehicle
        -> rules_engine.detect_events(prev, current)
        -> DrivingEvent rows + notifications + maintenance signals
        -> ws_hub.publish(fleet_update)
   -> WebSocket /api/v1/ws/fleet?token=<jwt>
        -> connection -> fleet_snapshot -> fleet_update (3 s cadence)
```

The WebSocket hub keeps an in-process subscriber registry. With `REDIS_URL` configured it uses Redis
pub/sub so multiple API instances can fan out; without Redis it works correctly for a single instance.

The frontend opens the socket and falls back to `GET /api/v1/gps/live` polling after two failed attempts,
so a proxy that blocks upgrades still yields a live-feeling page.

## 6. AI pipeline

```
telemetry + trips + incidents + maintenance
   -> rules_engine (threshold events)            -- deterministic, unit-tested
   -> scoring.compute_score (0-100, renormalised) -- deterministic, explainable
   -> risk_model.build_driver_features (16 features)
   -> HistGradientBoostingClassifier + rule overlay
   -> risk_level + indicators + explanation + confidence + limitations
```

The model trains once at process start on 6,000 synthetic rows (25% holdout) and caches. Training is
deterministic (`seed=42`), so every deployment reports the same metrics. See [06](06-ai-scoring-and-risk.md).

## 7. Frontend architecture

```
app/
  layout.tsx            Theme + Auth providers, theme bootstrap script
  page.tsx              Redirects to /overview or /login
  (auth)/login, register
  (app)/layout.tsx      AppShell (sidebar, topbar, toast host)
  (app)/<13 routes>
components/
  layout/               Sidebar, Topbar, AppShell
  ui/index.tsx          Primitives: Button, Card, Modal, Field, Badge, Switch, Tabs, toast…
  charts/               Recharts wrappers (area, bar, donut, ring, sparkline)
  map/                  FleetMap (dynamic import, SSR off) + Leaflet implementation
  tables/               DataTable, Pagination
lib/
  api.ts                fetch client, token store, single-flight refresh, error normalisation
  auth.tsx              AuthProvider (login/register/logout/refresh/permission)
  live.ts               useLiveFleet (WebSocket + polling fallback)
  theme.tsx             ThemeProvider
  types.ts              API types
  format.ts             Formatters and tone maps
  scoreDisplay.ts       Score bands and confidence labels
```

**State management:** server state is fetched per page with `useCallback` + `useEffect`; there is no global
store because every page's data is independent and short-lived. Auth and theme are the only global
contexts. This keeps the bundle small (88 kB shared JS) and avoids cache-invalidation bugs.

**Map:** Leaflet accesses `window` at import time, so `components/map/FleetMap.tsx` wraps the
implementation in `next/dynamic({ ssr: false })`. This is why every page with a map still pre-renders.

## 8. Key trade-offs

| Decision | Alternative | Why |
| --- | --- | --- |
| SQLite default | PostgreSQL only | Reviewers can run the stack with zero services; Postgres is a `DATABASE_URL` change and migrations support both |
| JWT access + rotating refresh | Session cookies | Simpler for API-first integrations and device ingestion; refresh tokens are stored hashed and revocable |
| Train risk model at boot | Persist model artefact | Reproducible and dependency-free; ~4 s startup cost on this hardware |
| Per-page fetching | React Query / SWR | Adds a dependency for little gain at this scale; the api client already handles refresh and errors |
| In-process WS hub | Redis-only | Single-instance demo must work without Redis; Redis is a config flag |
| Pydantic `dict` payloads on a few config endpoints | Typed models | Faster iteration on threshold editing; validation is explicit in the handler |

## 9. Scaling path

1. **Stateless API** — JWT means any instance can serve any request; move refresh-token checks to a shared
   store (Redis) before running multiple instances.
2. **WebSocket fan-out** — set `REDIS_URL`; the hub switches to pub/sub.
3. **Database** — `DATABASE_URL=postgresql+psycopg://…`, run `alembic upgrade head`, add read replicas.
4. **Reports** — move PDF generation to a worker queue (Celery/ARQ) and object storage for files.
5. **Model** — persist the trained model to object storage and load it instead of training at boot.
