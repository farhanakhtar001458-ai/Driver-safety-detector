"use client";

import { useEffect, useRef, useState } from "react";
import { api, tokenStore } from "@/lib/api";
import type { LiveVehicle } from "@/lib/types";

type Connection = "websocket" | "polling" | "connecting" | "error";

/**
 * Live fleet hook.
 *
 * It first tries the WebSocket endpoint (same origin, proxied by nginx in
 * production). When the WebSocket cannot be established - for example inside a
 * development preview that does not proxy upgrades - it falls back to polling
 * the REST endpoint every few seconds. Both paths show the same data and the UI
 * always labels simulated telemetry.
 */
export function useLiveFleet(enabled = true, intervalMs = 5000) {
  const [vehicles, setVehicles] = useState<LiveVehicle[]>([]);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [connection, setConnection] = useState<Connection>("connecting");
  const socketRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const attempts = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let polling = false;
    attempts.current = 0;

    const poll = async () => {
      if (cancelled || polling) return;
      polling = true;
      try {
        const data = await api.get<LiveVehicle[]>("/gps/live");
        if (cancelled) return;
        setVehicles(data);
        setLastUpdated(new Date());
        setConnection((current) => (current === "websocket" ? current : "polling"));
      } catch {
        if (!cancelled) setConnection((current) => current === "websocket" ? current : "error");
      } finally {
        polling = false;
      }
    };

    const startPolling = () => {
      if (cancelled || pollRef.current) return;
      void poll();
      pollRef.current = setInterval(poll, intervalMs);
    };

    const connectSocket = () => {
      if (cancelled || typeof window === "undefined") return;
      const token = tokenStore.get().access;
      if (!token) {
        startPolling();
        return;
      }
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const base = process.env.NEXT_PUBLIC_WS_URL || `${protocol}://${window.location.host}`;
      let socket: WebSocket;
      try {
        socket = new WebSocket(`${base}/api/v1/ws/fleet?token=${encodeURIComponent(token)}`);
      } catch {
        startPolling();
        return;
      }
      socketRef.current = socket;

      socket.onopen = () => {
        attempts.current = 0;
        if (!cancelled) setConnection("websocket");
        // Real device ingestion does not broadcast WebSocket updates yet.
        // Keep periodic REST refresh active even while the socket is connected.
        startPolling();
      };
      socket.onmessage = (event) => {
        if (cancelled) return;
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "fleet_update" && Array.isArray(payload.vehicles)) {
            setVehicles((current) => {
              const byId = new Map(current.map((vehicle) => [vehicle.vehicle_id, vehicle]));
              for (const vehicle of payload.vehicles as LiveVehicle[]) {
                byId.set(vehicle.vehicle_id, { ...byId.get(vehicle.vehicle_id), ...vehicle });
              }
              return Array.from(byId.values());
            });
            setLastUpdated(new Date());
          } else if (payload.type === "fleet_snapshot" && Array.isArray(payload.vehicles)) {
            // REST is authoritative and includes metrics absent from snapshots.
            void poll();
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      socket.onerror = () => {
        attempts.current += 1;
        if (attempts.current >= 2) startPolling();
      };
      socket.onclose = () => {
        if (cancelled) return;
        setConnection("connecting");
        attempts.current += 1;
        if (attempts.current >= 2) {
          startPolling();
        } else {
          reconnectTimer = setTimeout(connectSocket, 1500);
        }
      };
    };

    connectSocket();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socketRef.current?.close();
      socketRef.current = null;
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [enabled, intervalMs]);

  return { vehicles, lastUpdated, connection };
}
