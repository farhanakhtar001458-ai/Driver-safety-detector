# SafeWay AI — Documentation

SafeWay AI is a multi-tenant driving-safety management platform: live GPS tracking, explainable driver
scoring, AI risk triage, incident workflow, predictive maintenance and reporting.

Start here if you are new to the project:

| If you want to… | Read |
| --- | --- |
| Evaluate the product against the market | [01 — Competitor research](01-competitor-research.md) |
| Understand what was built and why | [02 — Product requirements](02-product-requirements.md) |
| Understand how the systems fit together | [03 — Architecture](03-architecture.md) |
| Change the schema | [04 — Database design](04-database-design.md) |
| Integrate with the API | [05 — API reference](05-api-reference.md) |
| Understand or challenge a score | [06 — AI, scoring and risk](06-ai-scoring-and-risk.md) |
| Work on the interface | [07 — Frontend and design system](07-frontend-design-system.md) |
| Review security or privacy posture | [08 — Security and privacy](08-security-and-privacy.md) |
| Run or extend the tests | [09 — Testing strategy](09-testing-strategy.md) |
| Deploy it | [10 — Deployment and operations](10-deployment-and-operations.md) |
| Know what data is real | [11 — Simulation and data provenance](11-simulation-and-data-provenance.md) |
| See the build plan and what is finished | [12 — Implementation phases](12-implementation-phases.md) |
| See what is planned next | [13 — Roadmap](13-roadmap.md) |
| Operate it day to day | [14 — Runbook](14-runbook.md) |
| Configure or audit the LLM features | [15 — LLM integration](15-llm-integration.md) |
| Review accessibility and localisation | [16 — Accessibility and localisation](16-accessibility-and-localisation.md) |
| Run a demo | [17 — Demo script](17-demo-script.md) |
| Know exactly what is *not* done | [18 — Limitations and honesty](18-limitations-and-honesty.md) |

## Non-negotiable product rules

These rules are enforced in code, tests and copy. They are not aspirations.

1. **Simulated data is always labelled.** Every simulator record carries `is_simulated=True` and
   `source="simulated"`. The interface shows a provenance banner and per-row badges.
2. **No accident prediction.** Scores and risk levels are triage priorities for human review. Copy, API
   descriptions and PDF footers all say so.
3. **No automatic emergency contact.** Incident and possible-accident alerts notify people only.
4. **No medical or legal determinations.** Fatigue, distraction and "violation" language is avoided or
   explicitly marked as an unverified observation.
5. **No invented statistics.** Road-safety hotspots are labelled illustrative. Weather is labelled simulated
   unless a provider key is configured.
6. **No secrets in the browser.** LLM, weather, SMS and SMTP credentials live server-side only.
7. **Every write is validated, authorised and audited.**

## Quick facts

| | |
| --- | --- |
| Backend | FastAPI 0.115, Python 3.11, SQLAlchemy 2.0, Pydantic v2 |
| Frontend | Next.js 14.2 (App Router), React 18, TypeScript, Tailwind, Recharts, Leaflet |
| Database | SQLite by default, PostgreSQL 16 supported; Alembic migrations |
| Cache / queue | Optional Redis; in-process fallback for single-instance deployments |
| API surface | 109 paths, 132 operations under `/api/v1` |
| Database tables | 30 (see [04](04-database-design.md)) |
| Roles | 5 (super_admin, org_admin, fleet_manager, safety_officer, driver) |
| Sidebar modules | 13 routes plus authentication and billing pages |
| Automated tests | 62 backend (pytest) + 27 frontend (vitest) |
| Contract checks | 67 API smoke checks + 401 page-contract checks |
| Container | Dockerfiles for API and web, nginx reverse proxy, docker-compose |

## Repository layout

```
.
├── backend/
│   ├── app/
│   │   ├── api/v1/          # 20 routers, one per domain
│   │   ├── core/            # config, security, RBAC, deps, errors, rate limits
│   │   ├── db/              # engine, session, schema bootstrap
│   │   ├── models/          # 30 SQLAlchemy entities
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── services/        # business logic, AI, reports, notifications, simulator
│   │   └── seed.py          # idempotent demo dataset
│   ├── migrations/          # Alembic environment + revisions
│   └── tests/               # 62 pytest tests
├── frontend/
│   ├── app/                 # App Router pages (auth + 13 dashboard routes)
│   ├── components/          # ui, charts, map, layout, tables
│   ├── lib/                 # api client, auth, live telemetry, types, theme
│   └── tests/               # 27 vitest tests
├── docs/                    # this documentation set
├── nginx/                   # reverse proxy configuration
├── scripts/                 # smoke test and operational helpers
├── docker-compose.yml
└── Makefile
```
