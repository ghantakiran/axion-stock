"""Configuration for Axion - Stock Recommendation System."""

# Factor weights (must sum to 1.0)
FACTOR_WEIGHTS = {
    "value": 0.25,
    "momentum": 0.30,
    "quality": 0.25,
    "growth": 0.20,
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
