"""Fidelity Research Tools (PRD-156).

Research data unique to Fidelity: fundamentals, fund screening,
analyst ratings. All methods work in demo mode with realistic data.
Fidelity is known for its extensive mutual fund research capabilities.
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
    eps: float = 0.0
    dividend_yield: float = 0.0
    market_cap: float = 0.0
    revenue: float = 0.0
    profit_margin: float = 0.0
    roe: float = 0.0
    debt_to_equity: float = 0.0
    beta: float = 0.0
    sector: str = ""
    industry: str = ""

    @classmethod
    def from_api(cls, data: dict, symbol: str = "") -> "FundamentalData":
        fundamental = data.get("fundamental", data)
        return cls(
            symbol=symbol or data.get("symbol", ""),
            pe_ratio=float(fundamental.get("peRatio", 0)),
            eps=float(fundamental.get("eps", 0)),
            dividend_yield=float(fundamental.get("dividendYield", fundamental.get("divYield", 0))),
            market_cap=float(fundamental.get("marketCap", 0)),
            revenue=float(fundamental.get("revenue", 0)),
            profit_margin=float(fundamental.get("profitMargin", 0)),
            roe=float(fundamental.get("returnOnEquity", fundamental.get("roe", 0))),
            debt_to_equity=float(fundamental.get("debtToEquity", 0)),
            beta=float(fundamental.get("beta", 0)),
            sector=fundamental.get("sector", ""),
            industry=fundamental.get("industry", ""),
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "pe_ratio": self.pe_ratio,
            "eps": self.eps,
            "dividend_yield": self.dividend_yield,
            "market_cap": self.market_cap,
            "revenue": self.revenue,
            "profit_margin": self.profit_margin,
            "roe": self.roe,
            "debt_to_equity": self.debt_to_equity,
            "beta": self.beta,
            "sector": self.sector,
            "industry": self.industry,
        }


@dataclass
class FundScreenResult:
    """A mutual fund screener result from Fidelity."""
    symbol: str = ""
    name: str = ""
    category: str = ""
    morningstar_rating: int = 0
    expense_ratio: float = 0.0
    ytd_return: float = 0.0
    aum: float = 0.0

    @classmethod
    def from_api(cls, data: dict) -> "FundScreenResult":
        return cls(
            symbol=data.get("symbol", ""),
            name=data.get("name", data.get("fundName", "")),
            category=data.get("category", data.get("morningstarCategory", "")),
            morningstar_rating=int(data.get("morningstarRating", data.get("starRating", 0))),
            expense_ratio=float(data.get("expenseRatio", data.get("netExpenseRatio", 0))),
            ytd_return=float(data.get("ytdReturn", data.get("ytdTotalReturn", 0))),
            aum=float(data.get("aum", data.get("totalNetAssets", 0))),
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "category": self.category,
            "morningstar_rating": self.morningstar_rating,
            "expense_ratio": self.expense_ratio,
            "ytd_return": self.ytd_return,
            "aum": self.aum,
        }


@dataclass
class AnalystRating:
    """Analyst rating for a symbol."""
    symbol: str = ""
    firm: str = ""
    rating: str = "Hold"
    target_price: float = 0.0
    date_issued: str = ""

    @classmethod
    def from_api(cls, data: dict, symbol: str = "") -> "AnalystRating":
        return cls(
            symbol=symbol or data.get("symbol", ""),
            firm=data.get("firm", data.get("analystFirm", "")),
            rating=data.get("rating", data.get("recommendation", "Hold")),
            target_price=float(data.get("targetPrice", data.get("priceTarget", 0))),
            date_issued=data.get("dateIssued", data.get("date", "")),
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "firm": self.firm,
            "rating": self.rating,
            "target_price": self.target_price,
            "date_issued": self.date_issued,
        }


class FidelityResearch:
    """Research tools powered by Fidelity's data APIs.

    All methods return demo data when no live connection is available.
    Includes Fidelity-specific mutual fund screening.

    Example:
        research = FidelityResearch(client)
        fundamentals = await research.get_fundamentals("AAPL")
        ratings = await research.get_analyst_ratings("AAPL")
        funds = await research.screen_funds({"category": "Large Blend"})
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

    async def screen_funds(self, criteria: dict) -> list[FundScreenResult]:
        """Screen mutual funds using Fidelity's fund screener.

        Args:
            criteria: Dict with filters like category, min_rating,
                      max_expense_ratio, min_ytd_return, etc.
        """
        if self._client and hasattr(self._client, '_mode') and self._client._mode == "http":
            try:
                resp = await self._client._http_client.get(
                    f"{self._client._config.marketdata_url}/funds/screener",
                    params=criteria,
                    headers=self._client._token_mgr.auth_headers(),
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
                return [FundScreenResult.from_api(r) for r in results]
            except Exception as e:
                logger.warning(f"Failed to screen funds: {e}")

        return self._demo_fund_screen(criteria)

    async def get_analyst_ratings(self, symbol: str) -> list[AnalystRating]:
        """Get analyst ratings for a symbol."""
        if self._client and hasattr(self._client, '_mode') and self._client._mode == "http":
            try:
                resp = await self._client._http_client.get(
                    f"{self._client._config.marketdata_url}/ratings/{symbol}",
                    headers=self._client._token_mgr.auth_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                ratings = data.get("ratings", [data] if "firm" in data else [])
                return [AnalystRating.from_api(r, symbol=symbol) for r in ratings]
            except Exception as e:
                logger.warning(f"Failed to fetch analyst ratings for {symbol}: {e}")

        return self._demo_analyst_ratings(symbol)

    # -- Demo Data ---------------------------------------------------------

    def _demo_fundamentals(self, symbol: str) -> FundamentalData:
        demo = {
            "SPY": FundamentalData(symbol="SPY", pe_ratio=23.5, eps=25.13, market_cap=5.2e12, dividend_yield=1.30, beta=1.0, sector="ETF", industry="Index Fund"),
            "AAPL": FundamentalData(symbol="AAPL", pe_ratio=31.2, eps=7.40, market_cap=3.56e12, dividend_yield=0.44, beta=1.21, revenue=3.94e11, profit_margin=25.6, roe=160.0, debt_to_equity=1.87, sector="Technology", industry="Consumer Electronics"),
            "MSFT": FundamentalData(symbol="MSFT", pe_ratio=36.8, eps=11.29, market_cap=3.09e12, dividend_yield=0.72, beta=0.89, revenue=2.36e11, profit_margin=37.5, roe=38.5, debt_to_equity=0.42, sector="Technology", industry="Software - Infrastructure"),
            "NVDA": FundamentalData(symbol="NVDA", pe_ratio=65.0, eps=13.46, market_cap=2.15e12, dividend_yield=0.02, beta=1.65, revenue=7.9e10, profit_margin=53.2, roe=115.0, debt_to_equity=0.41, sector="Technology", industry="Semiconductors"),
            "GOOGL": FundamentalData(symbol="GOOGL", pe_ratio=25.1, eps=7.39, market_cap=2.28e12, dividend_yield=0.0, beta=1.06, revenue=3.5e11, profit_margin=24.6, roe=32.0, debt_to_equity=0.10, sector="Technology", industry="Internet Content & Information"),
        }
        return demo.get(symbol, FundamentalData(
            symbol=symbol, pe_ratio=20.0, eps=5.0,
            market_cap=5.0e10, dividend_yield=1.5, beta=1.0,
            sector="Unknown", industry="Unknown",
        ))

    def _demo_fund_screen(self, criteria: dict) -> list[FundScreenResult]:
        all_funds = [
            FundScreenResult(symbol="FXAIX", name="Fidelity 500 Index Fund", category="Large Blend", morningstar_rating=5, expense_ratio=0.015, ytd_return=12.5, aum=4.1e11),
            FundScreenResult(symbol="FSKAX", name="Fidelity Total Market Index Fund", category="Large Blend", morningstar_rating=5, expense_ratio=0.015, ytd_return=11.8, aum=8.2e10),
            FundScreenResult(symbol="FTBFX", name="Fidelity Total Bond Fund", category="Intermediate Core Bond", morningstar_rating=4, expense_ratio=0.45, ytd_return=3.2, aum=3.1e10),
            FundScreenResult(symbol="FCNTX", name="Fidelity Contrafund", category="Large Growth", morningstar_rating=4, expense_ratio=0.39, ytd_return=18.7, aum=1.1e11),
            FundScreenResult(symbol="FBALX", name="Fidelity Balanced Fund", category="Allocation--50% to 70% Equity", morningstar_rating=4, expense_ratio=0.49, ytd_return=9.4, aum=3.8e10),
            FundScreenResult(symbol="FDGRX", name="Fidelity Growth Company Fund", category="Large Growth", morningstar_rating=5, expense_ratio=0.79, ytd_return=22.3, aum=5.5e10),
            FundScreenResult(symbol="FSMEX", name="Fidelity Select Medical Technology", category="Health", morningstar_rating=3, expense_ratio=0.68, ytd_return=6.1, aum=8.9e9),
            FundScreenResult(symbol="FSPTX", name="Fidelity Select Technology", category="Technology", morningstar_rating=4, expense_ratio=0.68, ytd_return=20.1, aum=1.2e10),
        ]
        results = all_funds
        if criteria.get("category"):
            results = [f for f in results if criteria["category"].lower() in f.category.lower()]
        if criteria.get("min_rating"):
            results = [f for f in results if f.morningstar_rating >= criteria["min_rating"]]
        if criteria.get("max_expense_ratio"):
            results = [f for f in results if f.expense_ratio <= criteria["max_expense_ratio"]]
        return results

    def _demo_analyst_ratings(self, symbol: str) -> list[AnalystRating]:
        demo = {
            "AAPL": [
                AnalystRating(symbol="AAPL", firm="Morgan Stanley", rating="Overweight", target_price=250.0, date_issued="2025-01-10"),
                AnalystRating(symbol="AAPL", firm="Goldman Sachs", rating="Buy", target_price=245.0, date_issued="2025-01-08"),
                AnalystRating(symbol="AAPL", firm="JP Morgan", rating="Neutral", target_price=225.0, date_issued="2025-01-05"),
            ],
            "MSFT": [
                AnalystRating(symbol="MSFT", firm="Morgan Stanley", rating="Overweight", target_price=460.0, date_issued="2025-01-12"),
                AnalystRating(symbol="MSFT", firm="Bank of America", rating="Buy", target_price=450.0, date_issued="2025-01-09"),
                AnalystRating(symbol="MSFT", firm="Barclays", rating="Overweight", target_price=440.0, date_issued="2025-01-06"),
            ],
            "NVDA": [
                AnalystRating(symbol="NVDA", firm="Goldman Sachs", rating="Buy", target_price=1000.0, date_issued="2025-01-11"),
                AnalystRating(symbol="NVDA", firm="Morgan Stanley", rating="Overweight", target_price=950.0, date_issued="2025-01-07"),
                AnalystRating(symbol="NVDA", firm="Wedbush", rating="Outperform", target_price=920.0, date_issued="2025-01-04"),
            ],
            "GOOGL": [
                AnalystRating(symbol="GOOGL", firm="JP Morgan", rating="Overweight", target_price=210.0, date_issued="2025-01-10"),
                AnalystRating(symbol="GOOGL", firm="Citigroup", rating="Buy", target_price=205.0, date_issued="2025-01-07"),
                AnalystRating(symbol="GOOGL", firm="UBS", rating="Neutral", target_price=190.0, date_issued="2025-01-03"),
            ],
            "SPY": [
                AnalystRating(symbol="SPY", firm="Market Consensus", rating="Buy", target_price=620.0, date_issued="2025-01-15"),
            ],
        }
        return demo.get(symbol, [
            AnalystRating(symbol=symbol, firm="Consensus", rating="Hold", target_price=110.0, date_issued="2025-01-01"),
        ])
