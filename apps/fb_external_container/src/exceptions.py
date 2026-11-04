"""App-level exception types + handlers.

Follows the fastapi-dev-guidelines pattern: a single ``AppError`` base
with `code` and `status_code`, plus a catch-all handler that prevents
stack traces from leaking to clients.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, code="NOT_FOUND", status_code=404)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, code="VALIDATION_ERROR", status_code=422)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict with existing resource"):
        super().__init__(message, code="CONFLICT", status_code=409)


class ServiceError(AppError):
    def __init__(self, message: str = "Service error"):
        super().__init__(message, code="SERVICE_ERROR", status_code=500)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.error(
            "AppError on %s: %s",
            request.url.path, exc.message,
            extra={"code": exc.code, "status_code": exc.status_code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message, "code": exc.code},
        )

    @app.exception_handler(Exception)
    async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "code": "INTERNAL_ERROR"},
        )
