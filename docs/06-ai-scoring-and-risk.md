# 06 — AI, scoring and risk

This document is the one to read before quoting any number from the product. Everything here is
deterministic or explicitly labelled as a statistical estimate.

## 1. Two models, two purposes

| | Driver Safety Score | Fleet Risk Classifier |
| --- | --- | --- |
| Purpose | Describe recorded behaviour for coaching | Rank drivers for human review |
| Type | Weighted formula | Gradient-boosted trees + transparent rule overlay |
| Output | 0–100, higher is better | Probability 0–1 → low/moderate/high/critical |
| Version | `score-exp-1.1.0` | `risk-hgb-1.0.0` |
| Training data | None (formula) | 6,000 synthetic historical rows |
| Calibration | Not applicable | Brier 0.104 on a 1,500-row holdout |
| Deterministic? | Yes | Yes (fixed seed, fixed hyperparameters) |

Neither model predicts accidents. The API's own description, every UI disclaimer and every generated PDF
says so.

## 2. Rule engine — event detection

`services/ai/rules_engine.py` compares consecutive GPS fixes and applies thresholds.

| Event | Trigger | Default threshold | Severe at |
| --- | --- | --- | --- |
| Speeding | `speed_kph - speed_limit_kph` | margin 5 km/h | margin 20 km/h |
| Harsh braking | deceleration between fixes | 3.0 m/s² | 4.5 m/s² |
| Rapid acceleration | acceleration between fixes | 2.5 m/s² | 3.8 m/s² |
| Aggressive cornering | lateral acceleration | 3.0 m/s² | — |
| Excessive duration | continuous driving | 4.5 h | — |
| Excessive idling | ignition on, no movement | 10 min | — |
| Seatbelt / distraction | only from an authorised sensor payload | — | low confidence until reviewed |

Speed limits by vehicle type: car 70, van 60, truck 55, bus 55, bike 60 km/h. These are **reference
values for the rule engine**, not legal advice; operators must configure thresholds for their
jurisdiction.

Thresholds are organisation-scoped, stored in `organisations.settings_json["behaviour"]`, editable via
`PUT /behaviour/config`, and audited.

### Severity assignment
Severity is derived from how far the measurement exceeds the threshold (low → medium → high → critical),
never from a model guess. A single harsh event is a `high` severity; only measurements beyond the severe
threshold become `critical`.

## 3. Driver Safety Score

### 3.1 Formula

```
category_score = 100 × e^(−event_rate_per_100km × penalty × 0.28)

overall = Σ (weight_i × category_score_i) / Σ weight_i     over available categories
```

Penalties: speed 2.2, braking 1.9, acceleration 1.6, cornering 1.7, seatbelt 5.0, duration 2.5.
A category with zero events scores 100.

Default weights (normalised to sum to 1):

| Category | Weight |
| --- | --- |
| Speed | 0.22 |
| Braking | 0.18 |
| Acceleration | 0.15 |
| Cornering | 0.15 |
| Seatbelt | 0.12 |
| Consistency | 0.18 |

Consistency is computed from the spread and mean of speeding excess (`100 − 1.8·mean − 1.2·σ`), rewarding
steady speeds rather than merely absent events.

An organisation can override weights (`PUT /scores/config`); values are renormalised server-side.

### 3.2 Missing sensors do not punish drivers

If a category has no data — most commonly seatbelt, when no seatbelt sensor exists — the category is
**excluded** and remaining weights are renormalised. The score row records `excluded_categories` in its
`breakdown`, so a reviewer can see exactly why a score is 100 for a category that was never measured.

### 3.3 Confidence

`confidence = min(1, distance_km / 100) × event_coverage_factor`, capped and reported per score. A driver
with 8 km of data in a week gets a low-confidence score rather than a confident-looking number. The UI
renders this as "Low confidence (34%)" instead of just a percentage.

### 3.4 What the score is not

- Not a probability of crashing.
- Not comparable across organisations with different thresholds or sensor coverage.
- Not evidence for disciplinary action on its own.

## 4. Fleet Risk Classifier

### 4.1 Features (16)

| Feature | Source |
| --- | --- |
| `events_per_100km` | driving events / distance |
| `speeding_rate`, `harsh_braking_rate`, `rapid_acceleration_rate`, `cornering_rate` | per 100 km |
| `night_event_share` | share of events 22:00–05:00 |
| `avg_speed_kph`, `max_speed_kph` | event speeds |
| `continuous_driving_hours` | longest stretch in sensor payload |
| `distance_km` | exposure |
| `vehicle_age_years` | vehicle record |
| `vehicle_health_score` | latest diagnostic reading |
| `open_maintenance_alerts` | 1 if the assigned vehicle has any open alert |
| `licence_days_to_expiry` | driver licence |
| `incidents_12m` | incident register |
| `safety_score_30d` | latest score |

Note the rename from an earlier internal name: `open_maintenance_alerts` means exactly what it says — the
vehicle has at least one open maintenance alert. It does **not** mean the service is overdue by mileage;
that is tracked separately in the maintenance schedule.

### 4.2 Training

- 6,000 synthetic rows generated at boot with a documented latent-risk formula (event rates, night share,
  vehicle age, health, open alerts, incident history, safety score, exposure).
- 25% holdout (1,500 rows); positive rate 0.418; 8% label noise so the task stays a ranking problem.
- `HistGradientBoostingClassifier`, `max_iter=300`, fixed `seed=42`.

Because the data is synthetic and the generator is deterministic, **every deployment reports identical
metrics**. That is a feature for reproducibility and a limitation for real-world validity.

### 4.3 Measured performance (holdout)

| Metric | Value | Reading |
| --- | --- | --- |
| ROC AUC | 0.907 | Good ranking on synthetic data |
| Brier score | 0.104 | Reasonable calibration on synthetic data |
| Accuracy | 0.883 | — |
| Precision | 0.883 | Of flagged, 88% true in the synthetic holdout |
| Recall | 0.831 | Of true, 83% flagged |
| False positive rate | 0.079 | ~8% wrongly flagged |
| False negative rate | 0.169 | ~17% missed |

These numbers describe performance **on synthetic data generated by the same process that trained the
model**. They are not field performance and must not be quoted as such.

### 4.4 Levels and the rule overlay

| Level | Probability band |
| --- | --- |
| Low | < 0.25 |
| Moderate | 0.25 – 0.50 |
| High | 0.50 – 0.75 |
| Critical | ≥ 0.75 |

The final score blends model and rules so a single glaring signal cannot be washed out by an average:
`score = min(0.99, p × 0.72 + rule_score × 0.6)`.

### 4.5 Explanation contract

Every assessment stores and returns:

- `indicators[]` — key, human label, value, detail sentence, weight, direction.
- `explanation` — a generated paragraph naming the top signals.
- `recommendations[]` — concrete next steps.
- `inputs` — the exact feature vector used.
- `confidence` — data-coverage derived.
- `limitations[]` — the model's published caveats.
- `model_version` — so historical assessments stay interpretable.

The risk page renders all of it. Nothing is hidden behind a "AI says high risk" badge.

### 4.6 Feature importance (permutation, holdout)

| Feature | Importance |
| --- | --- |
| `open_maintenance_alerts` | 0.100 |
| `incidents_12m` | 0.079 |
| `vehicle_health_score` | 0.066 |
| `safety_score_30d` | 0.038 |
| `vehicle_age_years` | 0.006 |

Remaining features contribute < 0.006 each. Importance is *not* causation and is not stable across
retraining on different data.

## 5. Coaching assistant

The assistant is grounded: it retrieves the caller's scores, events and risk assessments and includes the
retrieved context in the response (`grounding.context_used`). With `LLM_API_KEY` set it calls an
OpenAI-compatible endpoint from the backend; without a key it answers from local templates and labels the
response `mode: "local"`.

Hard boundaries enforced in prompt and code: no medical diagnosis, no legal determinations, no accident
prediction, no emergency dispatch, no cross-tenant data. See [15](15-llm-integration.md).

## 6. Model registry

`GET /ai-models` returns four entries: Driver Safety Scoring, Fleet Risk Classifier, Event Detection
Rules, Coaching Assistant. Metrics for the risk classifier are read from the trained model at seed time,
so the registry cannot drift from `/risk/model-info`. Entries without a formal evaluation say
`"formal_evaluation": "not performed"` instead of publishing invented accuracy numbers.

## 7. Change control

| Change | Process |
| --- | --- |
| Threshold edit | `PUT /behaviour/config`, audited, applies to new events only |
| Weight edit | `PUT /scores/config`, audited, applies on next recompute |
| Model retrain | Bump `RISK_MODEL_VERSION`, retrain, re-measure, update docs |
| Feature change | Requires a new model version; historical assessments keep their version |
