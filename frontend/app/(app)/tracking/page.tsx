"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Compass, Crosshair, MapPin, RefreshCw, Route, Satellite, ShieldOff, Signal, TriangleAlert } from "lucide-react";
import { api } from "@/lib/api";
import { useLiveFleet } from "@/lib/live";
import type { DrivingEvent, LiveVehicle, Vehicle } from "@/lib/types";
import type { Paginated } from "@/lib/api";
import PhoneGps from "@/components/map/PhoneGps";
import FleetMap, { type MapGeofence, type MapTrail } from "@/components/map/FleetMap";
import { Badge, Button, Card, DemoBanner, EmptyState, Input, Modal, PageHeader, PageSkeleton, Select, SimulatedBadge, toast } from "@/components/ui";
import { cn, formatKm, severityTone, timeAgo, VEHICLE_STATUS_LABELS } from "@/lib/format";

const TRAIL_MINUTES = [60, 180, 360];

export default function TrackingPage() {
  const { vehicles, connection, lastUpdated } = useLiveFleet(true);
  const [trailMinutes, setTrailMinutes] = useState(180);
  const [trails, setTrails] = useState<MapTrail[]>([]);
  const [geofences, setGeofences] = useState<MapGeofence[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = vehicles.find((vehicle) => vehicle.vehicle_id === selectedId) ?? null;
  const [loading, setLoading] = useState(true);
  const [showGeofence, setShowGeofence] = useState(false);
  const [geofenceForm, setGeofenceForm] = useState({ name: "", center_latitude: 23.2599, center_longitude: 77.4126, radius_meters: 500, description: "" });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<MapGeofence | null>(null);
  const [events, setEvents] = useState<DrivingEvent[]>([]);

  const loadStatic = useCallback(async () => {
    setLoading(true);
    try {
      const [trailData, fenceData, eventData] = await Promise.all([
        api.get<MapTrail[]>("/gps/trails", { minutes: trailMinutes }),
        api.get<MapGeofence[]>("/gps/geofences"),
        api.get<Paginated<DrivingEvent>>("/behaviour/events", { page_size: 8, min_severity: "high" }),
      ]);
      setTrails(trailData ?? []);
      setGeofences(fenceData ?? []);
      setEvents(eventData.items ?? []);
    } catch {
      /* map still renders from the live stream */
    } finally {
      setLoading(false);
    }
  }, [trailMinutes]);

  useEffect(() => {
    void loadStatic();
  }, [loadStatic]);

  const createGeofence = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const created = await api.post<MapGeofence>("/gps/geofences", geofenceForm);
      setGeofences((current) => [...current, created]);
      setShowGeofence(false);
      setGeofenceForm({ name: "", center_latitude: 23.2599, center_longitude: 77.4126, radius_meters: 500, description: "" });
      toast("Geofence created. Breach detection is evaluated on incoming telemetry.");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not create geofence.", "error");
    } finally {
      setSaving(false);
    }
  };

  const confirmDeleteGeofence = async () => {
    if (!deleting) return;
    setSaving(true);
    try {
      await api.delete(`/gps/geofences/${deleting.id}`);
      setGeofences((current) => current.filter((fence) => fence.id !== deleting.id));
      setDeleting(null);
      toast("Geofence removed.");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not delete geofence.", "error");
    } finally {
      setSaving(false);
    }
  };

  const moving = vehicles.filter((vehicle) => vehicle.source !== "phone" && vehicle.speed_kph > 3).length;
  const offline = vehicles.filter((vehicle) => vehicle.status === "offline").length;
  const maxSpeed = useMemo(() => Math.max(0, ...vehicles.filter((vehicle) => vehicle.source !== "phone").map((vehicle) => vehicle.speed_kph)), [vehicles]);
  const totalToday = useMemo(() => vehicles.reduce((sum, vehicle) => sum + (vehicle.today_distance_km ?? 0), 0), [vehicles]);

  if (loading && !vehicles.length) return <PageSkeleton cards={4} />;

  return (
    <div>
      <PageHeader
        eyebrow="Operations · real-time"
        title="Live tracking"
        description="Vehicle positions, trails and geofence status. Positions update over WebSocket with automatic polling fallback."
        actions={
          <>
            <Button variant="secondary" onClick={() => void loadStatic()}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            <Button onClick={() => setShowGeofence(true)}>
              <ShieldOff className="h-4 w-4" /> New geofence
            </Button>
          </>
        }
      />

      <PhoneGps />

      {(vehicles.some((vehicle) => vehicle.is_simulated) || trails.some((trail) => trail.is_simulated)) && (
        <DemoBanner message="Simulated vehicle positions and trails are labelled. Verify data sources before making safety decisions." />
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {[
          { label: "Vehicles reporting", value: vehicles.length, icon: <Satellite className="h-5 w-5" />, tone: "teal" },
          { label: "Moving now", value: moving, icon: <Route className="h-5 w-5" />, tone: "indigo" },
          { label: "Offline", value: offline, icon: <Signal className="h-5 w-5" />, tone: "rose" },
          { label: "Distance today", value: formatKm(totalToday), icon: <MapPin className="h-5 w-5" />, tone: "slate" },
          { label: "Fastest vehicle", value: `${maxSpeed.toFixed(0)} km/h`, icon: <Compass className="h-5 w-5" />, tone: "amber" },
        ].map((stat, index) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.04 }}
            className="card p-4"
          >
            <div className="flex items-center justify-between">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-500 dark:text-ink-400">{stat.label}</p>
              <span className="text-ink-400">{stat.icon}</span>
            </div>
            <p className="mt-2 text-xl font-semibold tracking-tight text-ink-950 dark:text-white">{stat.value}</p>
          </motion.div>
        ))}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Card
          padded={false}
          title={
            <span className="flex items-center gap-2">
              Fleet positions {vehicles.some((vehicle) => vehicle.is_simulated) && <SimulatedBadge />}
            </span>
          }
          subtitle={
            <span className="flex items-center gap-1.5">
              <span className={cn("h-1.5 w-1.5 rounded-full", connection === "websocket" ? "bg-emerald-500" : connection === "polling" ? "bg-brand-500" : "bg-amber-500")} />
              {connection === "websocket" ? "Live WebSocket" : connection === "polling" ? "Polling fallback" : connection === "error" ? "Connection error" : "Connecting"}
              {lastUpdated && <span className="text-ink-400">· {lastUpdated.toLocaleTimeString()}</span>}
            </span>
          }
          action={
            <Select
              value={String(trailMinutes)}
              onChange={(event) => setTrailMinutes(Number(event.target.value))}
              className="w-[130px] py-1.5 text-xs"
              aria-label="Trail length"
            >
              {TRAIL_MINUTES.map((minutes) => (
                <option key={minutes} value={minutes}>
                  {minutes >= 60 ? `${minutes / 60} h trail` : `${minutes} min trail`}
                </option>
              ))}
            </Select>
          }
          className="overflow-hidden"
        >
          <div className="p-2">
            <FleetMap
              vehicles={vehicles}
              trails={trails}
              geofences={geofences}
              height={520}
              selectedId={selectedId}
              onSelect={(vehicle) => setSelectedId(vehicle.vehicle_id)}
            />
          </div>
          <div className="flex flex-wrap items-center gap-4 border-t border-ink-100 px-4 py-2.5 text-[11px] text-ink-500 dark:border-white/5 dark:text-ink-400">
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-brand-500" /> Active</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-amber-500" /> Maintenance</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-rose-500" /> Offline</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-ink-400" /> Inactive</span>
            <span className="ml-auto flex items-center gap-1.5"><span className="h-2 w-2 rounded-full border border-dashed border-indigo-400" /> Geofence</span>
          </div>
        </Card>

        <div className="space-y-4">
          <Card title="Vehicle roster" subtitle="Tap a vehicle to focus" padded={false}>
            <div className="max-h-[330px] overflow-y-auto p-2">
              {vehicles.length === 0 ? (
                <EmptyState title="No vehicles reporting" description="Live positions will appear here once telemetry is received." />
              ) : (
                <div className="space-y-1">
                  {vehicles.map((vehicle) => {
                    const active = selected?.vehicle_id === vehicle.vehicle_id;
                    return (
                      <button
                        key={vehicle.vehicle_id}
                        onClick={() => setSelectedId(vehicle.vehicle_id)}
                        className={cn(
                          "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition",
                          active ? "bg-brand-50 ring-1 ring-brand-200 dark:bg-brand-500/10 dark:ring-brand-500/30" : "hover:bg-ink-50 dark:hover:bg-white/5",
                        )}
                      >
                        <span className={cn("h-2 w-2 shrink-0 rounded-full", vehicle.speed_kph > 3 ? "bg-emerald-500" : "bg-ink-400")} />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-xs font-semibold text-ink-900 dark:text-white">{vehicle.registration_number}</span>
                          <span className="block truncate text-[10px] text-ink-400">{vehicle.driver_name ?? "Unassigned"}</span>
                        </span>
                        <span className="text-xs font-semibold tabular-nums text-ink-700 dark:text-ink-200">{vehicle.source === "phone" ? "GPS" : vehicle.speed_kph.toFixed(0)}</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </Card>

          {selected ? (
            <Card title="Selected vehicle" subtitle={selected.registration_number}>
              <dl className="space-y-2.5 text-xs">
                {[
                  ["Driver", selected.driver_name ?? "Unassigned"],
                  ["Status", VEHICLE_STATUS_LABELS[selected.status] ?? selected.status],
                  ["Speed", selected.source === "phone" ? "Not verified (phone GPS)" : `${selected.speed_kph.toFixed(1)} km/h`],
                  ["Heading", selected.source === "phone" ? "Not verified (phone GPS)" : `${selected.heading.toFixed(0)}°`],
                  ["Ignition", selected.source === "phone" ? "Unknown (phone GPS)" : selected.ignition_on ? "On" : "Off"],
                  ["Distance today", formatKm(selected.today_distance_km ?? 0)],
                  ["Last seen", timeAgo(selected.last_seen)],
                ].map(([label, value]) => (
                  <div key={label} className="flex items-center justify-between gap-3">
                    <dt className="text-ink-500 dark:text-ink-400">{label}</dt>
                    <dd className="font-medium text-ink-900 dark:text-white">{value}</dd>
                  </div>
                ))}
              </dl>
              {selected.is_simulated && (
                <p className="mt-3 rounded-lg bg-amber-50 px-2.5 py-2 text-[10px] leading-relaxed text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
                  Simulator position on the {selected.vehicle_type} demo route.
                </p>
              )}
            </Card>
          ) : (
            <Card>
              <EmptyState icon={<Crosshair className="h-5 w-5" />} title="No vehicle selected" description="Select a vehicle on the map or in the roster to inspect its live state." />
            </Card>
          )}
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Geofences" subtitle="Operational boundaries" className="lg:col-span-1" padded={false}>
          {geofences.length === 0 ? (
            <div className="p-4">
              <EmptyState
                icon={<ShieldOff className="h-5 w-5" />}
                title="No geofences configured"
                description="Create a geofence to detect depot exits or restricted-area entry."
                action={<Button size="sm" onClick={() => setShowGeofence(true)}>Create geofence</Button>}
              />
            </div>
          ) : (
            <div className="divide-y divide-ink-100 dark:divide-white/5">
              {geofences.map((fence) => (
                <div key={fence.id} className="flex items-start gap-3 px-4 py-3">
                  <span className={cn("mt-1 h-2 w-2 shrink-0 rounded-full", fence.is_active ? "bg-indigo-500" : "bg-ink-300")} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-ink-900 dark:text-white">{fence.name}</p>
                    <p className="text-[10px] text-ink-500">{Math.round(fence.radius_meters)} m radius</p>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => setDeleting(fence)}>
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card
          title="Recent high-severity events"
          subtitle="Speeding, harsh braking and cornering"
          className="lg:col-span-2"
          padded={false}
        >
          {events.length === 0 ? (
            <div className="p-4">
              <EmptyState title="No high-severity events" description="Nothing at high or critical severity in the selected window." />
            </div>
          ) : (
            <div className="max-h-[320px] divide-y divide-ink-100 overflow-y-auto dark:divide-white/5">
              {events.map((event) => (
                <div key={event.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
                  <Badge tone={severityTone(event.severity)}>{event.severity}</Badge>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold capitalize text-ink-900 dark:text-white">
                      {event.event_type.replace(/_/g, " ")}
                      {event.speed_kph !== null && event.speed_kph !== undefined && (
                        <span className="ml-2 font-normal text-ink-500">{event.speed_kph.toFixed(0)} km/h</span>
                      )}
                    </p>
                    <p className="truncate text-[10px] text-ink-400">
                      {event.driver_name ?? "Unassigned"} · {event.registration_number ?? "—"} · {timeAgo(event.occurred_at)}
                    </p>
                  </div>
                  {event.is_simulated && <SimulatedBadge />}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card title="How tracking behaves" subtitle="Honest limits of this deployment" className="mt-4">
        <ul className="grid gap-2 text-xs leading-relaxed text-ink-600 dark:text-ink-300 sm:grid-cols-2">
          <li className="flex gap-2"><TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" /> Map tiles load from OpenStreetMap and need internet access at the browser.</li>
          <li className="flex gap-2"><TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" /> Simulated positions are labelled; configured devices can send real telemetry via API key.</li>
          <li className="flex gap-2"><TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" /> Route-deviation detection is indicative and based on the configured route polyline.</li>
          <li className="flex gap-2"><TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" /> Geofence alerts never contact emergency services automatically.</li>
        </ul>
      </Card>

      <Modal
        open={showGeofence}
        onClose={() => setShowGeofence(false)}
        title="Create geofence"
        description="Circular boundary alerts for depot, customer site or restricted zones."
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowGeofence(false)}>Cancel</Button>
            <Button type="submit" form="geofence-form" loading={saving}>Create geofence</Button>
          </>
        }
      >
        <form id="geofence-form" onSubmit={createGeofence} className="grid gap-4 sm:grid-cols-2">
          <label className="block sm:col-span-2">
            <span className="label">Name *</span>
            <Input value={geofenceForm.name} onChange={(event) => setGeofenceForm({ ...geofenceForm, name: event.target.value })} required minLength={2} placeholder="Bhopal depot" />
          </label>
          <label className="block">
            <span className="label">Centre latitude *</span>
            <Input type="number" step="0.000001" min={-90} max={90} value={geofenceForm.center_latitude} onChange={(event) => setGeofenceForm({ ...geofenceForm, center_latitude: Number(event.target.value) })} required />
          </label>
          <label className="block">
            <span className="label">Centre longitude *</span>
            <Input type="number" step="0.000001" min={-180} max={180} value={geofenceForm.center_longitude} onChange={(event) => setGeofenceForm({ ...geofenceForm, center_longitude: Number(event.target.value) })} required />
          </label>
          <label className="block">
            <span className="label">Radius (m) *</span>
            <Input type="number" step={50} min={10} max={50000} value={geofenceForm.radius_meters} onChange={(event) => setGeofenceForm({ ...geofenceForm, radius_meters: Number(event.target.value) })} required />
          </label>
          <label className="block">
            <span className="label">Description</span>
            <Input value={geofenceForm.description} onChange={(event) => setGeofenceForm({ ...geofenceForm, description: event.target.value })} placeholder="Optional note" />
          </label>
        </form>
      </Modal>

      <Modal
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        title="Remove geofence"
        description={deleting ? `Delete "${deleting.name}"? Historical breach events are retained.` : ""}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleting(null)}>Cancel</Button>
            <Button variant="danger" onClick={confirmDeleteGeofence} loading={saving}>Delete geofence</Button>
          </>
        }
      >
        <p className="text-sm text-ink-600 dark:text-ink-300">
          This stops future breach detection for this boundary. It does not delete any recorded safety events.
        </p>
      </Modal>
    </div>
  );
}
