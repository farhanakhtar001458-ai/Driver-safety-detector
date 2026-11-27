"use client";

import { useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Circle, MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import type { LiveVehicle } from "@/lib/types";
import { validCoordinates } from "@/lib/map";
import { VEHICLE_STATUS_LABELS } from "@/lib/format";

export interface MapTrail {
  vehicle_id: number;
  registration_number: string;
  points: { latitude: number; longitude: number; speed_kph: number; recorded_at: string }[];
  is_simulated: boolean;
}

export interface MapGeofence {
  id: number;
  name: string;
  center_latitude: number;
  center_longitude: number;
  radius_meters: number;
  is_active: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  active: "#0dab99",
  inactive: "#94a3b8",
  under_maintenance: "#f59e0b",
  offline: "#ef4444",
};

function vehicleIcon(status: string, speed: number) {
  const colour = STATUS_COLORS[status] ?? "#0dab99";
  const moving = speed > 3;
  const html = `
    <div style="position:relative;display:flex;align-items:center;justify-content:center;">
      <div style="position:absolute;width:34px;height:34px;border-radius:9999px;background:${colour}22;animation:pulse 1.8s infinite;"></div>
      <div style="width:22px;height:22px;border-radius:9999px;background:${colour};border:3px solid white;box-shadow:0 4px 10px rgba(15,23,42,.35);display:flex;align-items:center;justify-content:center;">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="white"><path d="M18 10a2 2 0 00-2-2H8a2 2 0 00-2 2v8h2v-2h8v2h2v-8zM8.5 14A1.5 1.5 0 1110 12.5 1.5 1.5 0 018.5 14zm7 0a1.5 1.5 0 111.5-1.5A1.5 1.5 0 0115.5 14z"/></svg>
      </div>
      ${moving ? `<div style="position:absolute;top:-14px;left:50%;transform:translateX(-50%);background:#0f172a;color:#fff;font-size:9px;font-weight:700;padding:1px 4px;border-radius:4px;white-space:nowrap;">${Math.round(speed)} km/h</div>` : ""}
    </div>
    <style>@keyframes pulse{0%{transform:scale(.7);opacity:.7}70%{transform:scale(1.35);opacity:0}100%{opacity:0}}</style>`;
  return L.divIcon({ className: "leaflet-div-icon", html, iconSize: [34, 34], iconAnchor: [17, 17], popupAnchor: [0, -12] });
}

function MapViewport({ vehicles, trails, selectedId }: { vehicles: LiveVehicle[]; trails: MapTrail[]; selectedId?: number | null }) {
  const map = useMap();
  const fitted = useRef(false);
  const lastSelection = useRef<number | null>(null);
  useEffect(() => {
    if (fitted.current) return;
    const points: [number, number][] = [
      ...vehicles.filter((v) => validCoordinates(v.latitude, v.longitude)).map((v) => [v.latitude, v.longitude] as [number, number]),
      ...trails.flatMap((trail) => trail.points.filter((p) => validCoordinates(p.latitude, p.longitude)).slice(-2).map((p) => [p.latitude, p.longitude] as [number, number])),
    ];
    if (!points.length) return;
    fitted.current = true;
    if (points.length === 1) map.setView(points[0], 13);
    else map.fitBounds(L.latLngBounds(points), { padding: [36, 36], maxZoom: 14 });
  }, [vehicles, trails, map]);
  useEffect(() => {
    if (selectedId == null) { lastSelection.current = null; return; }
    if (lastSelection.current === selectedId) return;
    const vehicle = vehicles.find((v) => v.vehicle_id === selectedId && validCoordinates(v.latitude, v.longitude));
    if (vehicle) {
      lastSelection.current = selectedId;
      map.setView([vehicle.latitude, vehicle.longitude], Math.max(map.getZoom(), 13));
    }
  }, [selectedId, vehicles, map]);
  useEffect(() => {
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => map.invalidateSize({ pan: false }));
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  return null;
}

export default function FleetMap({
  vehicles = [],
  trails = [],
  geofences = [],
  height = 440,
  selectedId,
  onSelect,
  className,
}: {
  vehicles?: LiveVehicle[];
  trails?: MapTrail[];
  geofences?: MapGeofence[];
  height?: number | string;
  selectedId?: number | null;
  onSelect?: (vehicle: LiveVehicle) => void;
  className?: string;
}) {
  const centre = useMemo<[number, number]>(() => {
    const first = vehicles.find((v) => validCoordinates(v.latitude, v.longitude));
    return first ? [first.latitude, first.longitude] : [23.2599, 77.4126];
  }, [vehicles]);

  const trailColours = ["#0dab99", "#6366f1", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

  return (
    <div className={className} style={{ height }}>
      <MapContainer center={centre} zoom={12} scrollWheelZoom className="h-full w-full rounded-2xl">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapViewport vehicles={vehicles} trails={trails} selectedId={selectedId} />

        {geofences.filter((fence) => validCoordinates(fence.center_latitude, fence.center_longitude) && Number.isFinite(fence.radius_meters) && fence.radius_meters > 0).map((fence) => (
          <Circle
            key={fence.id}
            center={[fence.center_latitude, fence.center_longitude]}
            radius={fence.radius_meters}
            pathOptions={{
              color: fence.is_active ? "#6366f1" : "#94a3b8",
              weight: 1.5,
              fillColor: "#6366f1",
              fillOpacity: 0.06,
              dashArray: "6 6",
            }}
          >
            <Popup>
              <div className="text-xs">
                <p className="font-semibold">Geofence · {fence.name}</p>
                <p className="text-ink-500">Radius {Math.round(fence.radius_meters)} m</p>
              </div>
            </Popup>
          </Circle>
        ))}

        {trails.map((trail, index) => (
          <Polyline
            key={trail.vehicle_id}
            positions={trail.points.filter((point) => validCoordinates(point.latitude, point.longitude)).map((point) => [point.latitude, point.longitude] as [number, number])}
            pathOptions={{ color: trailColours[index % trailColours.length], weight: 3, opacity: 0.65 }}
          />
        ))}

        {vehicles.filter((vehicle) => validCoordinates(vehicle.latitude, vehicle.longitude)).map((vehicle) => (
          <Marker
            key={vehicle.vehicle_id}
            position={[vehicle.latitude, vehicle.longitude]}
            icon={vehicleIcon(vehicle.status, vehicle.source === "phone" ? 0 : vehicle.speed_kph)}
            eventHandlers={{ click: () => onSelect?.(vehicle) }}
          >
            <Popup>
              <div className="min-w-[180px] text-xs">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-semibold text-ink-900">{vehicle.registration_number}</p>
                  <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-semibold text-brand-700">
                    {VEHICLE_STATUS_LABELS[vehicle.status] ?? vehicle.status}
                  </span>
                </div>
                <p className="mt-1 text-ink-500">{vehicle.driver_name ?? "Unassigned"}</p>
                <p className="mt-0.5 text-ink-500">
                  {vehicle.source === "phone" ? "Phone GPS · speed may be unavailable" : `${vehicle.speed_kph.toFixed(0)} km/h`} · {vehicle.vehicle_type}
                </p>
                {vehicle.is_simulated && (
                  <p className="mt-1.5 rounded-md bg-amber-50 px-1.5 py-1 text-[10px] font-medium text-amber-700">
                    Simulated demo position
                  </p>
                )}
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
