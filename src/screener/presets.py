"""Preset Screen Definitions.

Built-in preset screens for common investment strategies.
"""

from src.screener.config import Operator, Universe, SortOrder
from src.screener.models import Screen, FilterCondition


def get_preset_screens() -> list[Screen]:
    """Get all preset screens.
    
    Returns:
        List of preset Screen objects.
    """
    return [
        # Value screens
        _deep_value_screen(),
        _buffett_screen(),
        _dividend_aristocrats_screen(),
        _undervalued_large_caps_screen(),
        
        # Growth screens
        _high_growth_screen(),
        _garp_screen(),
        _momentum_screen(),
        _small_cap_growth_screen(),
        
        # Quality screens
        _high_quality_screen(),
        _low_volatility_screen(),
        _financially_strong_screen(),
        
        # Technical screens
        _golden_cross_screen(),
        _oversold_screen(),
        _breakout_screen(),
        
        # Income screens
        _high_dividend_screen(),
        _dividend_growth_screen(),
        
        # Special situations
        _short_squeeze_screen(),
        _insider_buying_screen(),
    ]


def _deep_value_screen() -> Screen:
    """Deep value screen: Low P/E, P/B with dividend."""
    return Screen(
        screen_id="preset_deep_value",
        name="Deep Value",
        description="Low P/E, low P/B stocks with dividends - classic value investing",
        filters=[
            FilterCondition(filter_id="pe_ratio", operator=Operator.LT, value=10),
            FilterCondition(filter_id="pb_ratio", operator=Operator.LT, value=1.5),
            FilterCondition(filter_id="dividend_yield", operator=Operator.GT, value=2.0),
            FilterCondition(filter_id="market_cap", operator=Operator.GTE, value=1e9),
        ],
        sort_by="pe_ratio",
        sort_order=SortOrder.ASC,
        is_preset=True,
        is_public=True,
        tags=["value", "dividend", "classic"],
    )


def _buffett_screen() -> Screen:
    """Warren Buffett style screen."""
    return Screen(
        screen_id="preset_buffett",
        name="Buffett Quality Value",
        description="High ROE, low debt, consistent earnings growth - Buffett style",
        filters=[
            FilterCondition(filter_id="roe", operator=Operator.GTE, value=15),
            FilterCondition(filter_id="debt_to_equity", operator=Operator.LTE, value=0.5),
            FilterCondition(filter_id="gross_margin", operator=Operator.GTE, value=30),
            FilterCondition(filter_id="eps_growth_5y", operator=Operator.GTE, value=5),
            FilterCondition(filter_id="market_cap", operator=Operator.GTE, value=10e9),
        ],
        sort_by="roe",
        sort_order=SortOrder.DESC,
        is_preset=True,
        is_public=True,
        tags=["value", "quality", "buffett"],
    )


def _dividend_aristocrats_screen() -> Screen:
    """Dividend aristocrats screen."""
    return Screen(
        screen_id="preset_dividend_aristocrats",
        name="Dividend Aristocrats",
        description="25+ years of dividend growth, sustainable payout",
        filters=[
            FilterCondition(filter_id="dividend_growth_years", operator=Operator.GTE, value=25),
            FilterCondition(filter_id="payout_ratio", operator=Operator.LTE, value=60),
            FilterCondition(filter_id="dividend_yield", operator=Operator.GTE, value=1.5),
        ],
        sort_by="dividend_growth_years",
        sort_order=SortOrder.DESC,
        is_preset=True,
        is_public=True,
        tags=["dividend", "income", "aristocrats"],
    )


def _undervalued_large_caps_screen() -> Screen:
    """Undervalued large cap screen."""
    return Screen(
        screen_id="preset_undervalued_large",
        name="Undervalued Large Caps",
        description="Large caps trading below fair value",
        filters=[
            FilterCondition(filter_id="market_cap", operator=Operator.GTE, value=50e9),
            FilterCondition(filter_id="pe_ratio", operator=Operator.BETWEEN, value=5, value2=18),
            FilterCondition(filter_id="price_target_upside", operator=Operator.GTE, value=15),
            FilterCondition(filter_id="roe", operator=Operator.GTE, value=10),
        ],
        sort_by="price_target_upside",
        sort_order=SortOrder.DESC,
        is_preset=True,
        is_public=True,
        tags=["value", "large_cap"],
    )


def _high_growth_screen() -> Screen:
    """High growth screen."""
    return Screen(
        screen_id="preset_high_growth",
        name="High Growth",
        description="Companies with strong revenue and EPS growth",
        filters=[
            FilterCondition(filter_id="revenue_growth_yoy", operator=Operator.GTE, value=20),
            FilterCondition(filter_id="eps_growth_yoy", operator=Operator.GTE, value=20),
            FilterCondition(filter_id="revenue_growth_3y", operator=Operator.GTE, value=15),
            FilterCondition(filter_id="market_cap", operator=Operator.GTE, value=1e9),
        ],
        sort_by="revenue_growth_yoy",
        sort_order=SortOrder.DESC,
        is_preset=True,
        is_public=True,
        tags=["growth"],
    )


def _garp_screen() -> Screen:
    """Growth at a Reasonable Price screen."""
    return Screen(
        screen_id="preset_garp",
        name="GARP (Growth at Reasonable Price)",
        description="Growth stocks at reasonable valuations - PEG ratio focus",
        filters=[
            FilterCondition(filter_id="peg_ratio", operator=Operator.BETWEEN, value=0.5, value2=1.5),
            FilterCondition(filter_id="eps_growth_yoy", operator=Operator.GTE, value=10),
            FilterCondition(filter_id="roe", operator=Operator.GTE, value=15),
            FilterCondition(filter_id="debt_to_equity", operator=Operator.LTE, value=1.0),
        ],
        sort_by="peg_ratio",
        sort_order=SortOrder.ASC,
        is_preset=True,
        is_public=True,
        tags=["growth", "value", "garp"],
    )


def _momentum_screen() -> Screen:
    """Momentum screen."""
    return Screen(
        screen_id="preset_momentum",
        name="Momentum Leaders",
        description="Strong price momentum with trend confirmation",
        filters=[
            FilterCondition(filter_id="price_change_1y", operator=Operator.GTE, value=30),
            FilterCondition(filter_id="price_vs_sma_200", operator=Operator.GTE, value=10),
            FilterCondition(filter_id="rsi_14", operator=Operator.BETWEEN, value=50, value2=70),
            FilterCondition(filter_id="relative_volume", operator=Operator.GTE, value=1.0),
        ],
        sort_by="price_change_1y",
        sort_order=SortOrder.DESC,
        is_preset=True,
        is_public=True,
        tags=["momentum", "technical"],
    )


def _small_cap_growth_screen() -> Screen:
    """Small cap growth screen."""
    return Screen(
        screen_id="preset_small_cap_growth",
        name="Small Cap Growth",
        description="Fast-growing small cap companies",
        filters=[
            FilterCondition(filter_id="market_cap", operator=Operator.BETWEEN, value=300e6, value2=2e9),
            FilterCondition(filter_id="revenue_growth_yoy", operator=Operator.GTE, value=25),
            FilterCondition(filter_id="gross_margin", operator=Operator.GTE, value=30),
        ],
        sort_by="revenue_growth_yoy",
        sort_order=SortOrder.DESC,
        is_preset=True,
        is_public=True,
        tags=["growth", "small_cap"],
    )


def _high_quality_screen() -> Screen:
    """High quality screen."""
    return Screen(
        screen_id="preset_high_quality",
        name="High Quality",
        description="Best-in-class profitability and returns",
        filters=[
            FilterCondition(filter_id="roe", operator=Operator.GTE, value=20),
            FilterCondition(filter_id="roic", operator=Operator.GTE, value=15),
            FilterCondition(filter_id="gross_margin", operator=Operator.GTE, value=40),
            FilterCondition(filter_id="operating_margin", operator=Operator.GTE, value=15),
            FilterCondition(filter_id="debt_to_equity", operator=Operator.LTE, value=0.5),
        ],
        sort_by="roic",
        sort_order=SortOrder.DESC,
        is_preset=True,
        is_public=True,
        tags=["quality"],
    )


def _low_volatility_screen() -> Screen:
    """Low volatility screen."""
    return Screen(
        screen_id="preset_low_volatility",
        name="Low Volatility",
        description="Stable stocks with lower beta",
        filters=[
            FilterCondition(filter_id="beta", operator=Operator.LTE, value=0.8),
            FilterCondition(filter_id="volatility_30d", operator=Operator.LTE, value=20),
            FilterCondition(filter_id="dividend_yield", operator=Operator.GTE, value=1.5),
            FilterCondition(filter_id="market_cap", operator=Operator.GTE, value=10e9),
        ],
        sort_by="beta",
        sort_order=SortOrder.ASC,
        is_preset=True,
        is_public=True,
        tags=["defensive", "low_volatility"],
    )


def _financially_strong_screen() -> Screen:
    """Financially strong screen."""
    return Screen(
        screen_id="preset_financially_strong",
        name="Financially Strong",
        description="Rock-solid balance sheets",
        filters=[
            FilterCondition(filter_id="current_ratio", operator=Operator.GTE, value=2.0),
            FilterCondition(filter_id="debt_to_equity", operator=Operator.LTE, value=0.3),
            FilterCondition(filter_id="interest_coverage", operator=Operator.GTE, value=10),
            FilterCondition(filter_id="fcf_yield", operator=Operator.GTE, value=5),
        ],
        sort_by="current_ratio",
        sort_order=SortOrder.DESC,
        is_preset=True,
        is_public=True,
        tags=["quality", "defensive"],
    )


def _golden_cross_screen() -> Screen:
    """Golden cross technical screen."""
    return Screen(
        screen_id="preset_golden_cross",
        name="Golden Cross",
        description="50-day SMA recently crossed above 200-day SMA",
        filters=[
            FilterCondition(filter_id="sma_50_above_200", operator=Operator.EQ, value=True),
            FilterCondition(filter_id="price_vs_sma_50", operator=Operator.GTE, value=0),
            FilterCondition(filter_id="avg_volume", operator=Operator.GTE, value=500000),
        ],
        sort_by="price_change_1m",
        sort_order=SortOrder.DESC,
        is_preset=True,
        is_public=True,
        tags=["technical", "momentum"],
    )


def _oversold_screen() -> Screen:
    """Oversold stocks screen."""
    return Screen(
        screen_id="preset_oversold",
        name="Oversold Bounce Candidates",
        description="Quality stocks that appear oversold",
        filters=[
            FilterCondition(filter_id="rsi_14", operator=Operator.LTE, value=30),
            FilterCondition(filter_id="from_52w_high", operator=Operator.LTE, value=-25),
            FilterCondition(filter_id="roe", operator=Operator.GTE, value=10),
            FilterCondition(filter_id="market_cap", operator=Operator.GTE, value=5e9),
        ],
        sort_by="rsi_14",
        sort_order=SortOrder.ASC,
        is_preset=True,
        is_public=True,
        tags=["technical", "contrarian"],
    )


def _breakout_screen() -> Screen:
    """Breakout screen."""
    return Screen(
        screen_id="preset_breakout",
        name="Breakout Stocks",
        description="Stocks breaking out to new highs with volume",
        filters=[
            FilterCondition(filter_id="from_52w_high", operator=Operator.GTE, value=-5),
            FilterCondition(filter_id="relative_volume", operator=Operator.GTE, value=1.5),
            FilterCondition(filter_id="price_change_1d", operator=Operator.GTE, value=2),
            FilterCondition(filter_id="avg_volume", operator=Operator.GTE, value=500000),
        ],
        sort_by="relative_volume",
        sort_order=SortOrder.DESC,
        is_preset=True,
        is_public=True,
        tags=["technical", "breakout", "momentum"],
    )


def _high_dividend_screen() -> Screen:
    """High dividend yield screen."""
    return Screen(
        screen_id="preset_high_dividend",
        name="High Dividend Yield",
        description="High yielding stocks with sustainable payouts",
        filters=[
            FilterCondition(filter_id="dividend_yield", operator=Operator.GTE, value=4),
            FilterCondition(filter_id="payout_ratio", operator=Operator.LTE, value=80),
            FilterCondition(filter_id="fcf_yield", operator=Operator.GTE, value=5),
        ],
        sort_by="dividend_yield",
        sort_order=SortOrder.DESC,
        is_preset=True,
        is_public=True,
        tags=["dividend", "income"],
    )


def _dividend_growth_screen() -> Screen:
    """Dividend growth screen."""
    return Screen(
        screen_id="preset_dividend_growth",
        name="Dividend Growers",
        description="Companies growing dividends consistently",
        filters=[
            FilterCondition(filter_id="dividend_growth_5y", operator=Operator.GTE, value=7),
            FilterCondition(filter_id="payout_ratio", operator=Operator.LTE, value=60),
            FilterCondition(filter_id="revenue_growth_yoy", operator=Operator.GTE, value=5),
            FilterCondition(filter_id="debt_to_equity", operator=Operator.LTE, value=1.0),
        ],
        sort_by="dividend_growth_5y",
        sort_order=SortOrder.DESC,
        is_preset=True,
        is_public=True,
        tags=["dividend", "growth"],
    )


def _short_squeeze_screen() -> Screen:
    """Short squeeze candidates screen."""
    return Screen(
        screen_id="preset_short_squeeze",
        name="Short Squeeze Candidates",
        description="High short interest with potential squeeze setup",
        filters=[
            FilterCondition(filter_id="short_interest", operator=Operator.GTE, value=15),
            FilterCondition(filter_id="days_to_cover", operator=Operator.GTE, value=5),
            FilterCondition(filter_id="relative_volume", operator=Operator.GTE, value=1.2),
        ],
        sort_by="short_interest",
        sort_order=SortOrder.DESC,
        is_preset=True,
        is_public=True,
        tags=["special_situation", "short_squeeze"],
    )


def _insider_buying_screen() -> Screen:
    """Insider buying screen."""
    return Screen(
        screen_id="preset_insider_buying",
        name="Insider Buying",
        description="Stocks with significant insider purchases",
        filters=[
            FilterCondition(filter_id="institutional_change", operator=Operator.GTE, value=2),
            FilterCondition(filter_id="pe_ratio", operator=Operator.LTE, value=25),
            FilterCondition(filter_id="market_cap", operator=Operator.GTE, value=1e9),
        ],
        sort_by="institutional_change",
        sort_order=SortOrder.DESC,
        is_preset=True,
        is_public=True,
        tags=["special_situation", "insider"],
    )


# Preset screen registry
PRESET_SCREENS = {s.screen_id: s for s in get_preset_screens()}
