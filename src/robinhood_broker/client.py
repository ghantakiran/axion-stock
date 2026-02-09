"""Robinhood REST API Client (PRD-143).

Lightweight client for Robinhood's Trading API.
Uses robin_stocks SDK when available, falls back to raw HTTP via requests,
then to demo mode when credentials are unavailable.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import json
import logging
import uuid

logger = logging.getLogger(__name__)

# Try importing robin_stocks SDK; fall back gracefully
_HAS_ROBIN_STOCKS = False
try:
    import robin_stocks.robinhood as rh
    _HAS_ROBIN_STOCKS = True
except ImportError:
    rh = None  # type: ignore

_HAS_REQUESTS = False
try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _requests = None  # type: ignore


# =====================================================================
# Configuration
# =====================================================================


@dataclass
class RobinhoodConfig:
    """Configuration for Robinhood API connection."""
    username: str = ""
    password: str = ""
    mfa_code: Optional[str] = None
    device_token: Optional[str] = None
    base_url: str = "https://api.robinhood.com"
    # Rate limiting
    max_requests_per_minute: int = 60
    request_timeout: int = 30
    # Retry
    max_retries: int = 3
    retry_delay: float = 1.0


# =====================================================================
# Response Models
# =====================================================================


@dataclass
class RobinhoodAccount:
    """Robinhood account information."""
    account_id: str = ""
    account_number: str = ""
    buying_power: float = 0.0
    equity: float = 0.0
    cash: float = 0.0
    margin_enabled: bool = False
    portfolio_value: float = 0.0
    withdrawable_amount: float = 0.0
    status: str = "active"

    @classmethod
    def from_api(cls, data: dict) -> "RobinhoodAccount":
        return cls(
            account_id=data.get("id", data.get("url", "")),
            account_number=data.get("account_number", ""),
            buying_power=float(data.get("buying_power", data.get("margin_balances", {}).get("unallocated_margin_cash", 0)) or 0),
            equity=float(data.get("equity", data.get("portfolio_value", 0)) or 0),
            cash=float(data.get("cash", data.get("cash_balances", {}).get("cash_available_for_withdrawal", 0)) or 0),
            margin_enabled=data.get("type", "") == "margin",
            portfolio_value=float(data.get("portfolio_value", data.get("equity", 0)) or 0),
            withdrawable_amount=float(data.get("cash_available_for_withdrawal", 0) or 0),
            status=data.get("state", data.get("status", "active")),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RobinhoodPosition:
    """Robinhood position."""
    symbol: str = ""
    instrument_id: str = ""
    quantity: float = 0.0
    average_cost: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    side: str = "long"

    @classmethod
    def from_api(cls, data: dict) -> "RobinhoodPosition":
        qty = float(data.get("quantity", 0) or 0)
        avg_cost = float(data.get("average_buy_price", data.get("average_cost", 0)) or 0)
        current = float(data.get("current_price", data.get("last_trade_price", 0)) or 0)
        market_val = qty * current if current > 0 else float(data.get("equity", 0) or 0)
        cost_basis = qty * avg_cost
        pnl = market_val - cost_basis if cost_basis > 0 else 0.0
        pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0

        return cls(
            symbol=data.get("symbol", data.get("ticker", "")),
            instrument_id=data.get("instrument_id", data.get("instrument", "")),
            quantity=qty,
            average_cost=avg_cost,
            current_price=current,
            market_value=round(market_val, 2),
            unrealized_pnl=round(pnl, 2),
            unrealized_pnl_pct=round(pnl_pct, 2),
            side="long" if qty > 0 else "short",
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RobinhoodOrder:
    """Robinhood order."""
    order_id: str = ""
    symbol: str = ""
    side: str = "buy"
    quantity: float = 0.0
    order_type: str = "market"
    time_in_force: str = "gfd"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: str = "unconfirmed"
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict) -> "RobinhoodOrder":
        return cls(
            order_id=data.get("id", ""),
            symbol=data.get("symbol", data.get("instrument_symbol", "")),
            side=data.get("side", "buy"),
            quantity=float(data.get("quantity", 0) or 0),
            order_type=data.get("type", data.get("order_type", "market")),
            time_in_force=data.get("time_in_force", "gfd"),
            limit_price=float(data["price"]) if data.get("price") else None,
            stop_price=float(data["stop_price"]) if data.get("stop_price") else None,
            status=data.get("state", data.get("status", "unconfirmed")),
            filled_quantity=float(data.get("cumulative_quantity", 0) or 0),
            average_fill_price=float(data.get("average_price", 0) or 0),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RobinhoodQuote:
    """Robinhood real-time quote."""
    symbol: str = ""
    bid_price: float = 0.0
    ask_price: float = 0.0
    last_trade_price: float = 0.0
    previous_close: float = 0.0
    volume: int = 0
    high: float = 0.0
    low: float = 0.0
    open_price: float = 0.0

    @classmethod
    def from_api(cls, data: dict) -> "RobinhoodQuote":
        return cls(
            symbol=data.get("symbol", data.get("trading_halted", {}).get("symbol", "")),
            bid_price=float(data.get("bid_price", 0) or 0),
            ask_price=float(data.get("ask_price", 0) or 0),
            last_trade_price=float(data.get("last_trade_price", data.get("last_extended_hours_trade_price", 0)) or 0),
            previous_close=float(data.get("previous_close", data.get("adjusted_previous_close", 0)) or 0),
            volume=int(float(data.get("volume", 0) or 0)),
            high=float(data.get("high", 0) or 0),
            low=float(data.get("low", 0) or 0),
            open_price=float(data.get("open", data.get("open_price", 0)) or 0),
        )

    def to_dict(self) -> dict:
        return asdict(self)


# =====================================================================
# Client
# =====================================================================


class RobinhoodClient:
    """Robinhood REST API client.

    Supports robin_stocks SDK, raw HTTP (requests), and demo mode backends.
    Falls back to demo data when no credentials or SDK available.

    Example:
        client = RobinhoodClient(RobinhoodConfig(username="...", password="..."))
        client.connect()
        account = client.get_account()
        positions = client.get_positions()
    """

    def __init__(self, config: Optional[RobinhoodConfig] = None):
        self._config = config or RobinhoodConfig()
        self._connected = False
        self._mode: str = "demo"  # "sdk", "http", or "demo"
        self._session: Any = None
        self._auth_token: Optional[str] = None
        self._request_count = 0

    @property
    def config(self) -> RobinhoodConfig:
        return self._config

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def mode(self) -> str:
        return self._mode

    def connect(self) -> bool:
        """Connect to Robinhood API.

        Tries robin_stocks SDK first, then raw HTTP, falls back to demo mode.
        Returns True when connected (always succeeds due to demo fallback).
        """
        if not self._config.username or not self._config.password:
            logger.info("No Robinhood credentials — using demo mode")
            self._mode = "demo"
            self._connected = True
            return True

        # Try robin_stocks SDK
        if _HAS_ROBIN_STOCKS:
            try:
                login_kwargs: dict[str, Any] = {
                    "username": self._config.username,
                    "password": self._config.password,
                }
                if self._config.mfa_code:
                    login_kwargs["mfa_code"] = self._config.mfa_code
                if self._config.device_token:
                    login_kwargs["device_token"] = self._config.device_token

                login_result = rh.login(**login_kwargs)
                if login_result and login_result.get("access_token"):
                    self._auth_token = login_result["access_token"]
                    self._mode = "sdk"
                    self._connected = True
                    logger.info("Connected to Robinhood via robin_stocks SDK")
                    return True
            except Exception as e:
                logger.warning(f"robin_stocks login failed: {e}")

        # Try raw HTTP
        if _HAS_REQUESTS:
            try:
                payload = {
                    "username": self._config.username,
                    "password": self._config.password,
                    "grant_type": "password",
                    "client_id": "c82SH0WZOsabOXGP2sxqcj34FxkvfnWRZBKlBjFS",
                    "scope": "internal",
                }
                if self._config.mfa_code:
                    payload["mfa_code"] = self._config.mfa_code
                if self._config.device_token:
                    payload["device_token"] = self._config.device_token

                resp = _requests.post(
                    f"{self._config.base_url}/oauth2/token/",
                    json=payload,
                    timeout=self._config.request_timeout,
                )
                if resp.status_code == 200:
                    token_data = resp.json()
                    self._auth_token = token_data.get("access_token")
                    if self._auth_token:
                        self._session = _requests.Session()
                        self._session.headers.update({
                            "Authorization": f"Bearer {self._auth_token}",
                            "Content-Type": "application/json",
                        })
                        self._mode = "http"
                        self._connected = True
                        logger.info("Connected to Robinhood via HTTP")
                        return True
                else:
                    logger.warning(f"HTTP auth failed: {resp.status_code}")
            except Exception as e:
                logger.warning(f"HTTP connection failed: {e}")

        # Fallback to demo
        self._mode = "demo"
        self._connected = True
        logger.info("Using Robinhood demo mode (no live API)")
        return True

    def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        if self._mode == "sdk" and _HAS_ROBIN_STOCKS:
            try:
                rh.logout()
            except Exception:
                pass
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
        self._session = None
        self._auth_token = None
        self._connected = False
        self._mode = "demo"
        logger.info("Disconnected from Robinhood")

    # ── Account ──────────────────────────────────────────────────────

    def get_account(self) -> RobinhoodAccount:
        """Get account information."""
        if self._mode == "sdk" and _HAS_ROBIN_STOCKS:
            try:
                profile = rh.profiles.load_account_profile()
                portfolio = rh.profiles.load_portfolio_profile()
                merged = {**(profile or {}), **(portfolio or {})}
                return RobinhoodAccount.from_api(merged)
            except Exception as e:
                logger.warning(f"SDK get_account failed: {e}")

        if self._mode == "http" and self._session:
            try:
                resp = self._session.get(
                    f"{self._config.base_url}/accounts/",
                    timeout=self._config.request_timeout,
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
                if results:
                    return RobinhoodAccount.from_api(results[0])
            except Exception as e:
                logger.warning(f"HTTP get_account failed: {e}")

        return self._demo_account()

    def get_positions(self) -> list[RobinhoodPosition]:
        """Get all open positions."""
        if self._mode == "sdk" and _HAS_ROBIN_STOCKS:
            try:
                positions = rh.account.get_open_stock_positions()
                result = []
                for p in (positions or []):
                    qty = float(p.get("quantity", 0) or 0)
                    if qty > 0:
                        # Enrich with symbol
                        instrument_url = p.get("instrument", "")
                        if instrument_url:
                            try:
                                inst = rh.stocks.get_instrument_by_url(instrument_url)
                                p["symbol"] = inst.get("symbol", "")
                            except Exception:
                                pass
                        result.append(RobinhoodPosition.from_api(p))
                return result
            except Exception as e:
                logger.warning(f"SDK get_positions failed: {e}")

        if self._mode == "http" and self._session:
            try:
                resp = self._session.get(
                    f"{self._config.base_url}/positions/?nonzero=true",
                    timeout=self._config.request_timeout,
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
                return [RobinhoodPosition.from_api(p) for p in results]
            except Exception as e:
                logger.warning(f"HTTP get_positions failed: {e}")

        return self._demo_positions()

    def get_orders(self, status: Optional[str] = None) -> list[RobinhoodOrder]:
        """Get orders. Optionally filter by status (e.g., 'filled', 'confirmed')."""
        if self._mode == "sdk" and _HAS_ROBIN_STOCKS:
            try:
                orders = rh.orders.get_all_stock_orders()
                result = []
                for o in (orders or [])[:50]:
                    order = RobinhoodOrder.from_api(o)
                    if status and order.status != status:
                        continue
                    result.append(order)
                return result
            except Exception as e:
                logger.warning(f"SDK get_orders failed: {e}")

        if self._mode == "http" and self._session:
            try:
                resp = self._session.get(
                    f"{self._config.base_url}/orders/",
                    timeout=self._config.request_timeout,
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
                orders = [RobinhoodOrder.from_api(o) for o in results]
                if status:
                    orders = [o for o in orders if o.status == status]
                return orders
            except Exception as e:
                logger.warning(f"HTTP get_orders failed: {e}")

        return self._demo_orders(status)

    def place_order(
        self,
        symbol: str,
        qty: float,
        side: str = "buy",
        order_type: str = "market",
        time_in_force: str = "gfd",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> RobinhoodOrder:
        """Place an order.

        Args:
            symbol: Stock ticker symbol.
            qty: Number of shares.
            side: 'buy' or 'sell'.
            order_type: 'market', 'limit', 'stop', 'stop_limit'.
            time_in_force: 'gfd' (good for day), 'gtc' (good till cancel), 'ioc', 'opg'.
            limit_price: Limit price for limit/stop_limit orders.
            stop_price: Stop price for stop/stop_limit orders.
        """
        if self._mode == "sdk" and _HAS_ROBIN_STOCKS:
            try:
                if order_type == "market" and side == "buy":
                    result = rh.orders.order_buy_market(symbol, qty, timeInForce=time_in_force)
                elif order_type == "market" and side == "sell":
                    result = rh.orders.order_sell_market(symbol, qty, timeInForce=time_in_force)
                elif order_type == "limit" and side == "buy" and limit_price:
                    result = rh.orders.order_buy_limit(symbol, qty, limit_price, timeInForce=time_in_force)
                elif order_type == "limit" and side == "sell" and limit_price:
                    result = rh.orders.order_sell_limit(symbol, qty, limit_price, timeInForce=time_in_force)
                else:
                    result = rh.orders.order(
                        symbol, qty, side, limit_price, stop_price,
                        timeInForce=time_in_force, trigger="immediate" if not stop_price else "stop",
                        orderType=order_type,
                    )
                if result:
                    result["symbol"] = symbol
                    return RobinhoodOrder.from_api(result)
            except Exception as e:
                logger.warning(f"SDK place_order failed: {e}")

        if self._mode == "http" and self._session:
            try:
                payload = {
                    "symbol": symbol,
                    "quantity": str(qty),
                    "side": side,
                    "type": order_type,
                    "time_in_force": time_in_force,
                    "trigger": "immediate" if not stop_price else "stop",
                    "account": f"{self._config.base_url}/accounts/DEMO/",
                }
                if limit_price is not None:
                    payload["price"] = str(limit_price)
                if stop_price is not None:
                    payload["stop_price"] = str(stop_price)

                resp = self._session.post(
                    f"{self._config.base_url}/orders/",
                    json=payload,
                    timeout=self._config.request_timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                data["symbol"] = symbol
                return RobinhoodOrder.from_api(data)
            except Exception as e:
                logger.warning(f"HTTP place_order failed: {e}")

        return self._demo_place_order(symbol, qty, side, order_type, time_in_force, limit_price, stop_price)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order by ID."""
        if self._mode == "sdk" and _HAS_ROBIN_STOCKS:
            try:
                result = rh.orders.cancel_stock_order(order_id)
                return result is not None
            except Exception as e:
                logger.warning(f"SDK cancel_order failed: {e}")
                return False

        if self._mode == "http" and self._session:
            try:
                resp = self._session.post(
                    f"{self._config.base_url}/orders/{order_id}/cancel/",
                    timeout=self._config.request_timeout,
                )
                return resp.status_code in (200, 204)
            except Exception as e:
                logger.warning(f"HTTP cancel_order failed: {e}")
                return False

        return True  # demo mode always succeeds

    def get_quote(self, symbol: str) -> RobinhoodQuote:
        """Get real-time quote for a stock."""
        if self._mode == "sdk" and _HAS_ROBIN_STOCKS:
            try:
                quote = rh.stocks.get_quotes(symbol)
                if quote and isinstance(quote, list) and quote[0]:
                    data = quote[0]
                    data["symbol"] = symbol
                    return RobinhoodQuote.from_api(data)
            except Exception as e:
                logger.warning(f"SDK get_quote failed: {e}")

        if self._mode == "http" and self._session:
            try:
                resp = self._session.get(
                    f"{self._config.base_url}/quotes/{symbol}/",
                    timeout=self._config.request_timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                data["symbol"] = symbol
                return RobinhoodQuote.from_api(data)
            except Exception as e:
                logger.warning(f"HTTP get_quote failed: {e}")

        return self._demo_quote(symbol)

    def get_crypto_quote(self, symbol: str) -> RobinhoodQuote:
        """Get quote for a cryptocurrency (e.g., 'BTC', 'ETH')."""
        if self._mode == "sdk" and _HAS_ROBIN_STOCKS:
            try:
                quote = rh.crypto.get_crypto_quote(symbol)
                if quote:
                    quote["symbol"] = symbol
                    return RobinhoodQuote.from_api(quote)
            except Exception as e:
                logger.warning(f"SDK get_crypto_quote failed: {e}")

        if self._mode == "http" and self._session:
            try:
                resp = self._session.get(
                    f"{self._config.base_url}/marketdata/forex/quotes/{symbol}/",
                    timeout=self._config.request_timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    data["symbol"] = symbol
                    return RobinhoodQuote.from_api(data)
            except Exception as e:
                logger.warning(f"HTTP get_crypto_quote failed: {e}")

        return self._demo_crypto_quote(symbol)

    def get_options_chain(self, symbol: str, expiry: Optional[str] = None) -> list[dict]:
        """Get options chain data for a symbol.

        Args:
            symbol: Underlying stock ticker.
            expiry: Expiration date in YYYY-MM-DD format. If None, returns nearest expiry.

        Returns:
            List of option contract dicts with strike, type, bid, ask, etc.
        """
        if self._mode == "sdk" and _HAS_ROBIN_STOCKS:
            try:
                chains = rh.options.get_chains(symbol)
                if chains and chains.get("expiration_dates"):
                    target_expiry = expiry or chains["expiration_dates"][0]
                    calls = rh.options.find_options_by_expiration(
                        symbol, expirationDate=target_expiry, optionType="call"
                    )
                    puts = rh.options.find_options_by_expiration(
                        symbol, expirationDate=target_expiry, optionType="put"
                    )
                    return (calls or []) + (puts or [])
            except Exception as e:
                logger.warning(f"SDK get_options_chain failed: {e}")

        if self._mode == "http" and self._session:
            try:
                params = {"symbols": symbol}
                if expiry:
                    params["expiration_dates"] = expiry
                resp = self._session.get(
                    f"{self._config.base_url}/options/chains/",
                    params=params,
                    timeout=self._config.request_timeout,
                )
                if resp.status_code == 200:
                    return resp.json().get("results", [])
            except Exception as e:
                logger.warning(f"HTTP get_options_chain failed: {e}")

        return self._demo_options_chain(symbol, expiry)

    # ── Demo Data ────────────────────────────────────────────────────

    def _demo_account(self) -> RobinhoodAccount:
        return RobinhoodAccount(
            account_id="demo_rh_account",
            account_number="5RH000001",
            buying_power=45000.0,
            equity=92350.0,
            cash=45000.0,
            margin_enabled=True,
            portfolio_value=92350.0,
            withdrawable_amount=40000.0,
            status="active",
        )

    def _demo_positions(self) -> list[RobinhoodPosition]:
        return [
            RobinhoodPosition(
                symbol="AAPL", instrument_id="instr_aapl",
                quantity=100, average_cost=152.30,
                current_price=187.50, market_value=18750.0,
                unrealized_pnl=3520.0, unrealized_pnl_pct=23.11,
                side="long",
            ),
            RobinhoodPosition(
                symbol="NVDA", instrument_id="instr_nvda",
                quantity=25, average_cost=480.00,
                current_price=624.00, market_value=15600.0,
                unrealized_pnl=3600.0, unrealized_pnl_pct=30.0,
                side="long",
            ),
            RobinhoodPosition(
                symbol="TSLA", instrument_id="instr_tsla",
                quantity=40, average_cost=220.50,
                current_price=325.00, market_value=13000.0,
                unrealized_pnl=4180.0, unrealized_pnl_pct=47.39,
                side="long",
            ),
        ]

    def _demo_orders(self, status: Optional[str] = None) -> list[RobinhoodOrder]:
        orders = [
            RobinhoodOrder(
                order_id="rh_ord_001", symbol="AAPL", side="buy",
                quantity=10, order_type="market", time_in_force="gfd",
                status="filled", filled_quantity=10, average_fill_price=187.50,
                created_at="2025-01-15T10:30:00Z",
            ),
            RobinhoodOrder(
                order_id="rh_ord_002", symbol="NVDA", side="buy",
                quantity=5, order_type="limit", time_in_force="gtc",
                limit_price=600.00, status="confirmed", filled_quantity=0,
                created_at="2025-01-15T11:00:00Z",
            ),
            RobinhoodOrder(
                order_id="rh_ord_003", symbol="TSLA", side="sell",
                quantity=10, order_type="market", time_in_force="gfd",
                status="filled", filled_quantity=10, average_fill_price=328.00,
                created_at="2025-01-15T14:15:00Z",
            ),
        ]
        if status:
            orders = [o for o in orders if o.status == status]
        return orders

    def _demo_place_order(
        self, symbol: str, qty: float, side: str,
        order_type: str, time_in_force: str,
        limit_price: Optional[float], stop_price: Optional[float],
    ) -> RobinhoodOrder:
        prices = {"AAPL": 187.50, "NVDA": 624.00, "TSLA": 325.00, "MSFT": 378.00}
        fill_price = prices.get(symbol, 150.0)
        is_market = order_type == "market"
        return RobinhoodOrder(
            order_id=f"demo_{uuid.uuid4().hex[:12]}",
            symbol=symbol,
            side=side,
            quantity=qty,
            order_type=order_type,
            time_in_force=time_in_force,
            limit_price=limit_price,
            stop_price=stop_price,
            status="filled" if is_market else "confirmed",
            filled_quantity=qty if is_market else 0.0,
            average_fill_price=fill_price if is_market else 0.0,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _demo_quote(self, symbol: str) -> RobinhoodQuote:
        quotes = {
            "AAPL": RobinhoodQuote(
                symbol="AAPL", bid_price=187.25, ask_price=187.75,
                last_trade_price=187.50, previous_close=185.20,
                volume=52_345_678, high=189.00, low=186.10, open_price=186.50,
            ),
            "NVDA": RobinhoodQuote(
                symbol="NVDA", bid_price=622.00, ask_price=626.00,
                last_trade_price=624.00, previous_close=618.50,
                volume=38_200_000, high=630.00, low=615.00, open_price=620.00,
            ),
            "TSLA": RobinhoodQuote(
                symbol="TSLA", bid_price=323.50, ask_price=326.50,
                last_trade_price=325.00, previous_close=318.00,
                volume=74_500_000, high=330.00, low=317.00, open_price=320.00,
            ),
        }
        return quotes.get(symbol, RobinhoodQuote(
            symbol=symbol, bid_price=149.50, ask_price=150.50,
            last_trade_price=150.00, previous_close=148.00,
            volume=10_000_000, high=152.00, low=147.50, open_price=148.50,
        ))

    def _demo_crypto_quote(self, symbol: str) -> RobinhoodQuote:
        crypto_quotes = {
            "BTC": RobinhoodQuote(
                symbol="BTC", bid_price=67_200.00, ask_price=67_400.00,
                last_trade_price=67_300.00, previous_close=66_800.00,
                volume=25_000, high=68_000.00, low=66_000.00, open_price=66_900.00,
            ),
            "ETH": RobinhoodQuote(
                symbol="ETH", bid_price=3_450.00, ask_price=3_470.00,
                last_trade_price=3_460.00, previous_close=3_400.00,
                volume=150_000, high=3_500.00, low=3_380.00, open_price=3_410.00,
            ),
            "DOGE": RobinhoodQuote(
                symbol="DOGE", bid_price=0.162, ask_price=0.164,
                last_trade_price=0.163, previous_close=0.158,
                volume=2_500_000_000, high=0.170, low=0.155, open_price=0.160,
            ),
        }
        return crypto_quotes.get(symbol, RobinhoodQuote(
            symbol=symbol, bid_price=1.00, ask_price=1.02,
            last_trade_price=1.01, previous_close=0.99,
            volume=100_000, high=1.05, low=0.95, open_price=0.98,
        ))

    def _demo_options_chain(self, symbol: str, expiry: Optional[str] = None) -> list[dict]:
        prices = {"AAPL": 187.50, "NVDA": 624.00, "TSLA": 325.00}
        underlying = prices.get(symbol, 150.0)
        target_expiry = expiry or "2025-02-21"

        chain = []
        for offset in [-10, -5, 0, 5, 10]:
            strike = round(underlying + offset, 0)
            chain.append({
                "symbol": symbol,
                "strike_price": str(strike),
                "expiration_date": target_expiry,
                "type": "call",
                "bid_price": str(round(max(underlying - strike + 2.0, 0.10), 2)),
                "ask_price": str(round(max(underlying - strike + 3.0, 0.30), 2)),
                "volume": 1500 - abs(offset) * 100,
                "open_interest": 5000 - abs(offset) * 200,
                "implied_volatility": str(round(0.35 + abs(offset) * 0.005, 4)),
            })
            chain.append({
                "symbol": symbol,
                "strike_price": str(strike),
                "expiration_date": target_expiry,
                "type": "put",
                "bid_price": str(round(max(strike - underlying + 2.0, 0.10), 2)),
                "ask_price": str(round(max(strike - underlying + 3.0, 0.30), 2)),
                "volume": 1200 - abs(offset) * 80,
                "open_interest": 4000 - abs(offset) * 150,
                "implied_volatility": str(round(0.36 + abs(offset) * 0.006, 4)),
            })
        return chain
