"""Simulated telemetry generator.

Produces clearly-labelled demonstration telemetry for vehicles that have no
physical GPS device. Every generated row carries ``is_simulated=True`` and
``source='simulated'``; the UI shows a SIMULATED badge. The simulator never
represents these coordinates as real vehicle positions.
"""

from __future__ import annotations

import logging
import math
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Driver, Vehicle, VehicleLocation
from app.services.telemetry import close_stale_trips, record_health, record_point
from app.services.ws_hub import manager

logger = logging.getLogger(__name__)

# Approximate demonstration corridors around Bhopal, Madhya Pradesh.
# Coordinates are illustrative and are NOT real road geometry.
ROUTES: list[dict] = [
    {
        "name": "Airport Corridor (demo)",
        "points": [(23.2870, 77.3370), (23.2760, 77.3450), (23.2620, 77.3600), (23.2480, 77.3750), (23.2400, 77.3950), (23.2330, 77.4100)],
    },
    {
        "name": "MP Nagar Loop (demo)",
        "points": [(23.2360, 77.4010), (23.2330, 77.4080), (23.2280, 77.4140), (23.2220, 77.4080), (23.2260, 77.3990), (23.2330, 77.3950)],
    },
    {
        "name": "Habibganj Route (demo)",
        "points": [(23.2450, 77.4200), (23.2380, 77.4300), (23.2300, 77.4400), (23.2210, 77.4450), (23.2120, 77.4380)],
    },
    {
        "name": "Kolar Road (demo)",
        "points": [(23.2300, 77.3800), (23.2200, 77.3730), (23.2100, 77.3660), (23.2000, 77.3600), (23.1900, 77.3560)],
    },
    {
        "name": "Raisen Road (demo)",
        "points": [(23.2500, 77.4200), (23.2600, 77.4300), (23.2700, 77.4400), (23.2800, 77.4500), (23.2900, 77.4550)],
    },
    {
        "name": "Berasia Road (demo)",
        "points": [(23.2600, 77.3900), (23.2700, 77.3950), (23.2800, 77.4000), (23.2900, 77.4050), (23.3000, 77.4100)],
    },
]


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _heading(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    x = math.sin(d_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


@dataclass
class Route:
    name: str
    points: list[tuple[float, float]]
    cumulative: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cumulative = [0.0]
        for index in range(1, len(self.points)):
            previous = self.points[index - 1]
            current = self.points[index]
            self.cumulative.append(
                self.cumulative[-1] + _haversine(previous[0], previous[1], current[0], current[1])
            )

    @property
    def total_km(self) -> float:
        return self.cumulative[-1]

    def sample(self, distance_km: float) -> tuple[float, float, float]:
        distance = distance_km % max(self.total_km, 0.001)
        for index in range(1, len(self.points)):
            if distance <= self.cumulative[index]:
                segment = self.cumulative[index] - self.cumulative[index - 1]
                ratio = (distance - self.cumulative[index - 1]) / max(segment, 1e-9)
                lat1, lon1 = self.points[index - 1]
                lat2, lon2 = self.points[index]
                lat = lat1 + (lat2 - lat1) * ratio
                lon = lon1 + (lon2 - lon1) * ratio
                return lat, lon, _heading(lat1, lon1, lat2, lon2)
        return self.points[-1][0], self.points[-1][1], 0.0


@dataclass
class SimState:
    vehicle_id: int
    route: Route
    distance_km: float = random.uniform(0, 5)
    speed_kph: float = 40.0
    phase: float = random.uniform(0, math.tau)
    ticks: int = 0


class TelemetrySimulator:
    def __init__(self) -> None:
        self.routes = [Route(route["name"], route["points"]) for route in ROUTES]
        self.states: dict[int, SimState] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._started_at = time.time()
        self._lock = threading.Lock()

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="telemetry-simulator", daemon=True)
        self._thread.start()
        logger.info("Telemetry simulator started (simulated data only)")

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        # Give the database a moment after first boot.
        time.sleep(2)
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:  # never crash the worker thread
                logger.exception("Simulator tick failed: %s", exc)
            self._stop.wait(settings.SIMULATOR_INTERVAL_SECONDS)

    # -- state -------------------------------------------------------------
    def _ensure_states(self, db) -> None:
        vehicles = (
            db.query(Vehicle)
            .filter(Vehicle.is_archived.is_(False), Vehicle.status == "active")
            .order_by(Vehicle.id)
            .limit(settings.SIMULATOR_VEHICLE_COUNT)
            .all()
        )
        with self._lock:
            for index, vehicle in enumerate(vehicles):
                if vehicle.id not in self.states:
                    self.states[vehicle.id] = SimState(
                        vehicle_id=vehicle.id,
                        route=self.routes[index % len(self.routes)],
                    )

    def _speed(self, state: SimState) -> float:
        elapsed = time.time() - self._started_at
        wave = math.sin(elapsed / 45.0 + state.phase)
        target = 48 + wave * 22 + random.uniform(-4, 4)
        return max(18.0, min(102.0, target))

    # -- tick --------------------------------------------------------------
    def tick(self) -> dict:
        db = SessionLocal()
        try:
            self._ensure_states(db)
            now = datetime.utcnow()
            live = []
            live_by_org: dict[int, list[dict]] = {}
            with self._lock:
                states = list(self.states.values())
            for state in states:
                vehicle = db.get(Vehicle, state.vehicle_id)
                if not vehicle or vehicle.is_archived:
                    continue
                speed = self._speed(state)
                interval = settings.SIMULATOR_INTERVAL_SECONDS
                distance_delta = speed * interval / 3600.0
                state.distance_km += distance_delta
                lat, lng, heading = state.route.sample(state.distance_km)
                point = {
                    "latitude": round(lat, 6),
                    "longitude": round(lng, 6),
                    "speed_kph": round(speed, 1),
                    "heading": round(heading, 1),
                    "accuracy_m": round(random.uniform(3, 9), 1),
                    "recorded_at": now,
                    "ignition_on": True,
                }
                record_point(
                    db,
                    vehicle,
                    point,
                    source="simulated",
                    is_simulated=True,
                    device=vehicle.gps_device,
                )
                vehicle.status = "active"
                state.ticks += 1
                if state.ticks % 40 == 0:
                    record_health(
                        db,
                        vehicle,
                        engine_temperature_c=round(random.uniform(82, 96), 1),
                        battery_voltage=round(random.uniform(12.1, 13.9), 2),
                        fuel_level_pct=round(random.uniform(35, 95), 1),
                        fault_codes=[],
                        source="simulated",
                        is_simulated=True,
                    )
                live_row = (
                    {
                        "vehicle_id": vehicle.id,
                        "registration_number": vehicle.registration_number,
                        "vehicle_type": vehicle.vehicle_type,
                        "status": vehicle.status,
                        "driver_name": vehicle.assigned_driver.full_name if vehicle.assigned_driver else None,
                        "latitude": point["latitude"],
                        "longitude": point["longitude"],
                        "speed_kph": point["speed_kph"],
                        "heading": point["heading"],
                        "ignition_on": True,
                        "last_seen": now.isoformat() + "Z",
                        "is_simulated": True,
                        "route": state.route.name,
                    }
                )
                live.append(live_row)
                live_by_org.setdefault(vehicle.organisation_id, []).append(live_row)
            if live:
                db.commit()
                for organisation_id, org_vehicles in live_by_org.items():
                    manager.publish(
                        organisation_id,
                        {
                            "type": "fleet_update",
                            "server_time": now.isoformat() + "Z",
                            "simulated": True,
                            "vehicles": org_vehicles,
                        },
                    )
            # Housekeeping: close stale trips and trim very old simulated points.
            if int(time.time()) % 300 < settings.SIMULATOR_INTERVAL_SECONDS:
                close_stale_trips(db)
                cutoff = datetime.utcnow() - timedelta(hours=3)
                db.query(VehicleLocation).filter(
                    VehicleLocation.is_simulated.is_(True), VehicleLocation.recorded_at < cutoff
                ).delete(synchronize_session=False)
                db.commit()
            return {"vehicles": live, "simulated": True}
        finally:
            db.close()

    def status(self) -> dict:
        return {
            "running": bool(self._thread and self._thread.is_alive()),
            "tracked_vehicles": len(self.states),
            "interval_seconds": settings.SIMULATOR_INTERVAL_SECONDS,
            "routes": [route.name for route in self.routes],
            "note": "All simulator output is labelled simulated and does not represent real vehicles.",
        }


simulator = TelemetrySimulator()
