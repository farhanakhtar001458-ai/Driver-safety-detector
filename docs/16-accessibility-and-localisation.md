# 16 — Accessibility and localisation

## 1. Accessibility baseline

| Requirement | Implementation | Status |
| --- | --- | --- |
| Keyboard access | All interactive elements are native `button`/`a`/`input`; modals trap focus and close on Escape | Implemented |
| Focus visibility | `focus:ring-4` on buttons and inputs; visible ring colour per variant | Implemented |
| Labels | Every input is wrapped in a `<label>` via `Field`; icon-only buttons have `aria-label` | Implemented |
| Dialog semantics | `role="dialog"`, `aria-modal="true"`, body scroll lock, Escape to close | Implemented |
| Toggle semantics | `role="switch"` with `aria-checked` | Implemented |
| Live updates | Toasts appear in a region near the bottom-right; connection state is textual, not colour-only | Implemented |
| Colour independence | Status always pairs colour with a text label (e.g. "Critical", "Simulated") | Implemented |
| Contrast | Tailwind palette on white/ink-950; body text `ink-500`+ on light, `ink-300`+ on dark | Reviewed manually, not audited |
| Reduced motion | Not yet honoured | **Gap** |
| Screen-reader audit | Not performed | **Gap** |
| Touch targets | 32–44 px on buttons/inputs; some table row actions are 28 px | Partial |

## 2. Known accessibility gaps

1. **`prefers-reduced-motion` is not respected.** Framer Motion entrances always run.
2. **Charts are not described to screen readers.** Recharts renders SVG without a text alternative; the
   surrounding card title is the only description.
3. **Map interactions are mouse-oriented.** Vehicle selection is possible from the roster list (which is
   keyboard accessible), but the map itself is not.
4. **No skip-to-content link.** Keyboard users tab through the sidebar on every page.
5. **Colour contrast has not been measured with a tool** (axe/Lighthouse). Manual review suggests it
   passes AA for body text, but small 10 px muted text may not.

These belong in the next hardening cycle.

## 3. Localisation

The product is English-only in this build. There is no i18n framework, no string extraction, and no
pluralisation library. All copy lives inline in components.

India-first signals that *are* implemented:

| Signal | Implementation |
| --- | --- |
| Currency | INR (`₹`, `en-IN` number formatting) for plans and maintenance costs |
| Pricing tiers | ₹1,499 / ₹3,499 per month, with a Free tier and custom Enterprise |
| Vehicle types | car, van, truck, bus, bike |
| Demo geography | Bhopal routes and coordinates, `Asia/Kolkata` timezone default |
| Phone format | `+91 …` placeholders |
| Licence classes | LMV, MCWG, HMV, TRANSPORT, PSV |

### Suggested i18n approach

1. Introduce `next-intl` with `[locale]` route segments (`/en/...`, `/hi/...`).
2. Extract strings into message catalogs; start with navigation, KPI labels and form labels.
3. Externalise date/number/currency formatting through `Intl` (already using `toLocaleString("en-IN")`).
4. Translate the disclaimer copy first — it is a safety artefact, not marketing.
5. Add pseudo-localisation to the test suite to catch hardcoded strings.

## 4. Copy principles

- **Say what the data is.** "Simulated telemetry", not "live data".
- **Say what the model is not.** Every risk surface carries a limitation.
- **Prefer verbs for actions.** "Resolve alert", not "OK".
- **Name the consequence.** "Deactivate member — they will lose access immediately."
- **No blame language for drivers.** "Focus areas" and "coaching", never "bad driver".
