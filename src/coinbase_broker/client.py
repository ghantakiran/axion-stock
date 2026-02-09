"""Coinbase REST API Client (PRD-144).

Lightweight HTTP client for Coinbase Advanced Trade API.
Uses coinbase SDK when available, falls back to raw HTTP with JWT auth,
then to demo mode when no credentials or network available.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import json
import logging
import uuid
import random
import hashlib
import hmac
import time

logger = logging.getLogger(__name__)

# Try importing coinbase SDK; fall back to raw HTTP
_HAS_COINBASE_SDK = False
try:
    from coinbase.rest import RESTClient as CoinbaseRESTClient
    _HAS_COINBASE_SDK = True
except ImportError:
    CoinbaseRESTClient = None  # type: ignore

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
class CoinbaseConfig:
    """Configuration for Coinbase API connection."""
    api_key: str = ""
    api_secret: str = ""
    base_url: str = "https://api.coinbase.com/v2"
    advanced_url: str = "https://api.coinbase.com/api/v3"
    # Rate limiting
    max_requests_per_minute: int = 100
    request_timeout: int = 30
    # Retry
    max_retries: int = 3
    retry_delay: float = 1.0

    @property
    def ws_url(self) -> str:
        return "wss://advanced-trade-ws.coinbase.com"


# =====================================================================
# Response Models
# =====================================================================


@dataclass
class CoinbaseAccount:
    """Coinbase account / wallet."""
    account_id: str = ""
    name: str = ""
    currency: str = ""
    balance: float = 0.0
    available: float = 0.0
    hold: float = 0.0
    native_balance_amount: float = 0.0
    native_balance_currency: str = "USD"
    created_at: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict) -> "CoinbaseAccount":
        balance_info = data.get("balance", {})
        native_info = data.get("native_balance", {})
        available_info = data.get("available_balance", {})
        hold_info = data.get("hold", {})
        return cls(
            account_id=data.get("uuid", data.get("id", "")),
            name=data.get("name", ""),
            currency=data.get("currency", balance_info.get("currency", "")),
            balance=float(balance_info.get("amount", data.get("balance", 0)) or 0),
            available=float(
                available_info.get("value", available_info.get("amount", 0)) or 0
            ),
            hold=float(hold_info.get("amount", data.get("hold", 0)) or 0),
            native_balance_amount=float(native_info.get("amount", 0) or 0),
            native_balance_currency=native_info.get("currency", "USD"),
            created_at=data.get("created_at"),
        )


@dataclass
class CoinbaseOrder:
    """Coinbase order."""
    order_id: str = ""
    client_order_id: str = ""
    product_id: str = ""
    side: str = "BUY"
    order_type: str = "MARKET"
    size: float = 0.0
    limit_price: Optional[float] = None
    status: str = "PENDING"
    filled_size: float = 0.0
    filled_price: float = 0.0
    fee: float = 0.0
    created_at: Optional[str] = None
    completed_at: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict) -> "CoinbaseOrder":
        config = data.get("order_configuration", {})
        # Extract limit price from config variants
        limit_price = None
        if "limit_limit_gtc" in config:
            limit_price = float(config["limit_limit_gtc"].get("limit_price", 0) or 0)
        elif "limit_limit_gtd" in config:
            limit_price = float(config["limit_limit_gtd"].get("limit_price", 0) or 0)

        # Extract size
        size = 0.0
        for key in ("market_market_ioc", "limit_limit_gtc", "limit_limit_gtd"):
            if key in config:
                size = float(config[key].get("base_size", config[key].get("quote_size", 0)) or 0)
                break
        if size == 0.0:
            size = float(data.get("size", data.get("filled_size", 0)) or 0)

        return cls(
            order_id=data.get("order_id", data.get("id", "")),
            client_order_id=data.get("client_order_id", ""),
            product_id=data.get("product_id", ""),
            side=data.get("side", "BUY"),
            order_type=data.get("order_type", "MARKET"),
            size=size,
            limit_price=limit_price,
            status=data.get("status", "PENDING"),
            filled_size=float(data.get("filled_size", 0) or 0),
            filled_price=float(data.get("average_filled_price", 0) or 0),
            fee=float(data.get("total_fees", 0) or 0),
            created_at=data.get("created_time", data.get("created_at")),
            completed_at=data.get("completion_percentage", None),
        )


@dataclass
class CoinbaseFill:
    """A trade fill."""
    fill_id: str = ""
    order_id: str = ""
    product_id: str = ""
    side: str = ""
    price: float = 0.0
    size: float = 0.0
    fee: float = 0.0
    trade_time: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict) -> "CoinbaseFill":
        return cls(
            fill_id=data.get("entry_id", data.get("trade_id", "")),
            order_id=data.get("order_id", ""),
            product_id=data.get("product_id", ""),
            side=data.get("side", ""),
            price=float(data.get("price", 0) or 0),
            size=float(data.get("size", data.get("size_in_quote", 0)) or 0),
            fee=float(data.get("commission", data.get("fee", 0)) or 0),
            trade_time=data.get("trade_time", data.get("created_at")),
        )


@dataclass
class CoinbaseProduct:
    """A tradeable product (pair)."""
    product_id: str = ""
    base_currency: str = ""
    quote_currency: str = ""
    base_min_size: float = 0.0
    base_max_size: float = 0.0
    quote_increment: float = 0.01
    status: str = "online"
    price: float = 0.0

    @classmethod
    def from_api(cls, data: dict) -> "CoinbaseProduct":
        return cls(
            product_id=data.get("product_id", ""),
            base_currency=data.get("base_currency_id", data.get("base_currency", "")),
            quote_currency=data.get("quote_currency_id", data.get("quote_currency", "")),
            base_min_size=float(data.get("base_min_size", 0) or 0),
            base_max_size=float(data.get("base_max_size", 0) or 0),
            quote_increment=float(data.get("quote_increment", 0.01) or 0.01),
            status=data.get("status", "online"),
            price=float(data.get("price", 0) or 0),
        )


@dataclass
class CoinbaseCandle:
    """OHLCV candle."""
    timestamp: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0

    @classmethod
    def from_api(cls, data: dict) -> "CoinbaseCandle":
        # Coinbase candles come as dict with start, low, high, open, close, volume
        if isinstance(data, (list, tuple)):
            return cls(
                timestamp=str(data[0]) if len(data) > 0 else "",
                low=float(data[1]) if len(data) > 1 else 0.0,
                high=float(data[2]) if len(data) > 2 else 0.0,
                open=float(data[3]) if len(data) > 3 else 0.0,
                close=float(data[4]) if len(data) > 4 else 0.0,
                volume=float(data[5]) if len(data) > 5 else 0.0,
            )
        return cls(
            timestamp=str(data.get("start", data.get("timestamp", ""))),
            open=float(data.get("open", 0)),
            high=float(data.get("high", 0)),
            low=float(data.get("low", 0)),
            close=float(data.get("close", 0)),
            volume=float(data.get("volume", 0)),
        )


# =====================================================================
# Client
# =====================================================================


class CoinbaseClient:
    """Coinbase REST API client.

    Supports coinbase SDK, raw HTTP with JWT auth, and demo mode.
    Falls back to demo data when no credentials or network available.

    Example:
        client = CoinbaseClient(CoinbaseConfig(api_key="...", api_secret="..."))
        await client.connect()
        accounts = await client.get_accounts()
    """

    # Demo crypto prices (realistic as of early 2025)
    DEMO_PRICES: dict[str, float] = {
        "BTC": 95000.0,
        "ETH": 3500.0,
        "SOL": 200.0,
        "DOGE": 0.32,
        "ADA": 0.95,
        "XRP": 2.30,
    }

    def __init__(self, config: CoinbaseConfig):
        self._config = config
        self._connected = False
        self._http_client: Any = None
        self._sdk_client: Any = None
        self._mode: str = "demo"  # "sdk", "http", or "demo"
        self._request_count = 0

    @property
    def config(self) -> CoinbaseConfig:
        return self._config

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def mode(self) -> str:
        return self._mode

    async def connect(self) -> bool:
        """Connect to Coinbase API.

        Tries SDK first, then raw HTTP with JWT auth, falls back to demo.
        """
        if not self._config.api_key or not self._config.api_secret:
            logger.info("No Coinbase credentials - using demo mode")
            self._mode = "demo"
            self._connected = True
            return True

        # Try coinbase SDK
        if _HAS_COINBASE_SDK:
            try:
                self._sdk_client = CoinbaseRESTClient(
                    api_key=self._config.api_key,
                    api_secret=self._config.api_secret,
                )
                self._mode = "sdk"
                self._connected = True
                logger.info("Connected to Coinbase via SDK")
                return True
            except Exception as e:
                logger.warning(f"SDK connection failed: {e}")

        # Try raw HTTP
        if _HAS_HTTPX:
            try:
                self._http_client = httpx.AsyncClient(
                    base_url=self._config.advanced_url,
                    timeout=self._config.request_timeout,
                )
                # We would add JWT auth headers per-request
                self._mode = "http"
                self._connected = True
                logger.info("Connected to Coinbase via HTTP")
                return True
            except Exception as e:
                logger.warning(f"HTTP connection failed: {e}")

        # Fallback to demo
        self._mode = "demo"
        self._connected = True
        logger.info("Using Coinbase demo mode (no live API)")
        return True

    async def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        if self._http_client and hasattr(self._http_client, "aclose"):
            await self._http_client.aclose()
        self._http_client = None
        self._sdk_client = None
        self._connected = False
        self._mode = "demo"
        logger.info("Disconnected from Coinbase")

    def _auth_headers(self, method: str, path: str, body: str = "") -> dict:
        """Generate JWT / HMAC auth headers for HTTP mode."""
        timestamp = str(int(time.time()))
        message = timestamp + method.upper() + path + body
        signature = hmac.new(
            self._config.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "CB-ACCESS-KEY": self._config.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json",
        }

    # ── Accounts ────────────────────────────────────────────────────

    async def get_accounts(self) -> list[CoinbaseAccount]:
        """Get all crypto wallets/accounts."""
        if self._mode == "http" and self._http_client:
            resp = await self._http_client.get(
                "/brokerage/accounts",
                headers=self._auth_headers("GET", "/api/v3/brokerage/accounts"),
            )
            resp.raise_for_status()
            accounts_data = resp.json().get("accounts", [])
            return [CoinbaseAccount.from_api(a) for a in accounts_data]

        if self._mode == "sdk" and self._sdk_client:
            data = self._sdk_client.get_accounts()
            accounts_list = data.get("accounts", []) if isinstance(data, dict) else []
            return [CoinbaseAccount.from_api(a) for a in accounts_list]

        return self._demo_accounts()

    async def get_portfolio_value(self) -> float:
        """Get total portfolio value in USD."""
        accounts = await self.get_accounts()
        return sum(a.native_balance_amount for a in accounts)

    async def get_spot_price(self, pair: str) -> float:
        """Get spot price for a trading pair (e.g. 'BTC-USD')."""
        if self._mode == "http" and self._http_client:
            resp = await self._http_client.get(
                f"/brokerage/products/{pair}",
                headers=self._auth_headers("GET", f"/api/v3/brokerage/products/{pair}"),
            )
            resp.raise_for_status()
            return float(resp.json().get("price", 0))

        # Demo mode
        base = pair.split("-")[0].upper()
        return self.DEMO_PRICES.get(base, 100.0)

    # ── Products ────────────────────────────────────────────────────

    async def list_products(self) -> list[CoinbaseProduct]:
        """List available trading pairs."""
        if self._mode == "http" and self._http_client:
            resp = await self._http_client.get(
                "/brokerage/products",
                headers=self._auth_headers("GET", "/api/v3/brokerage/products"),
            )
            resp.raise_for_status()
            products = resp.json().get("products", [])
            return [CoinbaseProduct.from_api(p) for p in products]

        return self._demo_products()

    # ── Orders ──────────────────────────────────────────────────────

    async def place_order(
        self,
        product_id: str,
        side: str,
        size: float,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
    ) -> CoinbaseOrder:
        """Place a new order."""
        client_order_id = uuid.uuid4().hex[:16]
        order_config: dict[str, Any] = {}

        if order_type.upper() == "MARKET":
            order_config["market_market_ioc"] = {"base_size": str(size)}
        else:
            order_config["limit_limit_gtc"] = {
                "base_size": str(size),
                "limit_price": str(limit_price or 0),
            }

        body = {
            "client_order_id": client_order_id,
            "product_id": product_id,
            "side": side.upper(),
            "order_configuration": order_config,
        }

        if self._mode == "http" and self._http_client:
            body_str = json.dumps(body)
            resp = await self._http_client.post(
                "/brokerage/orders",
                content=body_str,
                headers=self._auth_headers("POST", "/api/v3/brokerage/orders", body_str),
            )
            resp.raise_for_status()
            return CoinbaseOrder.from_api(resp.json().get("success_response", resp.json()))

        # Demo mode
        return self._demo_order(product_id, side, size, order_type, limit_price)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        if self._mode == "http" and self._http_client:
            body = json.dumps({"order_ids": [order_id]})
            resp = await self._http_client.post(
                "/brokerage/orders/batch_cancel",
                content=body,
                headers=self._auth_headers("POST", "/api/v3/brokerage/orders/batch_cancel", body),
            )
            return resp.status_code in (200, 204)

        return True

    async def get_order(self, order_id: str) -> Optional[CoinbaseOrder]:
        """Get order status by ID."""
        if self._mode == "http" and self._http_client:
            resp = await self._http_client.get(
                f"/brokerage/orders/historical/{order_id}",
                headers=self._auth_headers(
                    "GET", f"/api/v3/brokerage/orders/historical/{order_id}"
                ),
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return CoinbaseOrder.from_api(resp.json().get("order", resp.json()))

        return None

    async def get_fills(self, product_id: Optional[str] = None) -> list[CoinbaseFill]:
        """Get trade fills, optionally filtered by product."""
        if self._mode == "http" and self._http_client:
            params: dict[str, Any] = {}
            if product_id:
                params["product_id"] = product_id
            resp = await self._http_client.get(
                "/brokerage/orders/historical/fills",
                params=params,
                headers=self._auth_headers("GET", "/api/v3/brokerage/orders/historical/fills"),
            )
            resp.raise_for_status()
            fills = resp.json().get("fills", [])
            return [CoinbaseFill.from_api(f) for f in fills]

        return self._demo_fills(product_id)

    # ── Market Data ─────────────────────────────────────────────────

    async def get_candles(
        self,
        product_id: str,
        granularity: str = "ONE_DAY",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> list[CoinbaseCandle]:
        """Get OHLCV candles for a product."""
        if self._mode == "http" and self._http_client:
            params: dict[str, Any] = {"granularity": granularity}
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            resp = await self._http_client.get(
                f"/brokerage/products/{product_id}/candles",
                params=params,
                headers=self._auth_headers(
                    "GET", f"/api/v3/brokerage/products/{product_id}/candles"
                ),
            )
            resp.raise_for_status()
            candles_data = resp.json().get("candles", [])
            return [CoinbaseCandle.from_api(c) for c in candles_data]

        return self._demo_candles(product_id)

    # ── Demo Data ───────────────────────────────────────────────────

    def _demo_accounts(self) -> list[CoinbaseAccount]:
        """Generate realistic demo crypto accounts."""
        holdings = [
            ("BTC", "Bitcoin", 0.52, 95000.0),
            ("ETH", "Ethereum", 4.2, 3500.0),
            ("SOL", "Solana", 45.0, 200.0),
            ("DOGE", "Dogecoin", 15000.0, 0.32),
            ("ADA", "Cardano", 5000.0, 0.95),
            ("XRP", "XRP", 2000.0, 2.30),
        ]
        accounts = []
        for currency, name, balance, price in holdings:
            usd_value = round(balance * price, 2)
            accounts.append(CoinbaseAccount(
                account_id=uuid.uuid4().hex[:12],
                name=f"{name} Wallet",
                currency=currency,
                balance=balance,
                available=balance,
                hold=0.0,
                native_balance_amount=usd_value,
                native_balance_currency="USD",
            ))
        # Add USD cash wallet
        accounts.append(CoinbaseAccount(
            account_id=uuid.uuid4().hex[:12],
            name="USD Wallet",
            currency="USD",
            balance=10000.0,
            available=10000.0,
            hold=0.0,
            native_balance_amount=10000.0,
            native_balance_currency="USD",
        ))
        return accounts

    def _demo_products(self) -> list[CoinbaseProduct]:
        """Generate demo product list."""
        products = []
        for base, price in self.DEMO_PRICES.items():
            products.append(CoinbaseProduct(
                product_id=f"{base}-USD",
                base_currency=base,
                quote_currency="USD",
                base_min_size=0.00001 if base in ("BTC", "ETH") else 0.01,
                base_max_size=10000.0,
                quote_increment=0.01,
                status="online",
                price=price,
            ))
        return products

    def _demo_order(
        self,
        product_id: str,
        side: str,
        size: float,
        order_type: str,
        limit_price: Optional[float],
    ) -> CoinbaseOrder:
        """Generate a demo order response."""
        base = product_id.split("-")[0]
        fill_price = self.DEMO_PRICES.get(base, 100.0)
        is_market = order_type.upper() == "MARKET"
        return CoinbaseOrder(
            order_id=uuid.uuid4().hex[:12],
            client_order_id=uuid.uuid4().hex[:16],
            product_id=product_id,
            side=side.upper(),
            order_type=order_type.upper(),
            size=size,
            limit_price=limit_price,
            status="FILLED" if is_market else "PENDING",
            filled_size=size if is_market else 0.0,
            filled_price=fill_price if is_market else 0.0,
            fee=round(size * fill_price * 0.006, 2) if is_market else 0.0,
        )

    def _demo_fills(self, product_id: Optional[str] = None) -> list[CoinbaseFill]:
        """Generate demo trade fills."""
        all_fills = [
            CoinbaseFill(
                fill_id=uuid.uuid4().hex[:8],
                order_id=uuid.uuid4().hex[:12],
                product_id="BTC-USD",
                side="BUY",
                price=94500.0,
                size=0.1,
                fee=56.70,
                trade_time="2025-01-15T10:30:00Z",
            ),
            CoinbaseFill(
                fill_id=uuid.uuid4().hex[:8],
                order_id=uuid.uuid4().hex[:12],
                product_id="ETH-USD",
                side="BUY",
                price=3450.0,
                size=2.0,
                fee=41.40,
                trade_time="2025-01-15T11:00:00Z",
            ),
            CoinbaseFill(
                fill_id=uuid.uuid4().hex[:8],
                order_id=uuid.uuid4().hex[:12],
                product_id="SOL-USD",
                side="BUY",
                price=195.0,
                size=10.0,
                fee=11.70,
                trade_time="2025-01-14T14:22:00Z",
            ),
        ]
        if product_id:
            return [f for f in all_fills if f.product_id == product_id]
        return all_fills

    def _demo_candles(self, product_id: str, count: int = 30) -> list[CoinbaseCandle]:
        """Generate demo OHLCV candle data."""
        base = product_id.split("-")[0]
        base_price = self.DEMO_PRICES.get(base, 100.0)
        rng = random.Random(hash(product_id))
        candles = []
        price = base_price
        for i in range(count):
            change = rng.uniform(-0.03, 0.03)
            o = price * (1 + change)
            c = o * (1 + rng.uniform(-0.02, 0.02))
            h = max(o, c) * (1 + rng.uniform(0, 0.015))
            lo = min(o, c) * (1 - rng.uniform(0, 0.015))
            vol = rng.uniform(100, 5000) * base_price / 100
            candles.append(CoinbaseCandle(
                timestamp=str(int(time.time()) - (count - i) * 86400),
                open=round(o, 2),
                high=round(h, 2),
                low=round(lo, 2),
                close=round(c, 2),
                volume=round(vol, 2),
            ))
            price = c
        return candles
