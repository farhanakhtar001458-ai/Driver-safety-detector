"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Activity, AlertTriangle, BrainCircuit, Gauge, RefreshCw, Save, Settings2, SlidersHorizontal } from "lucide-react";
import { api, type Paginated } from "@/lib/api";
import type { BehaviourSummary, DrivingEvent, Pattern } from "@/lib/types";
import { Badge, Button, Card, DemoBanner, EmptyState, Field, Input, Modal, PageHeader, PageSkeleton, Select, SimulatedBadge, toast } from "@/components/ui";
import { DataTable, type Column, Pagination } from "@/components/tables/DataTable";
import { EventTypeBarChart, SeverityDonut, TrendAreaChart } from "@/components/charts";
import { cn, EVENT_LABELS, formatKm, formatNumber, severityTone, timeAgo } from "@/lib/format";

const RANGES = [
  { id: "7", label: "7 days" },
  { id: "30", label: "30 days" },
  { id: "90", label: "90 days" },
];

const EVENT_TYPES = [
  ["all", "All event types"],
  ["speeding", "Speeding"],
  ["harsh_braking", "Harsh braking"],
  ["rapid_acceleration", "Rapid acceleration"],
  ["aggressive_cornering", "Aggressive cornering"],
  ["excessive_duration", "Excessive duration"],
  ["seatbelt_violation", "Seatbelt"],
  ["distraction", "Distraction (camera)"],
  ["night_driving", "Night driving"],
];

const SEVERITIES = [
  ["all", "All severities"],
  ["low", "Low"],
  ["medium", "Medium"],
  ["high", "High"],
  ["critical", "Critical"],
];

type Config = {
  thresholds: Record<string, number>;
  defaults: Record<string, number>;
  speed_limits: Record<string, number>;
  note?: string;
};

export default function BehaviourPage() {
  const [days, setDays] = useState(30);
  const [summary, setSummary] = useState<BehaviourSummary | null>(null);
  const [patterns, setPatterns] = useState<{ patterns: Pattern[]; methodology: string; limitations: string[] } | null>(null);
  const [events, setEvents] = useState<DrivingEvent[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [typeFilter, setTypeFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [configOpen, setConfigOpen] = useState(false);
  const [config, setConfig] = useState<Config | null>(null);
  const [thresholds, setThresholds] = useState<Record<string, number>>({});
  const [savingConfig, setSavingConfig] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<DrivingEvent | null>(null);

  const loadSummary = useCallback(async () => {
    setLoading(true);
    try {
      const [summaryData, patternData] = await Promise.all([
        api.get<BehaviourSummary>("/behaviour/summary", { days }),
        api.get<{ patterns: Pattern[]; methodology: string; limitations: string[] }>("/behaviour/patterns", { days }),
      ]);
      setSummary(summaryData);
      setPatterns(patternData);
    } catch {
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }, [days]);

  const loadEvents = useCallback(async () => {
    try {
      const result = await api.get<Paginated<DrivingEvent>>("/behaviour/events", {
        page,
        page_size: 20,
        event_type: typeFilter === "all" ? undefined : typeFilter,
        min_severity: severityFilter === "all" ? undefined : severityFilter,
        days,
      });
      setEvents(result.items ?? []);
      setTotal(result.total ?? 0);
      setPages(result.pages ?? 1);
    } catch {
      setEvents([]);
    }
  }, [page, typeFilter, severityFilter, days]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

  const openConfig = async () => {
    try {
      const result = await api.get<Config>("/behaviour/config");
      setConfig(result);
      setThresholds({ ...(result.thresholds ?? {}) });
      setConfigOpen(true);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not load scoring configuration.", "error");
    }
  };

  const saveConfig = async () => {
    setSavingConfig(true);
    try {
      await api.put("/behaviour/config", thresholds);
      setConfigOpen(false);
      toast("Thresholds updated. They apply to events detected from now on.");
      await loadSummary();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not save configuration.", "error");
    } finally {
      setSavingConfig(false);
    }
  };

  const changedThresholds = Object.entries(thresholds).filter(
    ([key, value]) => config?.thresholds && Number(config.thresholds[key]) !== Number(value),
  ).length;

  const columns: Column<DrivingEvent>[] = [
    {
      key: "type",
      header: "Event",
      render: (row) => (
        <div>
          <p className="text-xs font-semibold capitalize text-ink-900 dark:text-white">{EVENT_LABELS[row.event_type] ?? row.event_type.replace(/_/g, " ")}</p>
          <p className="text-[10px] text-ink-400">{row.driver_name ?? "Unassigned"} · {timeAgo(row.occurred_at)}</p>
        </div>
      ),
    },
    {
      key: "severity",
      header: "Severity",
      render: (row) => <Badge tone={severityTone(row.severity)}>{row.severity}</Badge>,
    },
    {
      key: "speed",
      header: "Speed",
      align: "right",
      render: (row) => (
        <span className="text-xs tabular-nums">
          {row.speed_kph !== null && row.speed_kph !== undefined ? `${row.speed_kph.toFixed(0)} km/h` : "—"}
          {row.speed_limit_kph !== null && row.speed_limit_kph !== undefined && (
            <span className="ml-1 text-[10px] text-rose-500">/ {row.speed_limit_kph}</span>
          )}
        </span>
      ),
    },
    {
      key: "vehicle",
      header: "Vehicle",
      render: (row) => <span className="text-xs text-ink-600 dark:text-ink-300">{row.registration_number ?? "—"}</span>,
    },
    {
      key: "source",
      header: "Source",
      render: (row) => (row.is_simulated ? <SimulatedBadge /> : <Badge tone="bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">Device</Badge>),
    },
  ];

  if (loading && !summary) return <PageSkeleton cards={4} />;

  const trend = (summary?.trend ?? []).map((point) => ({
    label: point.label ?? "",
    events: point.events,
    high_risk: point.high_risk,
  }));

  return (
    <div>
      <PageHeader
        eyebrow="Safety intelligence · behaviour"
        title="Driving behaviour"
        description="Event analysis across speeding, braking, acceleration, cornering and fatigue-related duration. Every event keeps its source."
        actions={
          <>
            <div className="flex rounded-xl bg-ink-100/80 p-1 dark:bg-white/5">
              {RANGES.map((range) => (
                <button
                  key={range.id}
                  onClick={() => setDays(Number(range.id))}
                  className={cn(
                    "rounded-lg px-3 py-1.5 text-xs font-semibold transition",
                    days === Number(range.id) ? "bg-white text-ink-900 shadow-sm dark:bg-white/10 dark:text-white" : "text-ink-500 hover:text-ink-800 dark:text-ink-400",
                  )}
                >
                  {range.label}
                </button>
              ))}
            </div>
            <Button variant="secondary" onClick={() => void openConfig()}>
              <SlidersHorizontal className="h-4 w-4" /> Thresholds
            </Button>
          </>
        }
      />

      <DemoBanner
        message={`${summary?.simulation_share_pct?.toFixed(0) ?? "100"}% of the events in this period come from simulated telemetry. Sensor-derived events (seatbelt, distraction) are only produced where a supported sensor is present.`}
      />

      <div className="page-grid">
        {[
          { label: "Total events", value: formatNumber(summary?.total_events), icon: <Activity className="h-5 w-5" />, hint: `${days}-day window` },
          { label: "High risk", value: formatNumber(summary?.high_risk_events), icon: <AlertTriangle className="h-5 w-5" />, hint: `${formatNumber(summary?.critical_events)} critical` },
          { label: "Events / 100 km", value: summary ? summary.events_per_100km.toFixed(1) : "—", icon: <Gauge className="h-5 w-5" />, hint: `${formatKm(summary?.distance_km ?? 0)} analysed` },
          { label: "Simulated share", value: `${summary?.simulation_share_pct?.toFixed(0) ?? "—"}%`, icon: <BrainCircuit className="h-5 w-5" />, hint: "Data provenance" },
        ].map((stat, index) => (
          <motion.div key={stat.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.04 }} className="card card-hover p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-500 dark:text-ink-400">{stat.label}</p>
                <p className="mt-2 text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">{stat.value}</p>
                <p className="mt-1 text-[11px] text-ink-400">{stat.hint}</p>
              </div>
              <span className="text-brand-500">{stat.icon}</span>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Event trend" subtitle="Volume and high-risk share over time" className="lg:col-span-2">
          <TrendAreaChart data={trend} height={250} />
        </Card>
        <Card title="Severity mix" subtitle="Share of recorded events">
          <SeverityDonut data={summary?.by_severity ?? []} height={250} />
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Event types" subtitle="What drivers are being flagged for" className="lg:col-span-2">
          <EventTypeBarChart
            data={(summary?.by_type ?? []).map((row) => ({ type: EVENT_LABELS[row.event_type] ?? row.event_type, count: row.count }))}
            height={260}
          />
        </Card>
        <Card title="Behaviour patterns" subtitle={patterns?.methodology}>
          {patterns?.patterns.length ? (
            <div className="space-y-3">
              {patterns.patterns.map((pattern) => (
                <div key={pattern.key} className="rounded-xl border border-ink-100 p-3 dark:border-white/10">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-xs font-semibold text-ink-900 dark:text-white">{pattern.title}</p>
                    <Badge tone={severityTone(pattern.severity)}>{pattern.severity}</Badge>
                  </div>
                  <p className="mt-1 text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">{pattern.description}</p>
                  <p className="mt-2 text-[10px] text-ink-400">{pattern.affected_drivers} drivers · confidence {Math.round(pattern.confidence * 100)}%</p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon={<BrainCircuit className="h-5 w-5" />} title="No patterns detected" description="Patterns need enough events in the selected window." />
          )}
          {patterns?.limitations?.length ? (
            <p className="mt-3 text-[10px] leading-relaxed text-ink-400">
              Limitations: {patterns.limitations.join(" ")}
            </p>
          ) : null}
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Most flagged drivers" subtitle="Highest event count in the period" padded={false}>
          {(summary?.top_drivers ?? []).length ? (
            <div className="divide-y divide-ink-100 dark:divide-white/5">
              {summary!.top_drivers.map((row, index) => (
                <div key={row.driver_id} className="flex items-center gap-3 px-4 py-3">
                  <span className="w-4 text-[11px] font-semibold text-ink-400">{index + 1}</span>
                  <p className="flex-1 truncate text-xs font-semibold text-ink-900 dark:text-white">{row.driver_name}</p>
                  <Badge tone="bg-ink-100 text-ink-600 dark:bg-white/10 dark:text-ink-300">{row.events} events</Badge>
                  <Badge tone="bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">{row.high_risk} high risk</Badge>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4"><EmptyState title="No driver ranking" description="Not enough events yet." /></div>
          )}
        </Card>
        <Card title="Most improved / safest drivers" subtitle="Highest safety scores" padded={false}>
          {(summary?.safest_drivers ?? []).length ? (
            <div className="divide-y divide-ink-100 dark:divide-white/5">
              {summary!.safest_drivers.map((row, index) => (
                <div key={row.driver_id} className="flex items-center gap-3 px-4 py-3">
                  <span className="w-4 text-[11px] font-semibold text-ink-400">{index + 1}</span>
                  <p className="flex-1 truncate text-xs font-semibold text-ink-900 dark:text-white">{row.driver_name}</p>
                  <Badge tone="bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">{row.score.toFixed(1)}</Badge>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4"><EmptyState title="No scored drivers" description="Scores appear after enough distance is recorded." /></div>
          )}
        </Card>
      </div>

      <Card padded={false} className="mt-4" title="Event log" subtitle="Every recorded safety event, newest first">
        <div className="flex flex-col justify-between gap-3 border-b border-ink-100 p-4 dark:border-white/5 sm:flex-row">
          <Select value={typeFilter} onChange={(event) => { setTypeFilter(event.target.value); setPage(1); }} className="w-full sm:w-[220px]" aria-label="Event type">
            {EVENT_TYPES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
          </Select>
          <Select value={severityFilter} onChange={(event) => { setSeverityFilter(event.target.value); setPage(1); }} className="w-full sm:w-[170px]" aria-label="Severity">
            {SEVERITIES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
          </Select>
        </div>
        <DataTable
          columns={columns}
          rows={events}
          loading={loading}
          onRowClick={setSelectedEvent}
          emptyTitle="No events match"
          emptyDescription="Widen the filters or increase the time window."
        />
        <Pagination page={page} pages={pages} total={total} onPage={setPage} pageSize={20} />
      </Card>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Card>
          <div className="flex gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300">
              <AlertTriangle className="h-4 w-4" />
            </span>
            <div>
              <h4 className="text-xs font-semibold text-ink-900 dark:text-white">What this page does not claim</h4>
              <p className="mt-1 text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">
                Behaviour scores are coaching inputs, not proof of unsafe character and not a prediction of a future
                crash. Distraction events require authorised camera data and are marked low-confidence unless a person
                reviews them.
              </p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">
              <Settings2 className="h-4 w-4" />
            </span>
            <div>
              <h4 className="text-xs font-semibold text-ink-900 dark:text-white">Thresholds are configurable</h4>
              <p className="mt-1 text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">
                Speed margins, g-force thresholds and scoring weights can be tuned by an organisation admin. Changes
                apply to events processed after the change; historical scores keep their model version.
              </p>
            </div>
          </div>
        </Card>
      </div>

      <Modal
        open={selectedEvent !== null}
        onClose={() => setSelectedEvent(null)}
        title={selectedEvent ? EVENT_LABELS[selectedEvent.event_type] ?? selectedEvent.event_type : "Event"}
        description={selectedEvent ? `${selectedEvent.registration_number ?? "Unassigned"} · ${timeAgo(selectedEvent.occurred_at)}` : ""}
        size="md"
      >
        {selectedEvent && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={severityTone(selectedEvent.severity)}>{selectedEvent.severity}</Badge>
              {selectedEvent.is_simulated ? <SimulatedBadge /> : <Badge tone="bg-emerald-50 text-emerald-700">Device source</Badge>}
              <Badge tone="bg-ink-100 text-ink-600 dark:bg-white/10 dark:text-ink-300">source: {selectedEvent.source}</Badge>
            </div>
            <dl className="grid grid-cols-2 gap-3 text-xs">
              <div><dt className="text-[10px] uppercase tracking-wide text-ink-400">Driver</dt><dd className="font-medium text-ink-900 dark:text-white">{selectedEvent.driver_name ?? "Unassigned"}</dd></div>
              <div><dt className="text-[10px] uppercase tracking-wide text-ink-400">Speed</dt><dd className="font-medium text-ink-900 dark:text-white">{selectedEvent.speed_kph != null ? `${selectedEvent.speed_kph.toFixed(0)} km/h` : "—"}</dd></div>
              <div><dt className="text-[10px] uppercase tracking-wide text-ink-400">Speed limit</dt><dd className="font-medium text-ink-900 dark:text-white">{selectedEvent.speed_limit_kph != null ? `${selectedEvent.speed_limit_kph} km/h` : "—"}</dd></div>
              <div><dt className="text-[10px] uppercase tracking-wide text-ink-400">Recorded</dt><dd className="font-medium text-ink-900 dark:text-white">{new Date(selectedEvent.occurred_at).toLocaleString()}</dd></div>
            </dl>
            {selectedEvent.recommended_action && (
              <div className="rounded-xl bg-brand-50 p-3 text-xs leading-relaxed text-brand-900 dark:bg-brand-500/10 dark:text-brand-100">
                <span className="font-semibold">Recommended action: </span>
                {selectedEvent.recommended_action}
              </div>
            )}
            {selectedEvent.sensor_data && Object.keys(selectedEvent.sensor_data).length > 0 && (
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-ink-400">Sensor payload</p>
                <pre className="max-h-48 overflow-auto rounded-xl bg-ink-950 p-3 text-[10px] leading-relaxed text-ink-200">
                  {JSON.stringify(selectedEvent.sensor_data, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </Modal>

      <Modal
        open={configOpen}
        onClose={() => setConfigOpen(false)}
        title="Scoring configuration"
        description="Weights are renormalised automatically when a sensor category is unavailable."
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfigOpen(false)}>Cancel</Button>
            <Button onClick={saveConfig} loading={savingConfig} disabled={!changedThresholds}>
              <Save className="h-4 w-4" /> Save thresholds
            </Button>
          </>
        }
      >
        {config ? (
          <div className="space-y-5">
            <div className="rounded-xl border border-ink-100 bg-ink-50 p-3 text-[11px] leading-relaxed text-ink-500 dark:border-white/10 dark:bg-white/5 dark:text-ink-400">
              {config.note ?? "Thresholds are organisation-wide and auditable. Changes apply to newly detected events only."}
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-semibold text-ink-900 dark:text-white">Detection thresholds</p>
                <Badge tone={changedThresholds ? "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300" : "bg-ink-100 text-ink-600 dark:bg-white/10 dark:text-ink-300"}>
                  {changedThresholds ? `${changedThresholds} unsaved change${changedThresholds === 1 ? "" : "s"}` : "No changes"}
                </Badge>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {Object.keys(config.thresholds ?? {}).length === 0 ? (
                  <p className="text-xs text-ink-400 sm:col-span-2">No thresholds exposed by the API.</p>
                ) : (
                  Object.keys(config.thresholds).map((key) => (
                    <Field
                      key={key}
                      label={key.replace(/_/g, " ")}
                      hint={config.defaults?.[key] !== undefined ? `Default ${config.defaults[key]}` : undefined}
                    >
                      <Input
                        type="number"
                        step="0.1"
                        min={0.1}
                        max={200}
                        value={thresholds[key] ?? ""}
                        onChange={(event) => setThresholds({ ...thresholds, [key]: Number(event.target.value) })}
                      />
                    </Field>
                  ))
                )}
              </div>
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold text-ink-900 dark:text-white">Speed limits by vehicle type (km/h)</p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {Object.entries(config.speed_limits ?? {}).map(([type, limit]) => (
                  <div key={type} className="rounded-lg bg-ink-50 px-2.5 py-2 dark:bg-white/5">
                    <p className="text-[9px] uppercase tracking-wide text-ink-400">{type}</p>
                    <p className="text-xs font-semibold text-ink-900 dark:text-white">{limit}</p>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-[10px] leading-relaxed text-ink-400">
                Speed limits are reference values for the rule engine. Local law always takes precedence; configure
                thresholds to match the jurisdictions you operate in.
              </p>
            </div>

            <div className="rounded-xl bg-amber-50 p-3 text-[11px] leading-relaxed text-amber-800 dark:bg-amber-500/10 dark:text-amber-200">
              Changing a threshold does not rewrite historical events or scores. Every score stores the model version it
              was computed with, so past reports stay reproducible.
            </div>
          </div>
        ) : (
          <div className="skeleton h-40 w-full" />
        )}
      </Modal>
    </div>
  );
}
