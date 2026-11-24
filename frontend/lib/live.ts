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

    const poll = async () => {
      try {
        const data = await api.get<LiveVehicle[]>("/gps/live");
        if (cancelled) return;
        setVehicles(data);
        setLastUpdated(new Date());
        setConnection((current) => (current === "websocket" ? current : "polling"));
      } catch {
        if (!cancelled) setConnection("error");
      }
    };

    const startPolling = () => {
      if (pollRef.current) return;
      void poll();
      pollRef.current = setInterval(poll, intervalMs);
    };

    const connectSocket = () => {
      if (typeof window === "undefined") return;
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
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      };
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "fleet_update" && Array.isArray(payload.vehicles)) {
            setVehicles(payload.vehicles);
            setLastUpdated(new Date());
          } else if (payload.type === "fleet_snapshot" && Array.isArray(payload.vehicles)) {
            setVehicles(payload.vehicles);
            setLastUpdated(new Date());
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
        attempts.current += 1;
        if (attempts.current >= 2) {
          startPolling();
          setConnection("polling");
        } else {
          setTimeout(connectSocket, 1500);
        }
      };
    };

    connectSocket();

    return () => {
      cancelled = true;
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
