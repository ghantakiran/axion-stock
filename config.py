"""Configuration for Axion - Stock Recommendation System."""

# Factor weights v1 (must sum to 1.0) - 4 factors
FACTOR_WEIGHTS = {
    "value": 0.25,
    "momentum": 0.30,
    "quality": 0.25,
    "growth": 0.20,
}

# Factor weights v2 (must sum to 1.0) - 6 factors
FACTOR_WEIGHTS_V2 = {
    "value": 0.20,
    "momentum": 0.25,
    "quality": 0.20,
    "growth": 0.15,
    "volatility": 0.10,
    "technical": 0.10,
}

# Regime-specific factor weights for v2 engine
REGIME_WEIGHTS = {
    "bull": {
        "value": 0.10, "momentum": 0.35, "quality": 0.15,
        "growth": 0.25, "volatility": 0.05, "technical": 0.10,
    },
    "bear": {
        "value": 0.25, "momentum": 0.05, "quality": 0.35,
        "growth": 0.05, "volatility": 0.25, "technical": 0.05,
    },
    "sideways": {
        "value": 0.25, "momentum": 0.15, "quality": 0.25,
        "growth": 0.10, "volatility": 0.15, "technical": 0.10,
    },
    "crisis": {
        "value": 0.05, "momentum": 0.00, "quality": 0.40,
        "growth": 0.00, "volatility": 0.50, "technical": 0.05,
    },
}

# Universe settings
MIN_PRICE = 5.0
MIN_MARKET_CAP = 500_000_000  # $500M

# Data fetching
BATCH_SIZE = 50
BATCH_SLEEP = 2.0  # seconds between batch downloads
FUNDAMENTAL_SLEEP = 0.5  # seconds between individual ticker info calls
PRICE_HISTORY_MONTHS = 14  # months of price history to download

# Cache settings
CACHE_DIR = "cache"
CACHE_EXPIRY_HOURS = 24

# Portfolio
TOP_N_STOCKS = 9
MIN_PERCENTILE = 0.90  # must be in top 10th percentile

# Risk management
MAX_POSITION_WEIGHT = 0.25  # Max 25% in single position
MAX_SECTOR_WEIGHT = 0.40  # Max 40% in single sector

# Backtest
BACKTEST_MONTHS = 24
BENCHMARK_TICKER = "SPY"
RISK_FREE_RATE = 0.05  # annualized, for Sharpe ratio

# Infrastructure settings (loaded from environment when available)
try:
    from src.settings import get_settings as _get_settings
    _s = _get_settings()
    DATABASE_URL = _s.database_url
    DATABASE_SYNC_URL = _s.database_sync_url
    REDIS_URL = _s.redis_url
    POLYGON_API_KEY = _s.polygon_api_key
    FRED_API_KEY = _s.fred_api_key
    USE_DATABASE = _s.use_database
    USE_REDIS = _s.use_redis
    FACTOR_ENGINE_V2 = _s.factor_engine_v2
    FACTOR_ENGINE_ADAPTIVE_WEIGHTS = _s.factor_engine_adaptive_weights
    FACTOR_ENGINE_SECTOR_RELATIVE = _s.factor_engine_sector_relative
except ImportError:
    DATABASE_URL = ""
    DATABASE_SYNC_URL = ""
    REDIS_URL = ""
    POLYGON_API_KEY = ""
    FRED_API_KEY = ""
    USE_DATABASE = False
    USE_REDIS = False
    FACTOR_ENGINE_V2 = False
    FACTOR_ENGINE_ADAPTIVE_WEIGHTS = True
    FACTOR_ENGINE_SECTOR_RELATIVE = True
