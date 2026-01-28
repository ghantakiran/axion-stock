"""Redis key naming conventions for Axion.

All keys are namespaced with 'axion:' prefix.
"""

# Real-time quotes (TTL: 30s)
QUOTE = "axion:quote:{ticker}"

# Price DataFrames (TTL: 5min)
PRICES = "axion:prices:{ticker}:{timeframe}"
PRICES_BULK = "axion:prices:bulk:{hash}"

# Fundamentals (TTL: 4hr)
FUNDAMENTALS = "axion:fundamentals:{ticker}"
FUNDAMENTALS_ALL = "axion:fundamentals:all"

# Factor scores (TTL: 1hr)
SCORES_ALL = "axion:scores:all"
SCORES_TICKER = "axion:scores:{ticker}"

# Universe (TTL: 24hr)
UNIVERSE = "axion:universe:{index}"

# Economic indicators (TTL: 1hr)
ECONOMIC = "axion:economic:{series_id}"

# Session data (TTL: 8hr)
SESSION = "axion:session:{session_id}"
