# 07 — Frontend and design system

## 1. Stack

| Concern | Choice | Why |
| --- | --- | --- |
| Framework | Next.js 14.2, App Router | File-system routing, server rendering for fast first paint, API rewrites for same-origin calls |
| Language | TypeScript (strict) | End-to-end types mirroring API schemas |
| Styling | Tailwind CSS 3.4 | Utility-first with a small design-token layer |
| Animation | Framer Motion | Page/section entrance, modal springs, active-nav indicator |
| Charts | Recharts 2.13 | Composable, React-native SVG, good tooltips |
| Maps | Leaflet 1.9 + react-leaflet 4 | OpenStreetMap tiles, no API key, circle/polyline support |
| Icons | Lucide React | Consistent 1.5px stroke icon set |
| State | React context for auth/theme, local state per page | No global cache to invalidate at this scale |

## 2. Design tokens

Defined in `tailwind.config.ts`:

| Token | Value | Use |
| --- | --- | --- |
| `brand-50…900` | Teal ramp, `#0dab99` primary | Primary actions, links, live indicators |
| `ink-50…950` | Slate ramp | Neutrals, text, borders |
| `shadow-card` | `0 1px 2px rgba(15,23,42,.06), 0 8px 24px -12px rgba(15,23,42,.18)` | Resting surfaces |
| `shadow-pop` | Deeper shadow with blur | Modals, dropdowns, toasts |
| `animate-fade-up` | 400 ms rise + fade | Section entrances |
| `animate-shimmer` | 1.4 s sweep | Skeleton loading |

Semantic colours: emerald = healthy/positive, amber = attention/simulated, rose = critical/danger,
indigo = informational/AI. **Amber is reserved for provenance and caution**, so a simulated badge is never
confused with a healthy status.

## 3. Component inventory (`components/ui/index.tsx`)

| Component | Purpose |
| --- | --- |
| `Button` | primary / secondary / ghost / danger, loading spinner, optional `href` |
| `Card` | Surface with optional title, subtitle, action |
| `StatCard` | KPI tile with icon tone, hint, entrance animation |
| `Badge`, `SeverityBadge`, `SimulatedBadge` | Status chips; the simulated badge is visually distinct (dashed amber) |
| `Modal`, `ConfirmDialog` | Accessible dialogs with escape/overlay close, sticky header/footer |
| `Field`, `Input`, `Textarea`, `Select` | Form primitives with label, hint, error |
| `Switch` | Boolean toggle used for team active state and notification channels |
| `Tabs` | Segmented control (settings, report type) |
| `PageHeader` | Eyebrow, title, description, actions |
| `EmptyState` | Icon, title, description, optional action — never a blank area |
| `Avatar` | Initials with per-driver colour |
| `ProgressBar`, `CategoryBars`, `ScoreRing`, `Sparkline` | Data display |
| `DataTable`, `Pagination` | Tabular data with loading skeleton, empty state, page controls |
| `ToastHost`, `toast()` | Non-blocking feedback |
| `PageSkeleton` | Layout-matched loading state |
| `DemoBanner` | Provenance warning used on every data page |

## 4. Routes

| Route | Page | Primary data |
| --- | --- | --- |
| `/` | Redirect | — |
| `/login`, `/register` | Authentication | `/auth/*` |
| `/overview` | Command centre | `/dashboard`, `/gps/live` (WS) |
| `/tracking` | Live map | `/gps/live`, `/gps/trails`, `/gps/geofences`, `/behaviour/events` |
| `/vehicles` | Asset register | `/vehicles`, `/vehicles/{id}/overview` |
| `/drivers` | People & scores | `/drivers`, `/drivers/{id}/scores` |
| `/behaviour` | Event analytics | `/behaviour/*` |
| `/risk` | Risk triage | `/risk/*` |
| `/incidents` | Response workflow | `/incidents/*` |
| `/maintenance` | Health & service | `/maintenance/*` |
| `/reports` | Exports | `/reports/*` |
| `/road-safety` | External context | `/intelligence/*` |
| `/notifications` | Inbox & preferences | `/notifications/*` |
| `/assistant` | Grounded chat | `/assistant/*` |
| `/settings` | Org, team, security, audit | `/organisations/*`, `/audit-logs` |
| `/subscriptions` | Plans & billing | `/subscriptions/*` |
| `/not-found`, `global-error` | Error boundaries | — |

## 5. Data-fetching conventions

```ts
const load = useCallback(async () => {
  setLoading(true);
  try {
    const result = await api.get<DashboardData>("/dashboard", { days });
    setData(result);
  } catch (err) {
    setError(err instanceof Error ? err.message : "Could not load the dashboard.");
  } finally {
    setLoading(false);
  }
}, [days]);

useEffect(() => { void load(); }, [load]);
```

Rules followed on every page:

- Skeleton on first load, inline error with a Retry action on failure.
- Loading state never blanks existing content (only the initial load shows a full skeleton).
- Empty states are written for the specific module, not generic.
- Every page that displays telemetry renders `DemoBanner`.

## 6. Live telemetry hook

`useLiveFleet(enabled, intervalMs)`:

1. Opens `wss://<host>/api/v1/ws/fleet?token=<jwt>`.
2. On `fleet_snapshot` / `fleet_update` frames, updates state and stamps `lastUpdated`.
3. After two failed socket attempts, starts polling `GET /gps/live` every 5 s and reports
   `connection: "polling"`.
4. Cleans up the socket and interval on unmount.

Pages render the connection state as a labelled dot: green = WebSocket, teal = polling fallback, amber =
connecting, rose = error. The user can always tell whether they are seeing a stream or a poll.

## 7. Forms and validation

- Client-side: `required`, `minLength`, `min`/`max`, `type=email`, `pattern` where useful.
- Server-side: Pydantic validators return 422 with a readable `detail`.
- Errors render inline next to the field when field-scoped, otherwise as a toast and an alert block.
- Submit buttons show a spinner and are disabled while in flight to prevent double posts.
- Destructive actions (delete, deactivate, cancel subscription) require an explicit confirmation dialog.

## 8. Responsiveness

| Breakpoint | Layout |
| --- | --- |
| `< 640px` | Single column, sidebar off-canvas, tables scroll horizontally, stat grids 2-up |
| `640–1024px` | 2-up grids, topbar search visible, sidebar off-canvas |
| `> 1024px` | Fixed 288 px sidebar, 3–4 up grids, two-column detail layouts |
| `> 1280px` | Asymmetric grids (map + side panel), wider page container (max 1600 px) |

## 9. Performance notes

- Shared JS is 88 kB; the heaviest route (charts + map) is 259 kB first load.
- Leaflet is dynamically imported with `ssr: false` so it never runs on the server and never blocks
  pre-rendering.
- Charts are only rendered on pages that need them.
- No client-side animation library is loaded on auth pages.

## 10. Known frontend gaps

- No i18n layer; all copy is English (see [16](16-accessibility-and-localisation.md)).
- No end-to-end browser test suite (no browser available in the build environment); unit tests cover
  formatters, API client behaviour, component labelling and score bands.
- Maps require internet access to load OpenStreetMap tiles; there is no offline tile bundle.
- `next lint` is not configured (ESLint is not installed) — type-checking via `tsc --noEmit` is the gate.
