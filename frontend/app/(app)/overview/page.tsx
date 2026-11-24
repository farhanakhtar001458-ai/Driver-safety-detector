"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Award,
  Bell,
  Car,
  Gauge,
  MapPin,
  Route,
  ShieldAlert,
  Users,
  Wrench,
} from "lucide-react";
import { api } from "@/lib/api";
import { useLiveFleet } from "@/lib/live";
import type { DashboardData, LiveVehicle } from "@/lib/types";
import {
  Avatar,
  Badge,
  Button,
  Card,
  DemoBanner,
  EmptyState,
  PageHeader,
  PageSkeleton,
  SimulatedBadge,
  StatCard,
} from "@/components/ui";
import { ActivityBarChart, EventTypeBarChart, SeverityDonut, TrendAreaChart } from "@/components/charts";
import FleetMap from "@/components/map/FleetMap";
import { cn, formatKm, formatNumber, formatScore, scoreTone, severityTone, statusTone, timeAgo, VEHICLE_STATUS_LABELS } from "@/lib/format";

const RANGES = [
  { id: "7", label: "7 days" },
  { id: "30", label: "30 days" },
  { id: "90", label: "90 days" },
];

export default function OverviewPage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedVehicle, setSelectedVehicle] = useState<LiveVehicle | null>(null);
  const { vehicles, lastUpdated, connection } = useLiveFleet(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<DashboardData>("/dashboard", { days });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the dashboard.");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    void load();
  }, [load]);

  const kpis = data?.kpis ?? {};
  const simulatedShare = kpis.simulated_share_pct ?? 0;

  const statusCounts = useMemo(() => {
    return [
      { label: "Active", value: kpis.active_vehicles ?? 0, tone: "bg-brand-500" },
      { label: "Maintenance", value: kpis.under_maintenance ?? 0, tone: "bg-amber-500" },
      { label: "Offline", value: kpis.offline_vehicles ?? 0, tone: "bg-rose-500" },
      { label: "Inactive", value: kpis.inactive_vehicles ?? 0, tone: "bg-ink-400" },
    ];
  }, [kpis]);

  if (loading && !data) return <PageSkeleton cards={8} />;

  return (
    <div>
      <PageHeader
        eyebrow="Fleet command centre"
        title="Safety overview"
        description="A live view of fleet health, driver behaviour and operational risk across your organisation."
        actions={
          <>
            <div className="flex rounded-xl bg-ink-100/80 p-1 dark:bg-white/5">
              {RANGES.map((range) => (
                <button
                  key={range.id}
                  onClick={() => setDays(Number(range.id))}
                  className={cn(
                    "rounded-lg px-3 py-1.5 text-xs font-semibold transition",
                    days === Number(range.id)
                      ? "bg-white text-ink-900 shadow-sm dark:bg-white/10 dark:text-white"
                      : "text-ink-500 hover:text-ink-800 dark:text-ink-400",
                  )}
                >
                  {range.label}
                </button>
              ))}
            </div>
            <Button variant="secondary" href="/reports">
              <Activity className="h-4 w-4" /> Reports
            </Button>
          </>
        }
      />

      <DemoBanner message={`${simulatedShare.toFixed(0)}% of events in this period come from simulated telemetry. All figures are demonstrative.`} />
      {error && (
        <div className="mb-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
          {error}
          <button onClick={() => void load()} className="ml-3 font-semibold underline">
            Retry
          </button>
        </div>
      )}

      <div className="page-grid">
        <StatCard
          index={0}
          label="Total vehicles"
          value={formatNumber(kpis.total_vehicles)}
          icon={<Car className="h-5 w-5" />}
          hint={`${formatNumber(kpis.active_vehicles)} active · ${formatNumber(kpis.under_maintenance)} in maintenance`}
          tone="teal"
        />
        <StatCard
          index={1}
          label="Total drivers"
          value={formatNumber(kpis.total_drivers)}
          icon={<Users className="h-5 w-5" />}
          hint={`${formatNumber(kpis.active_drivers)} active · ${formatNumber(kpis.licences_expiring)} licence(s) expiring`}
          tone="indigo"
        />
        <StatCard
          index={2}
          label="Average safety score"
          value={formatScore(kpis.avg_driver_score)}
          icon={<Award className="h-5 w-5" />}
          hint={`Confidence ${Math.round((kpis.score_confidence ?? 0) * 100)}% · 0–100 scale`}
          tone={kpis.avg_driver_score >= 75 ? "teal" : "amber"}
        />
        <StatCard
          index={3}
          label="Maintenance alerts"
          value={formatNumber(kpis.maintenance_alerts)}
          icon={<Wrench className="h-5 w-5" />}
          hint={`${formatNumber(kpis.critical_maintenance_alerts)} high severity · ${formatNumber(kpis.open_incidents)} open incidents`}
          tone={kpis.critical_maintenance_alerts > 0 ? "rose" : "slate"}
        />
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard index={4} label="Distance (30 days)" value={formatKm(kpis.distance_period_km)} hint={`${formatNumber(kpis.trips_period)} trips recorded`} icon={<Route className="h-5 w-5" />} tone="slate" />
        <StatCard index={5} label="Safety events" value={formatNumber(kpis.total_events)} hint={`${formatNumber(kpis.high_risk_events)} high risk · ${formatNumber(kpis.critical_events)} critical`} icon={<ShieldAlert className="h-5 w-5" />} tone="amber" />
        <StatCard index={6} label="Incidents open" value={formatNumber(kpis.open_incidents)} hint={`${formatNumber(kpis.critical_incidents)} critical · workflow tracked`} icon={<AlertTriangle className="h-5 w-5" />} tone="rose" />
        <StatCard index={7} label="Data provenance" value={`${simulatedShare.toFixed(0)}%`} hint="of events are simulated demo data" icon={<Gauge className="h-5 w-5" />} tone="indigo" />
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1.9fr)_minmax(0,1fr)]">
        <Card
          padded={false}
          title={
            <div className="flex items-center gap-2">
              Live fleet map
              <SimulatedBadge />
            </div>
          }
          subtitle={
            <span className="inline-flex items-center gap-1.5">
              <span className={cn("h-1.5 w-1.5 rounded-full", connection === "websocket" ? "bg-emerald-500" : connection === "polling" ? "bg-brand-500" : "bg-ink-400")} />
              {connection === "websocket" ? "WebSocket stream" : connection === "polling" ? "Polling every 5s" : "Connecting…"}
              {lastUpdated && <span className="text-ink-400">· updated {lastUpdated.toLocaleTimeString()}</span>}
            </span>
          }
          action={
            <Link href="/tracking" className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:underline dark:text-brand-300">
              Open tracker <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          }
          className="overflow-hidden"
        >
          <div className="p-2">
            <FleetMap
              vehicles={vehicles}
              height={430}
              selectedId={selectedVehicle?.vehicle_id ?? null}
              onSelect={setSelectedVehicle}
            />
          </div>
          {selectedVehicle && (
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-ink-100 px-5 py-3 dark:border-white/5">
              <p className="text-sm font-semibold text-ink-900 dark:text-white">{selectedVehicle.registration_number}</p>
              <p className="text-xs text-ink-500">{selectedVehicle.driver_name ?? "Unassigned"}</p>
              <p className="text-xs text-ink-500">{selectedVehicle.speed_kph.toFixed(0)} km/h</p>
              <Badge tone={statusTone(selectedVehicle.status)}>{VEHICLE_STATUS_LABELS[selectedVehicle.status]}</Badge>
              <Badge tone="bg-amber-50 text-amber-700 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300">Simulated</Badge>
            </div>
          )}
        </Card>

        <div className="space-y-4">
          <Card title="Fleet status" subtitle="Current vehicle states">
            <div className="space-y-3">
              {statusCounts.map((item) => {
                const total = Math.max(1, kpis.total_vehicles ?? 1);
                return (
                  <div key={item.label}>
                    <div className="mb-1 flex items-center justify-between text-xs">
                      <span className="text-ink-600 dark:text-ink-300">{item.label}</span>
                      <span className="font-semibold text-ink-900 dark:text-white">{item.value}</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-ink-100 dark:bg-white/10">
                      <div className={cn("h-full rounded-full", item.tone)} style={{ width: `${(item.value / total) * 100}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card
            title="Driver leaderboard"
            subtitle="Highest weekly safety score"
            action={
              <Link href="/drivers" className="text-xs font-semibold text-brand-600 hover:underline dark:text-brand-300">
                All drivers
              </Link>
            }
          >
            {data?.leaderboard.length ? (
              <div className="space-y-3">
                {data.leaderboard.map((row, index) => (
                  <div key={row.driver_id} className="flex items-center gap-3">
                    <span className="w-4 text-[11px] font-semibold text-ink-400">{index + 1}</span>
                    <Avatar name={row.driver_name} color={row.avatar_color} size="sm" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-semibold text-ink-900 dark:text-white">{row.driver_name}</p>
                      <p className="text-[10px] text-ink-400">{formatKm(row.distance_km)} · {row.events} events</p>
                    </div>
                    <Badge tone={scoreTone(row.score)}>{formatScore(row.score)}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No scores yet" description="Scores appear after a week of recorded trips." />
            )}
          </Card>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Weekly safety trend" subtitle="Recorded events and high-risk events" className="lg:col-span-2">
          <TrendAreaChart data={data?.trend ?? []} height={250} />
        </Card>
        <Card title="Event severity mix" subtitle="Share of events by severity">
          <SeverityDonut data={data?.events_by_severity ?? []} height={250} />
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Events by type" subtitle="What is driving risk" className="lg:col-span-2">
          <EventTypeBarChart data={data?.events_by_type ?? []} height={250} />
        </Card>
        <Card title="Vehicle activity" subtitle="Distance travelled per day">
          <ActivityBarChart data={data?.vehicle_activity ?? []} height={250} />
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card
          title="Recent incidents"
          subtitle="Newest incident records"
          action={
            <Link href="/incidents" className="text-xs font-semibold text-brand-600 hover:underline dark:text-brand-300">
              Review all
            </Link>
          }
        >
          {data?.recent_incidents.length ? (
            <div className="divide-y divide-ink-100 dark:divide-white/5">
              {data.recent_incidents.map((incident) => (
                <Link
                  key={String(incident.id)}
                  href="/incidents"
                  className="flex items-start gap-3 py-3 first:pt-0 last:pb-0"
                >
                  <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", severityTone(String(incident.severity)).includes("rose") ? "bg-rose-500" : severityTone(String(incident.severity)).includes("amber") ? "bg-amber-500" : "bg-brand-500")} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-ink-900 dark:text-white">{String(incident.title)}</p>
                    <p className="mt-0.5 text-[11px] text-ink-500">
                      {String(incident.registration_number ?? "Unassigned")} · {timeAgo(String(incident.occurred_at))}
                    </p>
                  </div>
                  <Badge tone={statusTone(String(incident.status))}>{String(incident.status).replace("_", " ")}</Badge>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState icon={<AlertTriangle className="h-5 w-5" />} title="No incidents" description="That is a good sign." />
          )}
        </Card>

        <Card
          title="Notifications"
          subtitle="Latest safety and maintenance updates"
          action={
            <Link href="/notifications" className="text-xs font-semibold text-brand-600 hover:underline dark:text-brand-300">
              View all
            </Link>
          }
        >
          {data?.recent_notifications.length ? (
            <div className="space-y-2.5">
              {data.recent_notifications.map((notification) => (
                <div key={String(notification.id)} className="flex gap-3 rounded-xl bg-ink-50 p-3 dark:bg-white/5">
                  <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white text-ink-500 shadow-sm dark:bg-white/10 dark:text-ink-300">
                    <Bell className="h-3.5 w-3.5" />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold text-ink-900 dark:text-white">{String(notification.title)}</p>
                    <p className="mt-0.5 line-clamp-2 text-[11px] text-ink-500">{String(notification.message)}</p>
                    <p className="mt-1 text-[10px] text-ink-400">{timeAgo(String(notification.created_at))}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No notifications" description="You are up to date." />
          )}
        </Card>
      </div>

      <div className="mt-4">
        <Card
          title="Vehicle health"
          subtitle="Latest diagnostic snapshot"
          action={
            <Link href="/maintenance" className="text-xs font-semibold text-brand-600 hover:underline dark:text-brand-300">
              Maintenance desk
            </Link>
          }
          padded={false}
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px]">
              <thead className="border-b border-ink-100 dark:border-white/5">
                <tr>
                  <th className="table-th">Vehicle</th>
                  <th className="table-th">Status</th>
                  <th className="table-th">Health</th>
                  <th className="table-th">Fault codes</th>
                  <th className="table-th">Mileage</th>
                  <th className="table-th">Data</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100 dark:divide-white/5">
                {(data?.vehicle_health ?? []).map((row) => (
                  <tr key={row.vehicle_id} className="hover:bg-ink-50/70 dark:hover:bg-white/5">
                    <td className="table-td font-semibold text-ink-900 dark:text-white">{row.registration_number}</td>
                    <td className="table-td">
                      <Badge tone={statusTone(row.status)}>{VEHICLE_STATUS_LABELS[row.status] ?? row.status}</Badge>
                    </td>
                    <td className="table-td">
                      <div className="flex items-center gap-2">
                        <span className="w-9 text-xs font-semibold">{row.health_score === null ? "—" : Math.round(row.health_score)}</span>
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-ink-100 dark:bg-white/10">
                          <div
                            className={cn("h-full rounded-full", (row.health_score ?? 0) >= 80 ? "bg-emerald-500" : (row.health_score ?? 0) >= 60 ? "bg-amber-500" : "bg-rose-500")}
                            style={{ width: `${row.health_score ?? 0}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="table-td text-xs">
                      {row.fault_codes.length ? (
                        <span className="font-mono text-[11px] text-rose-600">{row.fault_codes.join(", ")}</span>
                      ) : (
                        <span className="text-ink-400">—</span>
                      )}
                    </td>
                    <td className="table-td">{formatKm(row.mileage_km)}</td>
                    <td className="table-td">{row.is_simulated ? <SimulatedBadge /> : <Badge tone="bg-emerald-50 text-emerald-700">Device</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <p className="mt-4 text-[11px] leading-relaxed text-ink-400 dark:text-ink-500">{data?.disclaimer}</p>
    </div>
  );
}
