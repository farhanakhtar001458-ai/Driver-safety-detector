"""SafeWay AI application entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.rate_limit import RateLimitMiddleware
from app.db.init_db import init_db
from app.services.simulator import simulator
from app.services.ws_hub import manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s (%s)", settings.APP_NAME, __version__, settings.ENVIRONMENT)
    init_db()
    consumer = asyncio.create_task(manager.consume())
    if settings.DEMO_MODE and settings.SIMULATOR_ENABLED:
        simulator.start()
    logger.info("Ready. Demo data: %s | Simulator: %s", settings.SEED_DEMO_DATA, settings.SIMULATOR_ENABLED)
    try:
        yield
    finally:
        simulator.stop()
        consumer.cancel()
        logger.info("Shutdown complete")


app = FastAPI(
    title="SafeWay AI - Driving Safety Management API",
    version=__version__,
    description=(
        "Multi-tenant driving safety platform: GPS tracking, behaviour analytics, "
        "explainable safety scoring, risk triage, incidents, maintenance and reporting.\n\n"
        "**Demo notice:** this deployment includes clearly-labelled simulated telemetry. "
        "Safety scores and risk levels support coaching and review; they do not predict accidents."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
app.add_middleware(GZipMiddleware, minimum_size=1200)
app.add_middleware(RateLimitMiddleware)
register_exception_handlers(app)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", include_in_schema=False)
def root():
    return {
        "name": settings.APP_NAME,
        "version": __version__,
        "docs": "/api/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
        "notice": "Simulated demo data is labelled throughout. No live vehicles are represented.",
    }
