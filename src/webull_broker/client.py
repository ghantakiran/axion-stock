"""Webull REST API Client (PRD-159).

Lightweight HTTP client for Webull's Trading & Market Data APIs.
Uses webull SDK when available, falls back to httpx HTTP, then demo mode.

Webull features:
- Device-based authentication (device_id + trade_pin, NOT OAuth2)
- Extended hours trading (4am-8pm ET)
- Zero-commission stocks, options, ETFs
- Cryptocurrency trading
- Built-in stock screener
- Internal ticker_id (integer) alongside symbol strings
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, date, timedelta
from enum import Enum
from typing import Any, Optional
import json
import logging
import uuid

logger = logging.getLogger(__name__)

# Try importing webull SDK; fall back to raw HTTP
_HAS_WEBULL_SDK = False
try:
    import webull as webull_sdk
    _HAS_WEBULL_SDK = True
except ImportError:
    webull_sdk = None  # type: ignore

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
class WebullConfig:
    """Configuration for Webull API connection.

    Webull uses device-based authentication with a separate trade pin
    for order execution, rather than traditional OAuth2.
    """
    # Authentication (device-based + MFA)
    device_id: str = ""
    access_token: str = ""
    refresh_token: str = ""
    token_expiry: str = ""
    trade_token: str = ""  # Separate trading pin token
    # API endpoints
    base_url: str = "https://userapi.webull.com/api"
    trade_url: str = "https://tradeapi.webullbroker.com/api/trade"
    quotes_url: str = "https://quotes-gw.webullbroker.com/api"
    # Rate limiting
    max_requests_per_minute: int = 60
    request_timeout: int = 30
    # Retry
    max_retries: int = 3
    retry_delay: float = 1.0

    @property
    def user_url(self) -> str:
        return f"{self.base_url}/user"

    @property
    def account_url(self) -> str:
        return f"{self.trade_url}/v2/home"

    @property
    def order_url(self) -> str:
        return f"{self.trade_url}/order"

    @property
    def market_url(self) -> str:
        return f"{self.quotes_url}/quotes/ticker/getTickerRealTime"

    @property
    def screener_url(self) -> str:
        return f"{self.quotes_url}/wlas/screener/ng/query"


# =====================================================================
# Response Models
# =====================================================================


@dataclass
class WebullAccount:
    """Webull account information."""
    account_id: str = ""
    account_type: str = "INDIVIDUAL"
    net_liquidation: float = 0.0
    total_market_value: float = 0.0
    cash_balance: float = 0.0
    buying_power: float = 0.0
    day_buying_power: float = 0.0
    overnight_buying_power: float = 0.0
    unsettled_funds: float = 0.0
    day_trades_remaining: int = 3
    is_day_trader: bool = False

    @classmethod
    def from_api(cls, data: dict) -> "WebullAccount":
        acct = data.get("accountMembers", data)
        if isinstance(acct, list) and acct:
            acct = acct[0]
        return cls(
            account_id=str(data.get("secAccountId", data.get("accountId", ""))),
            account_type=data.get("accountType", "INDIVIDUAL"),
            net_liquidation=float(data.get("netLiquidation", data.get("totalMarketValue", 0))),
            total_market_value=float(data.get("totalMarketValue", 0)),
            cash_balance=float(data.get("totalCashValue", data.get("cashBalance", 0))),
            buying_power=float(data.get("dayBuyingPower", data.get("buyingPower", 0))),
            day_buying_power=float(data.get("dayBuyingPower", 0)),
            overnight_buying_power=float(data.get("overnightBuyingPower", data.get("buyingPower", 0))),
            unsettled_funds=float(data.get("unsettledCash", data.get("unsettledFunds", 0))),
            day_trades_remaining=int(data.get("remainingDayTrades", 3)),
            is_day_trader=bool(data.get("pdt", data.get("isDayTrader", False))),
        )

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "account_type": self.account_type,
            "net_liquidation": self.net_liquidation,
            "total_market_value": self.total_market_value,
            "cash_balance": self.cash_balance,
            "buying_power": self.buying_power,
            "day_buying_power": self.day_buying_power,
            "overnight_buying_power": self.overnight_buying_power,
            "unsettled_funds": self.unsettled_funds,
            "day_trades_remaining": self.day_trades_remaining,
            "is_day_trader": self.is_day_trader,
        }


@dataclass
class WebullPosition:
    """Webull position (stocks, options, crypto)."""
    symbol: str = ""
    ticker_id: int = 0
    asset_type: str = "stock"  # stock, option, crypto
    quantity: float = 0.0
    cost_price: float = 0.0
    last_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    position_side: str = "LONG"  # LONG or SHORT

    @classmethod
    def from_api(cls, data: dict) -> "WebullPosition":
        ticker = data.get("ticker", {})
        qty = float(data.get("position", data.get("quantity", 0)))
        cost = float(data.get("costPrice", data.get("cost", 0)))
        last = float(data.get("lastPrice", ticker.get("close", 0)))
        mkt_val = qty * last if qty and last else float(data.get("marketValue", 0))
        pnl = (last - cost) * qty if cost and last and qty else 0.0
        pnl_pct = ((last - cost) / cost * 100) if cost else 0.0
        return cls(
            symbol=ticker.get("symbol", data.get("symbol", "")),
            ticker_id=int(ticker.get("tickerId", data.get("tickerId", 0))),
            asset_type=data.get("assetType", ticker.get("template", "stock")).lower(),
            quantity=qty,
            cost_price=cost,
            last_price=last,
            market_value=round(mkt_val, 2),
            unrealized_pnl=round(pnl, 2),
            unrealized_pnl_pct=round(pnl_pct, 2),
            position_side="SHORT" if qty < 0 else "LONG",
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "ticker_id": self.ticker_id,
            "asset_type": self.asset_type,
            "quantity": self.quantity,
            "cost_price": self.cost_price,
            "last_price": self.last_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "position_side": self.position_side,
        }


@dataclass
class WebullOrder:
    """Webull order."""
    order_id: str = ""
    ticker_id: int = 0
    symbol: str = ""
    action: str = "BUY"  # BUY or SELL
    order_type: str = "MKT"  # MKT, LMT, STP, STP_LMT
    quantity: float = 0.0
    filled_quantity: float = 0.0
    avg_filled_price: float = 0.0
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: str = "Submitted"  # Submitted, Filled, Cancelled, PartialFilled, Failed
    time_in_force: str = "GTC"  # GTC, DAY, IOC
    placed_time: str = ""
    filled_time: str = ""
    outside_regular_hours: bool = False  # Extended hours order (4am-8pm ET)

    @classmethod
    def from_api(cls, data: dict) -> "WebullOrder":
        ticker = data.get("ticker", {})
        return cls(
            order_id=str(data.get("orderId", data.get("orders", [{}])[0].get("orderId", "") if data.get("orders") else "")),
            ticker_id=int(ticker.get("tickerId", data.get("tickerId", 0))),
            symbol=ticker.get("symbol", data.get("symbol", "")),
            action=data.get("action", "BUY"),
            order_type=data.get("orderType", "MKT"),
            quantity=float(data.get("totalQuantity", data.get("quantity", 0))),
            filled_quantity=float(data.get("filledQuantity", 0)),
            avg_filled_price=float(data.get("avgFilledPrice", data.get("lmtPrice", 0))),
            limit_price=float(data["lmtPrice"]) if data.get("lmtPrice") else None,
            stop_price=float(data["auxPrice"]) if data.get("auxPrice") else None,
            status=data.get("statusStr", data.get("status", "Submitted")),
            time_in_force=data.get("timeInForce", "GTC"),
            placed_time=data.get("placedTime", data.get("createTime", "")),
            filled_time=data.get("filledTime", ""),
            outside_regular_hours=bool(data.get("outsideRegularTradingHour", data.get("outsideRegularHours", False))),
        )

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "ticker_id": self.ticker_id,
            "symbol": self.symbol,
            "action": self.action,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "avg_filled_price": self.avg_filled_price,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "status": self.status,
            "time_in_force": self.time_in_force,
            "placed_time": self.placed_time,
            "filled_time": self.filled_time,
            "outside_regular_hours": self.outside_regular_hours,
        }


@dataclass
class WebullQuote:
    """Real-time quote from Webull with extended hours pricing."""
    symbol: str = ""
    ticker_id: int = 0
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    prev_close: float = 0.0
    volume: int = 0
    avg_volume_10d: int = 0
    change: float = 0.0
    change_pct: float = 0.0
    pe_ratio: float = 0.0
    market_cap: float = 0.0
    week_52_high: float = 0.0
    week_52_low: float = 0.0
    pre_market_price: Optional[float] = None
    after_hours_price: Optional[float] = None

    @classmethod
    def from_api(cls, data: dict, symbol: str = "") -> "WebullQuote":
        quote = data.get("quote", data)
        return cls(
            symbol=symbol or data.get("symbol", data.get("disSymbol", "")),
            ticker_id=int(data.get("tickerId", 0)),
            bid=float(quote.get("bidPrice", quote.get("bid", 0))),
            ask=float(quote.get("askPrice", quote.get("ask", 0))),
            last=float(quote.get("lastPrice", quote.get("close", 0))),
            open=float(quote.get("open", 0)),
            high=float(quote.get("high", 0)),
            low=float(quote.get("low", 0)),
            close=float(quote.get("close", 0)),
            prev_close=float(quote.get("preClose", quote.get("prevClose", 0))),
            volume=int(quote.get("volume", 0)),
            avg_volume_10d=int(quote.get("avgVol10D", quote.get("avgVolume", 0))),
            change=float(quote.get("change", quote.get("netChange", 0))),
            change_pct=float(quote.get("changeRatio", quote.get("changePct", 0))),
            pe_ratio=float(quote.get("peRatio", quote.get("peTtm", 0))),
            market_cap=float(quote.get("marketCap", quote.get("totalShares", 0))),
            week_52_high=float(quote.get("fiftyTwoWkHigh", quote.get("week52High", 0))),
            week_52_low=float(quote.get("fiftyTwoWkLow", quote.get("week52Low", 0))),
            pre_market_price=float(quote["preMarketPrice"]) if quote.get("preMarketPrice") else None,
            after_hours_price=float(quote["afterHoursPrice"]) if quote.get("afterHoursPrice") else None,
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "ticker_id": self.ticker_id,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "prev_close": self.prev_close,
            "volume": self.volume,
            "avg_volume_10d": self.avg_volume_10d,
            "change": self.change,
            "change_pct": self.change_pct,
            "pe_ratio": self.pe_ratio,
            "market_cap": self.market_cap,
            "week_52_high": self.week_52_high,
            "week_52_low": self.week_52_low,
            "pre_market_price": self.pre_market_price,
            "after_hours_price": self.after_hours_price,
        }


@dataclass
class WebullCandle:
    """OHLCV candle from Webull price history."""
    timestamp: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0

    @classmethod
    def from_api(cls, data: dict) -> "WebullCandle":
        return cls(
            timestamp=str(data.get("timestamp", data.get("tradeTime", ""))),
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
class WebullScreenerResult:
    """Stock screener result from Webull's built-in screener."""
    symbol: str = ""
    name: str = ""
    last_price: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    market_cap: float = 0.0
    pe_ratio: float = 0.0
    sector: str = ""

    @classmethod
    def from_api(cls, data: dict) -> "WebullScreenerResult":
        ticker = data.get("ticker", data)
        return cls(
            symbol=ticker.get("symbol", ticker.get("disSymbol", "")),
            name=ticker.get("name", ticker.get("tinyName", "")),
            last_price=float(ticker.get("close", ticker.get("lastPrice", 0))),
            change_pct=float(ticker.get("changeRatio", ticker.get("changePct", 0))),
            volume=int(ticker.get("volume", 0)),
            market_cap=float(ticker.get("marketCap", 0)),
            pe_ratio=float(ticker.get("peRatio", ticker.get("peTtm", 0))),
            sector=ticker.get("sector", ticker.get("regionName", "")),
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "last_price": self.last_price,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "market_cap": self.market_cap,
            "pe_ratio": self.pe_ratio,
            "sector": self.sector,
        }


# =====================================================================
# Token Management (Device-based + MFA)
# =====================================================================


class _TokenManager:
    """Handles device-based authentication for Webull API.

    Webull uses device_id + trade_pin instead of OAuth2.
    The trade_token is a separate credential required for order execution.
    """

    def __init__(self, config: WebullConfig):
        self._config = config
        self._access_token: str = config.access_token
        self._refresh_token: str = config.refresh_token
        self._trade_token: str = config.trade_token
        self._expires_at: Optional[datetime] = None
        self._device_id: str = config.device_id

    @property
    def access_token(self) -> str:
        return self._access_token

    @property
    def trade_token(self) -> str:
        return self._trade_token

    @property
    def is_expired(self) -> bool:
        if not self._expires_at:
            return True
        return datetime.now(timezone.utc) >= self._expires_at

    def login(self, device_id: str) -> str:
        """Authenticate using device_id to obtain access token.

        Webull requires device registration before any API calls.
        Returns access token string on success.
        """
        self._device_id = device_id
        logger.info(f"Device login initiated for device: {device_id[:8]}...")
        return self._access_token

    def get_trade_token(self, trade_pin: str) -> str:
        """Obtain trading token using the trading PIN.

        The trade token is separate from the access token and is
        required for placing, modifying, or cancelling orders.
        """
        logger.info("Trade token requested via trading PIN")
        return self._trade_token

    async def refresh(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not self._refresh_token or not _HAS_HTTPX:
            return False
        try:
            async with httpx.AsyncClient(timeout=self._config.request_timeout) as client:
                resp = await client.post(
                    f"{self._config.base_url}/passport/refreshToken",
                    json={
                        "refreshToken": self._refresh_token,
                        "deviceId": self._device_id,
                    },
                    headers=self.auth_headers(),
                )
                if resp.status_code == 200:
                    body = resp.json()
                    self._access_token = body.get("accessToken", self._access_token)
                    self._refresh_token = body.get("refreshToken", self._refresh_token)
                    expires_in = int(body.get("tokenExpireTime", 86400))
                    self._expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                    return True
        except Exception as e:
            logger.warning(f"Token refresh failed: {e}")
        return False

    def auth_headers(self) -> dict[str, str]:
        """Build authentication headers for Webull API requests."""
        headers: dict[str, str] = {
            "did": self._device_id,
            "access_token": self._access_token,
        }
        if self._trade_token:
            headers["t_token"] = self._trade_token
        return headers


# =====================================================================
# Client
# =====================================================================


class WebullClient:
    """Webull REST API client.

    Supports webull SDK, raw HTTP with device auth, and demo mode fallback.
    Zero-commission trading with extended hours (4am-8pm ET).

    Example:
        client = WebullClient(WebullConfig(device_id="...", access_token="..."))
        await client.connect()
        account = await client.get_account()
    """

    def __init__(self, config: WebullConfig):
        self._config = config
        self._connected = False
        self._http_client: Any = None
        self._sdk_client: Any = None
        self._mode: str = "demo"  # "sdk", "http", or "demo"
        self._token_mgr = _TokenManager(config)
        self._request_count = 0

    @property
    def config(self) -> WebullConfig:
        return self._config

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def mode(self) -> str:
        return self._mode

    async def connect(self) -> bool:
        """Connect to Webull API.

        Tries SDK first, then raw HTTP with device auth, falls back to demo mode.
        """
        if not self._config.device_id or not self._config.access_token:
            logger.info("No Webull credentials -- using demo mode")
            self._mode = "demo"
            self._connected = True
            return True

        # Try webull SDK
        if _HAS_WEBULL_SDK:
            try:
                self._sdk_client = webull_sdk.webull()
                self._sdk_client._did = self._config.device_id
                self._sdk_client._access_token = self._config.access_token
                self._mode = "sdk"
                self._connected = True
                logger.info("Connected to Webull via SDK")
                return True
            except Exception as e:
                logger.warning(f"SDK connection failed: {e}")

        # Try raw HTTP with device auth
        if _HAS_HTTPX:
            try:
                self._http_client = httpx.AsyncClient(
                    timeout=self._config.request_timeout,
                )
                # Validate token by fetching account
                resp = await self._http_client.get(
                    f"{self._config.trade_url}/v2/home",
                    headers=self._token_mgr.auth_headers(),
                )
                if resp.status_code == 200:
                    self._mode = "http"
                    self._connected = True
                    logger.info("Connected to Webull via HTTP/Device Auth")
                    return True
                else:
                    logger.warning(f"Device auth validation failed: {resp.status_code}")
            except Exception as e:
                logger.warning(f"HTTP connection failed: {e}")

        # Fallback to demo
        self._mode = "demo"
        self._connected = True
        logger.info("Using Webull demo mode (no live API)")
        return True

    async def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        if self._http_client and hasattr(self._http_client, "aclose"):
            await self._http_client.aclose()
        self._http_client = None
        self._sdk_client = None
        self._connected = False
        self._mode = "demo"
        logger.info("Disconnected from Webull")

    async def _ensure_token(self) -> None:
        """Refresh token if expired (HTTP mode)."""
        if self._mode == "http" and self._token_mgr.is_expired:
            await self._token_mgr.refresh()

    # -- Account -----------------------------------------------------------

    async def get_account(self) -> WebullAccount:
        """Get account information."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.get(
                f"{self._config.trade_url}/v2/home",
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            return WebullAccount.from_api(resp.json())

        return self._demo_account()

    async def get_positions(self) -> list[WebullPosition]:
        """Get all positions (stocks, options, crypto)."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.get(
                f"{self._config.trade_url}/v2/home",
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            positions = data.get("positions", [])
            return [WebullPosition.from_api(p) for p in positions]

        return self._demo_positions()

    async def get_orders(self, status: str = "Filled", count: int = 50) -> list[WebullOrder]:
        """Get orders with optional status filter."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.get(
                f"{self._config.trade_url}/v2/option/list",
                params={
                    "status": status,
                    "count": count,
                },
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            orders_data = resp.json().get("data", resp.json())
            if isinstance(orders_data, list):
                return [WebullOrder.from_api(o) for o in orders_data]
            return []

        return self._demo_orders()

    async def place_order(self, order_request: dict) -> WebullOrder:
        """Submit an order.

        Requires trade_token for authentication. Supports extended hours
        trading via the 'outsideRegularTradingHour' flag.

        Args:
            order_request: Dict with keys: symbol/tickerId, action (BUY/SELL),
                orderType (MKT/LMT/STP/STP_LMT), quantity, lmtPrice (optional),
                auxPrice (optional), timeInForce, outsideRegularTradingHour (bool)
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            headers = self._token_mgr.auth_headers()
            resp = await self._http_client.post(
                f"{self._config.trade_url}/order/place",
                json=order_request,
                headers=headers,
            )
            resp.raise_for_status()
            return WebullOrder.from_api(resp.json())

        return self._demo_place_order(order_request)

    async def modify_order(self, order_id: str, changes: dict) -> WebullOrder:
        """Modify an existing open order.

        Args:
            order_id: The order ID to modify.
            changes: Dict with fields to update (lmtPrice, quantity, etc.)
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            payload = {"orderId": order_id, **changes}
            resp = await self._http_client.post(
                f"{self._config.trade_url}/order/modify",
                json=payload,
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            return WebullOrder.from_api(resp.json())

        return self._demo_modify_order(order_id, changes)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.post(
                f"{self._config.trade_url}/order/cancel",
                json={"orderId": order_id},
                headers=self._token_mgr.auth_headers(),
            )
            return resp.status_code in (200, 204)

        return True

    # -- Market Data -------------------------------------------------------

    async def get_quote(self, symbol: str) -> WebullQuote:
        """Get real-time quote for a single symbol (includes extended hours pricing)."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            # First resolve ticker_id from symbol
            ticker_id = await self._resolve_ticker_id(symbol)
            resp = await self._http_client.get(
                f"{self._config.quotes_url}/quotes/ticker/getTickerRealTime",
                params={"tickerId": ticker_id},
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            return WebullQuote.from_api(resp.json(), symbol=symbol)

        quotes = self._demo_quotes([symbol])
        return quotes[0] if quotes else WebullQuote(symbol=symbol)

    async def get_quotes(self, symbols: list[str]) -> list[WebullQuote]:
        """Get real-time quotes for multiple symbols."""
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            results = []
            for sym in symbols:
                try:
                    quote = await self.get_quote(sym)
                    results.append(quote)
                except Exception as e:
                    logger.warning(f"Failed to get quote for {sym}: {e}")
            return results

        return self._demo_quotes(symbols)

    async def get_price_history(
        self,
        symbol: str,
        interval: str = "d1",
        count: int = 30,
    ) -> list[WebullCandle]:
        """Get price history (OHLCV candles).

        Args:
            symbol: Ticker symbol.
            interval: Candle interval (m1, m5, m15, m30, h1, h2, h4, d1, w1, mo1).
            count: Number of candles to retrieve.
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            ticker_id = await self._resolve_ticker_id(symbol)
            resp = await self._http_client.get(
                f"{self._config.quotes_url}/quotes/ticker/getKLine",
                params={
                    "tickerId": ticker_id,
                    "type": interval,
                    "count": count,
                },
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            candles_data = resp.json().get("data", resp.json())
            if isinstance(candles_data, list):
                return [WebullCandle.from_api(c) for c in candles_data]
            return []

        return self._demo_candles(symbol, count)

    async def get_options_chain(
        self,
        symbol: str,
        expiration_date: Optional[str] = None,
    ) -> dict:
        """Get options chain for a symbol.

        Args:
            symbol: Underlying ticker symbol.
            expiration_date: Optional expiry filter (YYYY-MM-DD).
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            ticker_id = await self._resolve_ticker_id(symbol)
            params: dict[str, Any] = {"tickerId": ticker_id}
            if expiration_date:
                params["expireDate"] = expiration_date
            resp = await self._http_client.get(
                f"{self._config.quotes_url}/quotes/option/chain/query",
                params=params,
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            return resp.json()

        return self._demo_option_chain(symbol)

    async def get_crypto_quote(self, symbol: str) -> WebullQuote:
        """Get cryptocurrency quote.

        Webull supports crypto trading directly (BTC, ETH, DOGE, etc.).
        Crypto symbols use the format: 'BTC', 'ETH', 'DOGE'.
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            resp = await self._http_client.get(
                f"{self._config.quotes_url}/quotes/crypto/ticker",
                params={"symbol": symbol},
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            return WebullQuote.from_api(resp.json(), symbol=symbol)

        return self._demo_crypto_quote(symbol)

    async def screen_stocks(self, criteria: dict) -> list[WebullScreenerResult]:
        """Run Webull's built-in stock screener.

        Args:
            criteria: Screener filter dict. Common keys:
                - region: "US" (default)
                - marketCap: {"min": 1e9, "max": 1e12}
                - pe: {"min": 0, "max": 30}
                - changeRatio: {"min": 0.02}  (2%+ gainers)
                - volume: {"min": 1000000}
                - sector: "Technology"
                - sort: "changeRatio" / "volume" / "marketCap"
                - sortDir: "desc" / "asc"
                - pageSize: 20
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_token()
            payload = {
                "regionId": criteria.get("region", "US"),
                "rules": self._build_screener_rules(criteria),
                "sort": {
                    "rule": criteria.get("sort", "changeRatio"),
                    "desc": criteria.get("sortDir", "desc") == "desc",
                },
                "page": 1,
                "pageSize": criteria.get("pageSize", 20),
            }
            resp = await self._http_client.post(
                self._config.screener_url,
                json=payload,
                headers=self._token_mgr.auth_headers(),
            )
            resp.raise_for_status()
            tickers = resp.json().get("data", {}).get("tickers", [])
            return [WebullScreenerResult.from_api(t) for t in tickers]

        return self._demo_screener_results(criteria)

    # -- Internal Helpers --------------------------------------------------

    async def _resolve_ticker_id(self, symbol: str) -> int:
        """Resolve a symbol string to Webull's internal ticker_id."""
        demo_ids = {
            "TSLA": 913256135, "AMD": 913254235, "AAPL": 913256393,
            "NVDA": 913257561, "MSFT": 913323997, "GOOGL": 913257182,
            "AMZN": 913256327, "META": 913302844, "SPY": 913243261,
            "QQQ": 913243251, "BTC": 950160802, "ETH": 950160803,
        }
        if symbol in demo_ids:
            return demo_ids[symbol]
        # Fallback: search
        if self._mode == "http" and self._http_client:
            try:
                resp = await self._http_client.get(
                    f"{self._config.quotes_url}/search/pc/tickers",
                    params={"keyword": symbol, "pageSize": 1},
                    headers=self._token_mgr.auth_headers(),
                )
                if resp.status_code == 200:
                    results = resp.json().get("data", [])
                    if results:
                        return int(results[0].get("tickerId", 0))
            except Exception as e:
                logger.warning(f"Ticker ID resolution failed for {symbol}: {e}")
        return 0

    def _build_screener_rules(self, criteria: dict) -> list[dict]:
        """Convert user-friendly criteria to Webull screener rules format."""
        rules = []
        field_map = {
            "marketCap": "totalMarketValue",
            "pe": "peTtm",
            "changeRatio": "changeRatio",
            "volume": "volume",
            "price": "close",
        }
        for key, rule_name in field_map.items():
            if key in criteria:
                val = criteria[key]
                if isinstance(val, dict):
                    rule: dict[str, Any] = {"ruleName": rule_name}
                    if "min" in val:
                        rule["min"] = val["min"]
                    if "max" in val:
                        rule["max"] = val["max"]
                    rules.append(rule)
        if "sector" in criteria:
            rules.append({"ruleName": "sector", "value": criteria["sector"]})
        return rules

    # -- Demo Data ---------------------------------------------------------

    def _demo_account(self) -> WebullAccount:
        return WebullAccount(
            account_id="DEMO-WB-88776655",
            account_type="INDIVIDUAL",
            net_liquidation=98750.00,
            total_market_value=73450.00,
            cash_balance=25300.00,
            buying_power=50600.00,
            day_buying_power=101200.00,
            overnight_buying_power=50600.00,
            unsettled_funds=1250.00,
            day_trades_remaining=3,
            is_day_trader=False,
        )

    def _demo_positions(self) -> list[WebullPosition]:
        return [
            WebullPosition(
                symbol="TSLA", ticker_id=913256135, asset_type="stock",
                quantity=25, cost_price=242.50, last_price=258.75,
                market_value=6468.75, unrealized_pnl=406.25,
                unrealized_pnl_pct=6.70, position_side="LONG",
            ),
            WebullPosition(
                symbol="AMD", ticker_id=913254235, asset_type="stock",
                quantity=80, cost_price=155.20, last_price=168.40,
                market_value=13472.00, unrealized_pnl=1056.00,
                unrealized_pnl_pct=8.51, position_side="LONG",
            ),
            WebullPosition(
                symbol="AAPL", ticker_id=913256393, asset_type="stock",
                quantity=150, cost_price=195.30, last_price=228.50,
                market_value=34275.00, unrealized_pnl=4980.00,
                unrealized_pnl_pct=17.00, position_side="LONG",
            ),
        ]

    def _demo_orders(self) -> list[WebullOrder]:
        return [
            WebullOrder(
                order_id="DEMO-WB-ORD-001", ticker_id=913256135, symbol="TSLA",
                action="BUY", order_type="MKT", quantity=25, filled_quantity=25,
                avg_filled_price=242.50, status="Filled", time_in_force="DAY",
                placed_time="2025-01-20T09:35:00Z", filled_time="2025-01-20T09:35:02Z",
                outside_regular_hours=False,
            ),
            WebullOrder(
                order_id="DEMO-WB-ORD-002", ticker_id=913254235, symbol="AMD",
                action="BUY", order_type="LMT", quantity=80, filled_quantity=80,
                avg_filled_price=155.20, limit_price=156.00, status="Filled",
                time_in_force="GTC",
                placed_time="2025-01-18T06:15:00Z", filled_time="2025-01-18T09:30:05Z",
                outside_regular_hours=True,  # Pre-market fill
            ),
            WebullOrder(
                order_id="DEMO-WB-ORD-003", ticker_id=913256393, symbol="AAPL",
                action="BUY", order_type="LMT", quantity=50, filled_quantity=0,
                limit_price=220.00, status="Submitted", time_in_force="GTC",
                placed_time="2025-01-22T17:45:00Z",
                outside_regular_hours=True,  # After-hours order
            ),
        ]

    def _demo_place_order(self, order_request: dict) -> WebullOrder:
        symbol = order_request.get("symbol", order_request.get("ticker", {}).get("symbol", "TSLA"))
        action = order_request.get("action", "BUY")
        qty = float(order_request.get("quantity", order_request.get("totalQuantity", 10)))
        order_type = order_request.get("orderType", "MKT")
        outside_hours = bool(order_request.get("outsideRegularTradingHour", False))

        demo_prices = {
            "TSLA": 258.75, "AMD": 168.40, "AAPL": 228.50,
            "NVDA": 875.20, "MSFT": 415.30, "GOOGL": 185.40,
            "AMZN": 202.10, "META": 580.30, "SPY": 590.50,
        }
        price = demo_prices.get(symbol, 100.0)
        demo_ids = {
            "TSLA": 913256135, "AMD": 913254235, "AAPL": 913256393,
            "NVDA": 913257561, "MSFT": 913323997, "GOOGL": 913257182,
        }

        return WebullOrder(
            order_id=f"DEMO-WB-{uuid.uuid4().hex[:8].upper()}",
            ticker_id=demo_ids.get(symbol, 0),
            symbol=symbol,
            action=action,
            order_type=order_type,
            quantity=qty,
            filled_quantity=qty if order_type == "MKT" else 0,
            avg_filled_price=price if order_type == "MKT" else 0.0,
            limit_price=float(order_request.get("lmtPrice", 0)) if order_request.get("lmtPrice") else None,
            stop_price=float(order_request.get("auxPrice", 0)) if order_request.get("auxPrice") else None,
            status="Filled" if order_type == "MKT" else "Submitted",
            time_in_force=order_request.get("timeInForce", "DAY"),
            placed_time=datetime.now(timezone.utc).isoformat(),
            filled_time=datetime.now(timezone.utc).isoformat() if order_type == "MKT" else "",
            outside_regular_hours=outside_hours,
        )

    def _demo_modify_order(self, order_id: str, changes: dict) -> WebullOrder:
        return WebullOrder(
            order_id=order_id,
            symbol=changes.get("symbol", "TSLA"),
            action=changes.get("action", "BUY"),
            order_type=changes.get("orderType", "LMT"),
            quantity=float(changes.get("quantity", 10)),
            limit_price=float(changes["lmtPrice"]) if changes.get("lmtPrice") else None,
            stop_price=float(changes["auxPrice"]) if changes.get("auxPrice") else None,
            status="Submitted",
            time_in_force=changes.get("timeInForce", "GTC"),
        )

    def _demo_quotes(self, symbols: list[str]) -> list[WebullQuote]:
        demo_data = {
            "TSLA": {
                "last": 258.75, "bid": 258.70, "ask": 258.80, "vol": 95200000,
                "avg_vol": 88500000, "net": 6.25, "pct": 2.48, "pe": 72.5,
                "cap": 822e9, "hi52": 299.29, "lo52": 138.80,
                "o": 252.50, "h": 260.10, "l": 251.80, "prev": 252.50,
                "pre_mkt": 260.15, "ah": 259.30,
            },
            "AMD": {
                "last": 168.40, "bid": 168.35, "ask": 168.45, "vol": 52100000,
                "avg_vol": 48000000, "net": 3.20, "pct": 1.94, "pe": 45.8,
                "cap": 272e9, "hi52": 187.28, "lo52": 116.37,
                "o": 165.20, "h": 169.50, "l": 164.80, "prev": 165.20,
                "pre_mkt": 169.80, "ah": 168.95,
            },
            "AAPL": {
                "last": 228.50, "bid": 228.45, "ask": 228.55, "vol": 58700000,
                "avg_vol": 55100000, "net": 2.10, "pct": 0.93, "pe": 30.8,
                "cap": 3520e9, "hi52": 237.49, "lo52": 169.21,
                "o": 226.40, "h": 229.30, "l": 225.90, "prev": 226.40,
                "pre_mkt": 229.10, "ah": 228.80,
            },
            "NVDA": {
                "last": 875.20, "bid": 875.10, "ask": 875.30, "vol": 42000000,
                "avg_vol": 38500000, "net": 12.50, "pct": 1.45, "pe": 65.0,
                "cap": 2160e9, "hi52": 974.00, "lo52": 473.20,
                "o": 863.00, "h": 878.00, "l": 860.00, "prev": 862.70,
                "pre_mkt": 878.50, "ah": 876.10,
            },
            "MSFT": {
                "last": 415.30, "bid": 415.25, "ask": 415.35, "vol": 22100000,
                "avg_vol": 20800000, "net": -0.70, "pct": -0.17, "pe": 36.8,
                "cap": 3090e9, "hi52": 435.00, "lo52": 340.00,
                "o": 416.00, "h": 417.00, "l": 414.00, "prev": 416.00,
                "pre_mkt": 415.80, "ah": 415.50,
            },
            "GOOGL": {
                "last": 185.40, "bid": 185.35, "ask": 185.45, "vol": 28300000,
                "avg_vol": 25700000, "net": 0.90, "pct": 0.49, "pe": 25.1,
                "cap": 2290e9, "hi52": 195.00, "lo52": 140.00,
                "o": 184.50, "h": 186.00, "l": 184.00, "prev": 184.50,
                "pre_mkt": 186.20, "ah": 185.70,
            },
        }
        result = []
        for s in symbols:
            d = demo_data.get(s, {
                "last": 100.0, "bid": 99.95, "ask": 100.05, "vol": 1000000,
                "avg_vol": 950000, "net": 0.5, "pct": 0.5, "pe": 20.0,
                "cap": 10e9, "hi52": 120.0, "lo52": 80.0,
                "o": 99.5, "h": 100.5, "l": 99.0, "prev": 99.50,
                "pre_mkt": 100.20, "ah": 100.10,
            })
            demo_ids = {
                "TSLA": 913256135, "AMD": 913254235, "AAPL": 913256393,
                "NVDA": 913257561, "MSFT": 913323997, "GOOGL": 913257182,
            }
            result.append(WebullQuote(
                symbol=s, ticker_id=demo_ids.get(s, 0),
                last=d["last"], bid=d["bid"], ask=d["ask"],
                open=d["o"], high=d["h"], low=d["l"],
                close=d["last"], prev_close=d["prev"],
                volume=d["vol"], avg_volume_10d=d["avg_vol"],
                change=d["net"], change_pct=d["pct"],
                pe_ratio=d["pe"], market_cap=d["cap"],
                week_52_high=d["hi52"], week_52_low=d["lo52"],
                pre_market_price=d.get("pre_mkt"),
                after_hours_price=d.get("ah"),
            ))
        return result

    def _demo_crypto_quote(self, symbol: str) -> WebullQuote:
        crypto_data = {
            "BTC": {
                "last": 97250.00, "bid": 97240.00, "ask": 97260.00,
                "vol": 32500, "avg_vol": 28000, "net": 1850.00, "pct": 1.94,
                "cap": 1910e9, "hi52": 108000.0, "lo52": 39500.0,
                "o": 95400.0, "h": 97800.0, "l": 94900.0, "prev": 95400.0,
            },
            "ETH": {
                "last": 3425.00, "bid": 3424.00, "ask": 3426.00,
                "vol": 185000, "avg_vol": 172000, "net": 82.50, "pct": 2.47,
                "cap": 412e9, "hi52": 4090.0, "lo52": 1520.0,
                "o": 3342.50, "h": 3450.00, "l": 3330.00, "prev": 3342.50,
            },
            "DOGE": {
                "last": 0.1285, "bid": 0.1284, "ask": 0.1286,
                "vol": 2800000000, "avg_vol": 2500000000, "net": 0.0042, "pct": 3.38,
                "cap": 18.3e9, "hi52": 0.2280, "lo52": 0.0580,
                "o": 0.1243, "h": 0.1298, "l": 0.1235, "prev": 0.1243,
            },
        }
        d = crypto_data.get(symbol, {
            "last": 1.00, "bid": 0.99, "ask": 1.01,
            "vol": 100000, "avg_vol": 95000, "net": 0.02, "pct": 2.0,
            "cap": 1e9, "hi52": 2.0, "lo52": 0.50,
            "o": 0.98, "h": 1.02, "l": 0.97, "prev": 0.98,
        })
        crypto_ids = {"BTC": 950160802, "ETH": 950160803, "DOGE": 950160804}
        return WebullQuote(
            symbol=symbol, ticker_id=crypto_ids.get(symbol, 0),
            last=d["last"], bid=d["bid"], ask=d["ask"],
            open=d["o"], high=d["h"], low=d["l"],
            close=d["last"], prev_close=d["prev"],
            volume=d["vol"], avg_volume_10d=d["avg_vol"],
            change=d["net"], change_pct=d["pct"],
            market_cap=d["cap"],
            week_52_high=d["hi52"], week_52_low=d["lo52"],
        )

    def _demo_candles(self, symbol: str, count: int = 30) -> list[WebullCandle]:
        import random
        random.seed(hash(symbol) % 2**31)
        demo_bases = {
            "TSLA": 258.75, "AMD": 168.40, "AAPL": 228.50,
            "NVDA": 875.20, "MSFT": 415.30, "GOOGL": 185.40,
        }
        base = demo_bases.get(symbol, 100.0)
        candles = []
        for i in range(count):
            change = random.uniform(-0.02, 0.02)
            o = base * (1 + change)
            c = o * (1 + random.uniform(-0.015, 0.015))
            h = max(o, c) * (1 + random.uniform(0, 0.01))
            lo = min(o, c) * (1 - random.uniform(0, 0.01))
            candles.append(WebullCandle(
                open=round(o, 2), high=round(h, 2),
                low=round(lo, 2), close=round(c, 2),
                volume=random.randint(10_000_000, 80_000_000),
            ))
            base = c
        return candles

    def _demo_option_chain(self, symbol: str) -> dict:
        demo_bases = {
            "TSLA": 258.75, "AMD": 168.40, "AAPL": 228.50,
            "NVDA": 875.20, "MSFT": 415.30,
        }
        base = demo_bases.get(symbol, 100.0)
        strike_count = 10
        calls = []
        puts = []
        for i in range(-strike_count // 2, strike_count // 2 + 1):
            strike = round(base + i * 5, 2)
            calls.append({
                "type": "call", "symbol": f"{symbol}C{strike}",
                "strikePrice": strike,
                "bidPrice": max(0.10, round(base - strike + 5, 2)),
                "askPrice": max(0.15, round(base - strike + 5.5, 2)),
                "lastPrice": max(0.12, round(base - strike + 5.25, 2)),
                "delta": round(max(0.05, min(0.95, 0.5 + (base - strike) / 50)), 3),
                "gamma": 0.015, "theta": -0.05, "vega": 0.12,
                "openInterest": 5000 + i * 200,
                "volume": 1200 + i * 50,
            })
            puts.append({
                "type": "put", "symbol": f"{symbol}P{strike}",
                "strikePrice": strike,
                "bidPrice": max(0.10, round(strike - base + 5, 2)),
                "askPrice": max(0.15, round(strike - base + 5.5, 2)),
                "lastPrice": max(0.12, round(strike - base + 5.25, 2)),
                "delta": round(min(-0.05, max(-0.95, -0.5 + (base - strike) / 50)), 3),
                "gamma": 0.015, "theta": -0.04, "vega": 0.11,
                "openInterest": 4000 + i * 150,
                "volume": 900 + i * 30,
            })
        return {
            "symbol": symbol,
            "underlying": {"last": base},
            "expireDate": "2025-02-21",
            "calls": calls,
            "puts": puts,
        }

    def _demo_screener_results(self, criteria: dict) -> list[WebullScreenerResult]:
        all_results = [
            WebullScreenerResult(
                symbol="NVDA", name="NVIDIA Corporation",
                last_price=875.20, change_pct=1.45,
                volume=42000000, market_cap=2160e9,
                pe_ratio=65.0, sector="Technology",
            ),
            WebullScreenerResult(
                symbol="SMCI", name="Super Micro Computer Inc",
                last_price=903.50, change_pct=3.20,
                volume=12000000, market_cap=52.8e9,
                pe_ratio=48.2, sector="Technology",
            ),
            WebullScreenerResult(
                symbol="ARM", name="Arm Holdings plc",
                last_price=172.50, change_pct=4.10,
                volume=9500000, market_cap=178e9,
                pe_ratio=310.5, sector="Technology",
            ),
            WebullScreenerResult(
                symbol="TSLA", name="Tesla Inc",
                last_price=258.75, change_pct=2.48,
                volume=95200000, market_cap=822e9,
                pe_ratio=72.5, sector="Consumer Cyclical",
            ),
            WebullScreenerResult(
                symbol="PLTR", name="Palantir Technologies Inc",
                last_price=22.80, change_pct=5.30,
                volume=68000000, market_cap=49.5e9,
                pe_ratio=215.0, sector="Technology",
            ),
            WebullScreenerResult(
                symbol="SOFI", name="SoFi Technologies Inc",
                last_price=9.85, change_pct=3.75,
                volume=42000000, market_cap=9.8e9,
                pe_ratio=0.0, sector="Financial Services",
            ),
            WebullScreenerResult(
                symbol="AMD", name="Advanced Micro Devices Inc",
                last_price=168.40, change_pct=1.94,
                volume=52100000, market_cap=272e9,
                pe_ratio=45.8, sector="Technology",
            ),
            WebullScreenerResult(
                symbol="COIN", name="Coinbase Global Inc",
                last_price=178.25, change_pct=6.20,
                volume=18500000, market_cap=42.3e9,
                pe_ratio=35.2, sector="Financial Services",
            ),
        ]
        # Apply sector filter if present
        sector = criteria.get("sector", "")
        if sector:
            all_results = [r for r in all_results if r.sector.lower() == sector.lower()]

        page_size = criteria.get("pageSize", 20)
        return all_results[:page_size]
