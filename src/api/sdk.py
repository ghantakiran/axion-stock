"""Axion Python SDK.

Client library for programmatic access to the Axion API.
Supports REST endpoints, WebSocket streaming, and webhook management.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, Any, AsyncIterator

logger = logging.getLogger(__name__)


@dataclass
class SDKConfig:
    """SDK client configuration."""

    base_url: str = "http://localhost:8000"
    api_version: str = "v1"
    timeout: int = 30
    max_retries: int = 3
    ws_url: Optional[str] = None

    @property
    def api_base(self) -> str:
        return f"{self.base_url}/api/{self.api_version}"

    @property
    def websocket_url(self) -> str:
        return self.ws_url or self.base_url.replace("http", "ws") + "/ws"


class _FactorsAPI:
    """Factor scores API namespace."""

    def __init__(self, client: "AxionClient"):
        self._client = client

    def get(self, symbol: str, as_of: Optional[date] = None) -> dict:
        """Get factor scores for a symbol."""
        params = {}
        if as_of:
            params["as_of"] = as_of.isoformat()
        return self._client._request("GET", f"/factors/{symbol}", params=params)

    def history(
        self,
        symbol: str,
        factor: str = "composite",
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> dict:
        """Get historical factor scores."""
        params = {"factor": factor}
        if start:
            params["start"] = start.isoformat()
        if end:
            params["end"] = end.isoformat()
        return self._client._request("GET", f"/factors/{symbol}/history", params=params)

    def screen(
        self,
        factor: str = "composite",
        top: int = 20,
        universe: str = "sp500",
        sector: Optional[str] = None,
    ) -> dict:
        """Screen stocks by factor score."""
        params = {"factor": factor, "top": top, "universe": universe}
        if sector:
            params["sector"] = sector
        return self._client._request("GET", "/factors/screen/results", params=params)

    def regime(self) -> dict:
        """Get current market regime."""
        return self._client._request("GET", "/factors/regime")


class _OrdersAPI:
    """Trading orders API namespace."""

    def __init__(self, client: "AxionClient"):
        self._client = client

    def create(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> dict:
        """Submit a new order."""
        body = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "order_type": order_type,
        }
        if limit_price is not None:
            body["limit_price"] = limit_price
        if stop_price is not None:
            body["stop_price"] = stop_price
        return self._client._request("POST", "/orders", json=body)

    def get(self, order_id: str) -> dict:
        """Get order by ID."""
        return self._client._request("GET", f"/orders/{order_id}")

    def cancel(self, order_id: str) -> dict:
        """Cancel an order."""
        return self._client._request("DELETE", f"/orders/{order_id}")

    def list(
        self,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """List orders."""
        params = {"limit": limit}
        if status:
            params["status"] = status
        if symbol:
            params["symbol"] = symbol
        return self._client._request("GET", "/orders", params=params)


class _PortfolioAPI:
    """Portfolio API namespace."""

    def __init__(self, client: "AxionClient"):
        self._client = client

    def get(self) -> dict:
        """Get current portfolio."""
        return self._client._request("GET", "/portfolio")

    def optimize(
        self,
        method: str = "max_sharpe",
        max_weight: float = 0.10,
        max_positions: int = 20,
    ) -> dict:
        """Run portfolio optimization."""
        return self._client._request("POST", "/portfolio/optimize", json={
            "method": method,
            "max_weight": max_weight,
            "max_positions": max_positions,
        })

    def risk(self) -> dict:
        """Get risk metrics."""
        return self._client._request("GET", "/portfolio/risk")

    def performance(self, period: str = "1y") -> dict:
        """Get performance history."""
        return self._client._request("GET", "/portfolio/performance", params={"period": period})


class _AIAPI:
    """AI & predictions API namespace."""

    def __init__(self, client: "AxionClient"):
        self._client = client

    def chat(self, message: str, context: Optional[str] = None) -> dict:
        """Chat with AI."""
        body = {"message": message}
        if context:
            body["context"] = context
        return self._client._request("POST", "/ai/chat", json=body)

    def predict(self, symbol: str) -> dict:
        """Get ML prediction."""
        return self._client._request("GET", f"/ai/predictions/{symbol}")

    def sentiment(self, symbol: str) -> dict:
        """Get sentiment analysis."""
        return self._client._request("GET", f"/ai/sentiment/{symbol}")

    def picks(self, category: str = "overall", limit: int = 10) -> dict:
        """Get AI stock picks."""
        return self._client._request("GET", f"/ai/picks/{category}", params={"limit": limit})


class _BacktestAPI:
    """Backtesting API namespace."""

    def __init__(self, client: "AxionClient"):
        self._client = client

    def run(
        self,
        strategy: str,
        start: str,
        end: str,
        initial_capital: float = 100_000,
        symbols: Optional[list[str]] = None,
        rebalance_frequency: str = "monthly",
        params: Optional[dict] = None,
    ) -> dict:
        """Run a backtest."""
        body = {
            "strategy": strategy,
            "start_date": start,
            "end_date": end,
            "initial_capital": initial_capital,
            "rebalance_frequency": rebalance_frequency,
        }
        if symbols:
            body["symbols"] = symbols
        if params:
            body["params"] = params
        return self._client._request("POST", "/backtest", json=body)

    def get(self, backtest_id: str) -> dict:
        """Get backtest results."""
        return self._client._request("GET", f"/backtest/{backtest_id}")

    def tearsheet(self, backtest_id: str) -> dict:
        """Get backtest tear sheet."""
        return self._client._request("GET", f"/backtest/{backtest_id}/tearsheet")


class _StreamAPI:
    """WebSocket streaming API namespace (placeholder for async usage)."""

    def __init__(self, client: "AxionClient"):
        self._client = client

    def quotes_url(self, symbols: list[str]) -> str:
        """Get WebSocket URL for quote streaming."""
        return self._client.config.websocket_url


class AxionClient:
    """Python SDK for the Axion API.

    Usage:
        client = AxionClient(api_key="ax_...")
        scores = client.factors.get("AAPL")
        order = client.orders.create("AAPL", 10, "buy")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.config = SDKConfig(base_url=base_url, timeout=timeout)

        # API namespaces
        self.factors = _FactorsAPI(self)
        self.orders = _OrdersAPI(self)
        self.portfolio = _PortfolioAPI(self)
        self.ai = _AIAPI(self)
        self.backtest = _BacktestAPI(self)
        self.stream = _StreamAPI(self)

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> Any:
        """Make an API request (placeholder — no HTTP client dependency).

        In production, this would use httpx or requests.
        For now, returns the request details for testing.

        Args:
            method: HTTP method.
            path: API path.
            params: Query parameters.
            json: Request body.

        Returns:
            Request details dict (placeholder).
        """
        url = f"{self.config.api_base}{path}"

        return {
            "_sdk": True,
            "method": method,
            "url": url,
            "params": params,
            "json": json,
            "headers": {"Authorization": f"Bearer {self.api_key}"},
        }

    def health(self) -> dict:
        """Check API health."""
        return self._request("GET", "/../health")

    def rate_limit(self) -> dict:
        """Get current rate limit status."""
        return self._request("GET", "/../rate-limit")
