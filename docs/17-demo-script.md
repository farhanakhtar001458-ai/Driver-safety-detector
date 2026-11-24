# 17 — Demo script

A seven-minute walkthrough that exercises every module and shows the product's honesty rules in action.

## Setup

```bash
# Backend (seeds demo data on first start)
cd backend && ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend && npm run dev          # or: npm run build && npm start
```

Open http://localhost:3000 and sign in as:

| Role | Email | Password |
| --- | --- | --- |
| Organisation admin | `admin@meridian.demo` | `Demo@12345` |
| Fleet manager | `fleet@meridian.demo` | `Demo@12345` |
| Safety officer | `safety@meridian.demo` | `Demo@12345` |
| Driver | `rajesh@meridian.demo` | `Demo@12345` |
| Platform super admin | `superadmin@safeway.demo` | `Super@12345` |

## Minute 0–1 — Login and first impression

- Show the login screen and point at the demo-account panel.
- Sign in as org admin. Land on **Overview**.
- Call out the amber banner: *"100% of events are simulated"* — this is a demo workspace, not real vehicles.
- Point at the **Data provenance** KPI tile.

## Minute 1–2 — Overview

- KPI row: 12 vehicles, 12 drivers, average score ~73, 8 maintenance alerts.
- Live map: vehicles move; the connection pill says **WebSocket** (or **Polling fallback** if the proxy
  blocks upgrades). Click a vehicle → popup says "Simulated demo position".
- Trend chart, severity donut, event types, leaderboard, vehicle health table with `Simulated` badges.
- Switch the range 7 → 30 → 90 days and show the charts re-query.

## Minute 2–3 — Live tracking

- Show the roster and select a vehicle: speed, heading, ignition, last seen.
- Change trail length 1 h → 6 h.
- Create a geofence around the depot; it appears as a dashed circle.
- Show recent high-severity events with per-row provenance badges.
- Read the "How tracking behaves" card — map tiles need internet, telemetry is simulated, no auto-emergency-contact.

## Minute 3–4 — Behaviour, risk, incidents

- **Driving Behaviour:** summary KPIs, event type breakdown, patterns with methodology and limitations.
  Open an event → sensor payload JSON and `source: simulated`.
  Open **Thresholds** — change one value, save, and note that it applies only to new events.
- **AI Risk Analysis:** distribution across low/moderate/high/critical, priority list, model card with AUC
  0.907 / Brier 0.104 and the explicit statement that it was trained on synthetic data.
  Click an assessment → indicators, inputs, confidence, limitations.
  Run **Assess fleet** and watch the distribution update.
- **Incidents:** open a seeded incident, walk the state machine (investigate → verify → resolve), add a
  note, and point at the "never contacts emergency services" callout.

## Minute 4–5 — Maintenance, reports

- **Maintenance:** diagnostics table with fault codes and provenance, service schedule with urgency,
  **Predict** on a vehicle → component probabilities + disclaimer that it is not a manufacturer diagnostic.
  Resolve an alert.
- **Reports:** generate a weekly safety PDF with a driver filter, then download it. Show the stored
  parameters on the report detail modal. Generate a CSV to show both formats.

## Minute 5–6 — Assistant, road safety, notifications

- **AI Assistant:** ask "Which drivers should I coach first?" — show the grounding line and the mode badge
  ("Local mode · no external model"). Ask something out of scope ("Will driver 3 crash?") and show the
  refusal.
- **Road Safety:** illustrative hotspots vs live hazards on one map, with a provenance card explaining the
  difference. Report a hazard with a 24-hour expiry. Show weather labelled "Simulated sample".
- **Notifications:** unread badge, mark all read, edit preferences (quiet hours, channels).

## Minute 6–7 — Settings, billing, close

- **Settings → Team:** roles, activation switch, invite a member (shows role ceiling).
- **Settings → Audit log:** every action just performed is listed.
- **Plans & billing:** four published plans with limits; note that payments are not processed in this
  build and invoices stay pending.
- Close on the three promises: published pricing, explainable scores, honest demo data.

## Objection handling

| Objection | Answer |
| --- | --- |
| "Your demo data is fake." | Yes — and it is labelled at record, row and page level. Real devices authenticate with an ingest key and arrive as `is_simulated=false`. |
| "Your risk score says critical for a driver." | It is a review queue, not a verdict. Every assessment lists its indicators, inputs, confidence and limitations. |
| "Will it predict accidents?" | No. We deliberately do not build that; it is not technically defensible with this data. |
| "How accurate is the model?" | AUC 0.907 on a synthetic holdout. That is not field accuracy — we say so in the product. |
| "What does it cost?" | Plans are on screen: Free, ₹1,499, ₹3,499, and custom Enterprise. No quote-only wall. |
