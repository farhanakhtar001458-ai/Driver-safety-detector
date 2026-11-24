"""WebSocket endpoint for live fleet telemetry."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session, joinedload

from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models import User, Vehicle, VehicleLocation
from app.services.ws_hub import manager

router = APIRouter(tags=["Realtime"])


def _initial_snapshot(db: Session, organisation_id: int) -> dict:
    vehicles = (
        db.query(Vehicle)
        .options(joinedload(Vehicle.assigned_driver))
        .filter(Vehicle.organisation_id == organisation_id, Vehicle.is_archived.is_(False))
        .all()
    )
    rows = []
    for vehicle in vehicles:
        location = (
            db.query(VehicleLocation)
            .filter(VehicleLocation.vehicle_id == vehicle.id)
            .order_by(VehicleLocation.recorded_at.desc())
            .first()
        )
        if not location:
            continue
        rows.append(
            {
                "vehicle_id": vehicle.id,
                "registration_number": vehicle.registration_number,
                "vehicle_type": vehicle.vehicle_type,
                "status": vehicle.status,
                "driver_name": vehicle.assigned_driver.full_name if vehicle.assigned_driver else None,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "speed_kph": location.speed_kph,
                "heading": location.heading,
                "last_seen": location.recorded_at.isoformat() + "Z",
                "is_simulated": location.is_simulated,
            }
        )
    return {
        "type": "fleet_snapshot",
        "vehicles": rows,
        "simulated": all(row["is_simulated"] for row in rows) if rows else True,
    }


@router.websocket("/ws/fleet")
async def fleet_stream(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
):
    payload = decode_token(token or "", expected_type="access")
    if not payload:
        await websocket.close(code=4401)
        return
    db = SessionLocal()
    try:
        try:
            user_id = int(payload.get("sub"))
        except (TypeError, ValueError):
            await websocket.close(code=4401)
            return
        user = db.get(User, user_id)
        if not user or not user.is_active:
            await websocket.close(code=4403)
            return
        room = organisation_id if user.role == "super_admin" and organisation_id else user.organisation_id
        if not room:
            await websocket.close(code=4403)
            return
        await manager.connect(websocket, room, user.id)
        await manager.send_personal(websocket, _initial_snapshot(db, room))
        while True:
            # Client pings are accepted and ignored; server pushes updates.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        room = organisation_id if (payload and payload.get("role") == "super_admin" and organisation_id) else None
        manager.disconnect(websocket, room or -1, 0)
        db.close()
