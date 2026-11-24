# SafeWay AI backend image.
#
# Production notes:
# - runs as an unprivileged user
# - healthcheck hits the liveness endpoint
# - the SQLite file (if used) lives in /app/data, which should be a volume

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Build toolchain only for the dependency stage (bcrypt, pydantic-core wheels).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 safeway \
    && mkdir -p /app/data/reports \
    && chown -R safeway:safeway /app

USER safeway

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

# init_db() creates the schema and seeds demo data when SEED_DEMO_DATA=true.
# For managed production, run `alembic upgrade head` in a release step instead.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
