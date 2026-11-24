# 05 — API reference

Base URL: `/api/v1`. Interactive docs at `/api/docs` (Swagger) and `/api/redoc`.
OpenAPI document: `/api/openapi.json`. There are **109 paths / 132 operations**.

## 1. Authentication

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/auth/register` | POST | Create an organisation + admin. Starts on a Professional trial |
| `/auth/login` | POST | Email + password → access + refresh token |
| `/auth/refresh` | POST | Rotate refresh token (old one is revoked) |
| `/auth/logout` | POST | Revoke the refresh token tied to the presented access token |
| `/auth/me` | GET | Current user, organisation, subscription, usage, permissions |
| `/auth/change-password` | POST | Requires current password |

Tokens are HS256 JWTs. Access tokens expire after 30 minutes, refresh tokens after 7 days. Send
`Authorization: Bearer <access_token>` on every protected request.

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@meridian.demo","password":"Demo@12345"}'
```

### Device ingestion

GPS devices authenticate with a scoped key instead of a user token:

```
POST /api/v1/gps/ingest
X-Device-Key: sw_demo_device_key_1234567890
Content-Type: application/json

{"vehicle_id": 1, "points": [{"latitude": 23.2599, "longitude": 77.4126, "speed_kph": 42.5, "recorded_at": "2026-11-24T10:00:00Z"}]}
```

The key is stored hashed; it cannot be recovered. A bad key returns `401`.

### WebSocket

```
GET /api/v1/ws/fleet?token=<access_token>
```

Messages are JSON: `{"type": "connection"}`, then `{"type": "fleet_snapshot", "vehicles": [...]}`, then
`{"type": "fleet_update", "vehicles": [...]}` every ~3 seconds while the simulator runs.

## 2. Error envelope

Every non-2xx response is JSON:

```json
{
  "detail": "Plan limit reached: this organisation allows 60 vehicles.",
  "code": "plan_limit_exceeded",
  "status": 409
}
```

| Status | Meaning |
| --- | --- |
| 400 | Malformed action (e.g. empty note) |
| 401 | Missing/expired token, bad device key, bad credentials |
| 403 | Authenticated but not permitted (role or tenant) |
| 404 | Unknown id, or another tenant's id |
| 409 | State conflict (duplicate registration, invalid workflow transition, plan limit) |
| 422 | Validation error with `detail` describing the field |
| 429 | Rate limit exceeded |

Validation errors from Pydantic return a structured `detail` array; the frontend normalises both shapes
into a readable sentence.

## 3. Endpoints by domain

### Health
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/health` | Liveness probe (no auth) |
| GET | `/health/ready` | Readiness (database ping) |
| GET | `/health/details` | Version, environment, database driver |

### Dashboard
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/dashboard` | KPIs, trend, event mixes, leaderboard, health, recent items. `days=7\|30\|90` |
| GET | `/dashboard/activity` | Distance/events per day |
| GET | `/dashboard/quick-stats` | Cheap counts for widgets |

### Vehicles
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/vehicles` | `search`, `status`, `vehicle_type`, `page`, `page_size`, `include_archived` |
| GET | `/vehicles/meta/status-counts` | Status histogram |
| POST | `/vehicles` | 201; duplicate registration → 409 |
| GET / PATCH / DELETE | `/vehicles/{id}` | DELETE archives |
| POST | `/vehicles/{id}/assign-driver` | `{driver_id}` |
| GET | `/vehicles/{id}/overview` | Health, last location, open alerts, recent events, trip count |
| GET | `/vehicles/{id}/locations` | `{minutes}` (max 360) |
| GET | `/vehicles/{id}/trips` | Paginated |
| GET | `/vehicles/{id}/events` | Paginated |
| GET | `/vehicles/{id}/health` | Health history |
| GET | `/vehicles/{id}/maintenance` | Records |

### Drivers
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/drivers` | `search`, `status`, pagination |
| GET | `/drivers/meta/licences-expiring` | `{days}` |
| POST | `/drivers` | 201 |
| GET / PATCH / DELETE | `/drivers/{id}` | DELETE is a soft delete where history exists |
| GET | `/drivers/{id}/profile` | Latest/previous score, risk, event and incident counts |
| GET | `/drivers/{id}/scores` | History, weekly/monthly, recommendations, data coverage |
| POST | `/drivers/{id}/scores/recompute` | Recompute from raw events |
| GET | `/drivers/{id}/events` / `/trips` | Paginated |
| POST | `/drivers/{id}/coaching-report` | Structured coaching report |

### GPS / tracking
| Method | Path | Notes |
| --- | --- | --- |
| POST | `/gps/ingest` | Device key auth; up to 500 points per batch |
| GET | `/gps/live` | Current fleet snapshot |
| GET | `/gps/vehicles/{id}/latest` | Last fix |
| GET | `/gps/vehicles/{id}/history` | Paginated fixes |
| GET | `/gps/trails` | `minutes` (max 360), optional vehicle ids |
| GET / POST | `/gps/geofences` | List / create |
| PATCH / DELETE | `/gps/geofences/{id}` | Update / remove |

### Behaviour
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/behaviour/summary` | `days` |
| GET | `/behaviour/patterns` | Patterns, methodology, limitations |
| GET | `/behaviour/events` | `event_type`, `severity`, `driver_id`, `vehicle_id`, `from`, `to`, `simulated` |
| GET / POST | `/behaviour/events/{id}` | Detail / manual event creation |
| GET / PUT | `/behaviour/config` | Thresholds; PUT accepts threshold keys only |

### Scores
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/scores/leaderboard` | Latest weekly score per driver |
| GET / PUT | `/scores/config` | Weights (renormalised server-side) |
| POST | `/scores/recompute` | Recompute for `driver_id` or whole org |

### Risk
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/risk/overview` | Distribution, priority list, fleet index, model info |
| GET | `/risk/model-info` | Version, metrics, features, importance, limitations |
| POST | `/risk/assess` | `{driver_id, vehicle_id?}` → assessment |
| POST | `/risk/assess-fleet` | Assess every active driver |
| GET | `/risk/assessments` | Paginated history |
| GET | `/risk/assessments/{id}` | Full inputs and indicators |

### Incidents
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/incidents` | `status`, `severity`, `search`, pagination |
| GET | `/incidents/summary` | Counts by status/severity/type, avg response time |
| POST | `/incidents` | 201 |
| GET / PATCH | `/incidents/{id}` | Detail / field update |
| POST | `/incidents/{id}/investigate` | Transition, `{notes}` |
| POST | `/incidents/{id}/verify` | Transition, `{notes}` |
| POST | `/incidents/{id}/resolve` | Transition, `{notes}` |
| POST | `/incidents/{id}/false-alert` | Transition, `{notes}` |
| POST | `/incidents/{id}/notes` | `{note}` — timestamped and attributed |

### Maintenance
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/maintenance/health` | Latest reading per vehicle |
| GET | `/maintenance/alerts` | `status`, pagination |
| POST | `/maintenance/alerts/{id}/resolve` | Resolve |
| GET / POST | `/maintenance/records` | Paginated list / create |
| PATCH | `/maintenance/records/{id}` | Update |
| GET | `/maintenance/schedule` | Next service, due-in-km, urgency |
| POST | `/maintenance/predict/{vehicle_id}` | Component failure probabilities |

### Reports
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/reports/types` | Nine types with default windows |
| GET | `/reports/summary` | KPIs + charts without generating a file |
| POST | `/reports/generate` | `{report_type, format, from_date, to_date, driver_id, vehicle_id, title}` |
| GET | `/reports` | Paginated history |
| GET | `/reports/{id}` | Metadata |
| GET | `/reports/{id}/download` | Authenticated PDF/CSV |

### Notifications
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/notifications` | `type`, `priority`, `unread`, pagination |
| GET | `/notifications/unread-count` | `{unread}` |
| GET | `/notifications/stats` | By type and priority |
| POST | `/notifications/read-all` | Mark all read |
| POST | `/notifications/{id}/read` | Mark one read |
| POST | `/notifications/{id}/dispatch` | Force channel dispatch (stub without provider) |
| GET / PUT | `/notifications/preferences` | Per-user routing |

### Assistant
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/assistant/capabilities` | Mode, model, can/won't lists, disclaimer |
| POST | `/assistant/chat` | `{message, driver_id?, include_fleet_context}` |
| POST | `/assistant/coaching-report/{driver_id}` | Structured report |
| POST | `/assistant/feedback` | Thumbs up/down with comment |

### Platform
| Method | Path | Notes |
| --- | --- | --- |
| GET / PATCH | `/organisations/me` | Tenant profile |
| GET / POST | `/organisations/me/team` | List / create member |
| PATCH / DELETE | `/organisations/me/team/{user_id}` | Update role / deactivate |
| GET | `/organisations/me/usage` | Vehicle/driver/event/report usage |
| GET / POST | `/organisations` | Super admin list / create |
| GET | `/organisations/{id}` · `/usage` · `/subscription` · `/plans` | Super admin |
| GET / POST | `/subscriptions/plans` · `/me` · `/me/usage` · `/payments` · `/compare` · `/upgrade` · `/cancel` | Billing |
| GET | `/audit-logs` | `action`, `resource_type`, pagination |
| GET / POST / PATCH / DELETE | `/ai-models` | Model registry |
| GET | `/intelligence/overview` · `/hotspots` · `/hazards` · `/weather` | Road safety |
| POST / PATCH | `/intelligence/hazards` · `/hazards/{id}` | Report / update hazard |
| POST | `/intelligence/route-analysis` | `{points: [{latitude, longitude}]}` |

## 4. Pagination

List endpoints accept `page` (1-based) and `page_size` (max 100) and return:

```json
{"items": [...], "total": 42, "page": 1, "page_size": 20, "pages": 3}
```

## 5. Rate limits

`RATE_LIMIT_PER_MINUTE` (default 300) applies per identity on authenticated endpoints and per IP on
anonymous ones (login, health). Exceeding it returns `429` with `Retry-After`.

## 6. Example: full incident workflow

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@meridian.demo","password":"Demo@12345"}' | jq -r .access_token)

ID=$(curl -s -X POST localhost:8000/api/v1/incidents -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Harsh braking near MP Nagar","incident_type":"harsh_event","severity":"moderate"}' | jq -r .id)

curl -s -X POST localhost:8000/api/v1/incidents/$ID/investigate -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"notes":"Reviewed telematics; speed was 61 km/h"}' | jq .
```
