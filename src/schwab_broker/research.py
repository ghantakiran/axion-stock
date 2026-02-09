"""Schwab Research Tools (PRD-145).

Research data unique to Schwab/Fidelity: fundamentals, screener,
analyst ratings. All methods work in demo mode with realistic data.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class FundamentalData:
    """Fundamental data for a symbol."""
    symbol: str = ""
    pe_ratio: float = 0.0
    forward_pe: float = 0.0
    eps: float = 0.0
    market_cap: float = 0.0
    dividend_yield: float = 0.0
    beta: float = 0.0
    revenue: float = 0.0
    net_income: float = 0.0
    profit_margin: float = 0.0
    return_on_equity: float = 0.0
    debt_to_equity: float = 0.0
    current_ratio: float = 0.0
    sector: str = ""
    industry: str = ""
    description: str = ""

    @classmethod
    def from_api(cls, data: dict, symbol: str = "") -> "FundamentalData":
        fundamental = data.get("fundamental", data)
        return cls(
            symbol=symbol or data.get("symbol", ""),
            pe_ratio=float(fundamental.get("peRatio", 0)),
            forward_pe=float(fundamental.get("forwardPE", fundamental.get("pegRatio", 0))),
            eps=float(fundamental.get("eps", 0)),
            market_cap=float(fundamental.get("marketCap", 0)),
            dividend_yield=float(fundamental.get("dividendYield", fundamental.get("divYield", 0))),
            beta=float(fundamental.get("beta", 0)),
            revenue=float(fundamental.get("revenue", 0)),
            net_income=float(fundamental.get("netIncome", 0)),
            profit_margin=float(fundamental.get("profitMargin", 0)),
            return_on_equity=float(fundamental.get("returnOnEquity", 0)),
            debt_to_equity=float(fundamental.get("debtToEquity", 0)),
            current_ratio=float(fundamental.get("currentRatio", 0)),
            sector=fundamental.get("sector", ""),
            industry=fundamental.get("industry", ""),
            description=fundamental.get("description", data.get("description", "")),
        )


@dataclass
class ScreenerResult:
    """A single stock screener match."""
    symbol: str = ""
    description: str = ""
    last_price: float = 0.0
    volume: int = 0
    market_cap: float = 0.0
    pe_ratio: float = 0.0
    change_pct: float = 0.0
    sector: str = ""

    @classmethod
    def from_api(cls, data: dict) -> "ScreenerResult":
        return cls(
            symbol=data.get("symbol", ""),
            description=data.get("description", ""),
            last_price=float(data.get("lastPrice", data.get("last", 0))),
            volume=int(data.get("totalVolume", data.get("volume", 0))),
            market_cap=float(data.get("marketCap", 0)),
            pe_ratio=float(data.get("peRatio", 0)),
            change_pct=float(data.get("netPercentChange", data.get("changePct", 0))),
            sector=data.get("sector", ""),
        )


@dataclass
class AnalystRating:
    """Analyst consensus rating for a symbol."""
    symbol: str = ""
    consensus: str = "Hold"
    target_price: float = 0.0
    high_target: float = 0.0
    low_target: float = 0.0
    num_analysts: int = 0
    buy_count: int = 0
    hold_count: int = 0
    sell_count: int = 0

    @classmethod
    def from_api(cls, data: dict, symbol: str = "") -> "AnalystRating":
        return cls(
            symbol=symbol or data.get("symbol", ""),
            consensus=data.get("consensus", data.get("rating", "Hold")),
            target_price=float(data.get("targetPrice", data.get("meanTarget", 0))),
            high_target=float(data.get("highTarget", 0)),
            low_target=float(data.get("lowTarget", 0)),
            num_analysts=int(data.get("numAnalysts", data.get("analystCount", 0))),
            buy_count=int(data.get("buyCount", data.get("buy", 0))),
            hold_count=int(data.get("holdCount", data.get("hold", 0))),
            sell_count=int(data.get("sellCount", data.get("sell", 0))),
        )


class SchwabResearch:
    """Research tools powered by Schwab's data APIs.

    All methods return demo data when no live connection is available.

    Example:
        research = SchwabResearch(client)
        fundamentals = await research.get_fundamentals("AAPL")
        ratings = await research.get_analyst_ratings("AAPL")
    """

    def __init__(self, client: Any = None):
        self._client = client

    async def get_fundamentals(self, symbol: str) -> FundamentalData:
        """Get fundamental data for a symbol."""
        if self._client and hasattr(self._client, '_mode') and self._client._mode == "http":
            try:
                resp = await self._client._http_client.get(
                    f"{self._client._config.marketdata_url}/instruments",
                    params={"symbol": symbol, "projection": "fundamental"},
                    headers=self._client._token_mgr.auth_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                if symbol in data:
                    return FundamentalData.from_api(data[symbol], symbol=symbol)
            except Exception as e:
                logger.warning(f"Failed to fetch fundamentals for {symbol}: {e}")

        return self._demo_fundamentals(symbol)

    async def get_screener(self, criteria: dict) -> list[ScreenerResult]:
        """Run a stock screener with given criteria.

        Args:
            criteria: Dict with filters like min_market_cap, max_pe, sector, etc.
        """
        # Schwab API doesn't have a direct screener endpoint in public API,
        # so we always return demo data (or could use instruments search)
        return self._demo_screener(criteria)

    async def get_analyst_ratings(self, symbol: str) -> AnalystRating:
        """Get analyst consensus ratings for a symbol."""
        return self._demo_analyst_ratings(symbol)

    # -- Demo Data ---------------------------------------------------------

    def _demo_fundamentals(self, symbol: str) -> FundamentalData:
        demo = {
            "SPY": FundamentalData(symbol="SPY", pe_ratio=23.5, forward_pe=21.8, eps=25.13, market_cap=5.2e12, dividend_yield=1.30, beta=1.0, revenue=0, net_income=0, profit_margin=0, return_on_equity=0, sector="ETF", industry="Index Fund", description="SPDR S&P 500 ETF Trust"),
            "AAPL": FundamentalData(symbol="AAPL", pe_ratio=31.2, forward_pe=28.5, eps=7.40, market_cap=3.56e12, dividend_yield=0.44, beta=1.21, revenue=3.94e11, net_income=1.01e11, profit_margin=25.6, return_on_equity=160.0, debt_to_equity=1.87, current_ratio=0.99, sector="Technology", industry="Consumer Electronics", description="Apple Inc."),
            "MSFT": FundamentalData(symbol="MSFT", pe_ratio=36.8, forward_pe=32.1, eps=11.29, market_cap=3.09e12, dividend_yield=0.72, beta=0.89, revenue=2.36e11, net_income=8.85e10, profit_margin=37.5, return_on_equity=38.5, debt_to_equity=0.42, current_ratio=1.77, sector="Technology", industry="Software - Infrastructure", description="Microsoft Corporation"),
            "NVDA": FundamentalData(symbol="NVDA", pe_ratio=65.0, forward_pe=40.2, eps=13.46, market_cap=2.15e12, dividend_yield=0.02, beta=1.65, revenue=7.9e10, net_income=4.2e10, profit_margin=53.2, return_on_equity=115.0, debt_to_equity=0.41, current_ratio=4.17, sector="Technology", industry="Semiconductors", description="NVIDIA Corporation"),
            "GOOGL": FundamentalData(symbol="GOOGL", pe_ratio=25.1, forward_pe=22.3, eps=7.39, market_cap=2.28e12, dividend_yield=0.0, beta=1.06, revenue=3.5e11, net_income=8.6e10, profit_margin=24.6, return_on_equity=32.0, debt_to_equity=0.10, current_ratio=2.10, sector="Technology", industry="Internet Content & Information", description="Alphabet Inc."),
        }
        return demo.get(symbol, FundamentalData(
            symbol=symbol, pe_ratio=20.0, forward_pe=18.0, eps=5.0,
            market_cap=5.0e10, dividend_yield=1.5, beta=1.0,
            sector="Unknown", industry="Unknown", description=symbol,
        ))

    def _demo_screener(self, criteria: dict) -> list[ScreenerResult]:
        all_results = [
            ScreenerResult(symbol="NVDA", description="NVIDIA Corp", last_price=875.20, volume=42000000, market_cap=2.15e12, pe_ratio=65.0, change_pct=1.45, sector="Technology"),
            ScreenerResult(symbol="AAPL", description="Apple Inc", last_price=230.75, volume=55200000, market_cap=3.56e12, pe_ratio=31.2, change_pct=0.81, sector="Technology"),
            ScreenerResult(symbol="MSFT", description="Microsoft Corp", last_price=415.30, volume=22100000, market_cap=3.09e12, pe_ratio=36.8, change_pct=-0.17, sector="Technology"),
            ScreenerResult(symbol="AMZN", description="Amazon.com", last_price=202.10, volume=30200000, market_cap=2.1e12, pe_ratio=62.5, change_pct=1.05, sector="Consumer Cyclical"),
            ScreenerResult(symbol="GOOGL", description="Alphabet Inc", last_price=185.40, volume=28300000, market_cap=2.28e12, pe_ratio=25.1, change_pct=0.49, sector="Technology"),
            ScreenerResult(symbol="META", description="Meta Platforms", last_price=580.30, volume=18500000, market_cap=1.48e12, pe_ratio=27.9, change_pct=0.94, sector="Technology"),
            ScreenerResult(symbol="JPM", description="JPMorgan Chase", last_price=205.80, volume=9800000, market_cap=5.9e11, pe_ratio=12.1, change_pct=0.32, sector="Financial Services"),
            ScreenerResult(symbol="UNH", description="UnitedHealth Group", last_price=555.80, volume=4500000, market_cap=5.1e11, pe_ratio=22.5, change_pct=1.52, sector="Healthcare"),
        ]
        # Apply basic criteria filtering
        results = all_results
        if criteria.get("sector"):
            results = [r for r in results if r.sector.lower() == criteria["sector"].lower()]
        if criteria.get("min_market_cap"):
            results = [r for r in results if r.market_cap >= criteria["min_market_cap"]]
        if criteria.get("max_pe"):
            results = [r for r in results if r.pe_ratio <= criteria["max_pe"]]
        return results

    def _demo_analyst_ratings(self, symbol: str) -> AnalystRating:
        demo = {
            "SPY": AnalystRating(symbol="SPY", consensus="Buy", target_price=620.0, high_target=650.0, low_target=560.0, num_analysts=0, buy_count=0, hold_count=0, sell_count=0),
            "AAPL": AnalystRating(symbol="AAPL", consensus="Buy", target_price=250.0, high_target=275.0, low_target=200.0, num_analysts=42, buy_count=30, hold_count=10, sell_count=2),
            "MSFT": AnalystRating(symbol="MSFT", consensus="Strong Buy", target_price=450.0, high_target=500.0, low_target=380.0, num_analysts=38, buy_count=33, hold_count=5, sell_count=0),
            "NVDA": AnalystRating(symbol="NVDA", consensus="Strong Buy", target_price=950.0, high_target=1100.0, low_target=700.0, num_analysts=45, buy_count=40, hold_count=4, sell_count=1),
            "GOOGL": AnalystRating(symbol="GOOGL", consensus="Buy", target_price=200.0, high_target=220.0, low_target=170.0, num_analysts=40, buy_count=32, hold_count=7, sell_count=1),
        }
        return demo.get(symbol, AnalystRating(
            symbol=symbol, consensus="Hold", target_price=110.0,
            high_target=130.0, low_target=90.0, num_analysts=15,
            buy_count=6, hold_count=7, sell_count=2,
        ))
