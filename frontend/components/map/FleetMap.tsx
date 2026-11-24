"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import type { LiveVehicle } from "@/lib/types";
import type { MapGeofence, MapTrail } from "./FleetMapImpl";

export type { MapGeofence, MapTrail } from "./FleetMapImpl";

type Props = {
  vehicles?: LiveVehicle[];
  trails?: MapTrail[];
  geofences?: MapGeofence[];
  height?: number | string;
  selectedId?: number | null;
  onSelect?: (vehicle: LiveVehicle) => void;
  className?: string;
};

/**
 * Leaflet touches `window` at import time, so the map is loaded only in the
 * browser. The placeholder keeps the same height so the page does not shift.
 */
const FleetMapImpl: ComponentType<Props> = dynamic(() => import("./FleetMapImpl"), {
  ssr: false,
  loading: () => (
    <div
      className="flex w-full items-center justify-center rounded-2xl border border-dashed border-ink-200 bg-ink-50 dark:border-white/10 dark:bg-white/5"
      style={{ height: 400 }}
    >
      <div className="flex flex-col items-center gap-2">
        <span className="h-6 w-6 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
        <span className="text-[11px] text-ink-400">Loading map…</span>
      </div>
    </div>
  ),
});

export default function FleetMap(props: Props) {
  return <FleetMapImpl {...props} />;
}
