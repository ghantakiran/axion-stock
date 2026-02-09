"""TradingView Scanner preset scan configurations.

15 pre-built scans across 7 categories covering momentum, value,
volume, technical, dividend, growth, and crypto screening.
"""

from src.tv_scanner.config import AssetClass, TVScanCategory
from src.tv_scanner.models import TVFieldSpec, TVFilterCriterion, TVPreset


# ── Common field selections ─────────────────────────────────────────

_CORE_STOCK_FIELDS = [
    TVFieldSpec("close"),
    TVFieldSpec("change"),
    TVFieldSpec("volume"),
    TVFieldSpec("relative_volume_10d_calc"),
    TVFieldSpec("market_cap_basic"),
    TVFieldSpec("name"),
    TVFieldSpec("sector"),
]

_TECHNICAL_FIELDS = [
    TVFieldSpec("RSI"),
    TVFieldSpec("MACD.macd"),
    TVFieldSpec("MACD.signal"),
    TVFieldSpec("SMA20"),
    TVFieldSpec("SMA50"),
    TVFieldSpec("SMA200"),
    TVFieldSpec("Recommend.All"),
]

_PERFORMANCE_FIELDS = [
    TVFieldSpec("Perf.W"),
    TVFieldSpec("Perf.1M"),
    TVFieldSpec("Perf.Y"),
]

_VALUATION_FIELDS = [
    TVFieldSpec("price_earnings_ttm"),
    TVFieldSpec("dividend_yield_recent"),
    TVFieldSpec("earnings_per_share_basic_ttm"),
]

_ALL_STOCK_FIELDS = _CORE_STOCK_FIELDS + _TECHNICAL_FIELDS + _PERFORMANCE_FIELDS + _VALUATION_FIELDS


# ── Momentum Presets ────────────────────────────────────────────────

MOMENTUM_BREAKOUT = TVPreset(
    name="momentum_breakout",
    description="Stocks breaking out with strong momentum — price above SMA50, RSI 50-70, high relative volume",
    category=TVScanCategory.MOMENTUM,
    select_fields=_ALL_STOCK_FIELDS,
    criteria=[
        TVFilterCriterion("close", "gt", 5),
        TVFilterCriterion("volume", "gte", 500_000),
        TVFilterCriterion("RSI", "between", 50, 70),
        TVFilterCriterion("relative_volume_10d_calc", "gte", 1.5),
        TVFilterCriterion("change", "gt", 2),
    ],
    sort_field="change",
)

RSI_OVERSOLD = TVPreset(
    name="rsi_oversold",
    description="Oversold bounce candidates — RSI below 30 with decent volume",
    category=TVScanCategory.MOMENTUM,
    select_fields=_ALL_STOCK_FIELDS,
    criteria=[
        TVFilterCriterion("close", "gt", 5),
        TVFilterCriterion("volume", "gte", 500_000),
        TVFilterCriterion("RSI", "lt", 30),
    ],
    sort_field="RSI",
    sort_ascending=True,
)

RSI_OVERBOUGHT = TVPreset(
    name="rsi_overbought",
    description="Overbought stocks for potential short or exit — RSI above 70",
    category=TVScanCategory.MOMENTUM,
    select_fields=_ALL_STOCK_FIELDS,
    criteria=[
        TVFilterCriterion("close", "gt", 5),
        TVFilterCriterion("volume", "gte", 500_000),
        TVFilterCriterion("RSI", "gt", 70),
    ],
    sort_field="RSI",
)

MACD_BULLISH_CROSS = TVPreset(
    name="macd_bullish_cross",
    description="Bullish MACD crossover — MACD line above signal with positive momentum",
    category=TVScanCategory.MOMENTUM,
    select_fields=_ALL_STOCK_FIELDS,
    criteria=[
        TVFilterCriterion("close", "gt", 5),
        TVFilterCriterion("volume", "gte", 500_000),
        TVFilterCriterion("MACD.macd", "gt", 0),
        TVFilterCriterion("change", "gt", 0),
    ],
    sort_field="change",
)


# ── Value Presets ───────────────────────────────────────────────────

UNDERVALUED_QUALITY = TVPreset(
    name="undervalued_quality",
    description="Quality value stocks — low P/E, large cap, dividend paying",
    category=TVScanCategory.VALUE,
    select_fields=_ALL_STOCK_FIELDS,
    criteria=[
        TVFilterCriterion("price_earnings_ttm", "between", 0, 15),
        TVFilterCriterion("market_cap_basic", "gte", 1_000_000_000),
        TVFilterCriterion("dividend_yield_recent", "gte", 1),
    ],
    sort_field="price_earnings_ttm",
    sort_ascending=True,
)

HIGH_DIVIDEND = TVPreset(
    name="high_dividend",
    description="High-yield dividend stocks — yield above 4% with reasonable valuation",
    category=TVScanCategory.DIVIDEND,
    select_fields=_ALL_STOCK_FIELDS,
    criteria=[
        TVFilterCriterion("dividend_yield_recent", "gte", 4),
        TVFilterCriterion("price_earnings_ttm", "between", 0, 25),
        TVFilterCriterion("volume", "gte", 100_000),
    ],
    sort_field="dividend_yield_recent",
)


# ── Volume Presets ──────────────────────────────────────────────────

VOLUME_EXPLOSION = TVPreset(
    name="volume_explosion",
    description="Volume explosion — 3x+ relative volume with significant price move",
    category=TVScanCategory.VOLUME,
    select_fields=_ALL_STOCK_FIELDS,
    criteria=[
        TVFilterCriterion("relative_volume_10d_calc", "gte", 3),
        TVFilterCriterion("volume", "gte", 1_000_000),
        TVFilterCriterion("change", "gt", 2),
        TVFilterCriterion("close", "gt", 1),
    ],
    sort_field="relative_volume_10d_calc",
)

UNUSUAL_VOLUME = TVPreset(
    name="unusual_volume",
    description="Unusual volume activity — 2x+ relative volume indicating institutional interest",
    category=TVScanCategory.VOLUME,
    select_fields=_ALL_STOCK_FIELDS,
    criteria=[
        TVFilterCriterion("relative_volume_10d_calc", "gte", 2),
        TVFilterCriterion("volume", "gte", 500_000),
        TVFilterCriterion("close", "gt", 5),
    ],
    sort_field="relative_volume_10d_calc",
)


# ── Technical Presets ───────────────────────────────────────────────

GOLDEN_CROSS = TVPreset(
    name="golden_cross",
    description="Golden cross — SMA50 above SMA200, price above SMA50",
    category=TVScanCategory.TECHNICAL,
    select_fields=_ALL_STOCK_FIELDS,
    criteria=[
        TVFilterCriterion("close", "gt", 5),
        TVFilterCriterion("volume", "gte", 500_000),
        TVFilterCriterion("SMA50", "gt", 0),
        TVFilterCriterion("SMA200", "gt", 0),
    ],
    sort_field="change",
)

ABOVE_ALL_SMAS = TVPreset(
    name="above_all_smas",
    description="Price above all major moving averages — strong uptrend",
    category=TVScanCategory.TECHNICAL,
    select_fields=_ALL_STOCK_FIELDS,
    criteria=[
        TVFilterCriterion("close", "gt", 5),
        TVFilterCriterion("volume", "gte", 500_000),
        TVFilterCriterion("SMA20", "gt", 0),
        TVFilterCriterion("SMA50", "gt", 0),
        TVFilterCriterion("SMA200", "gt", 0),
    ],
    sort_field="Recommend.All",
)

BOLLINGER_OVERSOLD = TVPreset(
    name="bollinger_oversold",
    description="Oversold near Bollinger Band lower — mean reversion candidate",
    category=TVScanCategory.TECHNICAL,
    select_fields=_ALL_STOCK_FIELDS + [TVFieldSpec("BB.lower"), TVFieldSpec("BB.upper")],
    criteria=[
        TVFilterCriterion("close", "gt", 5),
        TVFilterCriterion("volume", "gte", 200_000),
        TVFilterCriterion("RSI", "lt", 40),
    ],
    sort_field="RSI",
    sort_ascending=True,
)


# ── Growth Presets ──────────────────────────────────────────────────

EARNINGS_MOMENTUM = TVPreset(
    name="earnings_momentum",
    description="Earnings momentum — positive EPS with price above SMA50",
    category=TVScanCategory.GROWTH,
    select_fields=_ALL_STOCK_FIELDS,
    criteria=[
        TVFilterCriterion("earnings_per_share_basic_ttm", "gt", 0),
        TVFilterCriterion("close", "gt", 10),
        TVFilterCriterion("volume", "gte", 500_000),
    ],
    sort_field="change",
)


# ── Crypto Presets ──────────────────────────────────────────────────

_CRYPTO_FIELDS = [
    TVFieldSpec("close"),
    TVFieldSpec("change"),
    TVFieldSpec("volume"),
    TVFieldSpec("RSI"),
    TVFieldSpec("MACD.macd"),
    TVFieldSpec("MACD.signal"),
    TVFieldSpec("SMA20"),
    TVFieldSpec("SMA50"),
    TVFieldSpec("Recommend.All"),
    TVFieldSpec("Perf.W"),
    TVFieldSpec("Perf.1M"),
    TVFieldSpec("name"),
]

CRYPTO_MOMENTUM = TVPreset(
    name="crypto_momentum",
    description="Crypto momentum — RSI above 50 with significant volume",
    category=TVScanCategory.CRYPTO,
    asset_class=AssetClass.CRYPTO,
    select_fields=_CRYPTO_FIELDS,
    criteria=[
        TVFilterCriterion("RSI", "gt", 50),
        TVFilterCriterion("change", "gt", 0),
    ],
    sort_field="change",
)

CRYPTO_OVERSOLD = TVPreset(
    name="crypto_oversold",
    description="Oversold crypto — RSI below 30 for potential bounce",
    category=TVScanCategory.CRYPTO,
    asset_class=AssetClass.CRYPTO,
    select_fields=_CRYPTO_FIELDS,
    criteria=[
        TVFilterCriterion("RSI", "lt", 30),
    ],
    sort_field="RSI",
    sort_ascending=True,
)


# ── Registry ────────────────────────────────────────────────────────

PRESET_TV_SCANS: dict[str, TVPreset] = {
    p.name: p
    for p in [
        MOMENTUM_BREAKOUT,
        RSI_OVERSOLD,
        RSI_OVERBOUGHT,
        MACD_BULLISH_CROSS,
        UNDERVALUED_QUALITY,
        HIGH_DIVIDEND,
        VOLUME_EXPLOSION,
        UNUSUAL_VOLUME,
        GOLDEN_CROSS,
        ABOVE_ALL_SMAS,
        BOLLINGER_OVERSOLD,
        EARNINGS_MOMENTUM,
        CRYPTO_MOMENTUM,
        CRYPTO_OVERSOLD,
    ]
}


def get_tv_preset(preset_id: str) -> TVPreset:
    """Get a preset by its ID. Raises KeyError if not found."""
    return PRESET_TV_SCANS[preset_id]


def get_tv_presets_by_category(category: TVScanCategory) -> list[TVPreset]:
    """Get all presets for a given category."""
    return [p for p in PRESET_TV_SCANS.values() if p.category == category]


def get_all_tv_presets() -> list[TVPreset]:
    """Return all registered presets."""
    return list(PRESET_TV_SCANS.values())
