"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CalendarClock,
  CircleDollarSign,
  Gauge,
  Plus,
  RefreshCw,
  Wrench,
} from "lucide-react";
import { api, type Paginated } from "@/lib/api";
import type { MaintenanceAlert, MaintenanceRecord, Vehicle, VehicleHealth } from "@/lib/types";
import { Badge, Button, Card, ConfirmDialog, DemoBanner, EmptyState, Field, Input, Modal, PageHeader, PageSkeleton, Select, SimulatedBadge, Textarea, toast } from "@/components/ui";
import { DataTable, type Column, Pagination } from "@/components/tables/DataTable";
import { CategoryBars } from "@/components/charts";
import { cn, formatKm, formatNumber, severityTone, timeAgo } from "@/lib/format";

type ScheduleRow = {
  vehicle_id: number;
  registration_number: string;
  status: string;
  mileage_km: number;
  next_service_km: number | null;
  due_in_km: number | null;
  last_service_at: string | null;
  open_alerts: number;
  urgency: string;
};

type PredictionComponent = { component: string; probability: number; basis?: string };

type Prediction = {
  vehicle_id: number;
  registration_number: string;
  method?: string;
  failure_probability: number;
  risk_level: string;
  components: PredictionComponent[];
  estimated_cost: number | null;
  cost_note?: string;
  recommendation: string;
  recommendations?: { type: string; priority: string; title: string; reason: string }[];
  confidence?: number;
  data_sources: string[];
  is_simulated: boolean;
  disclaimer: string;
};

const RECORD_TYPES = ["service", "repair", "inspection", "tyre", "battery", "other"];

const EMPTY_FORM = {
  vehicle_id: "",
  record_type: "service",
  title: "",
  description: "",
  odometer_km: "",
  cost: "",
  vendor: "",
  next_due_km: "",
  next_due_date: "",
  performed_at: "",
};

export default function MaintenancePage() {
  const [alerts, setAlerts] = useState<MaintenanceAlert[]>([]);
  const [health, setHealth] = useState<VehicleHealth[]>([]);
  const [schedule, setSchedule] = useState<ScheduleRow[]>([]);
  const [records, setRecords] = useState<MaintenanceRecord[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [resolving, setResolving] = useState<MaintenanceAlert | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [predicting, setPredicting] = useState<number | null>(null);
  const [predictionFor, setPredictionFor] = useState<Vehicle | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [alertData, healthData, scheduleData, recordData, vehicleData] = await Promise.all([
        api.get<Paginated<MaintenanceAlert>>("/maintenance/alerts", { page_size: 50, status: statusFilter === "all" ? undefined : statusFilter }),
        api.get<VehicleHealth[]>("/maintenance/health"),
        api.get<ScheduleRow[]>("/maintenance/schedule"),
        api.get<Paginated<MaintenanceRecord>>("/maintenance/records", { page, page_size: 10 }),
        api.get<Paginated<Vehicle>>("/vehicles", { page_size: 100 }),
      ]);
      setAlerts(alertData.items ?? []);
      setHealth(healthData ?? []);
      setSchedule(scheduleData ?? []);
      setRecords(recordData.items ?? []);
      setTotal(recordData.total ?? 0);
      setPages(recordData.pages ?? 1);
      setVehicles(vehicleData.items ?? []);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not load maintenance data.", "error");
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const resolveAlert = async () => {
    if (!resolving) return;
    setSaving(true);
    try {
      await api.post(`/maintenance/alerts/${resolving.id}/resolve`, {});
      setResolving(null);
      toast("Alert resolved.");
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not resolve the alert.", "error");
    } finally {
      setSaving(false);
    }
  };

  const runPrediction = async (vehicle: Vehicle) => {
    setPredicting(vehicle.id);
    setPredictionFor(vehicle);
    setPrediction(null);
    try {
      const result = await api.post<Prediction>(`/maintenance/predict/${vehicle.id}`, {});
      setPrediction(result);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Prediction failed.", "error");
    } finally {
      setPredicting(null);
    }
  };

  const submitRecord = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        vehicle_id: Number(form.vehicle_id),
        record_type: form.record_type,
        title: form.title.trim(),
        odometer_km: Number(form.odometer_km) || 0,
        cost: Number(form.cost) || 0,
        status: "completed",
      };
      if (form.description.trim()) payload.description = form.description.trim();
      if (form.vendor.trim()) payload.vendor = form.vendor.trim();
      if (form.next_due_km) payload.next_due_km = Number(form.next_due_km);
      if (form.next_due_date) payload.next_due_date = form.next_due_date;
      if (form.performed_at) payload.performed_at = new Date(form.performed_at).toISOString();

      await api.post("/maintenance/records", payload);
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      toast("Maintenance record added.");
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not save the record.", "error");
    } finally {
      setSaving(false);
    }
  };

  const openAlerts = alerts.filter((alert) => alert.status !== "resolved").length;
  const criticalAlerts = alerts.filter((alert) => alert.severity === "critical" || alert.severity === "high").length;
  const overdue = schedule.filter((row) => row.urgency === "overdue").length;
  const simulatedHealth = health.filter((row) => row.is_simulated).length;

  const alertColumns: Column<MaintenanceAlert>[] = [
    {
      key: "title",
      header: "Alert",
      render: (row) => (
        <div>
          <p className="text-xs font-semibold text-ink-900 dark:text-white">{row.title}</p>
          <p className="text-[10px] text-ink-400">{row.registration_number ?? "Unassigned"} · {timeAgo(row.created_at)}</p>
        </div>
      ),
    },
    { key: "type", header: "Type", render: (row) => <span className="text-xs capitalize text-ink-600 dark:text-ink-300">{row.alert_type.replace(/_/g, " ")}</span> },
    { key: "severity", header: "Severity", render: (row) => <Badge tone={severityTone(row.severity)}>{row.severity}</Badge> },
    { key: "cost", header: "Est. cost", align: "right", render: (row) => <span className="text-xs tabular-nums">{row.estimated_cost != null ? `₹${Math.round(row.estimated_cost).toLocaleString("en-IN")}` : "—"}</span> },
    {
      key: "status",
      header: "Status",
      render: (row) =>
        row.status === "resolved" ? (
          <Badge tone="bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">Resolved</Badge>
        ) : (
          <Button size="sm" variant="secondary" onClick={() => setResolving(row)}>Resolve</Button>
        ),
    },
  ];

  if (loading && !alerts.length) return <PageSkeleton cards={4} />;

  return (
    <div>
      <PageHeader
        eyebrow="Assets · health"
        title="Maintenance & vehicle health"
        description="Diagnostic readings, service schedule and predictive component risk. Real device data and simulator data are always distinguishable."
        actions={
          <>
            <Button variant="secondary" onClick={() => void load()}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" /> Add record
            </Button>
          </>
        }
      />

      <DemoBanner
        message={`${simulatedHealth} of ${health.length} health readings are simulator-generated. Predictive component risk is illustrative in this deployment and must not be used to postpone a manufacturer-recommended service.`}
      />

      <div className="page-grid">
        {[
          { label: "Open alerts", value: openAlerts, icon: <AlertTriangle className="h-5 w-5" />, hint: `${criticalAlerts} high or critical` },
          { label: "Vehicles tracked", value: health.length, icon: <Activity className="h-5 w-5" />, hint: `${simulatedHealth} simulated readings` },
          { label: "Service overdue", value: overdue, icon: <CalendarClock className="h-5 w-5" />, hint: "By mileage or date" },
          { label: "Avg health score", value: health.length ? (health.reduce((sum, row) => sum + row.health_score, 0) / health.length).toFixed(1) : "—", icon: <Gauge className="h-5 w-5" />, hint: "0–100 diagnostic score" },
        ].map((stat) => (
          <Card key={stat.label} className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-500 dark:text-ink-400">{stat.label}</p>
                <p className="mt-2 text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">{stat.value}</p>
                <p className="mt-1 text-[11px] text-ink-400">{stat.hint}</p>
              </div>
              <span className="text-ink-400">{stat.icon}</span>
            </div>
          </Card>
        ))}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Card padded={false} title="Vehicle diagnostics" subtitle="Latest health reading per vehicle">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px]">
              <thead className="border-b border-ink-100 dark:border-white/5">
                <tr>
                  <th className="table-th">Vehicle</th>
                  <th className="table-th">Health</th>
                  <th className="table-th">Engine</th>
                  <th className="table-th">Fuel</th>
                  <th className="table-th">Fault codes</th>
                  <th className="table-th">Data</th>
                  <th className="table-th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100 dark:divide-white/5">
                {health.map((row) => (
                  <tr key={row.vehicle_id} className="hover:bg-ink-50/70 dark:hover:bg-white/[0.04]">
                    <td className="table-td">
                      <p className="text-xs font-semibold text-ink-900 dark:text-white">{row.registration_number}</p>
                      <p className="text-[10px] text-ink-400">{formatKm(row.mileage_km)}</p>
                    </td>
                    <td className="table-td">
                      <div className="flex items-center gap-2">
                        <span className={cn("text-xs font-semibold", row.health_score >= 80 ? "text-emerald-600" : row.health_score >= 60 ? "text-amber-600" : "text-rose-600")}>
                          {row.health_score.toFixed(0)}
                        </span>
                        <div className="h-1.5 w-14 overflow-hidden rounded-full bg-ink-100 dark:bg-white/10">
                          <div
                            className={cn("h-full rounded-full", row.health_score >= 80 ? "bg-emerald-500" : row.health_score >= 60 ? "bg-amber-500" : "bg-rose-500")}
                            style={{ width: `${row.health_score}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="table-td text-xs">{row.engine_temperature_c != null ? `${row.engine_temperature_c.toFixed(0)} °C` : "—"}</td>
                    <td className="table-td text-xs">{row.fuel_level_pct != null ? `${row.fuel_level_pct.toFixed(0)}%` : "—"}</td>
                    <td className="table-td">
                      {row.fault_codes.length ? (
                        <span className="font-mono text-[10px] text-rose-600">{row.fault_codes.join(", ")}</span>
                      ) : (
                        <span className="text-ink-400">None</span>
                      )}
                    </td>
                    <td className="table-td">{row.is_simulated ? <SimulatedBadge /> : <Badge tone="bg-emerald-50 text-emerald-700">Device</Badge>}</td>
                    <td className="table-td text-right">
                      <Button size="sm" variant="ghost" onClick={() => runPrediction(vehicles.find((vehicle) => vehicle.id === row.vehicle_id) ?? { id: row.vehicle_id } as Vehicle)} loading={predicting === row.vehicle_id}>
                        Predict
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card title="Predictive maintenance" subtitle="Component risk for one vehicle" padded={false}>
          <div className="p-4">
            {prediction ? (
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-3 rounded-xl bg-ink-50 p-3 dark:bg-white/5">
                  <div>
                    <p className="text-xs font-semibold text-ink-900 dark:text-white">{prediction.registration_number}</p>
                    <p className="text-[10px] text-ink-400">Risk level: <span className="font-semibold capitalize">{prediction.risk_level}</span></p>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-semibold text-ink-950 dark:text-white">{(prediction.failure_probability * 100).toFixed(0)}%</p>
                    <p className="text-[9px] uppercase tracking-wide text-ink-400">failure prob.</p>
                  </div>
                </div>
                <CategoryBars
                  categories={(prediction.components ?? []).map((component) => ({
                    key: component.component,
                    label: component.component.replace(/_/g, " "),
                    value: Math.max(0, 100 - component.probability * 100),
                  }))}
                />
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-[11px] leading-relaxed text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
                  {prediction.disclaimer}
                </div>
                <p className="text-[10px] leading-relaxed text-ink-400">
                  Data sources: {prediction.data_sources?.length ? prediction.data_sources.join(", ") : "no diagnostic data"}.{" "}
                  {prediction.estimated_cost === null || prediction.estimated_cost === undefined
                    ? "Cost estimate not available."
                    : `Estimated cost ₹${Math.round(prediction.estimated_cost).toLocaleString("en-IN")}.`}
                </p>
              </div>
            ) : (
              <EmptyState
                icon={<Wrench className="h-5 w-5" />}
                title="No prediction yet"
                description="Choose Predict on a vehicle row to estimate component failure probability from health and service history."
              />
            )}
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card padded={false} title="Maintenance alerts" subtitle="Open and resolved alerts">
          <DataTable
            columns={alertColumns}
            rows={alerts}
            loading={loading}
            emptyTitle="No maintenance alerts"
            emptyDescription="Alerts appear when diagnostic readings or schedules breach a threshold."
            minWidth={620}
          />
        </Card>

        <Card padded={false} title="Service schedule" subtitle="Next service by mileage">
          <div className="max-h-[380px] overflow-y-auto">
            <table className="w-full min-w-[520px]">
              <thead className="border-b border-ink-100 dark:border-white/5">
                <tr>
                  <th className="table-th">Vehicle</th>
                  <th className="table-th">Next service</th>
                  <th className="table-th">Urgency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100 dark:divide-white/5">
                {schedule.map((row) => (
                  <tr key={row.vehicle_id} className="hover:bg-ink-50/70 dark:hover:bg-white/[0.04]">
                    <td className="table-td">
                      <p className="text-xs font-semibold text-ink-900 dark:text-white">{row.registration_number}</p>
                      <p className="text-[10px] text-ink-400">{formatKm(row.mileage_km)}</p>
                    </td>
                    <td className="table-td text-xs">{row.next_service_km != null ? formatKm(row.next_service_km) : "Not set"}</td>
                    <td className="table-td">
                      <Badge
                        tone={
                          row.urgency === "overdue"
                            ? "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300"
                            : row.urgency === "due_soon"
                              ? "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"
                              : "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300"
                        }
                      >
                        {row.urgency.replace("_", " ")}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <Card padded={false} className="mt-4" title="Service history" subtitle="Recorded maintenance work">
        <DataTable
          columns={[
            {
              key: "title",
              header: "Record",
              render: (row) => (
                <div>
                  <p className="text-xs font-semibold text-ink-900 dark:text-white">{row.title}</p>
                  <p className="text-[10px] text-ink-400">{row.vendor ? `${row.vendor} · ` : ""}{new Date(row.performed_at).toLocaleDateString()}</p>
                </div>
              ),
            },
            { key: "type", header: "Type", render: (row) => <span className="text-xs capitalize text-ink-600 dark:text-ink-300">{row.record_type}</span> },
            { key: "odometer", header: "Odometer", align: "right", render: (row) => <span className="text-xs tabular-nums">{formatKm(row.odometer_km)}</span> },
            { key: "cost", header: "Cost", align: "right", render: (row) => <span className="text-xs tabular-nums">₹{Math.round(row.cost).toLocaleString("en-IN")}</span> },
            {
              key: "next",
              header: "Next due",
              render: (row) => <span className="text-xs text-ink-500">{row.next_due_km ? formatKm(row.next_due_km) : row.next_due_date ? new Date(row.next_due_date).toLocaleDateString() : "—"}</span>,
            },
          ]}
          rows={records}
          loading={loading}
          emptyTitle="No service records"
          emptyDescription="Add a record when work is completed."
          minWidth={640}
        />
        <Pagination page={page} pages={pages} total={total} onPage={setPage} pageSize={10} />
      </Card>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Card>
          <div className="flex gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300">
              <AlertTriangle className="h-4 w-4" />
            </span>
            <div>
              <h4 className="text-xs font-semibold text-ink-900 dark:text-white">Predictions are advisory</h4>
              <p className="mt-1 text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">
                Component failure probabilities come from a model trained on this platform's historical data. They are
                not manufacturer diagnostics. Always follow the OEM service schedule for safety-critical parts.
              </p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">
              <CircleDollarSign className="h-4 w-4" />
            </span>
            <div>
              <h4 className="text-xs font-semibold text-ink-900 dark:text-white">Costs are estimates</h4>
              <p className="mt-1 text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">
                Estimated costs use demo regional rates and exclude labour variation, taxes and warranty coverage. Use
                them for planning, not procurement.
              </p>
            </div>
          </div>
        </Card>
      </div>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Add maintenance record"
        description="Log completed service, repair or inspection work against a vehicle."
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={submitRecord} loading={saving}>Save record</Button>
          </>
        }
      >
        <form onSubmit={submitRecord} className="grid gap-4 sm:grid-cols-2">
          <Field label="Vehicle" required>
            <Select value={form.vehicle_id} onChange={(event) => setForm({ ...form, vehicle_id: event.target.value })} required>
              <option value="">Select a vehicle</option>
              {vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicle.registration_number}</option>)}
            </Select>
          </Field>
          <Field label="Record type" required>
            <Select value={form.record_type} onChange={(event) => setForm({ ...form, record_type: event.target.value })}>
              {RECORD_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
            </Select>
          </Field>
          <div className="sm:col-span-2">
            <Field label="Title" required>
              <Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required placeholder="Full service and brake inspection" />
            </Field>
          </div>
          <div className="sm:col-span-2">
            <Field label="Description">
              <Textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Parts replaced, findings, advisories" />
            </Field>
          </div>
          <Field label="Odometer (km)">
            <Input type="number" min={0} step={100} value={form.odometer_km} onChange={(event) => setForm({ ...form, odometer_km: event.target.value })} />
          </Field>
          <Field label="Cost (₹)">
            <Input type="number" min={0} step={100} value={form.cost} onChange={(event) => setForm({ ...form, cost: event.target.value })} />
          </Field>
          <Field label="Vendor">
            <Input value={form.vendor} onChange={(event) => setForm({ ...form, vendor: event.target.value })} placeholder="Service centre name" />
          </Field>
          <Field label="Performed at">
            <Input type="datetime-local" value={form.performed_at} onChange={(event) => setForm({ ...form, performed_at: event.target.value })} />
          </Field>
          <Field label="Next due (km)">
            <Input type="number" min={0} step={500} value={form.next_due_km} onChange={(event) => setForm({ ...form, next_due_km: event.target.value })} />
          </Field>
          <Field label="Next due (date)">
            <Input type="date" value={form.next_due_date} onChange={(event) => setForm({ ...form, next_due_date: event.target.value })} />
          </Field>
          <button type="submit" className="hidden" aria-hidden="true" />
        </form>
      </Modal>

      <ConfirmDialog
        open={resolving !== null}
        onCancel={() => setResolving(null)}
        onConfirm={resolveAlert}
        title="Resolve maintenance alert"
        message={resolving ? `Mark "${resolving.title}" as resolved? This is recorded in the audit log but does not create a service record.` : ""}
        confirmLabel="Resolve alert"
        loading={saving}
      />

      <Modal
        open={prediction !== null}
        onClose={() => setPrediction(null)}
        title={prediction ? `Component risk · ${prediction.registration_number}` : "Prediction"}
        description={prediction ? `Model output · ${prediction.is_simulated ? "simulated inputs" : "device inputs"}` : ""}
        size="md"
      >
        {prediction && (
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-2xl bg-ink-50 p-4 dark:bg-white/5">
              <div>
                <p className="text-[10px] uppercase tracking-wide text-ink-400">Failure probability</p>
                <p className="text-2xl font-semibold text-ink-950 dark:text-white">{(prediction.failure_probability * 100).toFixed(1)}%</p>
              </div>
              <Badge tone={severityTone(prediction.risk_level)} className="text-sm">{prediction.risk_level}</Badge>
            </div>
            <p className="text-xs leading-relaxed text-ink-700 dark:text-ink-200">{prediction.recommendation}</p>
            <div className="space-y-2">
              {(prediction.components ?? []).map((component) => (
                <div key={component.component} className="flex items-center gap-3">
                  <span className="w-28 truncate text-[11px] capitalize text-ink-600 dark:text-ink-300">{component.component.replace(/_/g, " ")}</span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-100 dark:bg-white/10">
                    <div
                      className={cn("h-full rounded-full", component.probability > 0.5 ? "bg-rose-500" : component.probability > 0.25 ? "bg-amber-500" : "bg-emerald-500")}
                      style={{ width: `${component.probability * 100}%` }}
                    />
                  </div>
                  <span className="w-10 text-right text-[10px] font-semibold tabular-nums">{(component.probability * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
            <p className="text-[10px] leading-relaxed text-ink-400">{prediction.disclaimer}</p>
          </div>
        )}
      </Modal>
    </div>
  );
}
