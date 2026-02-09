"""Schwab REST API Client (PRD-145).

Lightweight HTTP client for Schwab's Trading & Market Data APIs.
Uses schwab-py SDK when available, falls back to OAuth2 HTTP, then demo mode.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, date, timedelta
from enum import Enum
from typing import Any, Optional
import json
import logging
import uuid

logger = logging.getLogger(__name__)

# Try importing schwab-py SDK; fall back to raw HTTP
_HAS_SCHWAB_SDK = False
try:
    import schwab as schwab_sdk
    _HAS_SCHWAB_SDK = True
except ImportError:
    schwab_sdk = None  # type: ignore

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
class SchwabConfig:
    """Configuration for Schwab API connection."""
    app_key: str = ""
    app_secret: str = ""
    callback_url: str = "https://127.0.0.1:8182/callback"
    token_path: str = ".schwab_token.json"
    base_url: str = "https://api.schwabapi.com"
    # Rate limiting
    max_requests_per_minute: int = 120
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
        return "https://api.schwabapi.com/v1/oauth/authorize"

    @property
    def token_url(self) -> str:
        return "https://api.schwabapi.com/v1/oauth/token"


# =====================================================================
# Response Models
# =====================================================================


@dataclass
class SchwabAccount:
    """Schwab account information."""
    account_number: str = ""
    account_type: str = "INDIVIDUAL"
    is_day_trader: bool = False
    round_trips: int = 0
    cash: float = 0.0
    equity: float = 0.0
    long_market_value: float = 0.0
    short_market_value: float = 0.0
    buying_power: float = 0.0
    maintenance_requirement: float = 0.0
    available_funds: float = 0.0
    position_count: int = 0

    @classmethod
    def from_api(cls, data: dict) -> "SchwabAccount":
        acct = data.get("securitiesAccount", data)
        balances = acct.get("currentBalances", acct.get("initialBalances", {}))
        positions = acct.get("positions", [])
        return cls(
            account_number=str(acct.get("accountNumber", acct.get("accountId", ""))),
            account_type=acct.get("type", "INDIVIDUAL"),
            is_day_trader=acct.get("isDayTrader", False),
            round_trips=int(acct.get("roundTrips", 0)),
            cash=float(balances.get("cashBalance", balances.get("cashAvailableForTrading", 0))),
            equity=float(balances.get("equity", balances.get("liquidationValue", 0))),
            long_market_value=float(balances.get("longMarketValue", 0)),
            short_market_value=float(balances.get("shortMarketValue", 0)),
            buying_power=float(balances.get("buyingPower", 0)),
            maintenance_requirement=float(balances.get("maintenanceRequirement", 0)),
            available_funds=float(balances.get("availableFunds", balances.get("cashAvailableForTrading", 0))),
            position_count=len(positions),
        )


@dataclass
class SchwabPosition:
    """Schwab position."""
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
    def from_api(cls, data: dict) -> "SchwabPosition":
        instrument = data.get("instrument", {})
        return cls(
            symbol=instrument.get("symbol", data.get("symbol", "")),
            asset_type=instrument.get("assetType", "EQUITY"),
            quantity=float(data.get("longQuantity", data.get("quantity", 0))),
            average_price=float(data.get("averagePrice", 0)),
            current_price=float(data.get("currentDayProfitLossPercentage", 0)),
            market_value=float(data.get("marketValue", 0)),
            unrealized_pnl=float(data.get("currentDayProfitLoss", data.get("unrealizedPnl", 0))),
            unrealized_pnl_pct=float(data.get("currentDayProfitLossPercentage", 0)),
            day_pnl=float(data.get("currentDayProfitLoss", 0)),
            cost_basis=float(data.get("averagePrice", 0)) * float(data.get("longQuantity", data.get("quantity", 0))),
            long_short="Long" if float(data.get("longQuantity", 0)) > 0 else "Short",
        )


@dataclass
class SchwabOrder:
    """Schwab order."""
    order_id: str = ""
    symbol: str = ""
    instruction: str = "BUY"
    quantity: float = 0.0
    filled_quantity: float = 0.0
    price: float = 0.0
    order_type: str = "MARKET"
    status: str = "QUEUED"
    duration: str = "DAY"
    entered_time: str = ""
    close_time: str = ""
    complex_order_strategy: str = "NONE"
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None

    @classmethod
    def from_api(cls, data: dict) -> "SchwabOrder":
        legs = data.get("orderLegCollection", [{}])
        first_leg = legs[0] if legs else {}
        instrument = first_leg.get("instrument", {})
        return cls(
            order_id=str(data.get("orderId", "")),
            symbol=instrument.get("symbol", ""),
            instruction=first_leg.get("instruction", "BUY"),
            quantity=float(first_leg.get("quantity", data.get("quantity", 0))),
            filled_quantity=float(data.get("filledQuantity", 0)),
            price=float(data.get("price", data.get("stopPrice", 0))),
            order_type=data.get("orderType", "MARKET"),
            status=data.get("status", "QUEUED"),
            duration=data.get("duration", "DAY"),
            entered_time=data.get("enteredTime", ""),
            close_time=data.get("closeTime", ""),
            complex_order_strategy=data.get("complexOrderStrategyType", "NONE"),
            stop_price=float(data["stopPrice"]) if data.get("stopPrice") else None,
            limit_price=float(data["price"]) if data.get("price") and data.get("orderType") == "LIMIT" else None,
        )


@dataclass
class SchwabQuote:
    """Real-time quote from Schwab."""
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

    @classmethod
    def from_api(cls, data: dict, symbol: str = "") -> "SchwabQuote":
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
            description=ref.get("description", ""),
            pe_ratio=float(quote.get("peRatio", 0)),
            week_52_high=float(quote.get("52WkHigh", quote.get("fiftyTwoWeekHigh", 0))),
            week_52_low=float(quote.get("52WkLow", quote.get("fiftyTwoWeekLow", 0))),
        )


@dataclass
class SchwabCandle:
    """OHLCV candle from Schwab price history."""
    timestamp: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0

    @classmethod
    def from_api(cls, data: dict) -> "SchwabCandle":
        return cls(
            timestamp=str(data.get("datetime", "")),
            open=float(data.get("open", 0)),
            high=float(data.get("high", 0)),
            low=float(data.get("low", 0)),
            close=float(data.get("close", 0)),
            volume=int(data.get("volume", 0)),
        )


@dataclass
class SchwabMover:
    """Market mover from Schwab."""
    symbol: str = ""
    description: str = ""
    direction: str = "up"
    change: float = 0.0
    percent_change: float = 0.0
    volume: int = 0
    last_price: float = 0.0

    @classmethod
    def from_api(cls, data: dict) -> "SchwabMover":
        return cls(
            symbol=data.get("symbol", ""),
            description=data.get("description", ""),
            direction=data.get("direction", "up"),
            change=float(data.get("change", data.get("netChange", 0))),
            percent_change=float(data.get("percentChange", data.get("netPercentChange", 0))),
            volume=int(data.get("totalVolume", data.get("volume", 0))),
            last_price=float(data.get("lastPrice", data.get("last", 0))),
        )


# =====================================================================
# OAuth2 Token Management
# =====================================================================


class _TokenManager:
    """Handles OAuth2 token persistence and refresh for Schwab API."""

    def __init__(self, config: SchwabConfig):
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
                        "client_id": self._config.app_key,
                        "client_secret": self._config.app_secret,
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


class SchwabClient:
    """Schwab REST API client.

    Supports schwab-py SDK, raw HTTP with OAuth2, and demo mode fallback.

    Example:
        client = SchwabClient(SchwabConfig(app_key="...", app_secret="..."))
        await client.connect()
        accounts = await client.get_accounts()
    """

    def __init__(self, config: SchwabConfig):
        self._config = config
        self._connected = False
        self._http_client: Any = None
        self._sdk_client: Any = None
        self._mode: str = "demo"  # "sdk", "http", or "demo"
        self._token_mgr = _TokenManager(config)
        self._request_count = 0

    @property
    def config(self) -> SchwabConfig:
        return self._config

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def mode(self) -> str:
        return self._mode

    async def connect(self) -> bool:
        """Connect to Schwab API.

        Tries SDK first, then raw HTTP with OAuth2, falls back to demo mode.
        """
        if not self._config.app_key or not self._config.app_secret:
            logger.info("No Schwab credentials -- using demo mode")
            self._mode = "demo"
            self._connected = True
            return True

        # Try schwab-py SDK
        if _HAS_SCHWAB_SDK:
            try:
                self._sdk_client = schwab_sdk.auth.client_from_token_file(
                    self._config.token_path,
                    self._config.app_key,
                    self._config.app_secret,
                    self._config.callback_url,
                )
                self._mode = "sdk"
                self._connected = True
                logger.info("Connected to Schwab via SDK")
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
                        "client_id": self._config.app_key,
                        "client_secret": self._config.app_secret,
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
                    logger.info("Connected to Schwab via HTTP/OAuth2")
                    return True
                else:
                    logger.warning(f"OAuth2 auth failed: {resp.status_code}")
            except Exception as e:
                logger.warning(f"HTTP connection failed: {e}")

        # Fallback to demo
        self._mode = "demo"
        self._connected = True
        logger.info("Using Schwab demo mode (no live API)")
        return True

    async def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        if self._http_client and hasattr(self._http_client, "aclose"):
            await self._http_client.aclose()
        self._http_client = None
        self._sdk_client = None
        self._connected = False
        self._mode = "demo"
        logger.info("Disconnected from Schwab")

    async def _ensure_token(self) -> None:
        """Refresh token if expired (HTTP mode)."""
        if self._mode == "http" and self._token_mgr.is_expired:
            await self._token_mgr.refresh()

    # -- Accounts ----------------------------------------------------------

    async def get_accounts(self) -> list[SchwabAccount]:
        """Get all linked accounts."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.get(
                f"{self._config.trader_url}/accounts",
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            return [SchwabAccount.from_api(a) for a in resp.json()]

        return self._demo_accounts()

    async def get_positions(self, account_id: str) -> list[SchwabPosition]:
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
            acct = data.get("securitiesAccount", data)
            positions = acct.get("positions", [])
            return [SchwabPosition.from_api(p) for p in positions]

        return self._demo_positions()

    async def get_orders(self, account_id: str, status: str = "FILLED") -> list[SchwabOrder]:
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
            return [SchwabOrder.from_api(o) for o in resp.json()]

        return self._demo_orders()

    async def place_order(self, account_id: str, order_request: dict) -> SchwabOrder:
        """Submit an order."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.post(
                f"{self._config.trader_url}/accounts/{account_id}/orders",
                json=order_request,
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            # Schwab returns location header; we build a synthetic order
            return SchwabOrder(
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

    async def get_quote(self, symbols: list[str]) -> list[SchwabQuote]:
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
            return [SchwabQuote.from_api(data[s], symbol=s) for s in symbols if s in data]

        return self._demo_quotes(symbols)

    async def get_price_history(
        self,
        symbol: str,
        period_type: str = "month",
        period: int = 1,
        frequency_type: str = "daily",
        frequency: int = 1,
    ) -> list[SchwabCandle]:
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
            return [SchwabCandle.from_api(c) for c in candles]

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

    async def get_movers(self, index: str = "$SPX") -> list[SchwabMover]:
        """Get market movers for an index."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.get(
                f"{self._config.marketdata_url}/movers/{index}",
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            screeners = resp.json().get("screeners", resp.json())
            if isinstance(screeners, list):
                return [SchwabMover.from_api(m) for m in screeners]
            return []

        return self._demo_movers(index)

    # -- Demo Data ---------------------------------------------------------

    def _demo_accounts(self) -> list[SchwabAccount]:
        return [
            SchwabAccount(
                account_number="DEMO-12345678",
                account_type="INDIVIDUAL",
                cash=65000.0,
                equity=142500.0,
                long_market_value=77500.0,
                buying_power=130000.0,
                available_funds=65000.0,
                position_count=3,
            ),
        ]

    def _demo_positions(self) -> list[SchwabPosition]:
        return [
            SchwabPosition(
                symbol="SPY", asset_type="EQUITY", quantity=50,
                average_price=575.00, current_price=590.50,
                market_value=29525.0, unrealized_pnl=775.0,
                unrealized_pnl_pct=2.70, cost_basis=28750.0, long_short="Long",
            ),
            SchwabPosition(
                symbol="AAPL", asset_type="EQUITY", quantity=100,
                average_price=218.00, current_price=230.75,
                market_value=23075.0, unrealized_pnl=1275.0,
                unrealized_pnl_pct=5.85, cost_basis=21800.0, long_short="Long",
            ),
            SchwabPosition(
                symbol="MSFT", asset_type="EQUITY", quantity=60,
                average_price=405.00, current_price=415.30,
                market_value=24918.0, unrealized_pnl=618.0,
                unrealized_pnl_pct=2.54, cost_basis=24300.0, long_short="Long",
            ),
        ]

    def _demo_orders(self) -> list[SchwabOrder]:
        return [
            SchwabOrder(
                order_id="DEMO-ORD-001", symbol="AAPL", instruction="BUY",
                quantity=100, filled_quantity=100, price=218.0,
                order_type="MARKET", status="FILLED", duration="DAY",
                entered_time="2025-01-15T10:30:00Z",
            ),
            SchwabOrder(
                order_id="DEMO-ORD-002", symbol="SPY", instruction="BUY",
                quantity=50, filled_quantity=50, price=575.0,
                order_type="LIMIT", status="FILLED", duration="DAY",
                limit_price=575.0,
                entered_time="2025-01-14T09:45:00Z",
            ),
            SchwabOrder(
                order_id="DEMO-ORD-003", symbol="MSFT", instruction="BUY",
                quantity=60, filled_quantity=60, price=405.0,
                order_type="MARKET", status="FILLED", duration="DAY",
                entered_time="2025-01-13T11:00:00Z",
            ),
        ]

    def _demo_place_order(self, order_request: dict) -> SchwabOrder:
        legs = order_request.get("orderLegCollection", [{}])
        first_leg = legs[0] if legs else {}
        instrument = first_leg.get("instrument", {})
        symbol = instrument.get("symbol", "AAPL")
        instruction = first_leg.get("instruction", "BUY")
        qty = float(first_leg.get("quantity", 10))
        order_type = order_request.get("orderType", "MARKET")

        demo_prices = {"SPY": 590.50, "AAPL": 230.75, "MSFT": 415.30, "NVDA": 875.20, "GOOGL": 185.40}
        price = demo_prices.get(symbol, 100.0)

        return SchwabOrder(
            order_id=f"DEMO-{uuid.uuid4().hex[:8].upper()}",
            symbol=symbol,
            instruction=instruction,
            quantity=qty,
            filled_quantity=qty if order_type == "MARKET" else 0,
            price=price,
            order_type=order_type,
            status="FILLED" if order_type == "MARKET" else "QUEUED",
            duration=order_request.get("duration", "DAY"),
        )

    def _demo_quotes(self, symbols: list[str]) -> list[SchwabQuote]:
        demo_data = {
            "SPY": {"last": 590.50, "bid": 590.45, "ask": 590.55, "vol": 78500000, "net": 2.30, "pct": 0.39, "pe": 23.5, "hi52": 610.0, "lo52": 490.0, "o": 588.0, "h": 591.5, "l": 587.5},
            "AAPL": {"last": 230.75, "bid": 230.70, "ask": 230.80, "vol": 55200000, "net": 1.85, "pct": 0.81, "pe": 31.2, "hi52": 240.0, "lo52": 170.0, "o": 229.0, "h": 231.5, "l": 228.5},
            "MSFT": {"last": 415.30, "bid": 415.25, "ask": 415.35, "vol": 22100000, "net": -0.70, "pct": -0.17, "pe": 36.8, "hi52": 435.0, "lo52": 340.0, "o": 416.0, "h": 417.0, "l": 414.0},
            "NVDA": {"last": 875.20, "bid": 875.10, "ask": 875.30, "vol": 42000000, "net": 12.50, "pct": 1.45, "pe": 65.0, "hi52": 950.0, "lo52": 470.0, "o": 863.0, "h": 878.0, "l": 860.0},
            "GOOGL": {"last": 185.40, "bid": 185.35, "ask": 185.45, "vol": 28300000, "net": 0.90, "pct": 0.49, "pe": 25.1, "hi52": 195.0, "lo52": 140.0, "o": 184.5, "h": 186.0, "l": 184.0},
        }
        result = []
        for s in symbols:
            d = demo_data.get(s, {"last": 100.0, "bid": 99.95, "ask": 100.05, "vol": 1000000, "net": 0.5, "pct": 0.5, "pe": 20.0, "hi52": 120.0, "lo52": 80.0, "o": 99.5, "h": 100.5, "l": 99.0})
            result.append(SchwabQuote(
                symbol=s, last_price=d["last"], bid_price=d["bid"],
                ask_price=d["ask"], total_volume=d["vol"],
                net_change=d["net"], net_percent_change=d["pct"],
                pe_ratio=d["pe"], week_52_high=d["hi52"], week_52_low=d["lo52"],
                open_price=d["o"], high_price=d["h"], low_price=d["l"],
                close_price=d["last"],
            ))
        return result

    def _demo_candles(self, symbol: str, count: int = 30) -> list[SchwabCandle]:
        import random
        random.seed(hash(symbol) % 2**31)
        demo_bases = {"SPY": 590.50, "AAPL": 230.75, "MSFT": 415.30, "NVDA": 875.20, "GOOGL": 185.40}
        base = demo_bases.get(symbol, 100.0)
        candles = []
        for i in range(count):
            change = random.uniform(-0.02, 0.02)
            o = base * (1 + change)
            c = o * (1 + random.uniform(-0.015, 0.015))
            h = max(o, c) * (1 + random.uniform(0, 0.01))
            lo = min(o, c) * (1 - random.uniform(0, 0.01))
            candles.append(SchwabCandle(
                open=round(o, 2), high=round(h, 2),
                low=round(lo, 2), close=round(c, 2),
                volume=random.randint(10_000_000, 80_000_000),
            ))
            base = c
        return candles

    def _demo_option_chain(self, symbol: str, strike_count: int) -> dict:
        demo_bases = {"SPY": 590.50, "AAPL": 230.75, "MSFT": 415.30}
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

    def _demo_movers(self, index: str) -> list[SchwabMover]:
        movers = {
            "$SPX": [
                SchwabMover(symbol="NVDA", description="NVIDIA Corp", direction="up", change=12.50, percent_change=1.45, volume=42000000, last_price=875.20),
                SchwabMover(symbol="AAPL", description="Apple Inc", direction="up", change=1.85, percent_change=0.81, volume=55200000, last_price=230.75),
                SchwabMover(symbol="TSLA", description="Tesla Inc", direction="down", change=-8.20, percent_change=-2.10, volume=38000000, last_price=382.50),
                SchwabMover(symbol="META", description="Meta Platforms", direction="up", change=5.40, percent_change=0.94, volume=18500000, last_price=580.30),
                SchwabMover(symbol="AMZN", description="Amazon.com", direction="up", change=2.10, percent_change=1.05, volume=30200000, last_price=202.10),
            ],
            "$DJI": [
                SchwabMover(symbol="UNH", description="UnitedHealth Group", direction="up", change=8.30, percent_change=1.52, volume=4500000, last_price=555.80),
                SchwabMover(symbol="GS", description="Goldman Sachs", direction="up", change=5.60, percent_change=1.18, volume=3200000, last_price=480.90),
                SchwabMover(symbol="BA", description="Boeing Co", direction="down", change=-4.20, percent_change=-1.85, volume=8100000, last_price=222.30),
            ],
            "$COMPX": [
                SchwabMover(symbol="NVDA", description="NVIDIA Corp", direction="up", change=12.50, percent_change=1.45, volume=42000000, last_price=875.20),
                SchwabMover(symbol="SMCI", description="Super Micro Computer", direction="up", change=28.00, percent_change=3.20, volume=12000000, last_price=903.50),
                SchwabMover(symbol="ARM", description="Arm Holdings", direction="up", change=6.80, percent_change=4.10, volume=9500000, last_price=172.50),
            ],
        }
        return movers.get(index, movers["$SPX"])
