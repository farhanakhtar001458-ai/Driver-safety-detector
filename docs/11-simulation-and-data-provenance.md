# 11 — Simulation and data provenance

This is the most important operational document in the set. SafeWay AI must never let a user mistake
generated data for real telemetry.

## 1. What is simulated in this build

| Data | Source | Labelling |
| --- | --- | --- |
| Vehicle positions | `services/simulator.py` walking six demo routes | `is_simulated=True`, `source="simulated"` on every `vehicle_location` |
| Driving events | Rule engine applied to simulated fixes | `is_simulated=True`, `source="simulated"` on every `driving_event` |
| Vehicle health readings | Generated from vehicle age/mileage | `is_simulated=True` on `vehicle_health_readings` |
| Trips | Generated around demo routes | `source="simulated"` |
| Demo incidents | Seeded records | Evidence carries `is_simulated` |
| Historical hotspots | Hard-coded illustrative coordinates | `is_illustrative=True`, `source_name` says "Illustrative demo dataset – not official accident statistics" |
| Weather | Sample values | `simulated: true`, `source: "simulated demo sample"` |
| Risk model training set | Synthetic generator in `risk_model.py` | Model card says "Trained on synthetic historical data for demonstration" |

## 2. What is real

- Organisations, users, roles, permissions.
- Vehicles, drivers, geofences, maintenance records, incidents you create.
- Scores computed from whatever events exist (simulated or real).
- Risk assessments computed from those features.
- Reports generated from the database.
- Audit log entries.

## 3. How the labelling reaches the user

| Level | Implementation |
| --- | --- |
| Database | `is_simulated` boolean + `source` string on telemetry tables |
| API | Flags serialised in every response (`is_simulated`, `simulated`, `simulation_share_pct`) |
| Page | `DemoBanner` on Overview, Tracking, Vehicles, Drivers, Behaviour, Risk, Incidents, Maintenance, Reports, Notifications, Road Safety, Settings |
| Row | `SimulatedBadge` on map popups, vehicle tables, health tables, event log, hazard lists |
| KPI | Overview shows "Data provenance: 100% of events are simulated" |
| Export | Reports carry a provenance footer |
| Assistant | Grounding block shows the context used; disclaimer attached to every reply |

## 4. The simulator

`app/services/simulator.py` starts with the API when `DEMO_MODE` and `SIMULATOR_ENABLED` are true.

- Six routes around Bhopal: Airport Corridor, MP Nagar Loop, Habibganj Route, Kolar Road, Raisen Road,
  Berasia Road.
- Every `SIMULATOR_INTERVAL_SECONDS` (3 s) it advances each vehicle along its route, computes speed and
  heading, writes a `vehicle_location`, runs the rule engine, and publishes a WebSocket frame.
- It never writes to a vehicle marked offline and never fabricates a camera or seatbelt signal.
- It stops on shutdown and is disabled by `DEMO_MODE=false`.

## 5. Ingesting real telemetry

Any device that can POST JSON works:

```http
POST /api/v1/gps/ingest
X-Device-Key: sw_<generated-key>
Content-Type: application/json

{
  "vehicle_id": 12,
  "points": [
    {"latitude": 23.2599, "longitude": 77.4126, "speed_kph": 44.2,
     "heading": 87.0, "accuracy_m": 5.0, "odometer_km": 42010.5,
     "ignition_on": true, "recorded_at": "2026-11-24T10:15:00Z"}
  ]
}
```

- Up to 500 points per batch.
- The device key maps to exactly one organisation; the vehicle must belong to it.
- Points are ordered and compared pairwise, so events are detected from real acceleration and speed.
- `is_simulated` is set to `false` for ingested rows — the provenance is preserved automatically.

To create a device key, insert a `gps_devices` row (or use the seed helper) and store the SHA-256 hash of
the key. The raw key is shown once and never again.

## 6. Disabling simulation for a real deployment

```
DEMO_MODE=false
SEED_DEMO_DATA=false
SIMULATOR_ENABLED=false
```

Then run migrations against an empty database and create your organisation through `/auth/register`.
The UI will still show provenance badges where they apply, but no new simulated data will be produced.

## 7. Why this matters commercially

Demonstrations that show fake numbers without labels create false expectations and, in safety software,
can lead to operational decisions made on invented data. A reviewer can verify our labelling in three
clicks: Overview banner → vehicle health table → event detail `source: simulated`.

## 8. Audit trail for provenance

- Every telemetry row carries its source.
- Every score stores `model_version` and `breakdown`, including `excluded_categories`.
- Every risk assessment stores its `inputs`.
- Every report stores its `params` and a provenance footer.
- `GET /dashboard` returns `simulated_share_pct`, which the UI surfaces as a KPI.
