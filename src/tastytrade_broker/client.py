"""tastytrade REST API Client (PRD-158).

Lightweight HTTP client for tastytrade's Trading & Market Data APIs.
Options-specialist broker with session-based auth, deep options chain
analytics, futures, and crypto support.

Uses tastytrade SDK when available, falls back to httpx session, then demo mode.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, date, timedelta
from enum import Enum
from typing import Any, Optional
import json
import logging
import uuid

logger = logging.getLogger(__name__)

# Try importing tastytrade SDK; fall back to raw HTTP
_HAS_TASTYTRADE_SDK = False
try:
    import tastytrade as tastytrade_sdk
    _HAS_TASTYTRADE_SDK = True
except ImportError:
    tastytrade_sdk = None  # type: ignore

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
class TastytradeConfig:
    """Configuration for tastytrade API connection.

    tastytrade uses session-based authentication (username/password -> session token),
    not OAuth2. Supports production and sandbox (certification) environments.
    """
    username: str = ""
    password: str = ""
    # API endpoints
    api_url: str = "https://api.tastyworks.com"
    sandbox_url: str = "https://api.cert.tastyworks.com"
    sandbox: bool = True
    # Session tokens (populated after login)
    session_token: str = ""
    remember_token: str = ""
    # Rate limiting
    max_requests_per_minute: int = 60
    request_timeout: int = 30
    # Retry
    max_retries: int = 3
    retry_delay: float = 1.0

    @property
    def base_url(self) -> str:
        """Return the appropriate API URL based on sandbox flag."""
        return self.sandbox_url if self.sandbox else self.api_url


# =====================================================================
# Response Models
# =====================================================================


@dataclass
class TastytradeAccount:
    """tastytrade account information."""
    account_number: str = ""
    account_type: str = "Individual"
    nickname: str = ""
    day_trader_status: bool = False
    is_margin: bool = False
    net_liquidating_value: float = 0.0
    cash_balance: float = 0.0
    equity_buying_power: float = 0.0
    derivative_buying_power: float = 0.0
    option_level: int = 1
    futures_enabled: bool = False

    @classmethod
    def from_api(cls, data: dict) -> "TastytradeAccount":
        acct = data.get("account", data)
        balances = data.get("balances", acct.get("balance-snapshots", {}))
        return cls(
            account_number=str(acct.get("account-number", acct.get("accountNumber", ""))),
            account_type=acct.get("account-type-name", acct.get("account-type", "Individual")),
            nickname=acct.get("nickname", ""),
            day_trader_status=acct.get("day-trader-status", acct.get("is-day-trader", False)),
            is_margin=acct.get("margin-or-cash", "").lower() == "margin" if isinstance(acct.get("margin-or-cash"), str) else acct.get("is-margin", False),
            net_liquidating_value=float(balances.get("net-liquidating-value", balances.get("netLiquidatingValue", 0))),
            cash_balance=float(balances.get("cash-balance", balances.get("cashBalance", 0))),
            equity_buying_power=float(balances.get("equity-buying-power", balances.get("equityBuyingPower", 0))),
            derivative_buying_power=float(balances.get("derivative-buying-power", balances.get("derivativeBuyingPower", 0))),
            option_level=int(acct.get("option-level", acct.get("optionLevel", 1))),
            futures_enabled=acct.get("futures-enabled", acct.get("futuresEnabled", False)),
        )

    def to_dict(self) -> dict:
        return {
            "account_number": self.account_number,
            "account_type": self.account_type,
            "nickname": self.nickname,
            "day_trader_status": self.day_trader_status,
            "is_margin": self.is_margin,
            "net_liquidating_value": self.net_liquidating_value,
            "cash_balance": self.cash_balance,
            "equity_buying_power": self.equity_buying_power,
            "derivative_buying_power": self.derivative_buying_power,
            "option_level": self.option_level,
            "futures_enabled": self.futures_enabled,
        }


@dataclass
class TastytradePosition:
    """tastytrade position (equity, option, future, or crypto)."""
    symbol: str = ""
    instrument_type: str = "Equity"  # Equity, Equity Option, Future, Cryptocurrency
    quantity: float = 0.0
    average_open_price: float = 0.0
    close_price: float = 0.0
    mark_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    realized_pnl: float = 0.0
    multiplier: int = 1  # 100 for options, 1 for equity
    direction: str = "long"  # long or short

    @classmethod
    def from_api(cls, data: dict) -> "TastytradePosition":
        qty = float(data.get("quantity", data.get("quantity-direction", 0)))
        avg_price = float(data.get("average-open-price", data.get("averageOpenPrice", 0)))
        mark = float(data.get("mark-price", data.get("mark", data.get("close-price", 0))))
        instrument_type = data.get("instrument-type", data.get("instrumentType", "Equity"))
        multiplier = 100 if "Option" in instrument_type else 1
        direction = "long" if qty > 0 else "short"
        abs_qty = abs(qty)
        cost = avg_price * abs_qty * multiplier
        current = mark * abs_qty * multiplier
        unrealized = current - cost if direction == "long" else cost - current
        pct = (unrealized / cost * 100) if cost > 0 else 0.0

        return cls(
            symbol=data.get("symbol", data.get("underlying-symbol", "")),
            instrument_type=instrument_type,
            quantity=abs_qty,
            average_open_price=avg_price,
            close_price=float(data.get("close-price", data.get("closePrice", 0))),
            mark_price=mark,
            unrealized_pnl=round(unrealized, 2),
            unrealized_pnl_pct=round(pct, 2),
            realized_pnl=float(data.get("realized-day-gain", data.get("realizedPnl", 0))),
            multiplier=multiplier,
            direction=direction,
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "instrument_type": self.instrument_type,
            "quantity": self.quantity,
            "average_open_price": self.average_open_price,
            "close_price": self.close_price,
            "mark_price": self.mark_price,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "realized_pnl": self.realized_pnl,
            "multiplier": self.multiplier,
            "direction": self.direction,
        }


@dataclass
class TastytradeOrder:
    """tastytrade order with multi-leg support."""
    order_id: str = ""
    account_number: str = ""
    symbol: str = ""
    order_type: str = "Limit"  # Limit, Market, Stop, Stop Limit
    time_in_force: str = "Day"  # Day, GTC, GTD, IOC
    price: float = 0.0
    size: float = 0.0
    filled_size: float = 0.0
    status: str = "Received"  # Received, Live, Filled, Cancelled, Rejected, Expired
    legs: list = field(default_factory=list)  # Multi-leg order legs
    order_class: str = "single"  # single, spread, combo

    @classmethod
    def from_api(cls, data: dict) -> "TastytradeOrder":
        legs_data = data.get("legs", data.get("order-legs", []))
        first_leg = legs_data[0] if legs_data else {}
        instrument = first_leg.get("instrument", first_leg)
        symbol = instrument.get("symbol", data.get("underlying-symbol", ""))

        # Determine order class from leg count
        leg_count = len(legs_data)
        if leg_count <= 1:
            order_class = "single"
        elif leg_count == 2:
            order_class = "spread"
        else:
            order_class = "combo"

        return cls(
            order_id=str(data.get("id", data.get("order-id", ""))),
            account_number=str(data.get("account-number", data.get("accountNumber", ""))),
            symbol=symbol,
            order_type=data.get("order-type", data.get("orderType", "Limit")),
            time_in_force=data.get("time-in-force", data.get("timeInForce", "Day")),
            price=float(data.get("price", data.get("limit-price", 0))),
            size=float(first_leg.get("quantity", data.get("size", 0))),
            filled_size=float(data.get("filled-quantity", data.get("filledSize", 0))),
            status=data.get("status", "Received"),
            legs=[
                {
                    "symbol": leg.get("symbol", leg.get("instrument", {}).get("symbol", "")),
                    "action": leg.get("action", "Buy to Open"),
                    "quantity": float(leg.get("quantity", 0)),
                    "instrument_type": leg.get("instrument-type", leg.get("instrumentType", "Equity")),
                }
                for leg in legs_data
            ],
            order_class=order_class,
        )

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "account_number": self.account_number,
            "symbol": self.symbol,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "price": self.price,
            "size": self.size,
            "filled_size": self.filled_size,
            "status": self.status,
            "legs": self.legs,
            "order_class": self.order_class,
        }


@dataclass
class TastytradeQuote:
    """Real-time quote from tastytrade (options-focused with IV metrics)."""
    symbol: str = ""
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    change: float = 0.0
    change_pct: float = 0.0
    iv_rank: float = 0.0  # IV Rank (0-100) — options-focused
    iv_percentile: float = 0.0  # IV Percentile (0-100) — options-focused

    @classmethod
    def from_api(cls, data: dict, symbol: str = "") -> "TastytradeQuote":
        quote = data.get("quote", data)
        return cls(
            symbol=symbol or data.get("symbol", quote.get("symbol", "")),
            bid=float(quote.get("bid", quote.get("bidPrice", 0))),
            ask=float(quote.get("ask", quote.get("askPrice", 0))),
            last=float(quote.get("last", quote.get("lastPrice", 0))),
            open=float(quote.get("open", quote.get("openPrice", 0))),
            high=float(quote.get("high", quote.get("highPrice", 0))),
            low=float(quote.get("low", quote.get("lowPrice", 0))),
            close=float(quote.get("close", quote.get("closePrice", 0))),
            volume=int(quote.get("volume", quote.get("totalVolume", 0))),
            change=float(quote.get("net-change", quote.get("netChange", 0))),
            change_pct=float(quote.get("net-change-pct", quote.get("netChangePct", 0))),
            iv_rank=float(quote.get("implied-volatility-rank", quote.get("ivRank", 0))),
            iv_percentile=float(quote.get("implied-volatility-percentile", quote.get("ivPercentile", 0))),
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "change": self.change,
            "change_pct": self.change_pct,
            "iv_rank": self.iv_rank,
            "iv_percentile": self.iv_percentile,
        }


@dataclass
class TastytradeCandle:
    """OHLCV candle from tastytrade price history."""
    timestamp: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0

    @classmethod
    def from_api(cls, data: dict) -> "TastytradeCandle":
        return cls(
            timestamp=str(data.get("datetime", data.get("time", ""))),
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


# =====================================================================
# Session Management (tastytrade uses session tokens, not OAuth2)
# =====================================================================


class _SessionManager:
    """Handles session-based authentication for tastytrade API.

    tastytrade uses username/password to obtain a session token,
    which is then sent in the Authorization header for all requests.
    """

    def __init__(self, config: TastytradeConfig):
        self._config = config
        self._session_token: str = config.session_token
        self._remember_token: str = config.remember_token
        self._valid = False

    @property
    def session_token(self) -> str:
        return self._session_token

    @property
    def is_valid(self) -> bool:
        return self._valid and bool(self._session_token)

    async def login(self, username: str, password: str) -> str:
        """Authenticate with tastytrade and obtain a session token.

        Args:
            username: tastytrade username or email.
            password: tastytrade password.

        Returns:
            Session token string.
        """
        if not _HAS_HTTPX:
            return ""
        try:
            async with httpx.AsyncClient(timeout=self._config.request_timeout) as client:
                resp = await client.post(
                    f"{self._config.base_url}/sessions",
                    json={
                        "login": username,
                        "password": password,
                        "remember-me": True,
                    },
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code in (200, 201):
                    body = resp.json()
                    data = body.get("data", body)
                    self._session_token = data.get("session-token", data.get("sessionToken", ""))
                    self._remember_token = data.get("remember-token", data.get("rememberToken", ""))
                    self._valid = True
                    return self._session_token
                else:
                    logger.warning(f"tastytrade login failed: {resp.status_code}")
        except Exception as e:
            logger.warning(f"tastytrade login error: {e}")
        return ""

    async def validate_session(self) -> bool:
        """Validate that the current session token is still active."""
        if not self._session_token or not _HAS_HTTPX:
            return False
        try:
            async with httpx.AsyncClient(timeout=self._config.request_timeout) as client:
                resp = await client.post(
                    f"{self._config.base_url}/sessions/validate",
                    headers=self.auth_headers(),
                )
                self._valid = resp.status_code == 200
                return self._valid
        except Exception as e:
            logger.warning(f"Session validation failed: {e}")
            self._valid = False
        return False

    async def destroy_session(self) -> None:
        """Destroy the current session (logout)."""
        if not self._session_token or not _HAS_HTTPX:
            self._session_token = ""
            self._valid = False
            return
        try:
            async with httpx.AsyncClient(timeout=self._config.request_timeout) as client:
                await client.delete(
                    f"{self._config.base_url}/sessions",
                    headers=self.auth_headers(),
                )
        except Exception as e:
            logger.warning(f"Session destroy failed: {e}")
        finally:
            self._session_token = ""
            self._remember_token = ""
            self._valid = False

    def auth_headers(self) -> dict[str, str]:
        """Return headers with the session token for authenticated requests."""
        return {"Authorization": self._session_token}


# =====================================================================
# Client
# =====================================================================


class TastytradeClient:
    """tastytrade REST API client.

    Options-specialist broker with support for equities, options, futures,
    and crypto. Supports tastytrade SDK, raw HTTP with session auth, and
    demo mode fallback.

    Example:
        client = TastytradeClient(TastytradeConfig(username="...", password="..."))
        await client.connect()
        accounts = await client.get_accounts()
        chain = await client.get_option_chain("SPY", "2025-03-21")
    """

    def __init__(self, config: TastytradeConfig):
        self._config = config
        self._connected = False
        self._http_client: Any = None
        self._sdk_client: Any = None
        self._mode: str = "demo"  # "sdk", "http", or "demo"
        self._session_mgr = _SessionManager(config)
        self._request_count = 0

    @property
    def config(self) -> TastytradeConfig:
        return self._config

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def mode(self) -> str:
        return self._mode

    # -- Connection --------------------------------------------------------

    async def connect(self) -> bool:
        """Connect to tastytrade API.

        Tries SDK first, then raw HTTP with session auth, falls back to demo mode.
        """
        if not self._config.username or not self._config.password:
            logger.info("No tastytrade credentials -- using demo mode")
            self._mode = "demo"
            self._connected = True
            return True

        # Try tastytrade SDK
        if _HAS_TASTYTRADE_SDK:
            try:
                self._sdk_client = tastytrade_sdk.Session(
                    self._config.username,
                    self._config.password,
                    is_test=self._config.sandbox,
                )
                self._mode = "sdk"
                self._connected = True
                logger.info("Connected to tastytrade via SDK")
                return True
            except Exception as e:
                logger.warning(f"SDK connection failed: {e}")

        # Try raw HTTP with session auth
        if _HAS_HTTPX:
            try:
                token = await self._session_mgr.login(
                    self._config.username,
                    self._config.password,
                )
                if token:
                    self._http_client = httpx.AsyncClient(
                        timeout=self._config.request_timeout,
                    )
                    self._mode = "http"
                    self._connected = True
                    logger.info("Connected to tastytrade via HTTP/session")
                    return True
                else:
                    logger.warning("Session login returned no token")
            except Exception as e:
                logger.warning(f"HTTP connection failed: {e}")

        # Fallback to demo
        self._mode = "demo"
        self._connected = True
        logger.info("Using tastytrade demo mode (no live API)")
        return True

    async def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        if self._mode == "http":
            await self._session_mgr.destroy_session()
        if self._http_client and hasattr(self._http_client, "aclose"):
            await self._http_client.aclose()
        self._http_client = None
        self._sdk_client = None
        self._connected = False
        self._mode = "demo"
        logger.info("Disconnected from tastytrade")

    async def _ensure_session(self) -> None:
        """Validate session and re-login if needed (HTTP mode)."""
        if self._mode == "http" and not self._session_mgr.is_valid:
            is_valid = await self._session_mgr.validate_session()
            if not is_valid and self._config.username and self._config.password:
                await self._session_mgr.login(
                    self._config.username,
                    self._config.password,
                )

    # -- Accounts ----------------------------------------------------------

    async def get_accounts(self) -> list[TastytradeAccount]:
        """Get all linked accounts."""
        if self._mode == "http" and self._http_client:
            await self._ensure_session()
            resp = await self._http_client.get(
                f"{self._config.base_url}/customers/me/accounts",
                headers=self._session_mgr.auth_headers(),
            )
            resp.raise_for_status()
            items = resp.json().get("data", {}).get("items", [])
            return [TastytradeAccount.from_api(a) for a in items]

        return self._demo_accounts()

    async def get_positions(self, account_number: str) -> list[TastytradePosition]:
        """Get positions for a specific account.

        Returns equity, option, futures, and crypto positions.
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_session()
            resp = await self._http_client.get(
                f"{self._config.base_url}/accounts/{account_number}/positions",
                headers=self._session_mgr.auth_headers(),
            )
            resp.raise_for_status()
            items = resp.json().get("data", {}).get("items", [])
            return [TastytradePosition.from_api(p) for p in items]

        return self._demo_positions()

    async def get_orders(
        self, account_number: str, status: str = "Filled"
    ) -> list[TastytradeOrder]:
        """Get orders for a specific account.

        Args:
            account_number: tastytrade account number.
            status: Filter by status (Received, Live, Filled, Cancelled, etc.).
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_session()
            resp = await self._http_client.get(
                f"{self._config.base_url}/accounts/{account_number}/orders",
                params={"status": status},
                headers=self._session_mgr.auth_headers(),
            )
            resp.raise_for_status()
            items = resp.json().get("data", {}).get("items", [])
            return [TastytradeOrder.from_api(o) for o in items]

        return self._demo_orders()

    async def place_order(
        self, account_number: str, order: dict
    ) -> TastytradeOrder:
        """Submit an order (single-leg).

        Args:
            account_number: tastytrade account number.
            order: Order specification dict with keys like order-type,
                   time-in-force, price, legs, etc.
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_session()
            resp = await self._http_client.post(
                f"{self._config.base_url}/accounts/{account_number}/orders",
                json=order,
                headers=self._session_mgr.auth_headers(),
            )
            resp.raise_for_status()
            data = resp.json().get("data", resp.json())
            return TastytradeOrder.from_api(data)

        return self._demo_place_order(order)

    async def place_complex_order(
        self, account_number: str, legs: list[dict]
    ) -> TastytradeOrder:
        """Submit a multi-leg options order (spread, strangle, iron condor, etc.).

        Args:
            account_number: tastytrade account number.
            legs: List of order leg dicts, each containing:
                  symbol, action (Buy to Open, Sell to Open, etc.),
                  quantity, instrument-type.
        """
        order = {
            "order-type": "Limit",
            "time-in-force": "Day",
            "price": 0.0,
            "legs": legs,
        }
        if self._mode == "http" and self._http_client:
            await self._ensure_session()
            resp = await self._http_client.post(
                f"{self._config.base_url}/accounts/{account_number}/orders",
                json=order,
                headers=self._session_mgr.auth_headers(),
            )
            resp.raise_for_status()
            data = resp.json().get("data", resp.json())
            return TastytradeOrder.from_api(data)

        return self._demo_place_complex_order(legs)

    async def cancel_order(self, account_number: str, order_id: str) -> bool:
        """Cancel an order.

        Args:
            account_number: tastytrade account number.
            order_id: Order ID to cancel.
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_session()
            resp = await self._http_client.delete(
                f"{self._config.base_url}/accounts/{account_number}/orders/{order_id}",
                headers=self._session_mgr.auth_headers(),
            )
            return resp.status_code in (200, 204)

        return True

    # -- Market Data -------------------------------------------------------

    async def get_quote(self, symbols: list[str]) -> list[TastytradeQuote]:
        """Get quotes for a list of symbols (includes IV rank/percentile).

        Args:
            symbols: List of symbols (equities, options, futures, crypto).
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_session()
            resp = await self._http_client.get(
                f"{self._config.base_url}/market-data",
                params={"symbols": ",".join(symbols)},
                headers=self._session_mgr.auth_headers(),
            )
            resp.raise_for_status()
            items = resp.json().get("data", {}).get("items", [])
            return [TastytradeQuote.from_api(item) for item in items]

        return self._demo_quotes(symbols)

    async def get_price_history(
        self,
        symbol: str,
        period: str = "1m",
    ) -> list[TastytradeCandle]:
        """Get price history (OHLCV candles).

        Args:
            symbol: Symbol to retrieve history for.
            period: Time period ('1d', '1w', '1m', '3m', '6m', '1y').
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_session()
            resp = await self._http_client.get(
                f"{self._config.base_url}/market-data/{symbol}/history",
                params={"period": period},
                headers=self._session_mgr.auth_headers(),
            )
            resp.raise_for_status()
            candles = resp.json().get("data", {}).get("items", [])
            return [TastytradeCandle.from_api(c) for c in candles]

        return self._demo_candles(symbol)

    async def get_option_chain(
        self, symbol: str, expiration_date: str = ""
    ) -> dict:
        """Get options chain for a symbol with deep chain data.

        Args:
            symbol: Underlying symbol (e.g., "SPY", "AAPL").
            expiration_date: Optional specific expiration (YYYY-MM-DD).
                            If empty, returns nearest expiration.

        Returns:
            Dict with chain data including greeks, bid/ask, OI, volume.
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_session()
            params: dict[str, Any] = {}
            if expiration_date:
                params["expiration-date"] = expiration_date
            resp = await self._http_client.get(
                f"{self._config.base_url}/option-chains/{symbol}/nested",
                params=params,
                headers=self._session_mgr.auth_headers(),
            )
            resp.raise_for_status()
            return resp.json()

        return self._demo_option_chain(symbol)

    async def get_futures_products(self) -> list[dict]:
        """List available futures products.

        Returns:
            List of dicts with futures product info (symbol, description, exchange).
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_session()
            resp = await self._http_client.get(
                f"{self._config.base_url}/instruments/future-products",
                headers=self._session_mgr.auth_headers(),
            )
            resp.raise_for_status()
            return resp.json().get("data", {}).get("items", [])

        return self._demo_futures_products()

    async def get_crypto_quotes(self, symbols: list[str]) -> list[TastytradeQuote]:
        """Get crypto quotes (BTC/USD, ETH/USD, etc.).

        Args:
            symbols: List of crypto symbols (e.g., ["BTC/USD", "ETH/USD"]).
        """
        if self._mode == "http" and self._http_client:
            await self._ensure_session()
            resp = await self._http_client.get(
                f"{self._config.base_url}/market-data",
                params={"symbols": ",".join(symbols)},
                headers=self._session_mgr.auth_headers(),
            )
            resp.raise_for_status()
            items = resp.json().get("data", {}).get("items", [])
            return [TastytradeQuote.from_api(item) for item in items]

        return self._demo_crypto_quotes(symbols)

    # -- Demo Data ---------------------------------------------------------

    def _demo_accounts(self) -> list[TastytradeAccount]:
        return [
            TastytradeAccount(
                account_number="DEMO-5YT12345",
                account_type="Individual",
                nickname="Options Trading",
                day_trader_status=False,
                is_margin=True,
                net_liquidating_value=185000.0,
                cash_balance=72000.0,
                equity_buying_power=144000.0,
                derivative_buying_power=72000.0,
                option_level=4,
                futures_enabled=True,
            ),
        ]

    def _demo_positions(self) -> list[TastytradePosition]:
        return [
            TastytradePosition(
                symbol="AAPL",
                instrument_type="Equity",
                quantity=200,
                average_open_price=218.50,
                close_price=230.75,
                mark_price=230.75,
                unrealized_pnl=2450.0,
                unrealized_pnl_pct=5.61,
                realized_pnl=0.0,
                multiplier=1,
                direction="long",
            ),
            TastytradePosition(
                symbol="SPY  250321P00580000",
                instrument_type="Equity Option",
                quantity=5,
                average_open_price=4.20,
                close_price=3.85,
                mark_price=3.85,
                unrealized_pnl=-175.0,
                unrealized_pnl_pct=-8.33,
                realized_pnl=0.0,
                multiplier=100,
                direction="long",
            ),
            TastytradePosition(
                symbol="/ESH5",
                instrument_type="Future",
                quantity=2,
                average_open_price=5875.00,
                close_price=5920.50,
                mark_price=5920.50,
                unrealized_pnl=4550.0,
                unrealized_pnl_pct=3.87,
                realized_pnl=0.0,
                multiplier=1,
                direction="long",
            ),
            TastytradePosition(
                symbol="BTC/USD",
                instrument_type="Cryptocurrency",
                quantity=0.5,
                average_open_price=95000.0,
                close_price=101500.0,
                mark_price=101500.0,
                unrealized_pnl=3250.0,
                unrealized_pnl_pct=6.84,
                realized_pnl=0.0,
                multiplier=1,
                direction="long",
            ),
        ]

    def _demo_orders(self) -> list[TastytradeOrder]:
        return [
            TastytradeOrder(
                order_id="DEMO-TT-001", account_number="DEMO-5YT12345",
                symbol="AAPL", order_type="Limit", time_in_force="Day",
                price=218.50, size=200, filled_size=200, status="Filled",
                legs=[{"symbol": "AAPL", "action": "Buy to Open", "quantity": 200, "instrument_type": "Equity"}],
                order_class="single",
            ),
            TastytradeOrder(
                order_id="DEMO-TT-002", account_number="DEMO-5YT12345",
                symbol="SPY", order_type="Limit", time_in_force="Day",
                price=1.25, size=10, filled_size=10, status="Filled",
                legs=[
                    {"symbol": "SPY  250321P00580000", "action": "Buy to Open", "quantity": 10, "instrument_type": "Equity Option"},
                    {"symbol": "SPY  250321P00570000", "action": "Sell to Open", "quantity": 10, "instrument_type": "Equity Option"},
                ],
                order_class="spread",
            ),
            TastytradeOrder(
                order_id="DEMO-TT-003", account_number="DEMO-5YT12345",
                symbol="/ES", order_type="Market", time_in_force="Day",
                price=5875.0, size=2, filled_size=2, status="Filled",
                legs=[{"symbol": "/ESH5", "action": "Buy to Open", "quantity": 2, "instrument_type": "Future"}],
                order_class="single",
            ),
            TastytradeOrder(
                order_id="DEMO-TT-004", account_number="DEMO-5YT12345",
                symbol="SPY", order_type="Limit", time_in_force="GTC",
                price=2.80, size=5, filled_size=0, status="Live",
                legs=[
                    {"symbol": "SPY  250418C00600000", "action": "Sell to Open", "quantity": 5, "instrument_type": "Equity Option"},
                    {"symbol": "SPY  250418C00610000", "action": "Buy to Open", "quantity": 5, "instrument_type": "Equity Option"},
                    {"symbol": "SPY  250418P00570000", "action": "Sell to Open", "quantity": 5, "instrument_type": "Equity Option"},
                    {"symbol": "SPY  250418P00560000", "action": "Buy to Open", "quantity": 5, "instrument_type": "Equity Option"},
                ],
                order_class="combo",
            ),
        ]

    def _demo_place_order(self, order_request: dict) -> TastytradeOrder:
        legs = order_request.get("legs", [{}])
        first_leg = legs[0] if legs else {}
        symbol = first_leg.get("symbol", "AAPL")
        action = first_leg.get("action", "Buy to Open")
        qty = float(first_leg.get("quantity", 10))
        order_type = order_request.get("order-type", order_request.get("order_type", "Limit"))

        demo_prices = {
            "AAPL": 230.75, "SPY": 590.50, "MSFT": 415.30,
            "NVDA": 875.20, "GOOGL": 185.40, "QQQ": 510.80,
        }
        price = order_request.get("price", demo_prices.get(symbol, 100.0))

        return TastytradeOrder(
            order_id=f"DEMO-{uuid.uuid4().hex[:8].upper()}",
            account_number="DEMO-5YT12345",
            symbol=symbol,
            order_type=order_type,
            time_in_force=order_request.get("time-in-force", "Day"),
            price=float(price),
            size=qty,
            filled_size=qty if order_type == "Market" else 0,
            status="Filled" if order_type == "Market" else "Received",
            legs=[{
                "symbol": symbol,
                "action": action,
                "quantity": qty,
                "instrument_type": first_leg.get("instrument-type", "Equity"),
            }],
            order_class="single",
        )

    def _demo_place_complex_order(self, legs: list[dict]) -> TastytradeOrder:
        first_leg = legs[0] if legs else {}
        symbol = first_leg.get("symbol", "SPY")
        leg_count = len(legs)

        if leg_count <= 1:
            order_class = "single"
        elif leg_count == 2:
            order_class = "spread"
        else:
            order_class = "combo"

        return TastytradeOrder(
            order_id=f"DEMO-{uuid.uuid4().hex[:8].upper()}",
            account_number="DEMO-5YT12345",
            symbol=symbol.split()[0] if " " in symbol else symbol,
            order_type="Limit",
            time_in_force="Day",
            price=1.50,
            size=float(first_leg.get("quantity", 1)),
            filled_size=0,
            status="Received",
            legs=[
                {
                    "symbol": leg.get("symbol", ""),
                    "action": leg.get("action", "Buy to Open"),
                    "quantity": float(leg.get("quantity", 1)),
                    "instrument_type": leg.get("instrument-type", leg.get("instrument_type", "Equity Option")),
                }
                for leg in legs
            ],
            order_class=order_class,
        )

    def _demo_quotes(self, symbols: list[str]) -> list[TastytradeQuote]:
        demo_data = {
            "SPY": {"last": 590.50, "bid": 590.45, "ask": 590.55, "vol": 78500000, "net": 2.30, "pct": 0.39, "o": 588.0, "h": 591.5, "l": 587.5, "ivr": 22.5, "ivp": 35.8},
            "AAPL": {"last": 230.75, "bid": 230.70, "ask": 230.80, "vol": 55200000, "net": 1.85, "pct": 0.81, "o": 229.0, "h": 231.5, "l": 228.5, "ivr": 28.3, "ivp": 42.1},
            "MSFT": {"last": 415.30, "bid": 415.25, "ask": 415.35, "vol": 22100000, "net": -0.70, "pct": -0.17, "o": 416.0, "h": 417.0, "l": 414.0, "ivr": 18.7, "ivp": 31.2},
            "NVDA": {"last": 875.20, "bid": 875.10, "ask": 875.30, "vol": 42000000, "net": 12.50, "pct": 1.45, "o": 863.0, "h": 878.0, "l": 860.0, "ivr": 45.2, "ivp": 58.6},
            "GOOGL": {"last": 185.40, "bid": 185.35, "ask": 185.45, "vol": 28300000, "net": 0.90, "pct": 0.49, "o": 184.5, "h": 186.0, "l": 184.0, "ivr": 20.1, "ivp": 33.5},
            "QQQ": {"last": 510.80, "bid": 510.75, "ask": 510.85, "vol": 45000000, "net": 3.20, "pct": 0.63, "o": 507.5, "h": 511.5, "l": 506.8, "ivr": 24.8, "ivp": 38.2},
            "IWM": {"last": 225.60, "bid": 225.55, "ask": 225.65, "vol": 32000000, "net": 1.10, "pct": 0.49, "o": 224.5, "h": 226.0, "l": 224.0, "ivr": 30.5, "ivp": 45.0},
            "TSLA": {"last": 382.50, "bid": 382.40, "ask": 382.60, "vol": 38000000, "net": -8.20, "pct": -2.10, "o": 390.5, "h": 391.0, "l": 380.0, "ivr": 62.3, "ivp": 75.8},
        }
        result = []
        for s in symbols:
            d = demo_data.get(s, {
                "last": 100.0, "bid": 99.95, "ask": 100.05, "vol": 1000000,
                "net": 0.5, "pct": 0.5, "o": 99.5, "h": 100.5, "l": 99.0,
                "ivr": 25.0, "ivp": 40.0,
            })
            result.append(TastytradeQuote(
                symbol=s, last=d["last"], bid=d["bid"], ask=d["ask"],
                volume=d["vol"], change=d["net"], change_pct=d["pct"],
                open=d["o"], high=d["h"], low=d["l"], close=d["last"],
                iv_rank=d["ivr"], iv_percentile=d["ivp"],
            ))
        return result

    def _demo_candles(self, symbol: str, count: int = 30) -> list[TastytradeCandle]:
        import random
        random.seed(hash(symbol) % 2**31)
        demo_bases = {
            "SPY": 590.50, "AAPL": 230.75, "MSFT": 415.30,
            "NVDA": 875.20, "GOOGL": 185.40, "QQQ": 510.80,
        }
        base = demo_bases.get(symbol, 100.0)
        candles = []
        for i in range(count):
            change = random.uniform(-0.02, 0.02)
            o = base * (1 + change)
            c = o * (1 + random.uniform(-0.015, 0.015))
            h = max(o, c) * (1 + random.uniform(0, 0.01))
            lo = min(o, c) * (1 - random.uniform(0, 0.01))
            candles.append(TastytradeCandle(
                open=round(o, 2), high=round(h, 2),
                low=round(lo, 2), close=round(c, 2),
                volume=random.randint(10_000_000, 80_000_000),
            ))
            base = c
        return candles

    def _demo_option_chain(self, symbol: str) -> dict:
        demo_bases = {
            "SPY": 590.50, "AAPL": 230.75, "MSFT": 415.30,
            "NVDA": 875.20, "QQQ": 510.80,
        }
        base = demo_bases.get(symbol, 100.0)
        step = max(1.0, round(base * 0.01, 0))
        strikes = []
        for i in range(-10, 11):
            strike = round(base + i * step, 2)
            moneyness = (base - strike) / base
            call_delta = round(max(0.02, min(0.98, 0.50 + moneyness * 5.0)), 3)
            put_delta = round(call_delta - 1.0, 3)
            iv = round(0.22 + abs(moneyness) * 0.15, 4)

            call_intrinsic = max(0, base - strike)
            put_intrinsic = max(0, strike - base)
            time_value = max(0.05, base * 0.02 * (1 - abs(moneyness) * 3))

            call_mid = round(call_intrinsic + time_value, 2)
            put_mid = round(put_intrinsic + time_value, 2)
            spread = round(max(0.01, call_mid * 0.02), 2)

            strikes.append({
                "strike-price": strike,
                "call": {
                    "bid": round(max(0.01, call_mid - spread), 2),
                    "ask": round(max(0.02, call_mid + spread), 2),
                    "last": round(max(0.01, call_mid), 2),
                    "volume": max(10, 5000 - abs(i) * 400),
                    "open-interest": max(100, 15000 - abs(i) * 1200),
                    "greeks": {
                        "delta": call_delta,
                        "gamma": round(max(0.001, 0.04 * (1 - abs(moneyness) * 8)), 4),
                        "theta": round(-0.08 * (1 - abs(moneyness) * 3), 4),
                        "vega": round(max(0.01, 0.25 * (1 - abs(moneyness) * 5)), 4),
                        "rho": round(0.05 * call_delta, 4),
                        "implied-volatility": iv,
                    },
                },
                "put": {
                    "bid": round(max(0.01, put_mid - spread), 2),
                    "ask": round(max(0.02, put_mid + spread), 2),
                    "last": round(max(0.01, put_mid), 2),
                    "volume": max(10, 4500 - abs(i) * 350),
                    "open-interest": max(100, 13000 - abs(i) * 1000),
                    "greeks": {
                        "delta": put_delta,
                        "gamma": round(max(0.001, 0.04 * (1 - abs(moneyness) * 8)), 4),
                        "theta": round(-0.07 * (1 - abs(moneyness) * 3), 4),
                        "vega": round(max(0.01, 0.25 * (1 - abs(moneyness) * 5)), 4),
                        "rho": round(0.05 * put_delta, 4),
                        "implied-volatility": round(iv + 0.005, 4),
                    },
                },
            })

        return {
            "symbol": symbol,
            "underlying-price": base,
            "expiration-date": "2025-03-21",
            "days-to-expiration": 30,
            "strikes": strikes,
        }

    def _demo_futures_products(self) -> list[dict]:
        return [
            {
                "symbol": "/ES",
                "description": "E-mini S&P 500 Futures",
                "exchange": "CME",
                "tick_size": 0.25,
                "multiplier": 50,
                "active_months": ["H", "M", "U", "Z"],
            },
            {
                "symbol": "/NQ",
                "description": "E-mini Nasdaq-100 Futures",
                "exchange": "CME",
                "tick_size": 0.25,
                "multiplier": 20,
                "active_months": ["H", "M", "U", "Z"],
            },
            {
                "symbol": "/CL",
                "description": "Crude Oil Futures",
                "exchange": "NYMEX",
                "tick_size": 0.01,
                "multiplier": 1000,
                "active_months": ["F", "G", "H", "J", "K", "M", "N", "Q", "U", "V", "X", "Z"],
            },
            {
                "symbol": "/GC",
                "description": "Gold Futures",
                "exchange": "COMEX",
                "tick_size": 0.10,
                "multiplier": 100,
                "active_months": ["G", "J", "M", "Q", "V", "Z"],
            },
            {
                "symbol": "/ZB",
                "description": "30-Year U.S. Treasury Bond Futures",
                "exchange": "CBOT",
                "tick_size": 0.03125,
                "multiplier": 1000,
                "active_months": ["H", "M", "U", "Z"],
            },
            {
                "symbol": "/RTY",
                "description": "E-mini Russell 2000 Futures",
                "exchange": "CME",
                "tick_size": 0.10,
                "multiplier": 50,
                "active_months": ["H", "M", "U", "Z"],
            },
        ]

    def _demo_crypto_quotes(self, symbols: list[str]) -> list[TastytradeQuote]:
        demo_data = {
            "BTC/USD": {"last": 101500.0, "bid": 101480.0, "ask": 101520.0, "vol": 28500, "net": 2350.0, "pct": 2.37, "o": 99150.0, "h": 102000.0, "l": 98800.0, "ivr": 52.3, "ivp": 65.0},
            "ETH/USD": {"last": 3850.0, "bid": 3848.0, "ask": 3852.0, "vol": 145000, "net": 85.0, "pct": 2.26, "o": 3765.0, "h": 3880.0, "l": 3740.0, "ivr": 48.7, "ivp": 60.2},
            "SOL/USD": {"last": 195.50, "bid": 195.30, "ask": 195.70, "vol": 520000, "net": 8.20, "pct": 4.38, "o": 187.3, "h": 197.0, "l": 185.5, "ivr": 68.1, "ivp": 78.5},
            "DOGE/USD": {"last": 0.285, "bid": 0.2848, "ask": 0.2852, "vol": 2800000, "net": 0.012, "pct": 4.40, "o": 0.273, "h": 0.290, "l": 0.271, "ivr": 72.0, "ivp": 82.0},
        }
        result = []
        for s in symbols:
            d = demo_data.get(s, {
                "last": 50.0, "bid": 49.90, "ask": 50.10, "vol": 10000,
                "net": 1.0, "pct": 2.0, "o": 49.0, "h": 51.0, "l": 48.5,
                "ivr": 40.0, "ivp": 55.0,
            })
            result.append(TastytradeQuote(
                symbol=s, last=d["last"], bid=d["bid"], ask=d["ask"],
                volume=d["vol"], change=d["net"], change_pct=d["pct"],
                open=d["o"], high=d["h"], low=d["l"], close=d["last"],
                iv_rank=d["ivr"], iv_percentile=d["ivp"],
            ))
        return result
