"""FastAPI Application Factory.

Creates and configures the Axion API application.
"""

import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.config import APIConfig, DEFAULT_API_CONFIG
from src.api.routes import market_data, factors, portfolio, trading, ai, options, backtesting
from src.api.routes import bot as bot_routes
from src.api.routes import bot_ws

logger = logging.getLogger(__name__)


def create_app(config: Optional[APIConfig] = None) -> FastAPI:
    """Create and configure the FastAPI application.

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
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=config.cors_methods,
        allow_headers=config.cors_headers,
    )

    # Health check
    @app.get("/health")
    async def health():
        return {"status": "ok", "version": config.version}

    # Mount route modules under API prefix
    app.include_router(market_data.router, prefix=config.prefix)
    app.include_router(factors.router, prefix=config.prefix)
    app.include_router(portfolio.router, prefix=config.prefix)
    app.include_router(trading.router, prefix=config.prefix)
    app.include_router(ai.router, prefix=config.prefix)
    app.include_router(options.router, prefix=config.prefix)
    app.include_router(backtesting.router, prefix=config.prefix)
    app.include_router(bot_routes.router, prefix=config.prefix)

    logger.info(f"Axion API v{config.version} initialized")
    return app
