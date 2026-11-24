"use client";

import { useCallback, useEffect, useState } from "react";
import { CloudFog, Droplets, Eye, MapPin, Plus, Route as RouteIcon, Thermometer, TriangleAlert } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Button, Card, DemoBanner, EmptyState, Field, Input, Modal, PageHeader, PageSkeleton, Select, toast } from "@/components/ui";
import FleetMap from "@/components/map/FleetMap";
import { cn, severityTone, timeAgo } from "@/lib/format";

type Hotspot = {
  id: number;
  latitude: number;
  longitude: number;
  label: string;
  severity: string;
  radius_meters: number;
  historical_count: number;
  source: string;
  is_illustrative: boolean;
};

type Hazard = {
  id: number;
  latitude: number;
  longitude: number;
  hazard_type: string;
  severity: string;
  description?: string | null;
  status: string;
  expires_at?: string | null;
  is_simulated: boolean;
  created_at: string;
};

type RouteAnalysis = {
  distance_km: number;
  risk_rating: string;
  risk_score: number;
  hazard_count: number;
  hotspot_count: number;
  warnings: string[];
  recommendations: string[];
  data_sources: string[];
  disclaimer: string;
};

type Weather = {
  location: { latitude: number; longitude: number };
  simulated: boolean;
  source: string;
  observed_at: string;
  condition: string;
  temperature_c?: number;
  visibility_km?: number;
  humidity_pct?: number;
};

const HAZARD_TYPES = ["pothole", "fog", "construction", "flooding", "accident", "obstruction", "other"];

const EMPTY_FORM = { latitude: "23.2599", longitude: "77.4126", hazard_type: "pothole", severity: "medium", description: "", expires_in_hours: 24 };

export default function RoadSafetyPage() {
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [hazards, setHazards] = useState<Hazard[]>([]);
  const [weather, setWeather] = useState<Weather | null>(null);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [analysis, setAnalysis] = useState<RouteAnalysis | null>(null);
  const [analysing, setAnalysing] = useState(false);
  const [waypoints, setWaypoints] = useState("23.2599,77.4126; 23.2330,77.4100");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [hotspotData, hazardData, weatherData] = await Promise.all([
        api.get<{ hotspots: Hotspot[] }>("/intelligence/hotspots"),
        api.get<Hazard[]>("/intelligence/hazards"),
        api.get<Weather>("/intelligence/weather"),
      ]);
      setHotspots(hotspotData.hotspots ?? []);
      setHazards(hazardData ?? []);
      setWeather(weatherData);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not load road safety data.", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const analyseRoute = async () => {
    const points = waypoints
      .split(";")
      .map((pair) => pair.split(",").map((value) => Number(value.trim())))
      .filter((pair) => pair.length === 2 && pair.every((value) => Number.isFinite(value)));
    if (points.length < 2) {
      toast("Enter at least two coordinate pairs separated by semicolons.", "error");
      return;
    }
    setAnalysing(true);
    try {
      const result = await api.post<RouteAnalysis>("/intelligence/route-analysis", {
        points: points.map(([latitude, longitude]) => ({ latitude, longitude })),
      });
      setAnalysis(result);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Route analysis failed.", "error");
    } finally {
      setAnalysing(false);
    }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await api.post("/intelligence/hazards", {
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
        hazard_type: form.hazard_type,
        severity: form.severity,
        description: form.description || null,
        expires_in_hours: Number(form.expires_in_hours),
      });
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      toast("Hazard reported. It expires automatically.");
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not report the hazard.", "error");
    } finally {
      setSaving(false);
    }
  };

  if (loading && !weather) return <PageSkeleton cards={3} />;

  const activeHazards = hazards.filter((hazard) => hazard.status === "active");

  return (
    <div>
      <PageHeader
        eyebrow="Safety intelligence · external context"
        title="Road safety intelligence"
        description="Historical hotspots and live-reported hazards are kept separate on purpose. Hotspots here are illustrative, not official accident statistics."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" /> Report hazard
          </Button>
        }
      />

      <DemoBanner message="Hotspot data is an illustrative demo dataset. It is not sourced from a police or government accident register and must not be quoted as a real statistic." />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Illustrative hotspots", value: hotspots.length, icon: <MapPin className="h-5 w-5" />, hint: "Historical, not live" },
          { label: "Active hazards", value: activeHazards.length, icon: <TriangleAlert className="h-5 w-5" />, hint: "Reported and time-bound" },
          { label: "High-severity hazards", value: activeHazards.filter((hazard) => hazard.severity === "high" || hazard.severity === "critical").length, icon: <Eye className="h-5 w-5" />, hint: "Worth routing around" },
          { label: "Weather source", value: weather?.simulated ? "Simulated" : "Provider", icon: <CloudFog className="h-5 w-5" />, hint: weather?.source ?? "—" },
        ].map((stat) => (
          <Card key={stat.label} className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-500 dark:text-ink-400">{stat.label}</p>
                <p className="mt-2 text-xl font-semibold tracking-tight text-ink-950 dark:text-white">{stat.value}</p>
                <p className="mt-1 text-[10px] text-ink-400">{stat.hint}</p>
              </div>
              <span className="text-ink-400">{stat.icon}</span>
            </div>
          </Card>
        ))}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card padded={false} title="Hotspots and live hazards" subtitle="Circles show hotspot radius; markers show reported hazards">
          <div className="p-2">
            <FleetMap
              vehicles={[]}
              geofences={hotspots.map((spot) => ({
                id: spot.id,
                name: `${spot.label} (illustrative)`,
                center_latitude: spot.latitude,
                center_longitude: spot.longitude,
                radius_meters: spot.radius_meters,
                is_active: true,
              }))}
              height={420}
            />
          </div>
          <div className="flex flex-wrap items-center gap-4 border-t border-ink-100 px-4 py-2.5 text-[11px] text-ink-500 dark:border-white/5 dark:text-ink-400">
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full border border-dashed border-indigo-400" /> Illustrative hotspot</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-amber-500" /> Reported hazard</span>
            <span className="ml-auto text-[10px]">Hotspots and hazards are distinct data sources.</span>
          </div>
        </Card>

        <div className="space-y-4">
          <Card title="Weather context" subtitle={weather?.observed_at ? `Observed ${timeAgo(weather.observed_at)}` : ""}>
            {weather ? (
              <>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">{weather.condition}</p>
                    <p className="text-[11px] text-ink-400">{weather.source}</p>
                  </div>
                  <Badge tone={weather.simulated ? "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300" : "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300"}>
                    {weather.simulated ? "Simulated sample" : "Live provider"}
                  </Badge>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2">
                  {[
                    { icon: <Thermometer className="h-3.5 w-3.5" />, label: "Temp", value: weather.temperature_c != null ? `${weather.temperature_c}°C` : "—" },
                    { icon: <Eye className="h-3.5 w-3.5" />, label: "Visibility", value: weather.visibility_km != null ? `${weather.visibility_km} km` : "—" },
                    { icon: <Droplets className="h-3.5 w-3.5" />, label: "Humidity", value: weather.humidity_pct != null ? `${weather.humidity_pct}%` : "—" },
                  ].map((item) => (
                    <div key={item.label} className="rounded-xl bg-ink-50 p-2.5 dark:bg-white/5">
                      <span className="text-ink-400">{item.icon}</span>
                      <p className="mt-1 text-[10px] uppercase tracking-wide text-ink-400">{item.label}</p>
                      <p className="text-xs font-semibold text-ink-900 dark:text-white">{item.value}</p>
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-[10px] leading-relaxed text-ink-400">
                  {weather.simulated
                    ? "No weather provider key is configured, so this is a labelled sample. It is not a live observation."
                    : "Weather data comes from the configured provider and may lag real conditions."}
                </p>
              </>
            ) : (
              <EmptyState title="Weather unavailable" description="No weather data could be loaded." />
            )}
          </Card>

          <Card
            title="Route risk check"
            subtitle="Analyse a polyline against hazards"
            action={<RouteIcon className="h-4 w-4 text-brand-500" />}
          >
            <Field label="Waypoints" hint="Pairs of latitude,longitude separated by semicolons.">
              <textarea
                value={waypoints}
                onChange={(event) => setWaypoints(event.target.value)}
                className="input min-h-[64px] font-mono text-[11px]"
                spellCheck={false}
              />
            </Field>
            <Button className="mt-3 w-full" onClick={analyseRoute} loading={analysing}>
              Analyse route
            </Button>
            {analysis && (
              <div className="mt-4 space-y-3 rounded-xl border border-ink-100 p-3 dark:border-white/10">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-ink-900 dark:text-white">Risk: {analysis.risk_rating}</span>
                  <Badge tone={severityTone(analysis.risk_rating)}>{analysis.risk_score.toFixed(2)}</Badge>
                </div>
                <p className="text-[11px] text-ink-500 dark:text-ink-400">
                  {analysis.distance_km.toFixed(1)} km · {analysis.hazard_count} hazards · {analysis.hotspot_count} illustrative hotspots
                </p>
                {analysis.warnings.map((warning) => (
                  <p key={warning} className="text-[11px] text-amber-700 dark:text-amber-300">· {warning}</p>
                ))}
                {analysis.recommendations.map((item) => (
                  <p key={item} className="text-[11px] text-ink-600 dark:text-ink-300">→ {item}</p>
                ))}
                <p className="text-[10px] leading-relaxed text-ink-400">Sources: {analysis.data_sources.join(", ")}.</p>
              </div>
            )}
          </Card>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card padded={false} title="Illustrative hotspots" subtitle="Historical pattern, not live condition">
          <div className="max-h-[360px] divide-y divide-ink-100 overflow-y-auto dark:divide-white/5">
            {hotspots.map((spot) => (
              <div key={spot.id} className="flex items-start gap-3 px-4 py-3">
                <Badge tone={severityTone(spot.severity)}>{spot.severity}</Badge>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-ink-900 dark:text-white">{spot.label}</p>
                  <p className="text-[10px] leading-relaxed text-ink-400">
                    {spot.historical_count} historical records · radius {Math.round(spot.radius_meters)} m
                  </p>
                  <p className="mt-0.5 text-[9px] italic text-ink-400">{spot.source}</p>
                </div>
                {spot.is_illustrative && <Badge tone="bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">Illustrative</Badge>}
              </div>
            ))}
          </div>
        </Card>

        <Card padded={false} title="Reported hazards" subtitle="Live, expiring, user-submitted">
          <div className="max-h-[360px] divide-y divide-ink-100 overflow-y-auto dark:divide-white/5">
            {hazards.length === 0 ? (
              <div className="p-4">
                <EmptyState icon={<TriangleAlert className="h-5 w-5" />} title="No hazards reported" description="Report a pothole, fog patch or obstruction to warn drivers." />
              </div>
            ) : (
              hazards.map((hazard) => (
                <div key={hazard.id} className="flex items-start gap-3 px-4 py-3">
                  <Badge tone={severityTone(hazard.severity)}>{hazard.severity}</Badge>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold capitalize text-ink-900 dark:text-white">{hazard.hazard_type.replace(/_/g, " ")}</p>
                    <p className="text-[10px] leading-relaxed text-ink-400">
                      {hazard.description ?? "No description"} · {timeAgo(hazard.created_at)}
                      {hazard.expires_at ? ` · expires ${new Date(hazard.expires_at).toLocaleTimeString()}` : ""}
                    </p>
                  </div>
                  {hazard.is_simulated && <Badge tone="bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">Simulated</Badge>}
                  {hazard.status !== "active" && <Badge tone="bg-ink-100 text-ink-600 dark:bg-white/10 dark:text-ink-300">{hazard.status}</Badge>}
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      <Card title="Data provenance" subtitle="Why hotspots and hazards look different" className="mt-4">
        <div className="grid gap-3 text-[11px] leading-relaxed sm:grid-cols-3">
          <div className={cn("rounded-xl border border-amber-200 bg-amber-50 p-3 dark:border-amber-500/20 dark:bg-amber-500/5")}>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">Historical hotspots</p>
            <p className="mt-1 text-amber-800 dark:text-amber-200">
              Aggregated past records for orientation. In this demo they are illustrative sample data, not official
              accident statistics.
            </p>
          </div>
          <div className={cn("rounded-xl border border-indigo-200 bg-indigo-50 p-3 dark:border-indigo-500/20 dark:bg-indigo-500/5")}>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-indigo-700 dark:text-indigo-300">Live hazards</p>
            <p className="mt-1 text-indigo-800 dark:text-indigo-200">
              User-reported, time-bound and expiring. They describe conditions right now and are removed when stale.
            </p>
          </div>
          <div className={cn("rounded-xl border border-ink-200 bg-ink-50 p-3 dark:border-white/10 dark:bg-white/5")}>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-600 dark:text-ink-300">Weather</p>
            <p className="mt-1 text-ink-600 dark:text-ink-300">
              Pulled from a provider when configured. Without a key this deployment returns a clearly labelled simulated
              sample rather than fabricating conditions.
            </p>
          </div>
        </div>
      </Card>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Report a road hazard"
        description="Hazard reports expire automatically to avoid stale warnings."
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={submit} loading={saving}>Report hazard</Button>
          </>
        }
      >
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          <Field label="Latitude" required>
            <Input type="number" step="0.000001" min={-90} max={90} value={form.latitude} onChange={(event) => setForm({ ...form, latitude: event.target.value })} required />
          </Field>
          <Field label="Longitude" required>
            <Input type="number" step="0.000001" min={-180} max={180} value={form.longitude} onChange={(event) => setForm({ ...form, longitude: event.target.value })} required />
          </Field>
          <Field label="Hazard type" required>
            <Select value={form.hazard_type} onChange={(event) => setForm({ ...form, hazard_type: event.target.value })}>
              {HAZARD_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
            </Select>
          </Field>
          <Field label="Severity" required>
            <Select value={form.severity} onChange={(event) => setForm({ ...form, severity: event.target.value })}>
              {["low", "medium", "high", "critical"].map((level) => <option key={level} value={level}>{level}</option>)}
            </Select>
          </Field>
          <div className="sm:col-span-2">
            <Field label="Description">
              <Input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Large pothole in the left lane" maxLength={255} />
            </Field>
          </div>
          <Field label="Expires in (hours)" hint="Between 1 and 720 hours.">
            <Input type="number" min={1} max={720} value={form.expires_in_hours} onChange={(event) => setForm({ ...form, expires_in_hours: Number(event.target.value) })} />
          </Field>
          <button type="submit" className="hidden" aria-hidden="true" />
        </form>
      </Modal>
    </div>
  );
}
