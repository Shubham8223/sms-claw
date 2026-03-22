"""
FastAPI application factory.

Exception handler maps domain exceptions to HTTP status codes.
All domain exceptions are defined in core/exceptions.py — the only
place that needs editing when adding new error types.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sms_claw.api.routers.admin import router as admin_router
from sms_claw.api.routers.webhook import router as webhook_router
from sms_claw.core.config import get_settings
from sms_claw.core.exceptions import (
    DispatchError,
    InvalidOTPError,
    NotEnrolledError,
    PhoneNotAllowedError,
    RateLimitExceededError,
    WebhookSignatureError,
)
from sms_claw.core.logging import get_logger, setup_logging
from sms_claw.database.base import engine

log = get_logger(__name__)
_s = get_settings()

# ── Domain exception → HTTP status mapping ─────────────────────────────────────
_EXCEPTION_STATUS: dict[type[DispatchError], int] = {
    PhoneNotAllowedError: 403,
    NotEnrolledError: 403,
    WebhookSignatureError: 403,
    InvalidOTPError: 422,
    RateLimitExceededError: 429,
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging(level=_s.log_level, production=_s.is_production)
    log.info(
        "sms_claw_starting",
        env=_s.app_env,
        sms=_s.default_sms_provider,
        llm=_s.default_llm_provider,
    )

    if not _s.is_production:
        from sms_claw.database.base import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("db_tables_synced")

    yield

    log.info("sms_claw_shutdown")
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Dispatch",
        description="SMS-powered AI agent gateway",
        version="0.1.0",
        docs_url=None if _s.is_production else "/docs",
        redoc_url=None if _s.is_production else "/redoc",
        lifespan=lifespan,
    )

    # ── Exception handler ──────────────────────────────────────────────────────
    @app.exception_handler(DispatchError)
    async def sms_claw_exception_handler(
        request: Request, exc: DispatchError
    ) -> JSONResponse:
        status_code = _EXCEPTION_STATUS.get(type(exc), 500)
        log.warning(
            "domain_exception",
            exc_type=type(exc).__name__,
            message=exc.message,
            path=str(request.url),
            status=status_code,
        )
        return JSONResponse(status_code=status_code, content={"detail": exc.message})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        log.error(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            path=str(request.url),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )

    # ── Middleware ─────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[] if _s.is_production else ["*"],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    # ── Routers ────────────────────────────────────────────────────────────────
    app.include_router(webhook_router)
    app.include_router(admin_router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {"service": "sms_claw", "status": "running", "env": _s.app_env}

    return app


app = create_app()
