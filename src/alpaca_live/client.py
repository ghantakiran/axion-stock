"""Alpaca REST API Client (PRD-139).

Lightweight HTTP client for Alpaca's Trading & Market Data APIs.
Uses alpaca-py SDK when available, falls back to raw HTTP via httpx.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, date, timedelta
from enum import Enum
from typing import Any, Optional
import json
import logging
import uuid

logger = logging.getLogger(__name__)

# Try importing alpaca-py SDK; fall back to raw HTTP
_HAS_ALPACA_SDK = False
try:
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient
    _HAS_ALPACA_SDK = True
except ImportError:
    TradingClient = None  # type: ignore
    StockHistoricalDataClient = None  # type: ignore

_HAS_HTTPX = False
try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    httpx = None  # type: ignore


# ═══════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════


class AlpacaEnvironment(str, Enum):
    """Alpaca API environment."""
    PAPER = "paper"
    LIVE = "live"


@dataclass
class AlpacaConfig:
    """Configuration for Alpaca API connection."""
    api_key: str = ""
    api_secret: str = ""
    environment: AlpacaEnvironment = AlpacaEnvironment.PAPER
    # Rate limiting
    max_requests_per_minute: int = 200
    request_timeout: int = 30
    # Retry
    max_retries: int = 3
    retry_delay: float = 1.0
    # Data
    data_feed: str = "iex"  # "iex" (free) or "sip" (paid)

    @property
    def base_url(self) -> str:
        if self.environment == AlpacaEnvironment.LIVE:
            return "https://api.alpaca.markets"
        return "https://paper-api.alpaca.markets"

    @property
    def data_url(self) -> str:
        return "https://data.alpaca.markets"

    @property
    def stream_url(self) -> str:
        if self.data_feed == "sip":
            return "wss://stream.data.alpaca.markets/v2/sip"
        return "wss://stream.data.alpaca.markets/v2/iex"

    @property
    def trading_stream_url(self) -> str:
        if self.environment == AlpacaEnvironment.LIVE:
            return "wss://api.alpaca.markets/stream"
        return "wss://paper-api.alpaca.markets/stream"


# ═══════════════════════════════════════════════════════════════════════
# Response Models
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class AlpacaAccount:
    """Alpaca account information."""
    account_id: str = ""
    status: str = "ACTIVE"
    currency: str = "USD"
    cash: float = 0.0
    portfolio_value: float = 0.0
    buying_power: float = 0.0
    day_trading_buying_power: float = 0.0
    equity: float = 0.0
    last_equity: float = 0.0
    long_market_value: float = 0.0
    short_market_value: float = 0.0
    initial_margin: float = 0.0
    maintenance_margin: float = 0.0
    daytrade_count: int = 0
    pattern_day_trader: bool = False
    trading_blocked: bool = False
    transfers_blocked: bool = False
    account_blocked: bool = False
    crypto_status: str = "ACTIVE"
    created_at: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict) -> "AlpacaAccount":
        return cls(
            account_id=data.get("id", data.get("account_number", "")),
            status=data.get("status", "ACTIVE"),
            currency=data.get("currency", "USD"),
            cash=float(data.get("cash", 0)),
            portfolio_value=float(data.get("portfolio_value", 0)),
            buying_power=float(data.get("buying_power", 0)),
            day_trading_buying_power=float(data.get("daytrading_buying_power", 0)),
            equity=float(data.get("equity", 0)),
            last_equity=float(data.get("last_equity", 0)),
            long_market_value=float(data.get("long_market_value", 0)),
            short_market_value=float(data.get("short_market_value", 0)),
            initial_margin=float(data.get("initial_margin", 0)),
            maintenance_margin=float(data.get("maintenance_margin", 0)),
            daytrade_count=int(data.get("daytrade_count", 0)),
            pattern_day_trader=data.get("pattern_day_trader", False),
            trading_blocked=data.get("trading_blocked", False),
            transfers_blocked=data.get("transfers_blocked", False),
            account_blocked=data.get("account_blocked", False),
            crypto_status=data.get("crypto_status", "ACTIVE"),
            created_at=data.get("created_at"),
        )


@dataclass
class AlpacaPosition:
    """Alpaca position."""
    asset_id: str = ""
    symbol: str = ""
    exchange: str = ""
    asset_class: str = "us_equity"
    qty: float = 0.0
    qty_available: float = 0.0
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    cost_basis: float = 0.0
    unrealized_pl: float = 0.0
    unrealized_plpc: float = 0.0
    unrealized_intraday_pl: float = 0.0
    unrealized_intraday_plpc: float = 0.0
    side: str = "long"
    change_today: float = 0.0

    @classmethod
    def from_api(cls, data: dict) -> "AlpacaPosition":
        return cls(
            asset_id=data.get("asset_id", ""),
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            asset_class=data.get("asset_class", "us_equity"),
            qty=float(data.get("qty", 0)),
            qty_available=float(data.get("qty_available", 0)),
            avg_entry_price=float(data.get("avg_entry_price", 0)),
            current_price=float(data.get("current_price", 0)),
            market_value=float(data.get("market_value", 0)),
            cost_basis=float(data.get("cost_basis", 0)),
            unrealized_pl=float(data.get("unrealized_pl", 0)),
            unrealized_plpc=float(data.get("unrealized_plpc", 0)),
            unrealized_intraday_pl=float(data.get("unrealized_intraday_pl", 0)),
            unrealized_intraday_plpc=float(data.get("unrealized_intraday_plpc", 0)),
            side=data.get("side", "long"),
            change_today=float(data.get("change_today", 0)),
        )


@dataclass
class AlpacaOrder:
    """Alpaca order."""
    order_id: str = ""
    client_order_id: str = ""
    symbol: str = ""
    asset_class: str = "us_equity"
    qty: float = 0.0
    filled_qty: float = 0.0
    filled_avg_price: float = 0.0
    order_type: str = "market"
    side: str = "buy"
    time_in_force: str = "day"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    trail_percent: Optional[float] = None
    trail_price: Optional[float] = None
    status: str = "new"
    extended_hours: bool = False
    created_at: Optional[str] = None
    submitted_at: Optional[str] = None
    filled_at: Optional[str] = None
    canceled_at: Optional[str] = None
    expired_at: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict) -> "AlpacaOrder":
        return cls(
            order_id=data.get("id", ""),
            client_order_id=data.get("client_order_id", ""),
            symbol=data.get("symbol", ""),
            asset_class=data.get("asset_class", "us_equity"),
            qty=float(data.get("qty", 0)),
            filled_qty=float(data.get("filled_qty", 0) or 0),
            filled_avg_price=float(data.get("filled_avg_price", 0) or 0),
            order_type=data.get("type", data.get("order_type", "market")),
            side=data.get("side", "buy"),
            time_in_force=data.get("time_in_force", "day"),
            limit_price=float(data["limit_price"]) if data.get("limit_price") else None,
            stop_price=float(data["stop_price"]) if data.get("stop_price") else None,
            trail_percent=float(data["trail_percent"]) if data.get("trail_percent") else None,
            trail_price=float(data["trail_price"]) if data.get("trail_price") else None,
            status=data.get("status", "new"),
            extended_hours=data.get("extended_hours", False),
            created_at=data.get("created_at"),
            submitted_at=data.get("submitted_at"),
            filled_at=data.get("filled_at"),
            canceled_at=data.get("canceled_at"),
            expired_at=data.get("expired_at"),
        )


@dataclass
class AlpacaBar:
    """OHLCV bar."""
    timestamp: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    trade_count: int = 0
    vwap: float = 0.0

    @classmethod
    def from_api(cls, data: dict) -> "AlpacaBar":
        return cls(
            timestamp=data.get("t", data.get("timestamp", "")),
            open=float(data.get("o", data.get("open", 0))),
            high=float(data.get("h", data.get("high", 0))),
            low=float(data.get("l", data.get("low", 0))),
            close=float(data.get("c", data.get("close", 0))),
            volume=int(data.get("v", data.get("volume", 0))),
            trade_count=int(data.get("n", data.get("trade_count", 0))),
            vwap=float(data.get("vw", data.get("vwap", 0))),
        )


@dataclass
class AlpacaQuote:
    """Real-time quote."""
    symbol: str = ""
    bid_price: float = 0.0
    bid_size: int = 0
    ask_price: float = 0.0
    ask_size: int = 0
    timestamp: str = ""

    @classmethod
    def from_api(cls, data: dict, symbol: str = "") -> "AlpacaQuote":
        return cls(
            symbol=symbol or data.get("symbol", ""),
            bid_price=float(data.get("bp", data.get("bid_price", 0))),
            bid_size=int(data.get("bs", data.get("bid_size", 0))),
            ask_price=float(data.get("ap", data.get("ask_price", 0))),
            ask_size=int(data.get("as", data.get("ask_size", 0))),
            timestamp=data.get("t", data.get("timestamp", "")),
        )


@dataclass
class AlpacaSnapshot:
    """Market snapshot for a symbol."""
    symbol: str = ""
    latest_trade_price: float = 0.0
    latest_trade_size: int = 0
    latest_quote_bid: float = 0.0
    latest_quote_ask: float = 0.0
    minute_bar: Optional[AlpacaBar] = None
    daily_bar: Optional[AlpacaBar] = None
    prev_daily_bar: Optional[AlpacaBar] = None

    @classmethod
    def from_api(cls, data: dict, symbol: str = "") -> "AlpacaSnapshot":
        latest_trade = data.get("latestTrade", data.get("latest_trade", {}))
        latest_quote = data.get("latestQuote", data.get("latest_quote", {}))
        minute = data.get("minuteBar", data.get("minute_bar"))
        daily = data.get("dailyBar", data.get("daily_bar"))
        prev = data.get("prevDailyBar", data.get("prev_daily_bar"))
        return cls(
            symbol=symbol,
            latest_trade_price=float(latest_trade.get("p", latest_trade.get("price", 0))),
            latest_trade_size=int(latest_trade.get("s", latest_trade.get("size", 0))),
            latest_quote_bid=float(latest_quote.get("bp", latest_quote.get("bid_price", 0))),
            latest_quote_ask=float(latest_quote.get("ap", latest_quote.get("ask_price", 0))),
            minute_bar=AlpacaBar.from_api(minute) if minute else None,
            daily_bar=AlpacaBar.from_api(daily) if daily else None,
            prev_daily_bar=AlpacaBar.from_api(prev) if prev else None,
        )


# ═══════════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════════


class AlpacaClient:
    """Alpaca REST API client.

    Supports both alpaca-py SDK and raw HTTP (httpx) backends.
    Falls back to demo data when no credentials or network available.

    Example:
        client = AlpacaClient(AlpacaConfig(api_key="...", api_secret="..."))
        await client.connect()
        account = await client.get_account()
        positions = await client.get_positions()
    """

    def __init__(self, config: AlpacaConfig):
        self._config = config
        self._connected = False
        self._http_client: Any = None
        self._sdk_trading: Any = None
        self._sdk_data: Any = None
        self._mode: str = "demo"  # "sdk", "http", or "demo"
        self._request_count = 0

    @property
    def config(self) -> AlpacaConfig:
        return self._config

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def mode(self) -> str:
        return self._mode

    async def connect(self) -> bool:
        """Connect to Alpaca API.

        Tries SDK first, then raw HTTP, falls back to demo mode.
        """
        if not self._config.api_key or not self._config.api_secret:
            logger.info("No Alpaca credentials — using demo mode")
            self._mode = "demo"
            self._connected = True
            return True

        # Try alpaca-py SDK
        if _HAS_ALPACA_SDK:
            try:
                paper = self._config.environment == AlpacaEnvironment.PAPER
                self._sdk_trading = TradingClient(
                    self._config.api_key,
                    self._config.api_secret,
                    paper=paper,
                )
                self._sdk_data = StockHistoricalDataClient(
                    self._config.api_key,
                    self._config.api_secret,
                )
                self._mode = "sdk"
                self._connected = True
                logger.info("Connected to Alpaca via SDK")
                return True
            except Exception as e:
                logger.warning(f"SDK connection failed: {e}")

        # Try raw HTTP
        if _HAS_HTTPX:
            try:
                self._http_client = httpx.AsyncClient(
                    base_url=self._config.base_url,
                    headers={
                        "APCA-API-KEY-ID": self._config.api_key,
                        "APCA-API-SECRET-KEY": self._config.api_secret,
                    },
                    timeout=self._config.request_timeout,
                )
                # Test connection
                resp = await self._http_client.get("/v2/account")
                if resp.status_code == 200:
                    self._mode = "http"
                    self._connected = True
                    logger.info("Connected to Alpaca via HTTP")
                    return True
                else:
                    logger.warning(f"HTTP auth failed: {resp.status_code}")
            except Exception as e:
                logger.warning(f"HTTP connection failed: {e}")

        # Fallback to demo
        self._mode = "demo"
        self._connected = True
        logger.info("Using Alpaca demo mode (no live API)")
        return True

    async def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        if self._http_client and hasattr(self._http_client, "aclose"):
            await self._http_client.aclose()
        self._http_client = None
        self._sdk_trading = None
        self._sdk_data = None
        self._connected = False
        self._mode = "demo"
        logger.info("Disconnected from Alpaca")

    # ── Account ──────────────────────────────────────────────────────

    async def get_account(self) -> AlpacaAccount:
        """Get account information."""
        if self._mode == "http" and self._http_client:
            resp = await self._http_client.get("/v2/account")
            resp.raise_for_status()
            return AlpacaAccount.from_api(resp.json())

        if self._mode == "sdk" and self._sdk_trading:
            acct = self._sdk_trading.get_account()
            return AlpacaAccount(
                account_id=str(getattr(acct, "id", "")),
                status=str(getattr(acct, "status", "ACTIVE")),
                cash=float(getattr(acct, "cash", 0)),
                portfolio_value=float(getattr(acct, "portfolio_value", 0)),
                buying_power=float(getattr(acct, "buying_power", 0)),
                equity=float(getattr(acct, "equity", 0)),
                pattern_day_trader=getattr(acct, "pattern_day_trader", False),
            )

        return self._demo_account()

    async def get_positions(self) -> list[AlpacaPosition]:
        """Get all open positions."""
        if self._mode == "http" and self._http_client:
            resp = await self._http_client.get("/v2/positions")
            resp.raise_for_status()
            return [AlpacaPosition.from_api(p) for p in resp.json()]

        if self._mode == "sdk" and self._sdk_trading:
            positions = self._sdk_trading.get_all_positions()
            return [
                AlpacaPosition(
                    asset_id=str(getattr(p, "asset_id", "")),
                    symbol=str(getattr(p, "symbol", "")),
                    qty=float(getattr(p, "qty", 0)),
                    avg_entry_price=float(getattr(p, "avg_entry_price", 0)),
                    current_price=float(getattr(p, "current_price", 0)),
                    market_value=float(getattr(p, "market_value", 0)),
                    unrealized_pl=float(getattr(p, "unrealized_pl", 0)),
                    unrealized_plpc=float(getattr(p, "unrealized_plpc", 0)),
                    side=str(getattr(p, "side", "long")),
                )
                for p in positions
            ]

        return self._demo_positions()

    async def get_position(self, symbol: str) -> Optional[AlpacaPosition]:
        """Get position for a specific symbol."""
        if self._mode == "http" and self._http_client:
            resp = await self._http_client.get(f"/v2/positions/{symbol}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return AlpacaPosition.from_api(resp.json())

        positions = await self.get_positions()
        for p in positions:
            if p.symbol == symbol:
                return p
        return None

    # ── Orders ───────────────────────────────────────────────────────

    async def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        time_in_force: str = "day",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        trail_percent: Optional[float] = None,
        extended_hours: bool = False,
        client_order_id: Optional[str] = None,
    ) -> AlpacaOrder:
        """Submit an order."""
        order_data = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
            "extended_hours": extended_hours,
        }
        if limit_price is not None:
            order_data["limit_price"] = str(limit_price)
        if stop_price is not None:
            order_data["stop_price"] = str(stop_price)
        if trail_percent is not None:
            order_data["trail_percent"] = str(trail_percent)
        if client_order_id:
            order_data["client_order_id"] = client_order_id

        if self._mode == "http" and self._http_client:
            resp = await self._http_client.post("/v2/orders", json=order_data)
            resp.raise_for_status()
            return AlpacaOrder.from_api(resp.json())

        # Demo mode
        return self._demo_order(order_data)

    async def get_order(self, order_id: str) -> Optional[AlpacaOrder]:
        """Get order by ID."""
        if self._mode == "http" and self._http_client:
            resp = await self._http_client.get(f"/v2/orders/{order_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return AlpacaOrder.from_api(resp.json())

        return None

    async def get_orders(
        self,
        status: str = "all",
        limit: int = 100,
        after: Optional[str] = None,
    ) -> list[AlpacaOrder]:
        """Get orders."""
        if self._mode == "http" and self._http_client:
            params: dict[str, Any] = {"status": status, "limit": limit}
            if after:
                params["after"] = after
            resp = await self._http_client.get("/v2/orders", params=params)
            resp.raise_for_status()
            return [AlpacaOrder.from_api(o) for o in resp.json()]

        return []

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if self._mode == "http" and self._http_client:
            resp = await self._http_client.delete(f"/v2/orders/{order_id}")
            return resp.status_code in (200, 204)

        return True

    async def cancel_all_orders(self) -> int:
        """Cancel all open orders. Returns count of canceled orders."""
        if self._mode == "http" and self._http_client:
            resp = await self._http_client.delete("/v2/orders")
            if resp.status_code in (200, 207):
                return len(resp.json()) if resp.text else 0
            return 0

        return 0

    # ── Market Data ──────────────────────────────────────────────────

    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 100,
    ) -> list[AlpacaBar]:
        """Get historical bars."""
        if self._mode == "http":
            data_client = httpx.AsyncClient(
                base_url=self._config.data_url,
                headers={
                    "APCA-API-KEY-ID": self._config.api_key,
                    "APCA-API-SECRET-KEY": self._config.api_secret,
                },
                timeout=self._config.request_timeout,
            )
            try:
                params: dict[str, Any] = {
                    "timeframe": timeframe,
                    "limit": limit,
                    "feed": self._config.data_feed,
                }
                if start:
                    params["start"] = start
                if end:
                    params["end"] = end
                resp = await data_client.get(
                    f"/v2/stocks/{symbol}/bars", params=params
                )
                resp.raise_for_status()
                bars_data = resp.json().get("bars", [])
                return [AlpacaBar.from_api(b) for b in bars_data]
            finally:
                await data_client.aclose()

        return self._demo_bars(symbol, limit)

    async def get_snapshot(self, symbol: str) -> AlpacaSnapshot:
        """Get latest snapshot for a symbol."""
        if self._mode == "http":
            data_client = httpx.AsyncClient(
                base_url=self._config.data_url,
                headers={
                    "APCA-API-KEY-ID": self._config.api_key,
                    "APCA-API-SECRET-KEY": self._config.api_secret,
                },
                timeout=self._config.request_timeout,
            )
            try:
                resp = await data_client.get(
                    f"/v2/stocks/{symbol}/snapshot",
                    params={"feed": self._config.data_feed},
                )
                resp.raise_for_status()
                return AlpacaSnapshot.from_api(resp.json(), symbol=symbol)
            finally:
                await data_client.aclose()

        return self._demo_snapshot(symbol)

    async def get_latest_quote(self, symbol: str) -> AlpacaQuote:
        """Get latest quote for a symbol."""
        if self._mode == "http":
            data_client = httpx.AsyncClient(
                base_url=self._config.data_url,
                headers={
                    "APCA-API-KEY-ID": self._config.api_key,
                    "APCA-API-SECRET-KEY": self._config.api_secret,
                },
                timeout=self._config.request_timeout,
            )
            try:
                resp = await data_client.get(
                    f"/v2/stocks/{symbol}/quotes/latest",
                    params={"feed": self._config.data_feed},
                )
                resp.raise_for_status()
                data = resp.json().get("quote", resp.json())
                return AlpacaQuote.from_api(data, symbol=symbol)
            finally:
                await data_client.aclose()

        return AlpacaQuote(
            symbol=symbol,
            bid_price=184.50 if symbol == "AAPL" else 100.0,
            ask_price=185.00 if symbol == "AAPL" else 100.10,
            bid_size=100,
            ask_size=100,
        )

    # ── Clock & Calendar ─────────────────────────────────────────────

    async def get_clock(self) -> dict:
        """Get market clock."""
        if self._mode == "http" and self._http_client:
            resp = await self._http_client.get("/v2/clock")
            resp.raise_for_status()
            return resp.json()

        now = datetime.now(timezone.utc)
        return {
            "timestamp": now.isoformat(),
            "is_open": now.weekday() < 5 and 13 <= now.hour < 20,
            "next_open": (now + timedelta(hours=1)).isoformat(),
            "next_close": (now + timedelta(hours=4)).isoformat(),
        }

    async def get_calendar(
        self, start: Optional[str] = None, end: Optional[str] = None
    ) -> list[dict]:
        """Get market calendar."""
        if self._mode == "http" and self._http_client:
            params = {}
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            resp = await self._http_client.get("/v2/calendar", params=params)
            resp.raise_for_status()
            return resp.json()

        return []

    # ── Assets ───────────────────────────────────────────────────────

    async def get_asset(self, symbol: str) -> Optional[dict]:
        """Get asset information."""
        if self._mode == "http" and self._http_client:
            resp = await self._http_client.get(f"/v2/assets/{symbol}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()

        return {
            "id": uuid.uuid4().hex,
            "symbol": symbol,
            "name": symbol,
            "exchange": "NASDAQ",
            "asset_class": "us_equity",
            "tradable": True,
            "fractionable": True,
            "shortable": True,
            "easy_to_borrow": True,
            "status": "active",
        }

    # ── Demo Data ────────────────────────────────────────────────────

    def _demo_account(self) -> AlpacaAccount:
        return AlpacaAccount(
            account_id="demo_account",
            status="ACTIVE",
            cash=50000.0,
            portfolio_value=87400.0,
            buying_power=90000.0,
            day_trading_buying_power=180000.0,
            equity=87400.0,
            last_equity=86900.0,
            long_market_value=37400.0,
            pattern_day_trader=False,
        )

    def _demo_positions(self) -> list[AlpacaPosition]:
        return [
            AlpacaPosition(
                symbol="AAPL", qty=100, avg_entry_price=150.0,
                current_price=185.0, market_value=18500.0,
                cost_basis=15000.0, unrealized_pl=3500.0,
                unrealized_plpc=0.2333, side="long",
            ),
            AlpacaPosition(
                symbol="MSFT", qty=50, avg_entry_price=350.0,
                current_price=378.0, market_value=18900.0,
                cost_basis=17500.0, unrealized_pl=1400.0,
                unrealized_plpc=0.08, side="long",
            ),
        ]

    def _demo_order(self, data: dict) -> AlpacaOrder:
        return AlpacaOrder(
            order_id=uuid.uuid4().hex[:12],
            client_order_id=data.get("client_order_id", uuid.uuid4().hex[:8]),
            symbol=data.get("symbol", ""),
            qty=float(data.get("qty", 0)),
            filled_qty=float(data.get("qty", 0)),
            filled_avg_price=185.0,
            order_type=data.get("type", "market"),
            side=data.get("side", "buy"),
            time_in_force=data.get("time_in_force", "day"),
            status="filled" if data.get("type") == "market" else "new",
        )

    def _demo_bars(self, symbol: str, limit: int) -> list[AlpacaBar]:
        import random
        random.seed(hash(symbol))
        base = 185.0 if symbol == "AAPL" else 378.0 if symbol == "MSFT" else 150.0
        bars = []
        for i in range(min(limit, 30)):
            change = random.uniform(-0.02, 0.02)
            o = base * (1 + change)
            c = o * (1 + random.uniform(-0.015, 0.015))
            h = max(o, c) * (1 + random.uniform(0, 0.01))
            lo = min(o, c) * (1 - random.uniform(0, 0.01))
            bars.append(AlpacaBar(
                open=round(o, 2), high=round(h, 2),
                low=round(lo, 2), close=round(c, 2),
                volume=random.randint(10_000_000, 60_000_000),
            ))
            base = c
        return bars

    def _demo_snapshot(self, symbol: str) -> AlpacaSnapshot:
        prices = {"AAPL": 185.0, "MSFT": 378.0, "GOOGL": 141.0}
        price = prices.get(symbol, 150.0)
        return AlpacaSnapshot(
            symbol=symbol,
            latest_trade_price=price,
            latest_trade_size=100,
            latest_quote_bid=price - 0.25,
            latest_quote_ask=price + 0.25,
        )
