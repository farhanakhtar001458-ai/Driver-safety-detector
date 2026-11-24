from fastapi import APIRouter

from app.api.v1 import (
    ai_models,
    assistant,
    audit,
    auth,
    behaviour,
    dashboard,
    drivers,
    gps,
    health,
    incidents,
    intelligence,
    maintenance,
    notifications,
    organisations,
    reports,
    risk,
    scores,
    subscriptions,
    vehicles,
    ws,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(organisations.router)
api_router.include_router(vehicles.router)
api_router.include_router(drivers.router)
api_router.include_router(gps.router)
api_router.include_router(behaviour.router)
api_router.include_router(scores.router)
api_router.include_router(risk.router)
api_router.include_router(incidents.router)
api_router.include_router(maintenance.router)
api_router.include_router(notifications.router)
api_router.include_router(reports.router)
api_router.include_router(assistant.router)
api_router.include_router(subscriptions.router)
api_router.include_router(audit.router)
api_router.include_router(ai_models.router)
api_router.include_router(intelligence.router)
api_router.include_router(ws.router)
