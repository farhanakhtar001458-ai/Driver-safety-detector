# 18 — Limitations and honesty

A precise list of what is **not** done, not verified, or not claimed. If something is absent from the
"done" lists elsewhere, assume it is not done.

## 1. Not implemented

| Area | Status | Detail |
| --- | --- | --- |
| Payment processing | ❌ Not implemented | Plans, trials, limits and invoice records exist, but no gateway is connected. Invoices stay `pending`. |
| MFA / TOTP | ❌ Not implemented | Listed in the Enterprise plan features; not built. |
| SSO / SAML | ❌ Not implemented | Same as above. |
| Real email delivery | ⚠️ Stub | Templates and preferences exist; SMTP is only used if configured, and no provider was tested. |
| Real SMS delivery | ⚠️ Stub | Provider adapter interface exists; no provider tested. |
| Camera / distraction pipeline | ❌ Not implemented | No camera integration is enabled, so no distraction events are produced. The schema and confidence language are ready. |
| Route deviation alerts | ⚠️ Partial | Route polylines and deviation detection exist in the tracking service, but alert tuning and UI surfacing are limited. |
| Retention worker | ❌ Not scheduled | `DATA_RETENTION_DAYS` exists as a setting; there is no recurring job that prunes data. |
| Report generation queue | ❌ Not implemented | PDF/CSV generation is synchronous. |
| Model persistence | ❌ Not implemented | The risk model trains at process start (~4 s). |
| Public API keys / webhooks | ❌ Not implemented | Only device ingest keys exist. |
| Multi-language UI | ❌ Not implemented | English only. |
| Driver mobile app | ❌ Not implemented | Drivers use the web app. |
| Offline map tiles | ❌ Not implemented | Tiles load from OpenStreetMap and need internet. |

## 2. Not verified in this environment

| Item | Why | What was done instead |
| --- | --- | --- |
| Docker image build / Compose run | No Docker daemon in the build sandbox | Dockerfiles, compose and nginx config written and reviewed; commands documented |
| PostgreSQL execution | No PostgreSQL server available | Alembic migration uses batch mode; `psycopg` installed and imported; SQLite path fully verified |
| Redis pub/sub fan-out | No Redis server available | Hub has an in-process path that was verified; Redis path is config-gated |
| Browser-level E2E tests | No browser binary available | 27 unit/component tests + 67 API smoke checks + manual route audit |
| Visual / accessibility audit | No browser | Manual review only; gaps listed in [16](16-accessibility-and-localisation.md) |
| Load testing | No fixture generator | Performance considerations documented, not measured |
| LLM output quality | No provider key configured | Local mode exercised; evaluation plan documented in [15](15-llm-integration.md) |
| Field accuracy of risk model | No real incident data | Synthetic holdout only: AUC 0.907, Brier 0.104 |

## 3. Claims we deliberately do not make

| Claim | Why not |
| --- | --- |
| "Prevents accidents" | No causal evidence, and the product cannot intervene in a vehicle. |
| "Predicts accidents" | A triage score is not a probability of a crash; the model is trained on synthetic labels. |
| "Detects fatigue" | No medical device, no validated fatigue model. Duration events are a proxy, not a diagnosis. |
| "Confirms distraction" | Camera observations are low-confidence until a person reviews them; no camera pipeline is enabled. |
| "Automatically calls emergency services" | Deliberately prohibited. Every surface states that escalation is manual. |
| "Compliant with <regulation>" | No legal review has been performed. The app supports policy acknowledgement and audit, not compliance certification. |
| "Production-ready" | It is a complete, tested v1 with the gaps listed above. Read this document before deploying. |
| "ISO/SOC certified" | No audit has been performed. |

## 4. Accuracy of published numbers

| Number | Source | Honest framing |
| --- | --- | --- |
| AUC 0.907, Brier 0.104, FPR 0.079, FNR 0.169 | Synthetic holdout, 1,500 rows | Performance on data from the same generator that trained the model |
| "62 tests passed" | pytest run in this environment | Real, repeatable |
| "27 tests passed" | vitest run in this environment | Real, repeatable |
| "67 smoke checks passed" | `scripts/smoke_api.py` against a live API | Real, repeatable |
| "109 API paths / 132 operations" | OpenAPI document | Real, generated |
| "30 tables" | Alembic migration | Real, generated |
| Pricing (₹1,499 / ₹3,499) | Product decision, seeded in the database | Illustrative pricing, not market research on Indian willingness-to-pay |
| Competitor prices ($4–$60) | Public pricing pages, Nov 2026 | Snapshot; changes frequently and excludes negotiated discounts |

## 5. Residual risks

1. **A new router could skip tenant filtering.** The pattern is tested, but discipline is required.
   Consider a lint rule or a base dependency that injects `org_filter`.
2. **JWT secret rotation logs everyone out.** Plan rotation windows.
3. **Field encryption key loss makes PII unreadable.** Back up `FIELD_ENCRYPTION_KEY` in a secret manager.
4. **Simulator left on in production** would fabricate telemetry. Set `DEMO_MODE=false` and verify
   `simulated_share_pct` is 0 in production.
5. **Thresholds copied from defaults may not match local law.** Operators must configure per jurisdiction.
6. **Score weights are a policy choice.** Changing them changes scores; historical scores keep their model
   version, but cross-period comparisons become invalid.
7. **No MFA** is the largest account-security gap for admin roles.
8. **Single-instance rate limiting** is trivially bypassed by distributing requests across instances.

## 6. What "done" means here

- Every route renders with real data or a deliberate empty state.
- Every visible action performs its documented function against the API.
- Automated tests pass (60 backend, 27 frontend) and the smoke test passes (67 checks).
- Documentation describes both the implementation and its limits.

Anything beyond that — payments, MFA, camera AI, field validation, load testing, browser E2E — is future
work, and this document is the contract that says so.
