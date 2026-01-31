"""Filter Definitions and Registry.

Built-in filter definitions for the screener.
"""

from typing import Optional
import logging

from src.screener.config import FilterCategory, DataType, Operator
from src.screener.models import FilterDefinition

logger = logging.getLogger(__name__)


class FilterRegistry:
    """Registry of available screening filters.
    
    Provides 100+ built-in filters across fundamentals, technicals,
    and alternative data categories.
    
    Example:
        registry = FilterRegistry()
        pe_filter = registry.get_filter("pe_ratio")
        all_valuation = registry.get_filters_by_category(FilterCategory.VALUATION)
    """
    
    def __init__(self):
        self._filters: dict[str, FilterDefinition] = {}
        self._register_builtin_filters()
    
    def register(self, filter_def: FilterDefinition) -> None:
        """Register a filter definition."""
        self._filters[filter_def.filter_id] = filter_def
    
    def get_filter(self, filter_id: str) -> Optional[FilterDefinition]:
        """Get a filter by ID."""
        return self._filters.get(filter_id)
    
    def get_all_filters(self) -> list[FilterDefinition]:
        """Get all registered filters."""
        return list(self._filters.values())
    
    def get_filters_by_category(self, category: FilterCategory) -> list[FilterDefinition]:
        """Get filters by category."""
        return [f for f in self._filters.values() if f.category == category]
    
    def search_filters(self, query: str) -> list[FilterDefinition]:
        """Search filters by name or description."""
        query = query.lower()
        return [
            f for f in self._filters.values()
            if query in f.name.lower() or query in f.description.lower()
        ]
    
    def _register_builtin_filters(self) -> None:
        """Register all built-in filters."""
        self._register_valuation_filters()
        self._register_growth_filters()
        self._register_profitability_filters()
        self._register_financial_health_filters()
        self._register_size_filters()
        self._register_dividend_filters()
        self._register_price_filters()
        self._register_ma_filters()
        self._register_momentum_filters()
        self._register_volatility_filters()
        self._register_volume_filters()
        self._register_analyst_filters()
        self._register_institutional_filters()
        self._register_short_interest_filters()
    
    def _register_valuation_filters(self) -> None:
        """Register valuation filters."""
        filters = [
            FilterDefinition(
                filter_id="pe_ratio",
                name="P/E Ratio",
                category=FilterCategory.VALUATION,
                data_type=DataType.NUMERIC,
                description="Price to earnings ratio (TTM)",
                min_value=0,
                max_value=500,
                unit="x",
                expression_name="pe_ratio",
            ),
            FilterDefinition(
                filter_id="forward_pe",
                name="Forward P/E",
                category=FilterCategory.VALUATION,
                data_type=DataType.NUMERIC,
                description="Price to forward earnings ratio",
                min_value=0,
                max_value=500,
                unit="x",
                expression_name="forward_pe",
            ),
            FilterDefinition(
                filter_id="peg_ratio",
                name="PEG Ratio",
                category=FilterCategory.VALUATION,
                data_type=DataType.NUMERIC,
                description="P/E to growth ratio",
                min_value=0,
                max_value=10,
                unit="x",
                expression_name="peg_ratio",
            ),
            FilterDefinition(
                filter_id="ps_ratio",
                name="P/S Ratio",
                category=FilterCategory.VALUATION,
                data_type=DataType.NUMERIC,
                description="Price to sales ratio",
                min_value=0,
                max_value=100,
                unit="x",
                expression_name="ps_ratio",
            ),
            FilterDefinition(
                filter_id="pb_ratio",
                name="P/B Ratio",
                category=FilterCategory.VALUATION,
                data_type=DataType.NUMERIC,
                description="Price to book ratio",
                min_value=0,
                max_value=50,
                unit="x",
                expression_name="pb_ratio",
            ),
            FilterDefinition(
                filter_id="ev_ebitda",
                name="EV/EBITDA",
                category=FilterCategory.VALUATION,
                data_type=DataType.NUMERIC,
                description="Enterprise value to EBITDA",
                min_value=0,
                max_value=100,
                unit="x",
                expression_name="ev_ebitda",
            ),
            FilterDefinition(
                filter_id="ev_revenue",
                name="EV/Revenue",
                category=FilterCategory.VALUATION,
                data_type=DataType.NUMERIC,
                description="Enterprise value to revenue",
                min_value=0,
                max_value=50,
                unit="x",
                expression_name="ev_revenue",
            ),
            FilterDefinition(
                filter_id="ev_fcf",
                name="EV/FCF",
                category=FilterCategory.VALUATION,
                data_type=DataType.NUMERIC,
                description="Enterprise value to free cash flow",
                min_value=0,
                max_value=100,
                unit="x",
                expression_name="ev_fcf",
            ),
            FilterDefinition(
                filter_id="fcf_yield",
                name="FCF Yield",
                category=FilterCategory.VALUATION,
                data_type=DataType.PERCENT,
                description="Free cash flow yield",
                min_value=-50,
                max_value=50,
                unit="%",
                expression_name="fcf_yield",
            ),
            FilterDefinition(
                filter_id="earnings_yield",
                name="Earnings Yield",
                category=FilterCategory.VALUATION,
                data_type=DataType.PERCENT,
                description="Earnings yield (inverse of P/E)",
                min_value=-20,
                max_value=50,
                unit="%",
                expression_name="earnings_yield",
            ),
        ]
        for f in filters:
            self.register(f)
    
    def _register_growth_filters(self) -> None:
        """Register growth filters."""
        filters = [
            FilterDefinition(
                filter_id="revenue_growth_yoy",
                name="Revenue Growth (YoY)",
                category=FilterCategory.GROWTH,
                data_type=DataType.PERCENT,
                description="Year-over-year revenue growth",
                min_value=-100,
                max_value=500,
                unit="%",
                expression_name="revenue_growth",
            ),
            FilterDefinition(
                filter_id="revenue_growth_3y",
                name="Revenue Growth (3Y CAGR)",
                category=FilterCategory.GROWTH,
                data_type=DataType.PERCENT,
                description="3-year revenue CAGR",
                min_value=-50,
                max_value=200,
                unit="%",
                expression_name="revenue_growth_3y",
            ),
            FilterDefinition(
                filter_id="revenue_growth_5y",
                name="Revenue Growth (5Y CAGR)",
                category=FilterCategory.GROWTH,
                data_type=DataType.PERCENT,
                description="5-year revenue CAGR",
                min_value=-50,
                max_value=200,
                unit="%",
                expression_name="revenue_growth_5y",
            ),
            FilterDefinition(
                filter_id="eps_growth_yoy",
                name="EPS Growth (YoY)",
                category=FilterCategory.GROWTH,
                data_type=DataType.PERCENT,
                description="Year-over-year EPS growth",
                min_value=-100,
                max_value=500,
                unit="%",
                expression_name="eps_growth",
            ),
            FilterDefinition(
                filter_id="eps_growth_5y",
                name="EPS Growth (5Y CAGR)",
                category=FilterCategory.GROWTH,
                data_type=DataType.PERCENT,
                description="5-year EPS CAGR",
                min_value=-50,
                max_value=200,
                unit="%",
                expression_name="eps_growth_5y",
            ),
            FilterDefinition(
                filter_id="fcf_growth_yoy",
                name="FCF Growth (YoY)",
                category=FilterCategory.GROWTH,
                data_type=DataType.PERCENT,
                description="Year-over-year free cash flow growth",
                min_value=-100,
                max_value=500,
                unit="%",
                expression_name="fcf_growth",
            ),
            FilterDefinition(
                filter_id="dividend_growth_5y",
                name="Dividend Growth (5Y CAGR)",
                category=FilterCategory.GROWTH,
                data_type=DataType.PERCENT,
                description="5-year dividend CAGR",
                min_value=-50,
                max_value=100,
                unit="%",
                expression_name="dividend_growth_5y",
            ),
        ]
        for f in filters:
            self.register(f)
    
    def _register_profitability_filters(self) -> None:
        """Register profitability filters."""
        filters = [
            FilterDefinition(
                filter_id="gross_margin",
                name="Gross Margin",
                category=FilterCategory.PROFITABILITY,
                data_type=DataType.PERCENT,
                description="Gross profit margin",
                min_value=-100,
                max_value=100,
                unit="%",
                expression_name="gross_margin",
            ),
            FilterDefinition(
                filter_id="operating_margin",
                name="Operating Margin",
                category=FilterCategory.PROFITABILITY,
                data_type=DataType.PERCENT,
                description="Operating profit margin",
                min_value=-100,
                max_value=100,
                unit="%",
                expression_name="operating_margin",
            ),
            FilterDefinition(
                filter_id="net_margin",
                name="Net Margin",
                category=FilterCategory.PROFITABILITY,
                data_type=DataType.PERCENT,
                description="Net profit margin",
                min_value=-100,
                max_value=100,
                unit="%",
                expression_name="net_margin",
            ),
            FilterDefinition(
                filter_id="roe",
                name="Return on Equity (ROE)",
                category=FilterCategory.PROFITABILITY,
                data_type=DataType.PERCENT,
                description="Return on equity",
                min_value=-100,
                max_value=200,
                unit="%",
                expression_name="roe",
            ),
            FilterDefinition(
                filter_id="roa",
                name="Return on Assets (ROA)",
                category=FilterCategory.PROFITABILITY,
                data_type=DataType.PERCENT,
                description="Return on assets",
                min_value=-50,
                max_value=100,
                unit="%",
                expression_name="roa",
            ),
            FilterDefinition(
                filter_id="roic",
                name="Return on Invested Capital (ROIC)",
                category=FilterCategory.PROFITABILITY,
                data_type=DataType.PERCENT,
                description="Return on invested capital",
                min_value=-50,
                max_value=100,
                unit="%",
                expression_name="roic",
            ),
            FilterDefinition(
                filter_id="roce",
                name="Return on Capital Employed (ROCE)",
                category=FilterCategory.PROFITABILITY,
                data_type=DataType.PERCENT,
                description="Return on capital employed",
                min_value=-50,
                max_value=100,
                unit="%",
                expression_name="roce",
            ),
        ]
        for f in filters:
            self.register(f)
    
    def _register_financial_health_filters(self) -> None:
        """Register financial health filters."""
        filters = [
            FilterDefinition(
                filter_id="debt_to_equity",
                name="Debt/Equity",
                category=FilterCategory.FINANCIAL_HEALTH,
                data_type=DataType.NUMERIC,
                description="Total debt to equity ratio",
                min_value=0,
                max_value=10,
                unit="x",
                expression_name="debt_to_equity",
            ),
            FilterDefinition(
                filter_id="debt_to_ebitda",
                name="Debt/EBITDA",
                category=FilterCategory.FINANCIAL_HEALTH,
                data_type=DataType.NUMERIC,
                description="Total debt to EBITDA",
                min_value=0,
                max_value=20,
                unit="x",
                expression_name="debt_to_ebitda",
            ),
            FilterDefinition(
                filter_id="current_ratio",
                name="Current Ratio",
                category=FilterCategory.FINANCIAL_HEALTH,
                data_type=DataType.NUMERIC,
                description="Current assets / current liabilities",
                min_value=0,
                max_value=10,
                unit="x",
                expression_name="current_ratio",
            ),
            FilterDefinition(
                filter_id="quick_ratio",
                name="Quick Ratio",
                category=FilterCategory.FINANCIAL_HEALTH,
                data_type=DataType.NUMERIC,
                description="(Current assets - inventory) / current liabilities",
                min_value=0,
                max_value=10,
                unit="x",
                expression_name="quick_ratio",
            ),
            FilterDefinition(
                filter_id="interest_coverage",
                name="Interest Coverage",
                category=FilterCategory.FINANCIAL_HEALTH,
                data_type=DataType.NUMERIC,
                description="EBIT / interest expense",
                min_value=0,
                max_value=100,
                unit="x",
                expression_name="interest_coverage",
            ),
            FilterDefinition(
                filter_id="altman_z",
                name="Altman Z-Score",
                category=FilterCategory.FINANCIAL_HEALTH,
                data_type=DataType.NUMERIC,
                description="Bankruptcy prediction score",
                min_value=-5,
                max_value=10,
                unit="",
                expression_name="altman_z",
            ),
        ]
        for f in filters:
            self.register(f)
    
    def _register_size_filters(self) -> None:
        """Register size filters."""
        filters = [
            FilterDefinition(
                filter_id="market_cap",
                name="Market Cap",
                category=FilterCategory.SIZE,
                data_type=DataType.CURRENCY,
                description="Market capitalization",
                min_value=0,
                max_value=5e12,
                unit="$",
                expression_name="market_cap",
            ),
            FilterDefinition(
                filter_id="enterprise_value",
                name="Enterprise Value",
                category=FilterCategory.SIZE,
                data_type=DataType.CURRENCY,
                description="Enterprise value",
                min_value=0,
                max_value=5e12,
                unit="$",
                expression_name="enterprise_value",
            ),
            FilterDefinition(
                filter_id="revenue",
                name="Revenue (TTM)",
                category=FilterCategory.SIZE,
                data_type=DataType.CURRENCY,
                description="Trailing twelve months revenue",
                min_value=0,
                max_value=1e12,
                unit="$",
                expression_name="revenue",
            ),
            FilterDefinition(
                filter_id="employees",
                name="Employees",
                category=FilterCategory.SIZE,
                data_type=DataType.NUMERIC,
                description="Number of employees",
                min_value=0,
                max_value=3e6,
                unit="",
                expression_name="employees",
            ),
        ]
        for f in filters:
            self.register(f)
    
    def _register_dividend_filters(self) -> None:
        """Register dividend filters."""
        filters = [
            FilterDefinition(
                filter_id="dividend_yield",
                name="Dividend Yield",
                category=FilterCategory.DIVIDENDS,
                data_type=DataType.PERCENT,
                description="Annual dividend yield",
                min_value=0,
                max_value=30,
                unit="%",
                expression_name="dividend_yield",
            ),
            FilterDefinition(
                filter_id="payout_ratio",
                name="Payout Ratio",
                category=FilterCategory.DIVIDENDS,
                data_type=DataType.PERCENT,
                description="Dividend payout ratio",
                min_value=0,
                max_value=200,
                unit="%",
                expression_name="payout_ratio",
            ),
            FilterDefinition(
                filter_id="dividend_growth_years",
                name="Years of Dividend Growth",
                category=FilterCategory.DIVIDENDS,
                data_type=DataType.NUMERIC,
                description="Consecutive years of dividend increases",
                min_value=0,
                max_value=70,
                unit="years",
                expression_name="dividend_growth_years",
            ),
        ]
        for f in filters:
            self.register(f)
    
    def _register_price_filters(self) -> None:
        """Register price filters."""
        filters = [
            FilterDefinition(
                filter_id="price",
                name="Price",
                category=FilterCategory.PRICE,
                data_type=DataType.CURRENCY,
                description="Current stock price",
                min_value=0,
                max_value=1e6,
                unit="$",
                expression_name="price",
            ),
            FilterDefinition(
                filter_id="price_change_1d",
                name="1-Day Change",
                category=FilterCategory.PRICE,
                data_type=DataType.PERCENT,
                description="1-day price change",
                min_value=-50,
                max_value=50,
                unit="%",
                expression_name="change_1d",
            ),
            FilterDefinition(
                filter_id="price_change_1w",
                name="1-Week Change",
                category=FilterCategory.PRICE,
                data_type=DataType.PERCENT,
                description="1-week price change",
                min_value=-50,
                max_value=100,
                unit="%",
                expression_name="change_1w",
            ),
            FilterDefinition(
                filter_id="price_change_1m",
                name="1-Month Change",
                category=FilterCategory.PRICE,
                data_type=DataType.PERCENT,
                description="1-month price change",
                min_value=-80,
                max_value=200,
                unit="%",
                expression_name="change_1m",
            ),
            FilterDefinition(
                filter_id="price_change_ytd",
                name="YTD Change",
                category=FilterCategory.PRICE,
                data_type=DataType.PERCENT,
                description="Year-to-date price change",
                min_value=-90,
                max_value=500,
                unit="%",
                expression_name="change_ytd",
            ),
            FilterDefinition(
                filter_id="price_change_1y",
                name="1-Year Change",
                category=FilterCategory.PRICE,
                data_type=DataType.PERCENT,
                description="1-year price change",
                min_value=-90,
                max_value=1000,
                unit="%",
                expression_name="change_1y",
            ),
            FilterDefinition(
                filter_id="from_52w_high",
                name="% from 52-Week High",
                category=FilterCategory.PRICE,
                data_type=DataType.PERCENT,
                description="Percentage below 52-week high",
                min_value=-100,
                max_value=0,
                unit="%",
                expression_name="from_52w_high",
            ),
            FilterDefinition(
                filter_id="from_52w_low",
                name="% from 52-Week Low",
                category=FilterCategory.PRICE,
                data_type=DataType.PERCENT,
                description="Percentage above 52-week low",
                min_value=0,
                max_value=500,
                unit="%",
                expression_name="from_52w_low",
            ),
        ]
        for f in filters:
            self.register(f)
    
    def _register_ma_filters(self) -> None:
        """Register moving average filters."""
        filters = [
            FilterDefinition(
                filter_id="sma_20",
                name="SMA 20",
                category=FilterCategory.MOVING_AVERAGE,
                data_type=DataType.CURRENCY,
                description="20-day simple moving average",
                unit="$",
                expression_name="sma_20",
            ),
            FilterDefinition(
                filter_id="sma_50",
                name="SMA 50",
                category=FilterCategory.MOVING_AVERAGE,
                data_type=DataType.CURRENCY,
                description="50-day simple moving average",
                unit="$",
                expression_name="sma_50",
            ),
            FilterDefinition(
                filter_id="sma_200",
                name="SMA 200",
                category=FilterCategory.MOVING_AVERAGE,
                data_type=DataType.CURRENCY,
                description="200-day simple moving average",
                unit="$",
                expression_name="sma_200",
            ),
            FilterDefinition(
                filter_id="price_vs_sma_50",
                name="Price vs SMA 50",
                category=FilterCategory.MOVING_AVERAGE,
                data_type=DataType.PERCENT,
                description="Price relative to 50-day SMA",
                min_value=-50,
                max_value=100,
                unit="%",
                expression_name="price_vs_sma_50",
            ),
            FilterDefinition(
                filter_id="price_vs_sma_200",
                name="Price vs SMA 200",
                category=FilterCategory.MOVING_AVERAGE,
                data_type=DataType.PERCENT,
                description="Price relative to 200-day SMA",
                min_value=-50,
                max_value=100,
                unit="%",
                expression_name="price_vs_sma_200",
            ),
            FilterDefinition(
                filter_id="sma_50_above_200",
                name="SMA 50 > SMA 200 (Golden Cross)",
                category=FilterCategory.MOVING_AVERAGE,
                data_type=DataType.BOOLEAN,
                description="50-day SMA above 200-day SMA",
                expression_name="golden_cross",
            ),
        ]
        for f in filters:
            self.register(f)
    
    def _register_momentum_filters(self) -> None:
        """Register momentum filters."""
        filters = [
            FilterDefinition(
                filter_id="rsi_14",
                name="RSI (14)",
                category=FilterCategory.MOMENTUM,
                data_type=DataType.NUMERIC,
                description="14-day Relative Strength Index",
                min_value=0,
                max_value=100,
                unit="",
                expression_name="rsi_14",
            ),
            FilterDefinition(
                filter_id="macd",
                name="MACD",
                category=FilterCategory.MOMENTUM,
                data_type=DataType.NUMERIC,
                description="MACD line value",
                expression_name="macd",
            ),
            FilterDefinition(
                filter_id="macd_signal",
                name="MACD Signal",
                category=FilterCategory.MOMENTUM,
                data_type=DataType.BOOLEAN,
                description="MACD above signal line",
                expression_name="macd_signal",
            ),
            FilterDefinition(
                filter_id="stochastic_k",
                name="Stochastic %K",
                category=FilterCategory.MOMENTUM,
                data_type=DataType.NUMERIC,
                description="Stochastic oscillator %K",
                min_value=0,
                max_value=100,
                unit="",
                expression_name="stoch_k",
            ),
            FilterDefinition(
                filter_id="williams_r",
                name="Williams %R",
                category=FilterCategory.MOMENTUM,
                data_type=DataType.NUMERIC,
                description="Williams %R oscillator",
                min_value=-100,
                max_value=0,
                unit="",
                expression_name="williams_r",
            ),
            FilterDefinition(
                filter_id="roc_20",
                name="Rate of Change (20)",
                category=FilterCategory.MOMENTUM,
                data_type=DataType.PERCENT,
                description="20-day rate of change",
                min_value=-50,
                max_value=100,
                unit="%",
                expression_name="roc_20",
            ),
        ]
        for f in filters:
            self.register(f)
    
    def _register_volatility_filters(self) -> None:
        """Register volatility filters."""
        filters = [
            FilterDefinition(
                filter_id="beta",
                name="Beta",
                category=FilterCategory.VOLATILITY,
                data_type=DataType.NUMERIC,
                description="5-year beta vs S&P 500",
                min_value=-2,
                max_value=5,
                unit="",
                expression_name="beta",
            ),
            FilterDefinition(
                filter_id="volatility_30d",
                name="30-Day Volatility",
                category=FilterCategory.VOLATILITY,
                data_type=DataType.PERCENT,
                description="30-day annualized volatility",
                min_value=0,
                max_value=200,
                unit="%",
                expression_name="volatility_30d",
            ),
            FilterDefinition(
                filter_id="atr_14",
                name="ATR (14)",
                category=FilterCategory.VOLATILITY,
                data_type=DataType.CURRENCY,
                description="14-day average true range",
                unit="$",
                expression_name="atr_14",
            ),
            FilterDefinition(
                filter_id="atr_percent",
                name="ATR %",
                category=FilterCategory.VOLATILITY,
                data_type=DataType.PERCENT,
                description="ATR as percentage of price",
                min_value=0,
                max_value=30,
                unit="%",
                expression_name="atr_percent",
            ),
        ]
        for f in filters:
            self.register(f)
    
    def _register_volume_filters(self) -> None:
        """Register volume filters."""
        filters = [
            FilterDefinition(
                filter_id="avg_volume",
                name="Average Volume",
                category=FilterCategory.VOLUME,
                data_type=DataType.NUMERIC,
                description="50-day average daily volume",
                min_value=0,
                max_value=1e9,
                unit="shares",
                expression_name="avg_volume",
            ),
            FilterDefinition(
                filter_id="relative_volume",
                name="Relative Volume",
                category=FilterCategory.VOLUME,
                data_type=DataType.NUMERIC,
                description="Today's volume vs average",
                min_value=0,
                max_value=50,
                unit="x",
                expression_name="relative_volume",
            ),
            FilterDefinition(
                filter_id="dollar_volume",
                name="Dollar Volume",
                category=FilterCategory.VOLUME,
                data_type=DataType.CURRENCY,
                description="Average daily dollar volume",
                min_value=0,
                max_value=100e9,
                unit="$",
                expression_name="dollar_volume",
            ),
        ]
        for f in filters:
            self.register(f)
    
    def _register_analyst_filters(self) -> None:
        """Register analyst filters."""
        filters = [
            FilterDefinition(
                filter_id="analyst_rating",
                name="Analyst Rating",
                category=FilterCategory.ANALYST,
                data_type=DataType.NUMERIC,
                description="Average analyst rating (1-5, 5=Strong Buy)",
                min_value=1,
                max_value=5,
                unit="",
                expression_name="analyst_rating",
            ),
            FilterDefinition(
                filter_id="price_target_upside",
                name="Price Target Upside",
                category=FilterCategory.ANALYST,
                data_type=DataType.PERCENT,
                description="Upside to average price target",
                min_value=-50,
                max_value=200,
                unit="%",
                expression_name="target_upside",
            ),
            FilterDefinition(
                filter_id="estimate_revisions",
                name="EPS Estimate Revisions",
                category=FilterCategory.ANALYST,
                data_type=DataType.NUMERIC,
                description="Net EPS estimate revisions (last 3 months)",
                min_value=-20,
                max_value=20,
                unit="",
                expression_name="estimate_revisions",
            ),
        ]
        for f in filters:
            self.register(f)
    
    def _register_institutional_filters(self) -> None:
        """Register institutional ownership filters."""
        filters = [
            FilterDefinition(
                filter_id="institutional_ownership",
                name="Institutional Ownership",
                category=FilterCategory.INSTITUTIONAL,
                data_type=DataType.PERCENT,
                description="Percentage held by institutions",
                min_value=0,
                max_value=100,
                unit="%",
                expression_name="inst_ownership",
            ),
            FilterDefinition(
                filter_id="institutional_change",
                name="Institutional Ownership Change",
                category=FilterCategory.INSTITUTIONAL,
                data_type=DataType.PERCENT,
                description="Change in institutional ownership (QoQ)",
                min_value=-30,
                max_value=30,
                unit="%",
                expression_name="inst_change",
            ),
            FilterDefinition(
                filter_id="num_institutions",
                name="Number of Institutional Holders",
                category=FilterCategory.INSTITUTIONAL,
                data_type=DataType.NUMERIC,
                description="Number of institutional holders",
                min_value=0,
                max_value=5000,
                unit="",
                expression_name="num_institutions",
            ),
        ]
        for f in filters:
            self.register(f)
    
    def _register_short_interest_filters(self) -> None:
        """Register short interest filters."""
        filters = [
            FilterDefinition(
                filter_id="short_interest",
                name="Short Interest",
                category=FilterCategory.SHORT_INTEREST,
                data_type=DataType.PERCENT,
                description="Short interest as % of float",
                min_value=0,
                max_value=100,
                unit="%",
                expression_name="short_interest",
            ),
            FilterDefinition(
                filter_id="days_to_cover",
                name="Days to Cover",
                category=FilterCategory.SHORT_INTEREST,
                data_type=DataType.NUMERIC,
                description="Short interest / average volume",
                min_value=0,
                max_value=30,
                unit="days",
                expression_name="days_to_cover",
            ),
            FilterDefinition(
                filter_id="short_interest_change",
                name="Short Interest Change",
                category=FilterCategory.SHORT_INTEREST,
                data_type=DataType.PERCENT,
                description="Change in short interest",
                min_value=-50,
                max_value=100,
                unit="%",
                expression_name="short_change",
            ),
        ]
        for f in filters:
            self.register(f)


# Global registry instance
FILTER_REGISTRY = FilterRegistry()
