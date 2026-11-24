# 13 — Roadmap

Sequenced by risk reduction first, then capability. Estimates are rough and assume one full-stack engineer.

## Now (post-v1 hardening) — 2–4 weeks

| Item | Why | Exit criterion |
| --- | --- | --- |
| Browser end-to-end tests (Playwright) | The biggest untested surface is the UI itself | Login → each of the 13 routes renders; one write flow per module |
| Docker build + Compose run in CI | Images are written but unverified | `docker compose up --build` healthy; smoke passes through nginx |
| PostgreSQL integration run | Only SQLite was executed | Migrations apply on PG 16; smoke passes; `alembic check` clean |
| Secrets and key management | `FIELD_ENCRYPTION_KEY` must not be ephemeral in prod | Documented rotation procedure; smoke test for decrypt-after-restart |
| Request IDs + structured logs | Debuggability | Correlation ID in every log line and error envelope |
| Rate-limit tuning per endpoint | Login and ingest need tighter budgets than reads | Separate budgets with tests |

## Next (1–2 months)

| Item | Why |
| --- | --- |
| Payment processing (Razorpay/Stripe) | Plans exist but invoices stay pending |
| MFA (TOTP) for admin roles | Closes the biggest account-takeover gap |
| SSO/SAML for Enterprise | Required by the plan's feature list |
| Email/SMS provider integration | Currently stubbed; templates and provider adapters |
| Report generation queue | PDF export blocks a request today |
| Model persistence | Remove the ~4 s boot-time training |
| Data retention worker | `DATA_RETENTION_DAYS` is a setting without a scheduled job |
| Route-deviation and geofence alert tuning | Detection exists; alert quality needs field data |

## Later (3–6 months)

| Item | Why |
| --- | --- |
| Camera integration framework | Optional distraction detection with consent workflow |
| Mobile driver app (React Native) | Drivers currently use the web app |
| Benchmark dataset + field validation | Replace synthetic model validation with real, consented data |
| Custom thresholds per vehicle class | Different risk profiles for trucks vs bikes |
| Multi-language UI | Hindi first, then other Indian languages |
| Public API keys + webhooks | Let customers build integrations |
| White-label / multi-brand | Agency and reseller motion |

## Deliberately not planned

- Accident prediction or "crash risk scores" marketed as probability of a crash.
- Automated disciplinary decisions.
- Automatic emergency-service dispatch.
- Selling or sharing driver-level data with third parties.
- Camera hardware sales.

## Success metrics to watch after launch

| Metric | Target | Why it matters |
| --- | --- | --- |
| Weekly active managers per org | ≥ 60% of seats | Product is actually used, not shelfware |
| Incidents reviewed within 24 h | ≥ 90% | The workflow is the product |
| Score confidence ≥ 0.7 | ≥ 80% of scored drivers | Data coverage is adequate |
| Simulated-data confusion reports | 0 | Honesty check |
| API p95 latency (dashboard) | < 500 ms | Performance promise |
| Test suite runtime | < 15 s | Keeps the suite running on every commit |
