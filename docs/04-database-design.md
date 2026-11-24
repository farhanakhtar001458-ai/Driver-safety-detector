# 04 — Database design

## 1. Overview

30 tables, defined as SQLAlchemy 2.0 `Mapped` models in `backend/app/models/`, migrated with Alembic
(`backend/migrations/versions/0001_initial.py`). SQLite by default, PostgreSQL for production — the
migration uses `render_as_batch` on SQLite and emits `ALTER TABLE` for cyclic foreign keys so it applies
cleanly on both.

Schema source of truth is the models; the migration is generated with
`SQLALCHEMY_URL=<fresh-db> alembic revision --autogenerate`. `alembic check` reports
"No new upgrade operations detected" against a freshly migrated database, which is the parity test used
before release.

## 2. Entity groups

### Identity and tenancy
| Table | Purpose | Notes |
| --- | --- | --- |
| `organisations` | Tenant root | Unique `slug`, `settings_json` for score weights and thresholds |
| `users` | Accounts | `organisation_id` nullable only for super admins; bcrypt `password_hash`, Fernet `phone_encrypted` |
| `roles`, `permissions`, `role_permissions` | Data-driven RBAC | Seeded from `core/rbac.py`; a super admin can adjust grants at runtime |
| `refresh_tokens`, `user_sessions` | Session security | Tokens stored as SHA-256 hashes; rotation on refresh, revocation on logout |

### Fleet
| Table | Purpose | Notes |
| --- | --- | --- |
| `vehicles` | Asset register | Unique registration (whitespace-normalised in code), masked VIN, `gps_device_id` |
| `gps_devices` | Telemetry hardware | `key_hash` stores SHA-256 of `sw_…` ingest keys; unique `serial_number` |
| `drivers` | Driver profiles | `phone_encrypted`, `licence_number_encrypted`, `emergency_contact_*` encrypted |
| `vehicle_locations` | GPS breadcrumbs | Composite indexes on `(vehicle_id, recorded_at)` and `(organisation_id, recorded_at)` |
| `trips` | Journey aggregate | Distance, duration, average/max speed, event count |
| `vehicle_health_readings` | Diagnostics | Engine temp, battery, fuel, fault codes, derived health score |
| `maintenance_alerts`, `maintenance_records` | Service workflow | Alerts have severity/status; records have odometer, cost, next due |

### Safety and analytics
| Table | Purpose | Notes |
| --- | --- | --- |
| `driving_events` | Detected events | `event_type`, `severity`, speed/limit, `sensor_data` JSON, `is_simulated`, `source` |
| `driver_scores` | Scored periods | `period` (weekly/monthly), six category subscores, `confidence`, `model_version`, `breakdown` JSON |
| `risk_assessments` | Risk output | `indicators`, `inputs`, `limitations` JSON; `model_version` stamped |
| `incidents` | Incident register | Status machine, investigation/resolution notes, evidence JSON, timestamps |
| `road_hotspots` | Historical context | `is_illustrative` flag and `source_name` make provenance explicit |
| `road_hazards` | Live, expiring | `expires_at`, `status`, `is_simulated` |
| `geofences` | Boundaries | `alert_on_enter` / `alert_on_exit`, `is_active` |

### Platform operations
| Table | Purpose | Notes |
| --- | --- | --- |
| `notifications` | Per-user messages | `priority`, `channel`, `delivery_status`, `related_type/id` |
| `notification_preferences` | Per-user routing | `in_app`, `email`, `sms`, `critical_only`, quiet hours |
| `reports` | Generated exports | `params` JSON, `file_path`, `row_count`, `status` |
| `audit_logs` | Write audit | `action`, `resource_type/id`, `detail` JSON, IP, user agent |
| `ai_model_versions` | Model registry | Metrics, limitations, status — values derived from the live model at seed time |
| `subscription_plans` | Published plans | `code`, price, vehicle/driver limits, features JSON, `is_custom` |
| `subscriptions` | Tenant subscription | Status, seats, trial window, `cancel_at_period_end` |
| `payments` | Invoice history | `invoice_number`, amount, status, provider reference |

## 3. Relationships

```
organisations 1─* users 1─* refresh_tokens / user_sessions
organisations 1─* vehicles 1─* vehicle_locations
                     │ 1─* trips 1─* driving_events
                     │ 1─* vehicle_health_readings
                     │ 1─* maintenance_alerts / maintenance_records
                     └──* gps_devices            (cycle broken with use_alter)
organisations 1─* drivers 1─* driver_scores / driving_events / incidents / risk_assessments
organisations 1─* notifications 1─1 notification_preferences (per user)
organisations 1─* reports / audit_logs / geofences / road_hazards / road_hotspots
organisations 1─* subscriptions *─1 subscription_plans 1─* payments
roles *─* permissions (role_permissions)
```

The `vehicles.gps_device_id` ↔ `gps_devices.vehicle_id` pair is a genuine cycle. It is declared with
`use_alter=True, name="fk_vehicles_gps_device_id"` so table creation order is deterministic and the
constraint is added afterwards — required for PostgreSQL, harmless on SQLite.

## 4. Indexes

| Index | Why |
| --- | --- |
| `ix_locations_vehicle_time` | Trail queries (`/gps/trails`, vehicle history) |
| `ix_locations_org_time` | Organisation-scoped time range scans |
| `ix_events_driver_time` | Driver score computation |
| `ix_events_org_time` | Behaviour summary and dashboard trend |
| `ix_events_type_severity` | Severity filters and pattern detection |
| `ix_events_vehicle_time` | Vehicle detail pages |
| `driving_events.severity` | Risk overlays and KPI counts |
| `vehicles.registration_number` (unique) | Duplicate prevention |
| `gps_devices.serial_number` (unique) | Device lookup during ingest |
| `users.email` (unique) | Login path |
| `driver_scores.driver_id, period_end` | Latest-score lookups |

## 5. Data types and JSON

`app/db/base.py` maps Python `dict` → `JSON` and `list` → `JSON`, so `sensor_data`, `breakdown`,
`indicators`, `inputs`, `evidence`, `params`, `detail`, `features`, `settings_json` and `limitations` are
queryable JSON columns on PostgreSQL and TEXT-backed JSON on SQLite. No JSON column stores data that must
be joined on.

## 6. Encryption and masking

| Field | Storage | API exposure |
| --- | --- | --- |
| `users.phone` | Fernet-encrypted | `phone_masked` (`+91•••••1234`) |
| `drivers.phone` | Fernet-encrypted | `phone_masked` |
| `drivers.licence_number` | Fernet-encrypted | `licence_number_masked` (`••••••4211`) |
| `drivers.emergency_contact_phone` | Fernet-encrypted | never returned |
| `vehicles.vin` | plaintext | `vin_masked` (`MH0•••••••4211`) |
| `gps_devices.key_hash` | SHA-256 (one-way) | never returned; only shown once at creation |
| `users.password_hash` | bcrypt | never returned |

`FIELD_ENCRYPTION_KEY` must be set in production. When empty, an ephemeral key is derived per process —
fine for a demo, fatal for persistence across restarts. The `.env.example` says so explicitly.

## 7. Retention and deletion

- `DATA_RETENTION_DAYS` (default 365) is the policy knob for location/event pruning.
- Deleting an organisation cascades to all tenant-owned rows (`ondelete="CASCADE"` on `organisation_id`).
- Vehicle deletion is an archive (`is_archived=True`) rather than a hard delete, preserving score and
  incident history.
- Report files live under `data/reports/` and are cleaned by the same retention job.

## 8. Migrations

```bash
cd backend
../.venv/bin/alembic upgrade head          # apply
../.venv/bin/alembic downgrade -1          # revert one revision
../.venv/bin/alembic check                 # models vs database parity
SQLALCHEMY_URL=sqlite:///./data/tmp.db \
  ../.venv/bin/alembic revision --autogenerate -m "describe change"
```

Verified during this build: `upgrade head` on an empty database creates all 30 tables,
`alembic check` reports no drift, `downgrade base` removes them, and `upgrade head` re-applies cleanly.
