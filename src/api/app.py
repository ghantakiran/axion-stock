"""FastAPI Application Factory.

Creates and configures the Axion API application with full
middleware stack: security headers, request tracing, error
handling, and CORS.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.api.config import APIConfig, DEFAULT_API_CONFIG
from src.api.routes import market_data, factors, portfolio, trading, ai, options, backtesting
from src.api.routes import bot as bot_routes
from src.api.routes import bot_ws
from src.api.routes import keys as keys_routes

logger = logging.getLogger(__name__)


# ── Security Headers Middleware ───────────────────────────────────────


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard security headers to all HTTP responses."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if os.environ.get("AXION_ENABLE_HSTS", "").lower() == "true":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


# ── Lifespan (startup / shutdown) ────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize logging and resources at startup."""
    # ── Startup ──
    try:
        from src.logging_config import configure_logging
        configure_logging()
        logger.info("Structured logging initialized")
    except ImportError:
        pass

    logger.info("Axion API starting up")
    yield
    # ── Shutdown ──
    logger.info("Axion API shutting down")


# ── App Factory ──────────────────────────────────────────────────────


def create_app(config: Optional[APIConfig] = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Middleware stack (outermost → innermost):
        SecurityHeaders → RequestTracing → ErrorHandling → CORS → App

    Args:
        config: API configuration. Uses defaults if not provided.

    Returns:
        Configured FastAPI application.
    """
    config = config or DEFAULT_API_CONFIG

    app = FastAPI(
        title=config.title,
        version=config.version,
        description=config.description,
        docs_url=config.docs_url,
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware stack ──────────────────────────────────────────
    # add_middleware prepends, so order here is innermost-first.

    # 1. CORS (innermost — handles preflight before routing)
    cors_origins = os.environ.get("AXION_CORS_ORIGINS", "").split(",")
    cors_origins = [o.strip() for o in cors_origins if o.strip()] or config.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=config.cors_methods,
        allow_headers=config.cors_headers,
    )

    # 2. Error handling (catches exceptions → structured JSON responses)
    try:
        from src.api_errors.middleware import ErrorHandlingMiddleware
        app.add_middleware(ErrorHandlingMiddleware)
    except ImportError:
        logger.warning("Error handling middleware not available")

    # 3. Request tracing (assigns X-Request-ID, logs lifecycle)
    try:
        from src.logging_config.middleware import RequestTracingMiddleware
        app.add_middleware(RequestTracingMiddleware)
    except ImportError:
        logger.warning("Request tracing middleware not available")

    # 4. Security headers (outermost — always adds headers)
    app.add_middleware(SecurityHeadersMiddleware)

    # ── Health check ─────────────────────────────────────────────

    @app.get("/health")
    async def health():
        components = {}

        # Database check
        try:
            from sqlalchemy import create_engine, text
            db_url = os.environ.get(
                "AXION_DATABASE_SYNC_URL",
                "postgresql+psycopg2://axion:axion_dev@localhost:5432/axion",
            )
            engine = create_engine(db_url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            components["database"] = "ok"
        except Exception as e:
            components["database"] = f"error: {e}"

        # Redis check
        try:
            from redis import Redis
            redis_url = os.environ.get("AXION_REDIS_URL", "redis://localhost:6379/0")
            r = Redis.from_url(redis_url, socket_connect_timeout=2)
            r.ping()
            components["redis"] = "ok"
            r.close()
        except Exception as e:
            components["redis"] = f"error: {e}"

        # Bot state check
        try:
            from src.bot_pipeline.state_manager import PersistentStateManager
            state = PersistentStateManager()
            components["bot"] = "killed" if state.kill_switch_active else "ready"
        except Exception:
            components["bot"] = "unavailable"

        # Metrics registry check
        try:
            from src.observability import MetricsRegistry
            registry = MetricsRegistry()
            components["metrics"] = f"ok ({len(registry.get_all_metrics())} metrics)"
        except Exception:
            components["metrics"] = "unavailable"

        overall = "ok" if all(
            v == "ok" or v == "ready" or v.startswith("ok (")
            for v in components.values()
        ) else "degraded"

        return {
            "status": overall,
            "version": config.version,
            "components": components,
        }

    # ── Route modules ────────────────────────────────────────────

    app.include_router(market_data.router, prefix=config.prefix)
    app.include_router(factors.router, prefix=config.prefix)
    app.include_router(portfolio.router, prefix=config.prefix)
    app.include_router(trading.router, prefix=config.prefix)
    app.include_router(ai.router, prefix=config.prefix)
    app.include_router(options.router, prefix=config.prefix)
    app.include_router(backtesting.router, prefix=config.prefix)
    app.include_router(bot_routes.router, prefix=config.prefix)
    app.include_router(keys_routes.router, prefix=config.prefix)

    # WebSocket endpoint (no prefix — path is absolute /ws/bot)
    app.include_router(bot_ws.router)

    # Prometheus metrics endpoint
    try:
        from src.observability import create_metrics_router
        app.include_router(create_metrics_router())
    except ImportError:
        logger.warning("Observability module not available — /metrics disabled")

    logger.info(f"Axion API v{config.version} initialized")
    return app
