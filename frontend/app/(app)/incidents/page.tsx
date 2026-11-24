"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, CheckCircle2, Clock, FileSearch, MessageSquarePlus, PhoneOff, Plus, Search, ShieldOff } from "lucide-react";
import { api, type Paginated } from "@/lib/api";
import type { Driver, Incident, Vehicle } from "@/lib/types";
import { Badge, Button, Card, DemoBanner, EmptyState, Field, Input, Modal, PageHeader, PageSkeleton, Select, Textarea, toast } from "@/components/ui";
import { DataTable, type Column, Pagination } from "@/components/tables/DataTable";
import { SeverityDonut } from "@/components/charts";
import { cn, formatDate, severityTone, statusTone, timeAgo } from "@/lib/format";

type Summary = {
  total: number;
  open: number;
  under_investigation: number;
  resolved: number;
  false_alerts: number;
  critical: number;
  by_type: { incident_type: string; count: number }[];
  by_severity: { severity: string; count: number }[];
  response_time_hours_avg: number | null;
};

const STATUS_FILTERS = [
  { id: "all", label: "All statuses" },
  { id: "new", label: "New" },
  { id: "under_investigation", label: "Under investigation" },
  { id: "verified", label: "Verified" },
  { id: "resolved", label: "Resolved" },
  { id: "false_alert", label: "False alert" },
];

const SEVERITY_FILTERS = ["all", "minor", "moderate", "severe", "critical"];

const INCIDENT_TYPES = [
  ["collision_suspected", "Collision suspected"],
  ["near_miss", "Near miss"],
  ["harsh_event", "Harsh event"],
  ["breakdown", "Breakdown"],
  ["theft", "Theft"],
  ["geofence_breach", "Geofence breach"],
  ["other", "Other"],
];

const EMPTY_FORM = {
  title: "",
  description: "",
  vehicle_id: "",
  driver_id: "",
  incident_type: "near_miss",
  severity: "moderate",
  occurred_at: "",
  latitude: "",
  longitude: "",
};

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [status, setStatus] = useState("all");
  const [severity, setSeverity] = useState("all");
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [detail, setDetail] = useState<Incident | null>(null);
  const [note, setNote] = useState("");
  const [working, setWorking] = useState(false);
  const [pendingAction, setPendingAction] = useState<"investigate" | "verify" | "resolve" | "false_alert" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, summaryData] = await Promise.all([
        api.get<Paginated<Incident>>("/incidents", {
          page,
          page_size: 20,
          status: status === "all" ? undefined : status,
          severity: severity === "all" ? undefined : severity,
          search: search || undefined,
        }),
        api.get<Summary>("/incidents/summary"),
      ]);
      setIncidents(list.items ?? []);
      setTotal(list.total ?? 0);
      setPages(list.pages ?? 1);
      setSummary(summaryData);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not load incidents.", "error");
    } finally {
      setLoading(false);
    }
  }, [page, status, severity, search]);

  useEffect(() => setPage(1), [status, severity, search]);
  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void (async () => {
      try {
        const [vehicleList, driverList] = await Promise.all([
          api.get<Paginated<Vehicle>>("/vehicles", { page_size: 100 }),
          api.get<Paginated<Driver>>("/drivers", { page_size: 100 }),
        ]);
        setVehicles(vehicleList.items ?? []);
        setDrivers(driverList.items ?? []);
      } catch {
        /* selectors just stay empty */
      }
    })();
  }, []);

  const refreshDetail = async (incident: Incident) => {
    try {
      const fresh = await api.get<Incident>(`/incidents/${incident.id}`);
      setDetail(fresh);
    } catch {
      setDetail(incident);
    }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        title: form.title.trim(),
        incident_type: form.incident_type,
        severity: form.severity,
      };
      if (form.description.trim()) payload.description = form.description.trim();
      if (form.vehicle_id) payload.vehicle_id = Number(form.vehicle_id);
      if (form.driver_id) payload.driver_id = Number(form.driver_id);
      if (form.occurred_at) payload.occurred_at = new Date(form.occurred_at).toISOString();
      if (form.latitude) payload.latitude = Number(form.latitude);
      if (form.longitude) payload.longitude = Number(form.longitude);

      const created = await api.post<Incident>("/incidents", payload);
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      toast("Incident recorded. It is now awaiting review.");
      await load();
      setDetail(created);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not create the incident.", "error");
    } finally {
      setSaving(false);
    }
  };

  const runAction = async (action: "investigate" | "verify" | "resolve" | "false_alert", notes?: string) => {
    if (!detail) return;
    setWorking(true);
    try {
      const updated = await api.post<Incident>(`/incidents/${detail.id}/${action === "false_alert" ? "false-alert" : action}`, {
        notes: notes ?? note.trim() ?? undefined,
      });
      setDetail(updated);
      setNote("");
      setPendingAction(null);
      toast(`Incident ${action.replace("_", " ")} complete.`);
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "The workflow transition was rejected.", "error");
    } finally {
      setWorking(false);
    }
  };

  const addNote = async () => {
    if (!detail || !note.trim()) return;
    setWorking(true);
    try {
      const updated = await api.post<Incident>(`/incidents/${detail.id}/notes`, { note: note.trim() });
      setDetail(updated);
      setNote("");
      toast("Note added to the incident timeline.");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not add the note.", "error");
    } finally {
      setWorking(false);
    }
  };

  const nextActions: Record<string, { id: "investigate" | "verify" | "resolve" | "false_alert"; label: string }[]> = {
    new: [
      { id: "investigate", label: "Start investigation" },
      { id: "verify", label: "Mark verified" },
      { id: "false_alert", label: "Mark false alert" },
    ],
    under_investigation: [
      { id: "verify", label: "Mark verified" },
      { id: "resolve", label: "Resolve" },
      { id: "false_alert", label: "Mark false alert" },
    ],
    verified: [
      { id: "resolve", label: "Resolve" },
      { id: "investigate", label: "Reopen investigation" },
    ],
    resolved: [],
    false_alert: [],
  };

  const columns: Column<Incident>[] = [
    {
      key: "incident",
      header: "Incident",
      render: (row) => (
        <div>
          <p className="text-xs font-semibold text-ink-900 dark:text-white">{row.title}</p>
          <p className="text-[10px] text-ink-400">
            {row.registration_number ?? "No vehicle"} · {row.driver_name ?? "Unassigned"} · {timeAgo(row.occurred_at)}
          </p>
        </div>
      ),
    },
    {
      key: "type",
      header: "Type",
      render: (row) => <span className="text-xs capitalize text-ink-600 dark:text-ink-300">{row.incident_type.replace(/_/g, " ")}</span>,
    },
    {
      key: "severity",
      header: "Severity",
      render: (row) => <Badge tone={severityTone(row.severity === "severe" ? "critical" : row.severity)}>{row.severity}</Badge>,
    },
    {
      key: "status",
      header: "Status",
      render: (row) => <Badge tone={statusTone(row.status)}>{row.status.replace(/_/g, " ")}</Badge>,
    },
    {
      key: "reporter",
      header: "Reported by",
      render: (row) => <span className="text-xs text-ink-600 dark:text-ink-300">{row.reporter_name ?? "—"}</span>,
    },
  ];

  if (loading && !incidents.length) return <PageSkeleton cards={4} />;

  return (
    <div>
      <PageHeader
        eyebrow="Response · workflow"
        title="Incidents"
        description="Report, investigate, verify and resolve safety incidents. Every transition is permission-checked and audit-logged."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" /> Report incident
          </Button>
        }
      />

      <DemoBanner message="Incident records created here are real rows in this database, but any incident seeded by the demo dataset is simulated and labelled in the evidence field." />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {[
          { label: "Total incidents", value: summary?.total ?? 0, icon: <AlertTriangle className="h-5 w-5" /> },
          { label: "Open", value: summary?.open ?? 0, icon: <Clock className="h-5 w-5" />, accent: true },
          { label: "Under investigation", value: summary?.under_investigation ?? 0, icon: <FileSearch className="h-5 w-5" /> },
          { label: "Resolved", value: summary?.resolved ?? 0, icon: <CheckCircle2 className="h-5 w-5" /> },
          { label: "False alerts", value: summary?.false_alerts ?? 0, icon: <ShieldOff className="h-5 w-5" /> },
        ].map((stat) => (
          <Card key={stat.label} className="p-4">
            <div className="flex items-start justify-between gap-2">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-500 dark:text-ink-400">{stat.label}</p>
              <span className="text-ink-400">{stat.icon}</span>
            </div>
            <p className={cn("mt-2 text-2xl font-semibold tracking-tight", stat.accent ? "text-amber-600" : "text-ink-950 dark:text-white")}>
              {stat.value}
            </p>
          </Card>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Severity mix" subtitle="All incidents in the organisation" className="lg:col-span-1">
          <SeverityDonut
            data={(summary?.by_severity ?? []).map((row) => ({ severity: row.severity, count: row.count }))}
            height={220}
          />
        </Card>
        <Card title="Incident types" subtitle="What is being reported" className="lg:col-span-1">
          <div className="space-y-2.5">
            {(summary?.by_type ?? []).length ? (
              summary!.by_type.map((row) => {
                const max = Math.max(...summary!.by_type.map((item) => item.count), 1);
                return (
                  <div key={row.incident_type} className="flex items-center gap-3">
                    <span className="w-28 truncate text-[11px] capitalize text-ink-600 dark:text-ink-300">{row.incident_type.replace(/_/g, " ")}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-100 dark:bg-white/10">
                      <div className="h-full rounded-full bg-brand-500" style={{ width: `${(row.count / max) * 100}%` }} />
                    </div>
                    <span className="w-6 text-right text-[11px] font-semibold">{row.count}</span>
                  </div>
                );
              })
            ) : (
              <EmptyState title="No incidents" description="Nothing reported yet." />
            )}
          </div>
        </Card>
        <Card title="Response performance" subtitle="Time from occurrence to resolution">
          <div className="rounded-2xl bg-ink-50 p-4 dark:bg-white/5">
            <p className="text-[10px] uppercase tracking-wide text-ink-400">Average response time</p>
            <p className="mt-1 text-2xl font-semibold text-ink-950 dark:text-white">
              {summary?.response_time_hours_avg != null ? `${summary.response_time_hours_avg} h` : "—"}
            </p>
            <p className="mt-1 text-[10px] leading-relaxed text-ink-400">
              Measured on resolved incidents only. A missing value means nothing has been resolved yet.
            </p>
          </div>
          <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-[11px] leading-relaxed text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
            <PhoneOff className="mb-1 h-3.5 w-3.5" />
            SafeWay AI never contacts emergency services automatically. Any escalation must be initiated by a person.
          </div>
        </Card>
      </div>

      <Card padded={false} className="mt-4" title="Incident register" subtitle="Newest first">
        <div className="flex flex-col justify-between gap-3 border-b border-ink-100 p-4 dark:border-white/5 lg:flex-row lg:items-center">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search title, vehicle, driver…" className="pl-9" aria-label="Search incidents" />
          </div>
          <div className="flex flex-wrap gap-2">
            <Select value={status} onChange={(event) => setStatus(event.target.value)} className="w-[180px]" aria-label="Status">
              {STATUS_FILTERS.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
            </Select>
            <Select value={severity} onChange={(event) => setSeverity(event.target.value)} className="w-[140px]" aria-label="Severity">
              {SEVERITY_FILTERS.map((option) => (
                <option key={option} value={option}>{option === "all" ? "All severities" : option}</option>
              ))}
            </Select>
          </div>
        </div>
        <DataTable
          columns={columns}
          rows={incidents}
          loading={loading}
          onRowClick={setDetail}
          emptyTitle="No incidents match"
          emptyDescription="Adjust the filters, or report a new incident."
        />
        <Pagination page={page} pages={pages} total={total} onPage={setPage} pageSize={20} />
      </Card>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Report incident"
        description="Recording an incident does not notify emergency services. It creates an auditable review item."
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={submit} loading={saving}>Record incident</Button>
          </>
        }
      >
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field label="Title" required>
              <Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required minLength={3} maxLength={200} placeholder="Harsh braking near MP Nagar junction" />
            </Field>
          </div>
          <Field label="Incident type" required>
            <Select value={form.incident_type} onChange={(event) => setForm({ ...form, incident_type: event.target.value })}>
              {INCIDENT_TYPES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </Select>
          </Field>
          <Field label="Severity" required>
            <Select value={form.severity} onChange={(event) => setForm({ ...form, severity: event.target.value })}>
              {["minor", "moderate", "severe", "critical"].map((option) => <option key={option} value={option}>{option}</option>)}
            </Select>
          </Field>
          <Field label="Vehicle">
            <Select value={form.vehicle_id} onChange={(event) => setForm({ ...form, vehicle_id: event.target.value })}>
              <option value="">Unspecified</option>
              {vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicle.registration_number}</option>)}
            </Select>
          </Field>
          <Field label="Driver">
            <Select value={form.driver_id} onChange={(event) => setForm({ ...form, driver_id: event.target.value })}>
              <option value="">Unspecified</option>
              {drivers.map((driver) => <option key={driver.id} value={driver.id}>{driver.full_name}</option>)}
            </Select>
          </Field>
          <Field label="Occurred at">
            <Input type="datetime-local" value={form.occurred_at} onChange={(event) => setForm({ ...form, occurred_at: event.target.value })} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Latitude">
              <Input type="number" step="0.000001" value={form.latitude} onChange={(event) => setForm({ ...form, latitude: event.target.value })} placeholder="23.2599" />
            </Field>
            <Field label="Longitude">
              <Input type="number" step="0.000001" value={form.longitude} onChange={(event) => setForm({ ...form, longitude: event.target.value })} placeholder="77.4126" />
            </Field>
          </div>
          <div className="sm:col-span-2">
            <Field label="Description">
              <Textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="What happened, in factual terms. Attach evidence in the detail view." />
            </Field>
          </div>
          <button type="submit" className="hidden" aria-hidden="true" />
        </form>
      </Modal>

      <Modal
        open={detail !== null}
        onClose={() => { setDetail(null); setNote(""); setPendingAction(null); }}
        title={detail?.title ?? "Incident"}
        description={detail ? `${detail.incident_type.replace(/_/g, " ")} · ${timeAgo(detail.occurred_at)} · reported by ${detail.reporter_name ?? "unknown"}` : ""}
        size="lg"
        footer={
          detail ? (
            <>
              <Button variant="secondary" onClick={() => { setDetail(null); setNote(""); setPendingAction(null); }}>Close</Button>
              {nextActions[detail.status]?.map((action) => (
                <Button
                  key={action.id}
                  variant={action.id === "false_alert" ? "secondary" : "primary"}
                  onClick={() => setPendingAction(action.id)}
                >
                  {action.label}
                </Button>
              ))}
            </>
          ) : null
        }
      >
        {detail && (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={severityTone(detail.severity === "severe" ? "critical" : detail.severity)}>{detail.severity}</Badge>
              <Badge tone={statusTone(detail.status)}>{detail.status.replace(/_/g, " ")}</Badge>
              {detail.evidence?.some((item) => item.is_simulated) && (
                <Badge tone="bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">Simulated evidence</Badge>
              )}
            </div>

            <div className="rounded-xl border border-ink-100 bg-ink-50 p-3 text-xs leading-relaxed text-ink-600 dark:border-white/10 dark:bg-white/5 dark:text-ink-300">
              <p className="mb-1 flex items-center gap-1.5 font-semibold text-ink-800 dark:text-ink-100">
                <ArrowRight className="h-3.5 w-3.5" /> Workflow status
              </p>
              <p>
                New → Under investigation → Verified → Resolved. A false alert closes the record without resolution credit.
                Transitions are validated server-side; invalid jumps return an error rather than silently succeeding.
              </p>
            </div>

            <dl className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
              {[
                ["Vehicle", detail.registration_number ?? "—"],
                ["Driver", detail.driver_name ?? "—"],
                ["Occurred", new Date(detail.occurred_at).toLocaleString()],
                ["Location", detail.latitude && detail.longitude ? `${detail.latitude.toFixed(4)}, ${detail.longitude.toFixed(4)}` : "Not recorded"],
                ["Verified", detail.verified_at ? formatDate(detail.verified_at) : "Not yet"],
                ["Resolved", detail.resolved_at ? formatDate(detail.resolved_at) : "Not yet"],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-[10px] uppercase tracking-wide text-ink-400">{label}</dt>
                  <dd className="mt-0.5 font-medium text-ink-800 dark:text-ink-100">{value}</dd>
                </div>
              ))}
            </dl>

            {detail.description && (
              <div>
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ink-400">Description</p>
                <p className="text-xs leading-relaxed text-ink-700 dark:text-ink-200">{detail.description}</p>
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ink-400">Investigation notes</p>
                <div className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded-xl bg-ink-50 p-3 text-[11px] leading-relaxed text-ink-600 dark:bg-white/5 dark:text-ink-300">
                  {detail.investigation_notes || "No investigation notes yet."}
                </div>
              </div>
              <div>
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ink-400">Resolution notes</p>
                <div className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded-xl bg-ink-50 p-3 text-[11px] leading-relaxed text-ink-600 dark:bg-white/5 dark:text-ink-300">
                  {detail.resolution_notes || "Not resolved."}
                </div>
              </div>
            </div>

            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ink-400">Evidence</p>
              {detail.evidence?.length ? (
                <div className="space-y-1.5">
                  {detail.evidence.map((item, index) => (
                    <div key={index} className="flex items-center gap-2 rounded-lg bg-ink-50 px-2.5 py-2 text-[11px] dark:bg-white/5">
                      <span className="font-medium text-ink-800 dark:text-ink-100">{String(item.type ?? item.kind ?? "evidence")}</span>
                      {Boolean(item.is_simulated) && <Badge tone="bg-amber-50 text-amber-700">Simulated</Badge>}
                      {typeof item.summary === "string" && <span className="truncate text-ink-500">{String(item.summary)}</span>}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-ink-400">No evidence attached.</p>
              )}
            </div>

            <div>
              <Field label="Add a note" hint="Notes are timestamped and attributed to you.">
                <Textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Factual observation, action taken, or follow-up owner…" />
              </Field>
              <div className="mt-2 flex justify-end">
                <Button size="sm" variant="secondary" onClick={addNote} loading={working} disabled={!note.trim()}>
                  <MessageSquarePlus className="h-3.5 w-3.5" /> Add note
                </Button>
              </div>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={pendingAction !== null}
        onClose={() => setPendingAction(null)}
        title={
          pendingAction === "investigate" ? "Start investigation" :
          pendingAction === "verify" ? "Mark as verified" :
          pendingAction === "resolve" ? "Resolve incident" : "Mark as false alert"
        }
        description="This transition is recorded in the audit log with your user identity."
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setPendingAction(null)}>Cancel</Button>
            <Button
              variant={pendingAction === "false_alert" ? "secondary" : "primary"}
              onClick={() => runAction(pendingAction!)}
              loading={working}
            >
              Confirm
            </Button>
          </>
        }
      >
        <Field label="Notes for this transition" hint="Optional, but recommended for anything beyond a routine step.">
          <Textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="What did you check? What was decided?" />
        </Field>
        {pendingAction === "resolve" && (
          <p className="mt-3 rounded-lg bg-ink-50 px-3 py-2 text-[11px] text-ink-500 dark:bg-white/5 dark:text-ink-400">
            Resolving closes the record. Reopen it later by starting a new investigation if new evidence appears.
          </p>
        )}
      </Modal>
    </div>
  );
}
