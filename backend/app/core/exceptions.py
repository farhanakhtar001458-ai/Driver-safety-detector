"""Application exceptions and handlers."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    status_code = 400
    error_code = "bad_request"

    def __init__(self, detail: str, *, status_code: Optional[int] = None, extra: Optional[dict] = None):
        self.detail = detail
        if status_code:
            self.status_code = status_code
        self.extra = extra or {}
        super().__init__(detail)


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class ConflictError(AppError):
    status_code = 409
    error_code = "conflict"


class ForbiddenError(AppError):
    status_code = 403
    error_code = "forbidden"


class RateLimitError(AppError):
    status_code = 429
    error_code = "rate_limited"


class QuotaExceededError(AppError):
    status_code = 402
    error_code = "quota_exceeded"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {"code": exc.error_code, "message": exc.detail, **exc.extra},
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        headers = getattr(exc, "headers", None) or {}
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": "http_error", "message": exc.detail}},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        errors: list[dict[str, Any]] = []
        for err in exc.errors():
            errors.append(
                {
                    "field": ".".join(str(loc) for loc in err.get("loc", []) if loc not in {"body", "query", "path"}),
                    "message": err.get("msg"),
                    "type": err.get("type"),
                }
            )
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {"code": "validation_error", "message": "Invalid input", "details": errors},
            },
        )
