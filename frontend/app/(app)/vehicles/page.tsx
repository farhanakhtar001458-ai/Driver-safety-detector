"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { BatteryCharging, Car, CircleDot, Plus, Search, Truck, Wrench } from "lucide-react";
import { api, type Paginated } from "@/lib/api";
import type { Driver, Vehicle, VehicleHealth } from "@/lib/types";
import { Badge, Button, Card, DemoBanner, EmptyState, Field, Input, Modal, PageHeader, PageSkeleton, Select, SimulatedBadge, Textarea, toast } from "@/components/ui";
import { DataTable, type Column } from "@/components/tables/DataTable";
import { CategoryBars } from "@/components/charts";
import FleetMap from "@/components/map/FleetMap";
import { cn, formatKm, formatDate, statusTone, VEHICLE_STATUS_LABELS } from "@/lib/format";

const STATUS_FILTERS = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "under_maintenance", label: "Maintenance" },
  { id: "offline", label: "Offline" },
  { id: "inactive", label: "Inactive" },
];

const VEHICLE_TYPES = ["car", "van", "truck", "bus", "bike"];

const EMPTY_FORM = {
  registration_number: "",
  vehicle_type: "car",
  manufacturer: "",
  model: "",
  manufacturing_year: new Date().getFullYear(),
  fuel_type: "diesel",
  vin: "",
  assigned_driver_id: "",
  gps_device_id: "",
  status: "active",
  insurance_expiry: "",
  mileage_km: 0,
  depot: "",
  notes: "",
};

export default function VehiclesPage() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [detail, setDetail] = useState<{
    vehicle: Vehicle;
    health: VehicleHealth;
    last_location: { latitude: number; longitude: number; speed_kph: number } | null;
    open_alerts: { id: number; title: string; severity: string }[];
    recent_events: { id: number; event_type: string; severity: string; occurred_at: string }[];
    trips_count: number;
  } | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.get<Paginated<Vehicle>>("/vehicles", {
        page,
        page_size: 20,
        search: search || undefined,
        status: status === "all" ? undefined : status,
        vehicle_type: typeFilter === "all" ? undefined : typeFilter,
        include_archived: false,
      });
      setVehicles(result.items ?? []);
      setTotal(result.total ?? 0);
      setPages(result.pages ?? 1);
    } catch {
      setVehicles([]);
    } finally {
      setLoading(false);
    }
  }, [page, search, status, typeFilter]);

  useEffect(() => {
    setPage(1);
  }, [search, status, typeFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void (async () => {
      try {
        const result = await api.get<Paginated<Driver>>("/drivers", { page_size: 100 });
        setDrivers(result.items ?? []);
      } catch {
        setDrivers([]);
      }
    })();
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        registration_number: form.registration_number,
        vehicle_type: form.vehicle_type,
        manufacturer: form.manufacturer,
        model: form.model,
        manufacturing_year: Number(form.manufacturing_year),
        fuel_type: form.fuel_type,
        status: form.status,
        mileage_km: Number(form.mileage_km),
        assigned_driver_id: form.assigned_driver_id ? Number(form.assigned_driver_id) : null,
        gps_device_id: form.gps_device_id ? Number(form.gps_device_id) : null,
      };
      if (form.vin.trim()) payload.vin = form.vin.trim();
      if (form.insurance_expiry) payload.insurance_expiry = form.insurance_expiry;
      if (form.depot.trim()) payload.depot = form.depot.trim();
      if (form.notes.trim()) payload.notes = form.notes.trim();

      await api.post<Vehicle>("/vehicles", payload);
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      toast("Vehicle added to the fleet.");
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not create the vehicle.", "error");
    } finally {
      setSaving(false);
    }
  };

  const openDetail = async (vehicle: Vehicle) => {
    setDetailLoading(true);
    try {
      const result = await api.get<Record<string, unknown>>(`/vehicles/${vehicle.id}/overview`);
      setDetail({
        vehicle: vehicle,
        health: result.health as VehicleHealth,
        last_location: (result.last_location as { latitude: number; longitude: number; speed_kph: number } | null) ?? null,
        open_alerts: (result.open_alerts as { id: number; title: string; severity: string }[]) ?? [],
        recent_events: (result.recent_events as { id: number; event_type: string; severity: string; occurred_at: string }[]) ?? [],
        trips_count: Number(result.trips_count ?? 0),
      });
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not load vehicle detail.", "error");
    } finally {
      setDetailLoading(false);
    }
  };

  const columns: Column<Vehicle>[] = [
    {
      key: "vehicle",
      header: "Vehicle",
      render: (row) => (
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">
            <Car className="h-4 w-4" />
          </span>
          <div>
            <p className="text-xs font-semibold text-ink-900 dark:text-white">{row.registration_number}</p>
            <p className="text-[10px] text-ink-400">
              {row.manufacturer} {row.model} · {row.manufacturing_year}
            </p>
          </div>
        </div>
      ),
    },
    {
      key: "type",
      header: "Type",
      render: (row) => <span className="capitalize text-xs text-ink-600 dark:text-ink-300">{row.vehicle_type}</span>,
    },
    {
      key: "status",
      header: "Status",
      render: (row) => (
        <span className="inline-flex items-center gap-1.5">
          <span className={cn("h-1.5 w-1.5 rounded-full", row.status === "active" ? "bg-emerald-500" : row.status === "under_maintenance" ? "bg-amber-500" : row.status === "offline" ? "bg-rose-500" : "bg-ink-400")} />
          <Badge tone={statusTone(row.status)}>{VEHICLE_STATUS_LABELS[row.status]}</Badge>
        </span>
      ),
    },
    {
      key: "driver",
      header: "Assigned driver",
      render: (row) => <span className="text-xs text-ink-600 dark:text-ink-300">{row.assigned_driver_name ?? <span className="text-ink-400">Unassigned</span>}</span>,
    },
    {
      key: "mileage",
      header: "Odometer",
      align: "right",
      render: (row) => <span className="text-xs font-medium tabular-nums">{formatKm(row.mileage_km)}</span>,
    },
    {
      key: "insurance",
      header: "Insurance expiry",
      render: (row) => {
        const expired = row.insurance_expiry ? new Date(row.insurance_expiry) < new Date() : false;
        return (
          <span className={cn("text-xs", expired ? "font-semibold text-rose-600" : "text-ink-600 dark:text-ink-300")}>
            {row.insurance_expiry ? formatDate(row.insurance_expiry) : "—"}
            {expired && <span className="ml-1 text-[10px] uppercase">expired</span>}
          </span>
        );
      },
    },
    {
      key: "gps",
      header: "GPS device",
      render: (row) => (
        <span className="font-mono text-[11px] text-ink-500">{row.gps_device_serial ?? <span className="text-ink-400">None</span>}</span>
      ),
    },
  ];

  const counts = {
    total: total,
    active: vehicles.filter((vehicle) => vehicle.status === "active").length,
    maintenance: vehicles.filter((vehicle) => vehicle.status === "under_maintenance").length,
    offline: vehicles.filter((vehicle) => vehicle.status === "offline").length,
  };

  if (loading && !vehicles.length) return <PageSkeleton cards={4} />;

  return (
    <div>
      <PageHeader
        eyebrow="Fleet · assets"
        title="Vehicles"
        description="Asset register, assignment, insurance and device binding for every vehicle in your organisation."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" /> Add vehicle
          </Button>
        }
      />

      <DemoBanner message="Vehicles are real records in this database; their telemetry, health readings and diagnostics are simulated and labelled as such." />

      <div className="page-grid">
        {[
          { label: "Vehicles in fleet", value: counts.total, icon: <Truck className="h-5 w-5" />, tone: "teal" as const, hint: "Active register" },
          { label: "Active", value: counts.active, icon: <CircleDot className="h-5 w-5" />, tone: "indigo" as const, hint: "Reported this page" },
          { label: "In maintenance", value: counts.maintenance, icon: <Wrench className="h-5 w-5" />, tone: "amber" as const, hint: "Service or repair" },
          { label: "Offline", value: counts.offline, icon: <BatteryCharging className="h-5 w-5" />, tone: "rose" as const, hint: "No recent telemetry" },
        ].map((stat, index) => (
          <Card key={stat.label} className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-500 dark:text-ink-400">{stat.label}</p>
                <p className="mt-2 text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">{stat.value}</p>
                <p className="mt-1 text-[11px] text-ink-400">{stat.hint}</p>
              </div>
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-ink-100 text-ink-500 dark:bg-white/5 dark:text-ink-300">{stat.icon}</span>
            </div>
          </Card>
        ))}
      </div>

      <Card padded={false} className="mt-4">
        <div className="flex flex-col justify-between gap-3 border-b border-ink-100 p-4 dark:border-white/5 lg:flex-row lg:items-center">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search registration, model, VIN…"
              className="pl-9"
              aria-label="Search vehicles"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Select value={status} onChange={(event) => setStatus(event.target.value)} className="w-[150px]" aria-label="Filter by status">
              {STATUS_FILTERS.map((option) => (
                <option key={option.id} value={option.id}>{option.label}</option>
              ))}
            </Select>
            <Select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} className="w-[130px]" aria-label="Filter by type">
              <option value="all">All types</option>
              {VEHICLE_TYPES.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </Select>
          </div>
        </div>

        <DataTable
          columns={columns}
          rows={vehicles}
          loading={loading}
          onRowClick={(row) => void openDetail(row)}
          emptyTitle="No vehicles match"
          emptyDescription="Try clearing filters or add a vehicle to the register."
          rowKey={(row) => row.id}
        />
        <div className="border-t border-ink-100 px-4 py-3 text-xs text-ink-500 dark:border-white/5 dark:text-ink-400">
          Page {page} of {Math.max(1, pages)} · {total} vehicles
          <div className="mt-2 flex gap-2">
            <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
            <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </div>
      </Card>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Add vehicle"
        description="Register a vehicle in your organisation. Plan limits are enforced by the server."
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={submit} loading={saving}>Add vehicle</Button>
          </>
        }
      >
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          <Field label="Registration number" required hint="Letters and digits, e.g. MP09AB4211">
            <Input value={form.registration_number} onChange={(event) => setForm({ ...form, registration_number: event.target.value })} required minLength={3} />
          </Field>
          <Field label="Vehicle type" required>
            <Select value={form.vehicle_type} onChange={(event) => setForm({ ...form, vehicle_type: event.target.value })}>
              {VEHICLE_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
            </Select>
          </Field>
          <Field label="Manufacturer" required>
            <Input value={form.manufacturer} onChange={(event) => setForm({ ...form, manufacturer: event.target.value })} required maxLength={60} />
          </Field>
          <Field label="Model" required>
            <Input value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })} required maxLength={80} />
          </Field>
          <Field label="Manufacturing year" required>
            <Input type="number" min={1980} max={2027} value={form.manufacturing_year} onChange={(event) => setForm({ ...form, manufacturing_year: Number(event.target.value) })} required />
          </Field>
          <Field label="Fuel type">
            <Select value={form.fuel_type} onChange={(event) => setForm({ ...form, fuel_type: event.target.value })}>
              {["diesel", "petrol", "electric", "cng", "hybrid"].map((fuel) => <option key={fuel} value={fuel}>{fuel}</option>)}
            </Select>
          </Field>
          <Field label="VIN" hint="Exactly 17 alphanumeric characters, or leave blank.">
            <Input value={form.vin} onChange={(event) => setForm({ ...form, vin: event.target.value })} maxLength={17} />
          </Field>
          <Field label="Status">
            <Select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
              {STATUS_FILTERS.filter((option) => option.id !== "all").map((option) => (
                <option key={option.id} value={option.id}>{option.label}</option>
              ))}
            </Select>
          </Field>
          <Field label="Assigned driver" hint="Optional. Drivers must belong to this organisation.">
            <Select value={form.assigned_driver_id} onChange={(event) => setForm({ ...form, assigned_driver_id: event.target.value })}>
              <option value="">Unassigned</option>
              {drivers.map((driver) => (
                <option key={driver.id} value={driver.id}>{driver.full_name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Odometer (km)">
            <Input type="number" min={0} step={100} value={form.mileage_km} onChange={(event) => setForm({ ...form, mileage_km: Number(event.target.value) })} />
          </Field>
          <Field label="Insurance expiry">
            <Input type="date" value={form.insurance_expiry} onChange={(event) => setForm({ ...form, insurance_expiry: event.target.value })} />
          </Field>
          <Field label="GPS device ID" hint="Bind to an existing device record, or leave blank.">
            <Input type="number" min={1} value={form.gps_device_id} onChange={(event) => setForm({ ...form, gps_device_id: event.target.value })} placeholder="Optional" />
          </Field>
          <Field label="Depot">
            <Input value={form.depot} onChange={(event) => setForm({ ...form, depot: event.target.value })} placeholder="e.g. Bhopal central" />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Notes">
              <Textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} placeholder="Optional internal notes" />
            </Field>
          </div>
          <button type="submit" className="hidden" aria-hidden="true" />
        </form>
      </Modal>

      <Modal
        open={detail !== null || detailLoading}
        onClose={() => setDetail(null)}
        title={detail?.vehicle.registration_number ?? "Vehicle"}
        description={detail ? `${detail.vehicle.manufacturer} ${detail.vehicle.model} · ${detail.vehicle.vehicle_type}` : "Loading vehicle"}
        size="lg"
      >
        {detail ? (
          <div className="space-y-5">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl bg-ink-50 p-3 dark:bg-white/5">
                <p className="text-[10px] uppercase tracking-wide text-ink-400">Status</p>
                <Badge tone={statusTone(detail.vehicle.status)} className="mt-1">{VEHICLE_STATUS_LABELS[detail.vehicle.status]}</Badge>
              </div>
              <div className="rounded-xl bg-ink-50 p-3 dark:bg-white/5">
                <p className="text-[10px] uppercase tracking-wide text-ink-400">Odometer</p>
                <p className="mt-1 text-sm font-semibold text-ink-900 dark:text-white">{formatKm(detail.vehicle.mileage_km)}</p>
              </div>
              <div className="rounded-xl bg-ink-50 p-3 dark:bg-white/5">
                <p className="text-[10px] uppercase tracking-wide text-ink-400">Trips</p>
                <p className="mt-1 text-sm font-semibold text-ink-900 dark:text-white">{detail.trips_count}</p>
              </div>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <div className="mb-3 flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-ink-900 dark:text-white">Latest health reading</h4>
                  {detail.health?.is_simulated && <SimulatedBadge />}
                </div>
                <CategoryBars
                  categories={[
                    { key: "health", label: "Overall health", value: detail.health?.health_score },
                    { key: "fuel", label: "Fuel level", value: detail.health?.fuel_level_pct },
                    { key: "battery", label: "Battery charge", value: detail.health?.battery_voltage ? Math.min(100, (detail.health.battery_voltage / 12.8) * 100) : null },
                  ]}
                />
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <p className="text-ink-500">Engine <span className="font-semibold text-ink-800 dark:text-white">{detail.health?.engine_temperature_c ?? "—"} °C</span></p>
                  <p className="text-ink-500">Fault codes <span className="font-semibold text-rose-600">{detail.health?.fault_codes?.length ?? 0}</span></p>
                </div>
              </div>
              <div>
                <h4 className="mb-3 text-xs font-semibold text-ink-900 dark:text-white">Recent events</h4>
                {detail.recent_events.length === 0 ? (
                  <p className="text-xs text-ink-400">No recent events recorded.</p>
                ) : (
                  <div className="space-y-2">
                    {detail.recent_events.map((event) => (
                      <div key={event.id} className="flex items-center gap-2 text-xs">
                        <Badge tone={event.severity === "critical" ? "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300" : event.severity === "high" ? "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300" : "bg-ink-100 text-ink-600 dark:bg-white/10 dark:text-ink-300"}>
                          {event.severity}
                        </Badge>
                        <span className="flex-1 truncate capitalize text-ink-700 dark:text-ink-200">{event.event_type.replace(/_/g, " ")}</span>
                        <span className="text-[10px] text-ink-400">{new Date(event.occurred_at).toLocaleDateString()}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {detail.last_location && detail.last_location.latitude ? (
              <FleetMap
                vehicles={[
                  {
                    vehicle_id: detail.vehicle.id,
                    registration_number: detail.vehicle.registration_number,
                    vehicle_type: detail.vehicle.vehicle_type,
                    status: detail.vehicle.status,
                    driver_name: detail.vehicle.assigned_driver_name,
                    latitude: detail.last_location.latitude,
                    longitude: detail.last_location.longitude,
                    speed_kph: detail.last_location.speed_kph,
                    heading: 0,
                    ignition_on: true,
                    last_seen: new Date().toISOString(),
                    is_simulated: Boolean(detail.health?.is_simulated),
                  },
                ]}
                height={240}
              />
            ) : (
              <p className="rounded-xl bg-ink-50 px-3 py-2 text-xs text-ink-500 dark:bg-white/5 dark:text-ink-400">No location recorded for this vehicle yet.</p>
            )}

            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3">
              {[
                ["Assigned driver", detail.vehicle.assigned_driver_name ?? "Unassigned"],
                ["VIN", detail.vehicle.vin_masked ?? "—"],
                ["GPS device", detail.vehicle.gps_device_serial ?? "None"],
                ["Insurance", detail.vehicle.insurance_expiry ? formatDate(detail.vehicle.insurance_expiry) : "—"],
                ["Depot", detail.vehicle.depot ?? "—"],
                ["Next service", detail.vehicle.next_service_km ? formatKm(detail.vehicle.next_service_km) : "Not set"],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-[10px] uppercase tracking-wide text-ink-400">{label}</dt>
                  <dd className="mt-0.5 font-medium text-ink-800 dark:text-ink-100">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="skeleton h-20 w-full" />
            <div className="skeleton h-32 w-full" />
          </div>
        )}
      </Modal>
    </div>
  );
}
