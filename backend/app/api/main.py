"""Aplicación FastAPI (panel + webhook).

    uvicorn app.api.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.api.routes import analytics, auth, bot, groups, incidents, internal, moderation, telegram
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import get_engine
from app.services.accounts import prepare

logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(get_settings().log_level)
    try:
        prepare()
    except Exception:
        logger.exception("admin_bootstrap_failed")
    logger.info("api_started", extra={"version": __version__})
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Centinela API", version=__version__, lifespan=lifespan,
                  docs_url=None if settings.app_env == "production" else "/api/docs",
                  openapi_url=None if settings.app_env == "production" else "/api/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Disposition"])

    @app.middleware("http")
    async def access_log(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled_error", extra={"request_id": request_id, "path": request.url.path})
            response = JSONResponse({"detail": "Error interno", "request_id": request_id}, status_code=500)
        response.headers["x-request-id"] = request_id
        logger.info("http_request", extra={
            "request_id": request_id, "method": request.method, "path": request.url.path,
            "status": response.status_code, "duration_ms": round((time.perf_counter() - start) * 1000, 1)})
        return response

    for module in (auth, analytics, bot, groups, incidents, internal, moderation, telegram):
        app.include_router(module.router, prefix="/api")

    @app.get("/api/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/health/ready", tags=["health"])
    def ready() -> JSONResponse:
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return JSONResponse({"status": "ok"})
        except Exception as exc:
            return JSONResponse({"status": "degraded", "error": type(exc).__name__}, status_code=503)

    return app


app = create_app()
