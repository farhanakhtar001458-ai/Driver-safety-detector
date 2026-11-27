"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Smartphone, MapPinOff } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Card, Select } from "@/components/ui";

type PhoneVehicle = { id: number; registration_number: string };
type Status = "idle" | "waiting" | "sharing" | "error";

/** Foreground-only opt-in location sharing; no coordinates are stored in the browser. */
export default function PhoneGps() {
  const { user } = useAuth();
  const eligible = !!user && ["org_admin", "fleet_manager", "driver"].includes(user.role);
  const [vehicles, setVehicles] = useState<PhoneVehicle[]>([]);
  const [vehicleId, setVehicleId] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");
  const [consent, setConsent] = useState(false);
  const watch = useRef<number | null>(null);
  const active = useRef(false);
  const busy = useRef(false);
  const lastSent = useRef(0);

  const stop = useCallback(() => {
    active.current = false;
    if (watch.current !== null && typeof navigator !== "undefined" && navigator.geolocation) {
      navigator.geolocation.clearWatch(watch.current);
      watch.current = null;
    }
  }, []);

  useEffect(() => {
    if (!eligible) return;
    let mounted = true;
    api.get<PhoneVehicle[]>("/gps/phone/vehicles").then((items) => {
      if (!mounted) return;
      setVehicles(items);
      setVehicleId(items[0] ? String(items[0].id) : "");
    }).catch(() => { if (mounted) setMessage("Could not load vehicles. Please refresh the page."); });
    return () => { mounted = false; stop(); };
  }, [eligible, stop]);

  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden && active.current) {
        stop();
        setStatus("idle");
        setMessage("Sharing stopped because this page was hidden. Start again when ready.");
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [stop]);

  const start = () => {
    if (!vehicleId || !consent || active.current) return;
    if (!window.isSecureContext || !navigator.geolocation) {
      setStatus("error");
      setMessage("Location requires HTTPS and a browser with GPS support.");
      return;
    }
    active.current = true;
    lastSent.current = 0;
    setStatus("waiting");
    setMessage("Allow location permission and wait for a GPS fix.");
    watch.current = navigator.geolocation.watchPosition((position) => {
      if (!active.current || busy.current || Date.now() - lastSent.current < 15000) return;
      if (Date.now() - position.timestamp > 60000 || position.coords.accuracy > 1000) {
        setMessage("Waiting for a recent GPS fix with better accuracy.");
        return;
      }
      lastSent.current = Date.now();
      busy.current = true;
      const { latitude, longitude, accuracy, speed, heading } = position.coords;
      api.post("/gps/phone", {
        vehicle_id: Number(vehicleId), latitude, longitude, accuracy_m: accuracy,
        speed_kph: speed !== null && speed >= 0 && speed * 3.6 <= 300 ? speed * 3.6 : null,
        heading: heading !== null && heading >= 0 && heading <= 360 ? heading : null,
      }).then(() => {
        if (active.current) { setStatus("sharing"); setMessage("Location sent. Keep this page open and visible."); }
      }).catch((error: unknown) => {
        if (!active.current) return;
        stop(); setStatus("error");
        setMessage(error instanceof Error ? `Sharing stopped: ${error.message}` : "Sharing stopped: could not send location.");
      }).finally(() => { busy.current = false; });
    }, (error) => {
      if (!active.current) return;
      stop(); setStatus("error");
      setMessage(error.code === 1 ? "Location permission denied. Enable it in browser settings." : "GPS unavailable or timed out. Check phone location settings and try again.");
    }, { enableHighAccuracy: true, maximumAge: 0, timeout: 20000 });
  };

  if (!eligible) return null;
  return (
    <Card title={<span className="flex items-center gap-2"><Smartphone className="h-4 w-4" /> Phone GPS</span>} subtitle="Share this phone’s location with your organisation" className="mb-4">
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
        <label className="block text-xs font-semibold text-ink-700 dark:text-ink-200">
          Vehicle
          <Select aria-label="Vehicle for phone GPS" value={vehicleId} disabled={active.current || vehicles.length === 0} onChange={(e) => setVehicleId(e.target.value)} className="mt-1.5 w-full">
            {vehicles.length === 0 && <option value="">No eligible vehicles</option>}
            {vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicle.registration_number}</option>)}
          </Select>
        </label>
        {status === "waiting" || status === "sharing" ? (
          <Button variant="secondary" onClick={() => { stop(); setStatus("idle"); setMessage("Location sharing stopped."); }}><MapPinOff className="h-4 w-4" /> Stop sharing</Button>
        ) : (
          <Button onClick={start} disabled={!vehicleId || !consent}><Smartphone className="h-4 w-4" /> Start phone GPS</Button>
        )}
      </div>
      <label className="mt-3 flex items-start gap-2 text-xs leading-relaxed text-ink-600 dark:text-ink-300">
        <input type="checkbox" className="mt-0.5" checked={consent} disabled={status === "waiting" || status === "sharing"} onChange={(e) => setConsent(e.target.checked)} />
        I agree to share this phone’s location for the selected vehicle with my organisation until I stop or hide this page.
      </label>
      <p className="mt-2 text-xs leading-relaxed text-ink-500 dark:text-ink-400">Set up before driving. Keep the page visible. Phone GPS can be inaccurate; it does not detect sleep, ignition or driving risk. A location request already in progress may finish after stopping.</p>
      {message && <p role="status" className={`mt-2 text-xs ${status === "error" ? "text-rose-600 dark:text-rose-300" : "text-brand-700 dark:text-brand-300"}`}>{message}</p>}
    </Card>
  );
}
