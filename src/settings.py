"""Centralized settings for Axion platform.

Uses pydantic-settings to load from environment variables (prefixed AXION_)
with sensible defaults matching the original config.py values.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Axion platform settings loaded from environment variables."""

    # --- Existing config (backward compatible) ---
    min_price: float = 5.0
    min_market_cap: int = 500_000_000
    batch_size: int = 50
    batch_sleep: float = 2.0
    fundamental_sleep: float = 0.5
    price_history_months: int = 14
    cache_dir: str = "cache"
    cache_expiry_hours: int = 24
    top_n_stocks: int = 9
    min_percentile: float = 0.90
    max_position_weight: float = 0.25
    max_sector_weight: float = 0.40
    backtest_months: int = 24
    benchmark_ticker: str = "SPY"
    risk_free_rate: float = 0.05

    # --- Database (PostgreSQL + TimescaleDB) ---
    database_url: str = "postgresql+asyncpg://axion:axion_dev@localhost:5432/axion"
    database_sync_url: str = "postgresql+psycopg2://axion:axion_dev@localhost:5432/axion"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"
    redis_quote_ttl: int = 30
    redis_score_ttl: int = 3600
    redis_fundamental_ttl: int = 14400
    redis_universe_ttl: int = 86400

    # --- Polygon.io ---
    polygon_api_key: str = ""
    polygon_ws_url: str = "wss://socket.polygon.io/stocks"
    polygon_rest_url: str = "https://api.polygon.io"

    # --- FRED ---
    fred_api_key: str = ""
    fred_base_url: str = "https://api.stlouisfed.org/fred"

    # --- Feature flags ---
    use_database: bool = False
    use_redis: bool = True
    fallback_to_yfinance: bool = True

    # --- Factor Engine v2 ---
    factor_engine_v2: bool = False  # Enable 6-factor model with regime detection
    factor_engine_adaptive_weights: bool = True  # Use regime-based weight adaptation
    factor_engine_sector_relative: bool = True  # Apply sector-relative scoring
    factor_engine_momentum_overlay: bool = True  # Tilt toward performing factors

    model_config = {
        "env_prefix": "AXION_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings singleton."""
    return Settings()
