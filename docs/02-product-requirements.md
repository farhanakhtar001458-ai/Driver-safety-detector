# 02 — Product requirements

## 1. Problem

Fleet operators are held accountable for driver safety but lack a single, trustworthy view of behaviour,
vehicle condition and incident response. Existing tools are expensive, hardware-locked and opaque about
how drivers are scored. Managers end up either over-policing drivers on flimsy evidence or ignoring risk
entirely.

## 2. Goals

| Goal | Measure of success |
| --- | --- |
| One operational picture | A manager can answer "what needs my attention today?" in under 30 seconds on the Overview page |
| Explainable evaluation | Every score can be traced to category subscores, event rates and a model version |
| Faster incident response | Every incident has an owner-visible state machine with timestamps and audit entries |
| Lower barrier to entry | Published plans, no hardware purchase, working demo without a sales call |
| Honest data | No user can mistake simulated telemetry for live vehicle data |
| Safe automation | No automated contact with emergency services; no automated discipline |

## 3. Non-goals (explicit)

- Accident prediction, crash-timing forecasts, or "prevention guarantees".
- Medical diagnosis (fatigue disorders, health conditions) or legal determinations.
- Video hardware sales, ELD/HOS compliance rule packs, IFTA fuel tax reporting.
- Insurance scoring or selling driver data to third parties.
- Fully autonomous disciplinary decisions.

## 4. Personas and roles

| Role | Wants | Sees | Cannot do |
| --- | --- | --- | --- |
| **Super admin** (platform operator) | Operate all tenants, manage model registry and plans | Cross-organisation views, AI model registry, organisations | Belongs to no organisation; cannot be created inside an organisation |
| **Organisation admin** | Full control of their own tenant | Everything in their org, team, billing, settings | Cannot touch other organisations; cannot manage platform models |
| **Fleet manager** | Vehicles, assignments, maintenance, incidents | Fleet operations, tracking, incidents, maintenance | Cannot manage team, billing or thresholds |
| **Safety officer** | Review behaviour, risk, incidents, coaching | Behaviour, risk, incidents, reports, coaching | Cannot change billing or team |
| **Driver** | Own score, own events, coaching | Own dashboard, own scores, own notifications, assistant | Cannot see other drivers or fleet-wide analytics |

The exact permission matrix is enforced in `backend/app/core/rbac.py` and covered by tests.

## 5. Functional requirements

### 5.1 Dashboard (Overview)
- 10 KPIs: total vehicles, active vehicles, total drivers, active drivers, average safety score, score
  confidence, maintenance alerts, critical maintenance alerts, open incidents, distance in period.
- Live fleet map with simulated-badge provenance, status legend and vehicle popups.
- Weekly trend chart, event type breakdown, severity mix, vehicle activity.
- Leaderboard, recent incidents, notifications, vehicle health table.
- Time range selector (7/30/90 days).

### 5.2 Vehicles
- List with search, status and type filters, pagination.
- Create with validated fields (registration format, VIN length, year range, status enum).
- Detail view: health reading, recent events, location, insurance, GPS device binding, trip count.
- Status lifecycle: `active`, `inactive`, `under_maintenance`, `offline`.

### 5.3 Drivers
- List with search and status filter; masked PII in list responses.
- Detail: licence class/expiry, score breakdown, trend, coaching report generation.
- Create with encrypted licence number, phone and emergency contact.

### 5.4 Live tracking
- WebSocket stream with automatic polling fallback after two failed attempts.
- Vehicle roster, selected-vehicle detail, speed, heading, ignition, last seen.
- Trail length selector (1/3/6 hours), geofence overlays, geofence create/delete.
- Recent high-severity events list.

### 5.5 Driving behaviour
- Period selector, summary KPIs, trend, severity mix, event types.
- Behaviour patterns with methodology and limitations.
- Most-flagged and safest driver lists.
- Filterable event log with sensor payload detail.
- Threshold editor (read-only defaults, editable current values).

### 5.6 AI risk analysis
- Fleet distribution by level, priority review list, fleet risk index.
- Model performance panel (AUC, Brier, accuracy, precision, recall, FPR/FNR).
- Feature importance, published limitations, disclaimer.
- Assess single driver or whole fleet; browse assessment history with inputs and confidence.

### 5.7 Incidents
- Summary tiles, severity mix, types, average response time.
- Register with search, status and severity filters.
- Detail drawer: workflow transitions (investigate → verify → resolve / false alert), notes, evidence.
- Explicit statement that emergency services are never contacted automatically.

### 5.8 Maintenance
- Diagnostics table with health score, engine temperature, fuel, fault codes, provenance.
- Predictive component risk per vehicle with disclaimer.
- Alerts with resolve action, service schedule with urgency, service history with pagination.
- Add maintenance record.

### 5.9 Reports
- Nine report types, PDF/CSV, date range, driver and vehicle filters.
- Generation, history, authenticated download, stored parameters.
- Weekly preview charts.

### 5.10 Notifications
- List with type filter and unread-only toggle, mark one/all read.
- Delivery preferences (in-app, email, SMS, critical-only, quiet hours).
- Type and priority breakdown.

### 5.11 AI assistant
- Chat grounded in the caller's own data, with per-message grounding context.
- Capability and boundary panels; mode badge (LLM vs local).
- Optional driver context; suggestions; disclaimer.

### 5.12 Road safety intelligence
- Illustrative hotspots clearly separated from live, expiring hazards.
- Hazard reporting, weather context (labelled simulated without a provider), route risk check.

### 5.13 Settings and billing
- Organisation profile, monitoring-policy status.
- Team management with role constraints and deactivation.
- Plan and usage with limit bars, invoice history, plan comparison, upgrade/cancel.
- Password change and security posture summary.
- Audit log with pagination.

## 6. Non-functional requirements

| Category | Requirement | Implementation |
| --- | --- | --- |
| Performance | Dashboard under 500 ms server time on the demo dataset | Indexed queries, single aggregation pass; measured informally during smoke tests |
| Security | Tenant isolation, hashed passwords, encrypted PII, rotating refresh tokens | `core/deps.py`, `core/security.py`, Fernet fields |
| Reliability | Live view survives WebSocket failure | Polling fallback in `frontend/lib/live.ts` |
| Accessibility | Keyboard-operable modals, labelled inputs, contrast | Focus handling, `aria-*` attributes, Tailwind palette |
| Observability | Every write auditable | `audit_logs` + structured request logs |
| Portability | Runs on SQLite or PostgreSQL | SQLAlchemy 2 + Alembic with batch mode |
| Honesty | Simulated data labelled everywhere | `is_simulated` columns, UI badges, API flags |

## 7. Acceptance criteria used for this build

1. Every sidebar destination renders real data or a deliberate empty state — no dead links.
2. Every button performs a documented action or is disabled with a reason.
3. Inputs are validated on the client *and* the server; server errors surface as readable messages.
4. Data is persisted in a real database and survives restarts.
5. Simulated data is labelled at record, row, and page level.
6. No API key is present in any client bundle.
7. Automated tests cover auth, RBAC, CRUD, scoring, risk, incidents, notifications, reports, billing.
8. Documentation states what is incomplete rather than claiming production readiness.
