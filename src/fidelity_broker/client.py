"""Fidelity REST API Client (PRD-156).

Lightweight HTTP client for Fidelity's Trading & Market Data APIs.
Uses fidelity SDK when available, falls back to OAuth2 HTTP, then demo mode.
Includes mutual fund support unique to Fidelity's platform.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, date, timedelta
from enum import Enum
from typing import Any, Optional
import json
import logging
import uuid

logger = logging.getLogger(__name__)

# Try importing fidelity SDK; fall back to raw HTTP
_HAS_FIDELITY_SDK = False
try:
    import fidelity as fidelity_sdk
    _HAS_FIDELITY_SDK = True
except ImportError:
    fidelity_sdk = None  # type: ignore

_HAS_HTTPX = False
try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    httpx = None  # type: ignore


# =====================================================================
# Configuration
# =====================================================================


@dataclass
class FidelityConfig:
    """Configuration for Fidelity API connection."""
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "https://127.0.0.1:8182/callback"
    token_path: str = ".fidelity_token.json"
    base_url: str = "https://api.fidelity.com"
    # Rate limiting
    max_requests_per_minute: int = 60
    request_timeout: int = 30
    # Retry
    max_retries: int = 3
    retry_delay: float = 1.0

    @property
    def trader_url(self) -> str:
        return f"{self.base_url}/trader/v1"

    @property
    def marketdata_url(self) -> str:
        return f"{self.base_url}/marketdata/v1"

    @property
    def auth_url(self) -> str:
        return "https://api.fidelity.com/v1/oauth/authorize"

    @property
    def token_url(self) -> str:
        return "https://api.fidelity.com/v1/oauth/token"


# =====================================================================
# Response Models
# =====================================================================


@dataclass
class FidelityAccount:
    """Fidelity account information."""
    account_number: str = ""
    account_type: str = "INDIVIDUAL"
    cash: float = 0.0
    equity: float = 0.0
    long_market_value: float = 0.0
    short_market_value: float = 0.0
    buying_power: float = 0.0
    margin_buying_power: float = 0.0
    available_funds: float = 0.0
    position_count: int = 0
    is_margin_account: bool = False

    @classmethod
    def from_api(cls, data: dict) -> "FidelityAccount":
        acct = data.get("account", data)
        balances = acct.get("currentBalances", acct.get("balances", {}))
        positions = acct.get("positions", [])
        return cls(
            account_number=str(acct.get("accountNumber", acct.get("accountId", ""))),
            account_type=acct.get("type", acct.get("accountType", "INDIVIDUAL")),
            cash=float(balances.get("cashBalance", balances.get("cashAvailableForTrading", 0))),
            equity=float(balances.get("equity", balances.get("liquidationValue", 0))),
            long_market_value=float(balances.get("longMarketValue", 0)),
            short_market_value=float(balances.get("shortMarketValue", 0)),
            buying_power=float(balances.get("buyingPower", 0)),
            margin_buying_power=float(balances.get("marginBuyingPower", balances.get("buyingPower", 0))),
            available_funds=float(balances.get("availableFunds", balances.get("cashAvailableForTrading", 0))),
            position_count=len(positions),
            is_margin_account=acct.get("isMarginAccount", acct.get("type", "") == "MARGIN"),
        )

    def to_dict(self) -> dict:
        return {
            "account_number": self.account_number,
            "account_type": self.account_type,
            "cash": self.cash,
            "equity": self.equity,
            "long_market_value": self.long_market_value,
            "short_market_value": self.short_market_value,
            "buying_power": self.buying_power,
            "margin_buying_power": self.margin_buying_power,
            "available_funds": self.available_funds,
            "position_count": self.position_count,
            "is_margin_account": self.is_margin_account,
        }


@dataclass
class FidelityPosition:
    """Fidelity position."""
    symbol: str = ""
    asset_type: str = "EQUITY"
    quantity: float = 0.0
    average_price: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    day_pnl: float = 0.0
    cost_basis: float = 0.0
    long_short: str = "Long"

    @classmethod
    def from_api(cls, data: dict) -> "FidelityPosition":
        instrument = data.get("instrument", {})
        qty = float(data.get("longQuantity", data.get("quantity", 0)))
        avg_price = float(data.get("averagePrice", 0))
        return cls(
            symbol=instrument.get("symbol", data.get("symbol", "")),
            asset_type=instrument.get("assetType", data.get("assetType", "EQUITY")),
            quantity=qty,
            average_price=avg_price,
            current_price=float(data.get("currentPrice", data.get("marketPrice", 0))),
            market_value=float(data.get("marketValue", 0)),
            unrealized_pnl=float(data.get("unrealizedPnl", data.get("currentDayProfitLoss", 0))),
            unrealized_pnl_pct=float(data.get("unrealizedPnlPct", data.get("currentDayProfitLossPercentage", 0))),
            day_pnl=float(data.get("currentDayProfitLoss", data.get("dayPnl", 0))),
            cost_basis=avg_price * qty,
            long_short="Long" if qty > 0 else "Short",
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "asset_type": self.asset_type,
            "quantity": self.quantity,
            "average_price": self.average_price,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "day_pnl": self.day_pnl,
            "cost_basis": self.cost_basis,
            "long_short": self.long_short,
        }


@dataclass
class FidelityOrder:
    """Fidelity order."""
    order_id: str = ""
    symbol: str = ""
    side: str = "BUY"
    quantity: float = 0.0
    filled_quantity: float = 0.0
    price: float = 0.0
    order_type: str = "MARKET"
    status: str = "QUEUED"
    duration: str = "DAY"
    entered_time: str = ""
    close_time: str = ""
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None

    @classmethod
    def from_api(cls, data: dict) -> "FidelityOrder":
        legs = data.get("orderLegCollection", data.get("legs", [{}]))
        first_leg = legs[0] if legs else {}
        instrument = first_leg.get("instrument", {})
        return cls(
            order_id=str(data.get("orderId", data.get("orderNumber", ""))),
            symbol=instrument.get("symbol", first_leg.get("symbol", "")),
            side=first_leg.get("instruction", first_leg.get("side", "BUY")),
            quantity=float(first_leg.get("quantity", data.get("quantity", 0))),
            filled_quantity=float(data.get("filledQuantity", 0)),
            price=float(data.get("price", data.get("executionPrice", 0))),
            order_type=data.get("orderType", "MARKET"),
            status=data.get("status", "QUEUED"),
            duration=data.get("duration", data.get("timeInForce", "DAY")),
            entered_time=data.get("enteredTime", data.get("placedTime", "")),
            close_time=data.get("closeTime", data.get("executedTime", "")),
            stop_price=float(data["stopPrice"]) if data.get("stopPrice") else None,
            limit_price=float(data["price"]) if data.get("price") and data.get("orderType") == "LIMIT" else None,
        )

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "price": self.price,
            "order_type": self.order_type,
            "status": self.status,
            "duration": self.duration,
            "entered_time": self.entered_time,
            "close_time": self.close_time,
            "stop_price": self.stop_price,
            "limit_price": self.limit_price,
        }


@dataclass
class FidelityQuote:
    """Real-time quote from Fidelity."""
    symbol: str = ""
    bid_price: float = 0.0
    ask_price: float = 0.0
    last_price: float = 0.0
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    close_price: float = 0.0
    total_volume: int = 0
    net_change: float = 0.0
    net_percent_change: float = 0.0
    exchange: str = ""
    description: str = ""
    pe_ratio: float = 0.0
    week_52_high: float = 0.0
    week_52_low: float = 0.0
    dividend_yield: float = 0.0
    market_cap: float = 0.0

    @classmethod
    def from_api(cls, data: dict, symbol: str = "") -> "FidelityQuote":
        quote = data.get("quote", data)
        ref = data.get("reference", {})
        return cls(
            symbol=symbol or data.get("symbol", ref.get("symbol", "")),
            bid_price=float(quote.get("bidPrice", 0)),
            ask_price=float(quote.get("askPrice", 0)),
            last_price=float(quote.get("lastPrice", quote.get("mark", 0))),
            open_price=float(quote.get("openPrice", 0)),
            high_price=float(quote.get("highPrice", 0)),
            low_price=float(quote.get("lowPrice", 0)),
            close_price=float(quote.get("closePrice", 0)),
            total_volume=int(quote.get("totalVolume", 0)),
            net_change=float(quote.get("netChange", 0)),
            net_percent_change=float(quote.get("netPercentChange", 0)),
            exchange=quote.get("exchangeName", ref.get("exchange", "")),
            description=ref.get("description", quote.get("description", "")),
            pe_ratio=float(quote.get("peRatio", 0)),
            week_52_high=float(quote.get("52WkHigh", quote.get("fiftyTwoWeekHigh", 0))),
            week_52_low=float(quote.get("52WkLow", quote.get("fiftyTwoWeekLow", 0))),
            dividend_yield=float(quote.get("dividendYield", quote.get("divYield", 0))),
            market_cap=float(quote.get("marketCap", 0)),
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "last_price": self.last_price,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "total_volume": self.total_volume,
            "net_change": self.net_change,
            "net_percent_change": self.net_percent_change,
            "exchange": self.exchange,
            "description": self.description,
            "pe_ratio": self.pe_ratio,
            "week_52_high": self.week_52_high,
            "week_52_low": self.week_52_low,
            "dividend_yield": self.dividend_yield,
            "market_cap": self.market_cap,
        }


@dataclass
class FidelityCandle:
    """OHLCV candle from Fidelity price history."""
    timestamp: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0

    @classmethod
    def from_api(cls, data: dict) -> "FidelityCandle":
        return cls(
            timestamp=str(data.get("datetime", data.get("timestamp", ""))),
            open=float(data.get("open", 0)),
            high=float(data.get("high", 0)),
            low=float(data.get("low", 0)),
            close=float(data.get("close", 0)),
            volume=int(data.get("volume", 0)),
        )

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass
class FidelityMutualFund:
    """Mutual fund data from Fidelity."""
    symbol: str = ""
    name: str = ""
    category: str = ""
    nav: float = 0.0
    expense_ratio: float = 0.0
    morningstar_rating: int = 0
    ytd_return: float = 0.0
    one_year_return: float = 0.0
    three_year_return: float = 0.0
    five_year_return: float = 0.0
    aum: float = 0.0
    min_investment: float = 0.0

    @classmethod
    def from_api(cls, data: dict) -> "FidelityMutualFund":
        return cls(
            symbol=data.get("symbol", data.get("ticker", "")),
            name=data.get("name", data.get("fundName", "")),
            category=data.get("category", data.get("morningstarCategory", "")),
            nav=float(data.get("nav", data.get("netAssetValue", 0))),
            expense_ratio=float(data.get("expenseRatio", data.get("netExpenseRatio", 0))),
            morningstar_rating=int(data.get("morningstarRating", data.get("starRating", 0))),
            ytd_return=float(data.get("ytdReturn", data.get("ytdTotalReturn", 0))),
            one_year_return=float(data.get("oneYearReturn", data.get("return1Yr", 0))),
            three_year_return=float(data.get("threeYearReturn", data.get("return3Yr", 0))),
            five_year_return=float(data.get("fiveYearReturn", data.get("return5Yr", 0))),
            aum=float(data.get("aum", data.get("totalNetAssets", 0))),
            min_investment=float(data.get("minInvestment", data.get("minimumInvestment", 0))),
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "category": self.category,
            "nav": self.nav,
            "expense_ratio": self.expense_ratio,
            "morningstar_rating": self.morningstar_rating,
            "ytd_return": self.ytd_return,
            "one_year_return": self.one_year_return,
            "three_year_return": self.three_year_return,
            "five_year_return": self.five_year_return,
            "aum": self.aum,
            "min_investment": self.min_investment,
        }


# =====================================================================
# OAuth2 Token Management
# =====================================================================


class _TokenManager:
    """Handles OAuth2 token persistence and refresh for Fidelity API."""

    def __init__(self, config: FidelityConfig):
        self._config = config
        self._access_token: str = ""
        self._refresh_token: str = ""
        self._expires_at: Optional[datetime] = None

    @property
    def access_token(self) -> str:
        return self._access_token

    @property
    def is_expired(self) -> bool:
        if not self._expires_at:
            return True
        return datetime.now(timezone.utc) >= self._expires_at

    def set_tokens(self, access: str, refresh: str, expires_in: int = 1800) -> None:
        self._access_token = access
        self._refresh_token = refresh
        self._expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    async def refresh(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not self._refresh_token or not _HAS_HTTPX:
            return False
        try:
            async with httpx.AsyncClient(timeout=self._config.request_timeout) as client:
                resp = await client.post(
                    self._config.token_url,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self._refresh_token,
                        "client_id": self._config.client_id,
                        "client_secret": self._config.client_secret,
                    },
                )
                if resp.status_code == 200:
                    body = resp.json()
                    self.set_tokens(
                        body["access_token"],
                        body.get("refresh_token", self._refresh_token),
                        body.get("expires_in", 1800),
                    )
                    return True
        except Exception as e:
            logger.warning(f"Token refresh failed: {e}")
        return False

    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}


# =====================================================================
# Client
# =====================================================================


class FidelityClient:
    """Fidelity REST API client.

    Supports fidelity SDK, raw HTTP with OAuth2, and demo mode fallback.
    Includes mutual fund support unique to Fidelity's platform.

    Example:
        client = FidelityClient(FidelityConfig(client_id="...", client_secret="..."))
        await client.connect()
        accounts = await client.get_accounts()
        funds = await client.get_mutual_funds("Large Blend")
    """

    def __init__(self, config: FidelityConfig):
        self._config = config
        self._connected = False
        self._http_client: Any = None
        self._sdk_client: Any = None
        self._mode: str = "demo"  # "sdk", "http", or "demo"
        self._token_mgr = _TokenManager(config)
        self._request_count = 0

    @property
    def config(self) -> FidelityConfig:
        return self._config

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def mode(self) -> str:
        return self._mode

    async def connect(self) -> bool:
        """Connect to Fidelity API.

        Tries SDK first, then raw HTTP with OAuth2, falls back to demo mode.
        """
        if not self._config.client_id or not self._config.client_secret:
            logger.info("No Fidelity credentials -- using demo mode")
            self._mode = "demo"
            self._connected = True
            return True

        # Try fidelity SDK
        if _HAS_FIDELITY_SDK:
            try:
                self._sdk_client = fidelity_sdk.auth.client_from_token_file(
                    self._config.token_path,
                    self._config.client_id,
                    self._config.client_secret,
                    self._config.redirect_uri,
                )
                self._mode = "sdk"
                self._connected = True
                logger.info("Connected to Fidelity via SDK")
                return True
            except Exception as e:
                logger.warning(f"SDK connection failed: {e}")

        # Try raw HTTP with OAuth2
        if _HAS_HTTPX:
            try:
                self._http_client = httpx.AsyncClient(
                    timeout=self._config.request_timeout,
                )
                # Attempt client credentials flow
                resp = await self._http_client.post(
                    self._config.token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._config.client_id,
                        "client_secret": self._config.client_secret,
                    },
                )
                if resp.status_code == 200:
                    body = resp.json()
                    self._token_mgr.set_tokens(
                        body["access_token"],
                        body.get("refresh_token", ""),
                        body.get("expires_in", 1800),
                    )
                    self._mode = "http"
                    self._connected = True
                    logger.info("Connected to Fidelity via HTTP/OAuth2")
                    return True
                else:
                    logger.warning(f"OAuth2 auth failed: {resp.status_code}")
            except Exception as e:
                logger.warning(f"HTTP connection failed: {e}")

        # Fallback to demo
        self._mode = "demo"
        self._connected = True
        logger.info("Using Fidelity demo mode (no live API)")
        return True

    async def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        if self._http_client and hasattr(self._http_client, "aclose"):
            await self._http_client.aclose()
        self._http_client = None
        self._sdk_client = None
        self._connected = False
        self._mode = "demo"
        logger.info("Disconnected from Fidelity")

    async def _ensure_token(self) -> None:
        """Refresh token if expired (HTTP mode)."""
        if self._mode == "http" and self._token_mgr.is_expired:
            await self._token_mgr.refresh()

    # -- Accounts ----------------------------------------------------------

    async def get_accounts(self) -> list[FidelityAccount]:
        """Get all linked accounts."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.get(
                f"{self._config.trader_url}/accounts",
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            return [FidelityAccount.from_api(a) for a in resp.json()]

        return self._demo_accounts()

    async def get_positions(self, account_id: str) -> list[FidelityPosition]:
        """Get positions for a specific account."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.get(
                f"{self._config.trader_url}/accounts/{account_id}",
                params={"fields": "positions"},
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            acct = data.get("account", data)
            positions = acct.get("positions", [])
            return [FidelityPosition.from_api(p) for p in positions]

        return self._demo_positions()

    async def get_orders(self, account_id: str, status: str = "FILLED") -> list[FidelityOrder]:
        """Get orders for a specific account."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            now = datetime.now(timezone.utc)
            resp = await self._http_client.get(
                f"{self._config.trader_url}/accounts/{account_id}/orders",
                params={
                    "fromEnteredTime": (now - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00.000Z"),
                    "toEnteredTime": now.strftime("%Y-%m-%dT23:59:59.000Z"),
                    "status": status,
                },
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            return [FidelityOrder.from_api(o) for o in resp.json()]

        return self._demo_orders()

    async def place_order(self, account_id: str, order_request: dict) -> FidelityOrder:
        """Submit an order."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.post(
                f"{self._config.trader_url}/accounts/{account_id}/orders",
                json=order_request,
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            return FidelityOrder(
                order_id=resp.headers.get("Location", "").split("/")[-1],
                symbol=order_request.get("orderLegCollection", [{}])[0].get("instrument", {}).get("symbol", ""),
                order_type=order_request.get("orderType", "MARKET"),
                status="QUEUED",
            )

        return self._demo_place_order(order_request)

    async def cancel_order(self, account_id: str, order_id: str) -> bool:
        """Cancel an order."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.delete(
                f"{self._config.trader_url}/accounts/{account_id}/orders/{order_id}",
                headers=self._token_mgr.auth_headers(),
            )
            return resp.status_code in (200, 204)

        return True

    # -- Market Data -------------------------------------------------------

    async def get_quote(self, symbols: list[str]) -> list[FidelityQuote]:
        """Get quotes for a list of symbols."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.get(
                f"{self._config.marketdata_url}/quotes",
                params={"symbols": ",".join(symbols)},
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            return [FidelityQuote.from_api(data[s], symbol=s) for s in symbols if s in data]

        return self._demo_quotes(symbols)

    async def get_price_history(
        self,
        symbol: str,
        period_type: str = "month",
        period: int = 1,
        frequency_type: str = "daily",
        frequency: int = 1,
    ) -> list[FidelityCandle]:
        """Get price history (OHLCV candles)."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.get(
                f"{self._config.marketdata_url}/pricehistory",
                params={
                    "symbol": symbol,
                    "periodType": period_type,
                    "period": period,
                    "frequencyType": frequency_type,
                    "frequency": frequency,
                },
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            candles = resp.json().get("candles", [])
            return [FidelityCandle.from_api(c) for c in candles]

        return self._demo_candles(symbol)

    async def get_option_chain(
        self,
        symbol: str,
        strike_count: int = 10,
        include_underlying: bool = True,
    ) -> dict:
        """Get options chain for a symbol."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.get(
                f"{self._config.marketdata_url}/chains",
                params={
                    "symbol": symbol,
                    "strikeCount": strike_count,
                    "includeUnderlyingQuote": include_underlying,
                },
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            return resp.json()

        return self._demo_option_chain(symbol, strike_count)

    async def get_mutual_funds(self, category: str = "") -> list[FidelityMutualFund]:
        """Get mutual fund data -- a Fidelity-specific feature.

        Args:
            category: Optional Morningstar category to filter by
                      (e.g. "Large Blend", "Large Growth", "Intermediate Core Bond").
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            params: dict[str, Any] = {}
            if category:
                params["category"] = category
            resp = await self._http_client.get(
                f"{self._config.marketdata_url}/funds",
                params=params,
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            funds = resp.json().get("funds", resp.json())
            if isinstance(funds, list):
                return [FidelityMutualFund.from_api(f) for f in funds]
            return []

        return self._demo_mutual_funds(category)

    # -- Demo Data ---------------------------------------------------------

    def _demo_accounts(self) -> list[FidelityAccount]:
        return [
            FidelityAccount(
                account_number="DEMO-FID-78901234",
                account_type="INDIVIDUAL",
                cash=72000.0,
                equity=158500.0,
                long_market_value=86500.0,
                short_market_value=0.0,
                buying_power=144000.0,
                margin_buying_power=144000.0,
                available_funds=72000.0,
                position_count=3,
                is_margin_account=True,
            ),
        ]

    def _demo_positions(self) -> list[FidelityPosition]:
        return [
            FidelityPosition(
                symbol="SPY", asset_type="EQUITY", quantity=50,
                average_price=575.00, current_price=590.50,
                market_value=29525.0, unrealized_pnl=775.0,
                unrealized_pnl_pct=2.70, day_pnl=125.0,
                cost_basis=28750.0, long_short="Long",
            ),
            FidelityPosition(
                symbol="AAPL", asset_type="EQUITY", quantity=100,
                average_price=218.00, current_price=230.75,
                market_value=23075.0, unrealized_pnl=1275.0,
                unrealized_pnl_pct=5.85, day_pnl=310.0,
                cost_basis=21800.0, long_short="Long",
            ),
            FidelityPosition(
                symbol="GOOGL", asset_type="EQUITY", quantity=80,
                average_price=178.00, current_price=185.40,
                market_value=14832.0, unrealized_pnl=592.0,
                unrealized_pnl_pct=4.16, day_pnl=88.0,
                cost_basis=14240.0, long_short="Long",
            ),
        ]

    def _demo_orders(self) -> list[FidelityOrder]:
        return [
            FidelityOrder(
                order_id="DEMO-FID-ORD-001", symbol="AAPL", side="BUY",
                quantity=100, filled_quantity=100, price=218.0,
                order_type="MARKET", status="FILLED", duration="DAY",
                entered_time="2025-01-15T10:30:00Z",
            ),
            FidelityOrder(
                order_id="DEMO-FID-ORD-002", symbol="SPY", side="BUY",
                quantity=50, filled_quantity=50, price=575.0,
                order_type="LIMIT", status="FILLED", duration="DAY",
                limit_price=575.0,
                entered_time="2025-01-14T09:45:00Z",
            ),
            FidelityOrder(
                order_id="DEMO-FID-ORD-003", symbol="GOOGL", side="BUY",
                quantity=80, filled_quantity=80, price=178.0,
                order_type="MARKET", status="FILLED", duration="DAY",
                entered_time="2025-01-13T11:00:00Z",
            ),
        ]

    def _demo_place_order(self, order_request: dict) -> FidelityOrder:
        legs = order_request.get("orderLegCollection", order_request.get("legs", [{}]))
        first_leg = legs[0] if legs else {}
        instrument = first_leg.get("instrument", {})
        symbol = instrument.get("symbol", first_leg.get("symbol", "AAPL"))
        side = first_leg.get("instruction", first_leg.get("side", "BUY"))
        qty = float(first_leg.get("quantity", 10))
        order_type = order_request.get("orderType", "MARKET")

        demo_prices = {
            "SPY": 590.50, "AAPL": 230.75, "GOOGL": 185.40,
            "MSFT": 415.30, "NVDA": 875.20, "AMZN": 202.10,
        }
        price = demo_prices.get(symbol, 100.0)

        return FidelityOrder(
            order_id=f"DEMO-FID-{uuid.uuid4().hex[:8].upper()}",
            symbol=symbol,
            side=side,
            quantity=qty,
            filled_quantity=qty if order_type == "MARKET" else 0,
            price=price,
            order_type=order_type,
            status="FILLED" if order_type == "MARKET" else "QUEUED",
            duration=order_request.get("duration", "DAY"),
        )

    def _demo_quotes(self, symbols: list[str]) -> list[FidelityQuote]:
        demo_data = {
            "SPY": {"last": 590.50, "bid": 590.45, "ask": 590.55, "vol": 78500000, "net": 2.30, "pct": 0.39, "pe": 23.5, "hi52": 610.0, "lo52": 490.0, "o": 588.0, "h": 591.5, "l": 587.5, "dy": 1.30, "mcap": 5.2e11, "desc": "SPDR S&P 500 ETF Trust"},
            "AAPL": {"last": 230.75, "bid": 230.70, "ask": 230.80, "vol": 55200000, "net": 1.85, "pct": 0.81, "pe": 31.2, "hi52": 240.0, "lo52": 170.0, "o": 229.0, "h": 231.5, "l": 228.5, "dy": 0.44, "mcap": 3.56e12, "desc": "Apple Inc."},
            "MSFT": {"last": 415.30, "bid": 415.25, "ask": 415.35, "vol": 22100000, "net": -0.70, "pct": -0.17, "pe": 36.8, "hi52": 435.0, "lo52": 340.0, "o": 416.0, "h": 417.0, "l": 414.0, "dy": 0.72, "mcap": 3.09e12, "desc": "Microsoft Corporation"},
            "NVDA": {"last": 875.20, "bid": 875.10, "ask": 875.30, "vol": 42000000, "net": 12.50, "pct": 1.45, "pe": 65.0, "hi52": 950.0, "lo52": 470.0, "o": 863.0, "h": 878.0, "l": 860.0, "dy": 0.02, "mcap": 2.15e12, "desc": "NVIDIA Corporation"},
            "GOOGL": {"last": 185.40, "bid": 185.35, "ask": 185.45, "vol": 28300000, "net": 0.90, "pct": 0.49, "pe": 25.1, "hi52": 195.0, "lo52": 140.0, "o": 184.5, "h": 186.0, "l": 184.0, "dy": 0.0, "mcap": 2.28e12, "desc": "Alphabet Inc."},
            "AMZN": {"last": 202.10, "bid": 202.05, "ask": 202.15, "vol": 30200000, "net": 2.10, "pct": 1.05, "pe": 62.5, "hi52": 215.0, "lo52": 155.0, "o": 200.0, "h": 203.0, "l": 199.5, "dy": 0.0, "mcap": 2.1e12, "desc": "Amazon.com Inc."},
        }
        result = []
        for s in symbols:
            d = demo_data.get(s, {"last": 100.0, "bid": 99.95, "ask": 100.05, "vol": 1000000, "net": 0.5, "pct": 0.5, "pe": 20.0, "hi52": 120.0, "lo52": 80.0, "o": 99.5, "h": 100.5, "l": 99.0, "dy": 1.5, "mcap": 5.0e10, "desc": s})
            result.append(FidelityQuote(
                symbol=s, last_price=d["last"], bid_price=d["bid"],
                ask_price=d["ask"], total_volume=d["vol"],
                net_change=d["net"], net_percent_change=d["pct"],
                pe_ratio=d["pe"], week_52_high=d["hi52"], week_52_low=d["lo52"],
                open_price=d["o"], high_price=d["h"], low_price=d["l"],
                close_price=d["last"], dividend_yield=d["dy"],
                market_cap=d["mcap"], description=d["desc"],
            ))
        return result

    def _demo_candles(self, symbol: str, count: int = 30) -> list[FidelityCandle]:
        import random
        random.seed(hash(symbol) % 2**31)
        demo_bases = {"SPY": 590.50, "AAPL": 230.75, "MSFT": 415.30, "NVDA": 875.20, "GOOGL": 185.40, "AMZN": 202.10}
        base = demo_bases.get(symbol, 100.0)
        candles = []
        for i in range(count):
            change = random.uniform(-0.02, 0.02)
            o = base * (1 + change)
            c = o * (1 + random.uniform(-0.015, 0.015))
            h = max(o, c) * (1 + random.uniform(0, 0.01))
            lo = min(o, c) * (1 - random.uniform(0, 0.01))
            candles.append(FidelityCandle(
                open=round(o, 2), high=round(h, 2),
                low=round(lo, 2), close=round(c, 2),
                volume=random.randint(10_000_000, 80_000_000),
            ))
            base = c
        return candles

    def _demo_option_chain(self, symbol: str, strike_count: int) -> dict:
        demo_bases = {"SPY": 590.50, "AAPL": 230.75, "MSFT": 415.30, "GOOGL": 185.40}
        base = demo_bases.get(symbol, 100.0)
        calls = {}
        puts = {}
        for i in range(-strike_count // 2, strike_count // 2 + 1):
            strike = round(base + i * 5, 2)
            key = f"{strike:.1f}"
            calls[key] = [{
                "putCall": "CALL", "symbol": f"{symbol}_C{strike}",
                "strike": strike, "bid": max(0.1, round(base - strike + 5, 2)),
                "ask": max(0.15, round(base - strike + 5.5, 2)),
                "last": max(0.12, round(base - strike + 5.25, 2)),
                "delta": round(max(0.05, min(0.95, 0.5 + (base - strike) / 50)), 3),
                "gamma": 0.015, "theta": -0.05, "vega": 0.12,
                "openInterest": 5000 + i * 200,
                "volume": 1200 + i * 50,
            }]
            puts[key] = [{
                "putCall": "PUT", "symbol": f"{symbol}_P{strike}",
                "strike": strike, "bid": max(0.1, round(strike - base + 5, 2)),
                "ask": max(0.15, round(strike - base + 5.5, 2)),
                "last": max(0.12, round(strike - base + 5.25, 2)),
                "delta": round(min(-0.05, max(-0.95, -0.5 + (base - strike) / 50)), 3),
                "gamma": 0.015, "theta": -0.04, "vega": 0.11,
                "openInterest": 4000 + i * 150,
                "volume": 900 + i * 30,
            }]
        return {
            "symbol": symbol,
            "status": "SUCCESS",
            "underlying": {"last": base, "mark": base},
            "callExpDateMap": {"2025-02-21": calls},
            "putExpDateMap": {"2025-02-21": puts},
        }

    def _demo_mutual_funds(self, category: str = "") -> list[FidelityMutualFund]:
        all_funds = [
            FidelityMutualFund(
                symbol="FXAIX", name="Fidelity 500 Index Fund",
                category="Large Blend", nav=196.50, expense_ratio=0.015,
                morningstar_rating=5, ytd_return=12.5, one_year_return=26.3,
                three_year_return=10.1, five_year_return=15.8,
                aum=4.1e11, min_investment=0.0,
            ),
            FidelityMutualFund(
                symbol="FSKAX", name="Fidelity Total Market Index Fund",
                category="Large Blend", nav=148.20, expense_ratio=0.015,
                morningstar_rating=5, ytd_return=11.8, one_year_return=24.9,
                three_year_return=9.6, five_year_return=15.2,
                aum=8.2e10, min_investment=0.0,
            ),
            FidelityMutualFund(
                symbol="FTBFX", name="Fidelity Total Bond Fund",
                category="Intermediate Core Bond", nav=9.85, expense_ratio=0.45,
                morningstar_rating=4, ytd_return=3.2, one_year_return=5.8,
                three_year_return=-1.2, five_year_return=0.9,
                aum=3.1e10, min_investment=0.0,
            ),
            FidelityMutualFund(
                symbol="FCNTX", name="Fidelity Contrafund",
                category="Large Growth", nav=18.92, expense_ratio=0.39,
                morningstar_rating=4, ytd_return=18.7, one_year_return=33.5,
                three_year_return=11.4, five_year_return=17.9,
                aum=1.1e11, min_investment=0.0,
            ),
            FidelityMutualFund(
                symbol="FBALX", name="Fidelity Balanced Fund",
                category="Allocation--50% to 70% Equity", nav=30.15, expense_ratio=0.49,
                morningstar_rating=4, ytd_return=9.4, one_year_return=18.2,
                three_year_return=6.3, five_year_return=10.5,
                aum=3.8e10, min_investment=0.0,
            ),
            FidelityMutualFund(
                symbol="FDGRX", name="Fidelity Growth Company Fund",
                category="Large Growth", nav=22.67, expense_ratio=0.79,
                morningstar_rating=5, ytd_return=22.3, one_year_return=40.1,
                three_year_return=13.2, five_year_return=20.6,
                aum=5.5e10, min_investment=0.0,
            ),
            FidelityMutualFund(
                symbol="FSMEX", name="Fidelity Select Medical Technology",
                category="Health", nav=68.40, expense_ratio=0.68,
                morningstar_rating=3, ytd_return=6.1, one_year_return=10.5,
                three_year_return=2.8, five_year_return=8.3,
                aum=8.9e9, min_investment=0.0,
            ),
            FidelityMutualFund(
                symbol="FSPTX", name="Fidelity Select Technology",
                category="Technology", nav=29.83, expense_ratio=0.68,
                morningstar_rating=4, ytd_return=20.1, one_year_return=38.6,
                three_year_return=12.0, five_year_return=19.4,
                aum=1.2e10, min_investment=0.0,
            ),
        ]
        if category:
            return [f for f in all_funds if category.lower() in f.category.lower()]
        return all_funds
