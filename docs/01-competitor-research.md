# 01 — Competitor research

Research completed before implementation, in November 2026, from public pricing and product pages.
Prices are per vehicle per month unless noted, exclude taxes, and change frequently — treat them as a
snapshot of the market band, not a quote.

## 1. Solutions reviewed

| Product | Segment | Observed pricing | Model | Differentiator | Weakness we can exploit |
| --- | --- | --- | --- | --- | --- |
| **Samsara** | Enterprise telematics | ≈$27–33 (GPS only) to $40–60+ with AI cameras; 36-month contracts | Hardware + subscription | Broad platform, connected operations, strong enterprise trust | Longest contract lock-in and highest total cost; hardware-as-a-service |
| **Motive** (formerly KeepTruckin) | Mid-market / enterprise | ≈$31–35 | Hardware + subscription | Dashcam-led safety workflow, strong driver-facing app | Quote-heavy, camera-first narrative, limited explainability of scores |
| **Geotab** | Open platform / marketplace | ≈$15–50 across GO Core and higher tiers | Hardware + subscription + add-ins | Most open ecosystem, large marketplace, strong reporting | Add-in sprawl; final cost hard to predict |
| **Lytx** | AI video safety | ≈$30–50 | Hardware + subscription | Video-based coaching with machine vision | Camera-centric; privacy and consent burden; opaque scoring |
| **Netradyne** | AI video safety | Quote-only | Hardware + subscription | Edge AI vision, driver recognition | No public price, heavy hardware dependency |
| **Azuga** | Mid-market | Published $25 / $30 / $35 tiers; SafetyCam +$49.99 | Subscription + hardware | One of the few with published tiered pricing | shallower analytics, dated UX |
| **Fleetio** | Fleet maintenance | ≈$4 / $7 / $10 per vehicle | SaaS only | Excellent maintenance-first workflow, low price | No native telematics — needs a hardware partner |
| **Verizon Connect** | Enterprise | ≈$15.95 (GSA-listed) + $4.03 ELD | Hardware + subscription | Network scale, compliance depth | Enterprise procurement, less safety coaching |
| **Quartix** | SMB | ≈$14 | Hardware + subscription | Simple, cheap tracking | Analytics depth limited |

**Market band observed: roughly $4–$60 per vehicle per month**, with hardware often extra
($50–$200 one-time) and multi-year contracts common above $25.

## 2. Patterns across the market

1. **Quote-only pricing is the norm above $25.** Only Azuga and Fleetio publish simple tiers. Buyers
   cannot compare without a sales call.
2. **Hardware lock-in drives the business model.** Samsara, Lytx, Netradyne, Motive and Verizon all
   bundle devices. Switching costs are deliberately high.
3. **Driver scores are black boxes.** Marketing describes "AI-powered safety scores" but rarely
   documents weights, thresholds, missing-data handling or confidence.
4. **Camera data is the dominant risk signal** — and also the biggest privacy exposure. Consent,
   retention and works-council requirements are rarely surfaced in the product UI.
5. **Maintenance is either the whole product (Fleetio) or an afterthought.** Few platforms connect
   maintenance state to driver risk.
6. **Demo data is usually hidden.** Prospects see polished dashboards with no indication that the
   numbers are fake, which sets false expectations.

## 3. Opportunities and gaps

| Gap | Our response |
| --- | --- |
| Opaque pricing | Four published plans (Free, Starter ₹1,499, Professional ₹3,499, Enterprise custom) with vehicle/driver limits and feature lists in the product itself (`/subscriptions`). |
| Black-box scores | Score = weighted category subscores with published weights, renormalisation for missing sensors, per-score confidence, and a model version stamped on every row (`docs/06`). |
| Camera-or-nothing safety | GPS-first behaviour detection (speeding, harsh braking, acceleration, cornering, duration). Camera-derived signals are optional, low-confidence, and only produced from authorised data. |
| No honest demo mode | Every simulator record is labelled `is_simulated`; the UI shows provenance banners, per-row badges and a data-provenance KPI. |
| Lock-in | Open REST API (109 paths) with device-key ingestion, CSV/PDF export, and no proprietary hardware requirement — any GPS tracker that can POST JSON works. |
| Data ownership unclear | Organisation-scoped isolation at query level, exportable reports, explicit retention setting, and a documented deletion path. |
| Maintenance and safety disconnected | Vehicle health and open maintenance alerts feed both the maintenance queue and the risk model. |

## 4. Positioning statement

> SafeWay AI is the driving-safety platform that shows its working: published pricing, explainable
> scores, honest demo data, and no hardware lock-in.

It is aimed at small and mid-sized fleets (10–200 vehicles), school-bus operators, and logistics
companies in India-first markets (INR pricing, vehicle types include bike/van/truck/bus) that are
underserved by enterprise quote-only vendors and over-served by cheap GPS trackers.

## 5. What we deliberately do not compete on

- **Video telematics hardware.** We do not sell cameras or edge devices.
- **Enterprise compliance depth** (ELD, hours-of-service rulesets, IFTA). Out of scope for v1.
- **Predictive accident analytics.** We refuse the category; see [18 — Limitations](18-limitations-and-honesty.md).
