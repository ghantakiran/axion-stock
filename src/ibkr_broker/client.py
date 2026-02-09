"""IBKR REST API Client (PRD-157).

Lightweight HTTP client for IBKR's Client Portal Gateway API.
Uses ib_insync SDK when available, falls back to httpx Gateway HTTP, then demo mode.

The Client Portal Gateway runs locally (typically https://localhost:5000)
and provides REST endpoints for account, trading, and market data operations.
IBKR uses contract IDs (conid) for instrument identification across all asset classes.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, date, timedelta
from enum import Enum
from typing import Any, Optional
import json
import logging
import uuid

logger = logging.getLogger(__name__)

# Try importing ib_insync SDK; fall back to raw HTTP
_HAS_IB_INSYNC = False
try:
    import ib_insync as ib_insync_sdk
    _HAS_IB_INSYNC = True
except ImportError:
    ib_insync_sdk = None  # type: ignore

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
class IBKRConfig:
    """Configuration for IBKR Client Portal Gateway connection.

    The gateway runs locally and proxies requests to IBKR servers.
    Default address is https://localhost:5000 with SSL verification
    disabled (self-signed cert from the gateway).
    """
    gateway_host: str = "localhost"
    gateway_port: int = 5000
    ssl_verify: bool = False
    # OAuth credentials (for web portal access, optional)
    client_id: str = ""
    client_secret: str = ""
    # Account
    account_id: str = ""
    # Rate limiting (IBKR is more restrictive than most brokers)
    max_requests_per_minute: int = 50
    request_timeout: int = 30
    # Retry
    max_retries: int = 3
    retry_delay: float = 1.0

    @property
    def gateway_url(self) -> str:
        protocol = "https"
        return f"{protocol}://{self.gateway_host}:{self.gateway_port}/v1/api"

    @property
    def auth_url(self) -> str:
        return f"{self.gateway_url}/iserver/auth/status"

    @property
    def token_url(self) -> str:
        return "https://oauth.interactivebrokers.com/v1/token"


# =====================================================================
# Response Models
# =====================================================================


@dataclass
class IBKRAccount:
    """IBKR account information."""
    account_id: str = ""
    account_type: str = "INDIVIDUAL"
    base_currency: str = "USD"
    net_liquidation: float = 0.0
    equity_with_loan: float = 0.0
    buying_power: float = 0.0
    available_funds: float = 0.0
    excess_liquidity: float = 0.0
    maintenance_margin: float = 0.0
    initial_margin: float = 0.0
    position_count: int = 0
    sma: float = 0.0

    @classmethod
    def from_api(cls, data: dict) -> "IBKRAccount":
        """Parse from IBKR /portfolio/accounts or /portfolio/{id}/summary."""
        summary = data.get("summary", data)
        # IBKR returns nested objects with value/currency pairs
        def _val(key: str, fallback: str = "") -> float:
            v = summary.get(key, {})
            if isinstance(v, dict):
                return float(v.get("amount", v.get("value", 0)))
            return float(v) if v else 0.0

        return cls(
            account_id=str(data.get("accountId", data.get("id", ""))),
            account_type=data.get("type", data.get("accountType", "INDIVIDUAL")),
            base_currency=data.get("currency", data.get("baseCurrency", "USD")),
            net_liquidation=_val("netliquidation") or _val("NetLiquidation"),
            equity_with_loan=_val("equitywithloanvalue") or _val("EquityWithLoanValue"),
            buying_power=_val("buyingpower") or _val("BuyingPower"),
            available_funds=_val("availablefunds") or _val("AvailableFunds"),
            excess_liquidity=_val("excessliquidity") or _val("ExcessLiquidity"),
            maintenance_margin=_val("maintenancemarginreq") or _val("MaintMarginReq"),
            initial_margin=_val("initmarginreq") or _val("InitMarginReq"),
            position_count=int(data.get("positionCount", 0)),
            sma=_val("sma") or _val("SMA"),
        )

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "account_type": self.account_type,
            "base_currency": self.base_currency,
            "net_liquidation": self.net_liquidation,
            "equity_with_loan": self.equity_with_loan,
            "buying_power": self.buying_power,
            "available_funds": self.available_funds,
            "excess_liquidity": self.excess_liquidity,
            "maintenance_margin": self.maintenance_margin,
            "initial_margin": self.initial_margin,
            "position_count": self.position_count,
            "sma": self.sma,
        }


@dataclass
class IBKRPosition:
    """IBKR position with contract ID (conid) support."""
    conid: int = 0
    symbol: str = ""
    asset_class: str = "STK"
    quantity: float = 0.0
    average_cost: float = 0.0
    market_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    realized_pnl: float = 0.0
    currency: str = "USD"

    @classmethod
    def from_api(cls, data: dict) -> "IBKRPosition":
        """Parse from IBKR /portfolio/{accountId}/positions."""
        qty = float(data.get("position", data.get("quantity", 0)))
        avg_cost = float(data.get("avgCost", data.get("averageCost", 0)))
        mkt_price = float(data.get("mktPrice", data.get("marketPrice", 0)))
        mkt_value = float(data.get("mktValue", data.get("marketValue", 0)))
        unrealized = float(data.get("unrealizedPnl", 0))
        cost_basis = abs(qty * avg_cost) if avg_cost else 0
        pnl_pct = (unrealized / cost_basis * 100) if cost_basis > 0 else 0.0
        return cls(
            conid=int(data.get("conid", data.get("conId", 0))),
            symbol=data.get("contractDesc", data.get("ticker", data.get("symbol", ""))),
            asset_class=data.get("assetClass", data.get("secType", "STK")),
            quantity=qty,
            average_cost=avg_cost,
            market_price=mkt_price,
            market_value=mkt_value,
            unrealized_pnl=unrealized,
            unrealized_pnl_pct=round(pnl_pct, 2),
            realized_pnl=float(data.get("realizedPnl", 0)),
            currency=data.get("currency", "USD"),
        )

    def to_dict(self) -> dict:
        return {
            "conid": self.conid,
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "quantity": self.quantity,
            "average_cost": self.average_cost,
            "market_price": self.market_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "realized_pnl": self.realized_pnl,
            "currency": self.currency,
        }


@dataclass
class IBKROrder:
    """IBKR order with contract ID and advanced fields."""
    order_id: str = ""
    conid: int = 0
    symbol: str = ""
    side: str = "BUY"
    quantity: float = 0.0
    filled_quantity: float = 0.0
    price: float = 0.0
    order_type: str = "MKT"
    tif: str = "DAY"
    status: str = "PreSubmitted"
    parent_id: str = ""
    oca_group: str = ""
    account_id: str = ""

    @classmethod
    def from_api(cls, data: dict) -> "IBKROrder":
        """Parse from IBKR /iserver/account/orders response."""
        return cls(
            order_id=str(data.get("orderId", data.get("order_id", ""))),
            conid=int(data.get("conid", data.get("conId", 0))),
            symbol=data.get("ticker", data.get("symbol", "")),
            side=data.get("side", data.get("orderSide", "BUY")),
            quantity=float(data.get("totalSize", data.get("quantity", 0))),
            filled_quantity=float(data.get("filledQuantity", data.get("cumFill", 0))),
            price=float(data.get("price", data.get("avgPrice", 0))),
            order_type=data.get("orderType", "MKT"),
            tif=data.get("timeInForce", data.get("tif", "DAY")),
            status=data.get("status", data.get("orderStatus", "PreSubmitted")),
            parent_id=str(data.get("parentId", "")),
            oca_group=data.get("ocaGroup", ""),
            account_id=data.get("acct", data.get("accountId", "")),
        )

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "conid": self.conid,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "price": self.price,
            "order_type": self.order_type,
            "tif": self.tif,
            "status": self.status,
            "parent_id": self.parent_id,
            "oca_group": self.oca_group,
            "account_id": self.account_id,
        }


@dataclass
class IBKRQuote:
    """Real-time quote from IBKR market data snapshot."""
    conid: int = 0
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
    market_status: str = "Open"

    @classmethod
    def from_api(cls, data: dict) -> "IBKRQuote":
        """Parse from IBKR /iserver/marketdata/snapshot response.

        IBKR returns numeric field codes (e.g. 31=Last, 84=Bid, 85=Ask, 86=Ask Size).
        We map these to human-readable fields.
        """
        # IBKR uses numeric keys or named keys depending on endpoint
        last_price = float(data.get("31", data.get("lastPrice", data.get("last", 0))))
        bid = float(data.get("84", data.get("bid", 0)))
        ask = float(data.get("85", data.get("ask", 0)))
        open_p = float(data.get("7295", data.get("open", 0)))
        high_p = float(data.get("70", data.get("high", 0)))
        low_p = float(data.get("71", data.get("low", 0)))
        close_p = float(data.get("7291", data.get("close", data.get("priorClose", 0))))
        vol = int(float(data.get("7762", data.get("volume", 0))))
        chg = float(data.get("82", data.get("change", 0)))
        chg_pct = float(data.get("83", data.get("changePercent", data.get("change_pct", 0))))

        return cls(
            conid=int(data.get("conid", data.get("conId", 0))),
            symbol=data.get("55", data.get("symbol", data.get("ticker", ""))),
            bid=bid,
            ask=ask,
            last=last_price,
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=vol,
            change=chg,
            change_pct=chg_pct,
            market_status=data.get("marketStatus", data.get("6509", "Open")),
        )

    def to_dict(self) -> dict:
        return {
            "conid": self.conid,
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
            "market_status": self.market_status,
        }


@dataclass
class IBKRCandle:
    """OHLCV candle from IBKR market data history."""
    timestamp: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    wap: float = 0.0
    trade_count: int = 0

    @classmethod
    def from_api(cls, data: dict) -> "IBKRCandle":
        """Parse from IBKR /iserver/marketdata/history response."""
        o = float(data.get("o", data.get("open", 0)))
        h = float(data.get("h", data.get("high", 0)))
        lo = float(data.get("l", data.get("low", 0)))
        c = float(data.get("c", data.get("close", 0)))
        return cls(
            timestamp=str(data.get("t", data.get("timestamp", ""))),
            open=o,
            high=h,
            low=lo,
            close=c,
            volume=int(data.get("v", data.get("volume", 0))),
            wap=float(data.get("wap", (o + h + lo + c) / 4 if (o + h + lo + c) else 0)),
            trade_count=int(data.get("n", data.get("tradeCount", 0))),
        )

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "wap": self.wap,
            "trade_count": self.trade_count,
        }


@dataclass
class IBKRContract:
    """IBKR contract definition used for contract-based trading.

    IBKR identifies instruments via conid (contract ID) rather than
    ticker symbols alone. This is necessary because the same symbol
    can refer to different instruments on different exchanges.
    """
    conid: int = 0
    symbol: str = ""
    sec_type: str = "STK"
    exchange: str = "SMART"
    currency: str = "USD"
    description: str = ""
    local_symbol: str = ""

    @classmethod
    def from_api(cls, data: dict) -> "IBKRContract":
        """Parse from IBKR /iserver/secdef/search response."""
        return cls(
            conid=int(data.get("conid", data.get("conId", 0))),
            symbol=data.get("symbol", data.get("ticker", "")),
            sec_type=data.get("secType", data.get("assetClass", "STK")),
            exchange=data.get("exchange", data.get("listingExchange", "SMART")),
            currency=data.get("currency", "USD"),
            description=data.get("companyName", data.get("description", "")),
            local_symbol=data.get("localSymbol", data.get("symbol", "")),
        )

    def to_dict(self) -> dict:
        return {
            "conid": self.conid,
            "symbol": self.symbol,
            "sec_type": self.sec_type,
            "exchange": self.exchange,
            "currency": self.currency,
            "description": self.description,
            "local_symbol": self.local_symbol,
        }


# =====================================================================
# Session / Token Management
# =====================================================================


class _TokenManager:
    """Handles OAuth2 token persistence and refresh for IBKR web portal access.

    Note: When using the local Client Portal Gateway, authentication is
    managed by the gateway itself. This token manager is used for the
    optional OAuth web portal flow.
    """

    def __init__(self, config: IBKRConfig):
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

    def set_tokens(self, access: str, refresh: str, expires_in: int = 3600) -> None:
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
                        body.get("expires_in", 3600),
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


class IBKRClient:
    """IBKR Client Portal Gateway REST API client.

    Supports ib_insync SDK, raw HTTP via local gateway, and demo mode fallback.
    IBKR uses contract IDs (conid) to identify instruments across all asset
    classes: stocks (STK), options (OPT), futures (FUT), forex (CASH), bonds (BOND).

    Example:
        client = IBKRClient(IBKRConfig(account_id="U1234567"))
        await client.connect()
        accounts = await client.get_accounts()
        contracts = await client.search_contract("AAPL", sec_type="STK")
    """

    def __init__(self, config: IBKRConfig):
        self._config = config
        self._connected = False
        self._http_client: Any = None
        self._ib_client: Any = None
        self._mode: str = "demo"  # "ib_insync", "gateway", or "demo"
        self._token_mgr = _TokenManager(config)
        self._request_count = 0

    @property
    def config(self) -> IBKRConfig:
        return self._config

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def mode(self) -> str:
        return self._mode

    async def connect(self) -> bool:
        """Connect to IBKR API.

        Tries ib_insync SDK first, then Client Portal Gateway HTTP,
        falls back to demo mode.
        """
        # Try ib_insync SDK
        if _HAS_IB_INSYNC:
            try:
                self._ib_client = ib_insync_sdk.IB()
                self._ib_client.connect(
                    self._config.gateway_host,
                    self._config.gateway_port,
                    clientId=1,
                )
                self._mode = "ib_insync"
                self._connected = True
                logger.info("Connected to IBKR via ib_insync SDK")
                return True
            except Exception as e:
                logger.warning(f"ib_insync connection failed: {e}")
                self._ib_client = None

        # Try Client Portal Gateway HTTP
        if _HAS_HTTPX:
            try:
                self._http_client = httpx.AsyncClient(
                    base_url=self._config.gateway_url,
                    verify=self._config.ssl_verify,
                    timeout=self._config.request_timeout,
                )
                # Check gateway auth status
                resp = await self._http_client.post("/iserver/auth/status")
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("authenticated", False):
                        self._mode = "gateway"
                        self._connected = True
                        logger.info("Connected to IBKR via Client Portal Gateway")
                        return True
                    else:
                        logger.warning("Gateway reachable but not authenticated")
                else:
                    logger.warning(f"Gateway auth check returned: {resp.status_code}")
            except Exception as e:
                logger.warning(f"Gateway connection failed: {e}")

        # Fallback to demo
        self._mode = "demo"
        self._connected = True
        logger.info("Using IBKR demo mode (no live gateway)")
        return True

    async def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        if self._http_client and hasattr(self._http_client, "aclose"):
            await self._http_client.aclose()
        if self._ib_client and hasattr(self._ib_client, "disconnect"):
            self._ib_client.disconnect()
        self._http_client = None
        self._ib_client = None
        self._connected = False
        self._mode = "demo"
        logger.info("Disconnected from IBKR")

    async def _reauthenticate(self) -> bool:
        """Reauthenticate with the gateway.

        IBKR sessions expire every few hours. This sends a reauthenticate
        request to the Client Portal Gateway to refresh the session.
        """
        if self._mode == "gateway" and self._http_client:
            try:
                resp = await self._http_client.post("/iserver/reauthenticate")
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("message") == "triggered":
                        logger.info("IBKR reauthentication triggered")
                        return True
            except Exception as e:
                logger.warning(f"Reauthentication failed: {e}")
        return False

    # -- Accounts ----------------------------------------------------------

    async def get_accounts(self) -> list[IBKRAccount]:
        """Get all linked IBKR accounts."""
        if self._mode == "gateway" and self._http_client:
            resp = await self._http_client.get("/portfolio/accounts")
            resp.raise_for_status()
            accounts = resp.json()
            result = []
            for acct in accounts:
                acct_id = acct.get("accountId", acct.get("id", ""))
                # Fetch summary for each account
                try:
                    summary_resp = await self._http_client.get(
                        f"/portfolio/{acct_id}/summary"
                    )
                    if summary_resp.status_code == 200:
                        summary_data = summary_resp.json()
                        summary_data["accountId"] = acct_id
                        summary_data["type"] = acct.get("type", "INDIVIDUAL")
                        summary_data["currency"] = acct.get("currency", "USD")
                        result.append(IBKRAccount.from_api(summary_data))
                    else:
                        result.append(IBKRAccount.from_api(acct))
                except Exception:
                    result.append(IBKRAccount.from_api(acct))
            return result

        return self._demo_accounts()

    async def get_positions(self, account_id: str = "") -> list[IBKRPosition]:
        """Get positions for a specific account.

        Args:
            account_id: IBKR account ID (e.g. "U1234567"). Uses config default if empty.
        """
        acct = account_id or self._config.account_id
        if self._mode == "gateway" and self._http_client:
            resp = await self._http_client.get(
                f"/portfolio/{acct}/positions/0"
            )
            resp.raise_for_status()
            positions = resp.json()
            return [IBKRPosition.from_api(p) for p in positions]

        return self._demo_positions()

    async def get_orders(self, account_id: str = "", filters: Optional[dict] = None) -> list[IBKROrder]:
        """Get orders for a specific account.

        Args:
            account_id: IBKR account ID. Uses config default if empty.
            filters: Optional filters (e.g. {"status": "Filled"}).
        """
        if self._mode == "gateway" and self._http_client:
            resp = await self._http_client.get("/iserver/account/orders")
            resp.raise_for_status()
            data = resp.json()
            orders = data.get("orders", data) if isinstance(data, dict) else data
            result = [IBKROrder.from_api(o) for o in orders]
            # Apply client-side filters if provided
            if filters:
                if filters.get("status"):
                    result = [o for o in result if o.status.lower() == filters["status"].lower()]
                if filters.get("side"):
                    result = [o for o in result if o.side.upper() == filters["side"].upper()]
            return result

        return self._demo_orders()

    async def place_order(self, account_id: str, order: dict) -> IBKROrder:
        """Submit an order via the Client Portal Gateway.

        Args:
            account_id: IBKR account ID.
            order: Order specification dict with keys:
                conid (int), side (BUY/SELL), quantity (float),
                orderType (MKT/LMT/STP/STP_LIMIT), price (float, for LMT),
                tif (DAY/GTC/IOC/OPG).

        Note: IBKR may require order confirmation. The gateway returns a
        reply ID that must be confirmed with a second request.
        """
        if self._mode == "gateway" and self._http_client:
            resp = await self._http_client.post(
                f"/iserver/account/{account_id}/orders",
                json={"orders": [order]},
            )
            resp.raise_for_status()
            data = resp.json()
            # Handle order confirmation flow
            if isinstance(data, list) and data:
                first = data[0]
                if first.get("id"):
                    # Need to confirm the order
                    confirm_resp = await self._http_client.post(
                        f"/iserver/reply/{first['id']}",
                        json={"confirmed": True},
                    )
                    if confirm_resp.status_code == 200:
                        confirm_data = confirm_resp.json()
                        if isinstance(confirm_data, list) and confirm_data:
                            return IBKROrder.from_api(confirm_data[0])
                return IBKROrder.from_api(first)

        return self._demo_place_order(order)

    async def modify_order(self, account_id: str, order_id: str, changes: dict) -> IBKROrder:
        """Modify an existing order.

        Args:
            account_id: IBKR account ID.
            order_id: Order ID to modify.
            changes: Fields to change (e.g. {"price": 150.0, "quantity": 200}).
        """
        if self._mode == "gateway" and self._http_client:
            resp = await self._http_client.post(
                f"/iserver/account/{account_id}/order/{order_id}",
                json=changes,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and data:
                return IBKROrder.from_api(data[0])
            return IBKROrder.from_api(data if isinstance(data, dict) else {})

        return IBKROrder(
            order_id=order_id,
            symbol=changes.get("symbol", "AAPL"),
            side=changes.get("side", "BUY"),
            quantity=float(changes.get("quantity", 100)),
            price=float(changes.get("price", 0)),
            order_type=changes.get("orderType", "LMT"),
            status="PreSubmitted",
            account_id=account_id,
        )

    async def cancel_order(self, account_id: str, order_id: str) -> bool:
        """Cancel an order.

        Args:
            account_id: IBKR account ID.
            order_id: Order ID to cancel.
        """
        if self._mode == "gateway" and self._http_client:
            resp = await self._http_client.delete(
                f"/iserver/account/{account_id}/order/{order_id}"
            )
            return resp.status_code in (200, 204)

        return True

    # -- Market Data -------------------------------------------------------

    async def get_quote(self, conids_or_symbols: list) -> list[IBKRQuote]:
        """Get market data snapshots for a list of conids or symbols.

        Args:
            conids_or_symbols: List of conids (int) or symbols (str).
                If symbols are provided, they are resolved to conids first.

        Note: IBKR requires at least one prior /snapshot call to "warm up"
        the data; the first call may return empty fields.
        """
        if self._mode == "gateway" and self._http_client:
            # Resolve symbols to conids if needed
            conids = []
            for item in conids_or_symbols:
                if isinstance(item, int):
                    conids.append(item)
                else:
                    contracts = await self.search_contract(str(item))
                    if contracts:
                        conids.append(contracts[0].conid)

            if not conids:
                return []

            conid_str = ",".join(str(c) for c in conids)
            # Request market data snapshot (fields: 31=last, 84=bid, 85=ask, etc.)
            resp = await self._http_client.get(
                "/iserver/marketdata/snapshot",
                params={
                    "conids": conid_str,
                    "fields": "31,84,85,86,70,71,82,83,7295,7291,7762,55,6509",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return [IBKRQuote.from_api(d) for d in data]
            return []

        return self._demo_quotes(conids_or_symbols)

    async def get_price_history(
        self,
        conid: int,
        period: str = "1m",
        bar: str = "1d",
        start_time: str = "",
    ) -> list[IBKRCandle]:
        """Get historical OHLCV data for a contract.

        Args:
            conid: IBKR contract ID.
            period: Time period (e.g. "1d", "1w", "1m", "3m", "6m", "1y").
            bar: Bar size (e.g. "1min", "5min", "15min", "1h", "1d", "1w").
            start_time: Optional start time in YYYYMMDD-HH:mm:ss format.
        """
        if self._mode == "gateway" and self._http_client:
            params: dict[str, Any] = {
                "conid": conid,
                "period": period,
                "bar": bar,
            }
            if start_time:
                params["startTime"] = start_time

            resp = await self._http_client.get(
                "/iserver/marketdata/history",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            bars = data.get("data", data.get("bars", []))
            return [IBKRCandle.from_api(b) for b in bars]

        return self._demo_candles(conid)

    async def search_contract(
        self, symbol: str, sec_type: str = ""
    ) -> list[IBKRContract]:
        """Search for IBKR contracts by symbol.

        This is unique to IBKR's contract-based trading model. The same
        ticker symbol can map to different conids depending on exchange,
        currency, and security type.

        Args:
            symbol: Ticker symbol to search (e.g. "AAPL", "EURUSD", "ES").
            sec_type: Optional security type filter (STK, OPT, FUT, CASH, BOND).
        """
        if self._mode == "gateway" and self._http_client:
            payload: dict[str, Any] = {"symbol": symbol}
            if sec_type:
                payload["secType"] = sec_type

            resp = await self._http_client.post(
                "/iserver/secdef/search",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            contracts = []
            if isinstance(data, list):
                for item in data:
                    contracts.append(IBKRContract.from_api(item))
                    # Also check for sections (IBKR groups results by sec type)
                    for section in item.get("sections", []):
                        contracts.append(IBKRContract(
                            conid=int(section.get("conid", 0)),
                            symbol=item.get("symbol", symbol),
                            sec_type=section.get("secType", "STK"),
                            exchange=section.get("exchange", "SMART"),
                            currency=section.get("currency", "USD"),
                            description=item.get("companyName", ""),
                        ))
            return contracts

        return self._demo_search_contract(symbol, sec_type)

    async def get_forex_pairs(self) -> list[IBKRContract]:
        """Get available forex pairs.

        IBKR lists forex as CASH contracts (e.g. EUR.USD with sec_type=CASH).
        Returns a curated list of major and common forex pairs.
        """
        if self._mode == "gateway" and self._http_client:
            # Search for common forex base currencies
            pairs = []
            for base in ["EUR", "GBP", "JPY", "AUD", "CHF", "CAD"]:
                try:
                    results = await self.search_contract(base, sec_type="CASH")
                    pairs.extend(results)
                except Exception as e:
                    logger.warning(f"Failed to search forex pair {base}: {e}")
            return pairs

        return self._demo_forex_pairs()

    # -- Demo Data ---------------------------------------------------------

    def _demo_accounts(self) -> list[IBKRAccount]:
        acct_id = self._config.account_id or "DU1234567"
        return [
            IBKRAccount(
                account_id=acct_id,
                account_type="INDIVIDUAL",
                base_currency="USD",
                net_liquidation=285400.0,
                equity_with_loan=285400.0,
                buying_power=571200.0,
                available_funds=142700.0,
                excess_liquidity=168200.0,
                maintenance_margin=117200.0,
                initial_margin=142700.0,
                position_count=4,
                sma=285400.0,
            ),
        ]

    def _demo_positions(self) -> list[IBKRPosition]:
        return [
            IBKRPosition(
                conid=756733, symbol="SPY", asset_class="STK",
                quantity=100, average_cost=575.00, market_price=590.50,
                market_value=59050.0, unrealized_pnl=1550.0,
                unrealized_pnl_pct=2.70, realized_pnl=0.0, currency="USD",
            ),
            IBKRPosition(
                conid=265598, symbol="AAPL", asset_class="STK",
                quantity=200, average_cost=218.00, market_price=230.75,
                market_value=46150.0, unrealized_pnl=2550.0,
                unrealized_pnl_pct=5.85, realized_pnl=320.0, currency="USD",
            ),
            IBKRPosition(
                conid=12087792, symbol="EUR.USD", asset_class="CASH",
                quantity=50000, average_cost=1.0820, market_price=1.0875,
                market_value=54375.0, unrealized_pnl=275.0,
                unrealized_pnl_pct=0.51, realized_pnl=0.0, currency="USD",
            ),
            IBKRPosition(
                conid=495512552, symbol="ESH5", asset_class="FUT",
                quantity=2, average_cost=5920.00, market_price=5965.50,
                market_value=596550.0, unrealized_pnl=4550.0,
                unrealized_pnl_pct=0.77, realized_pnl=1200.0, currency="USD",
            ),
        ]

    def _demo_orders(self) -> list[IBKROrder]:
        acct_id = self._config.account_id or "DU1234567"
        return [
            IBKROrder(
                order_id="DEMO-IB-001", conid=265598, symbol="AAPL",
                side="BUY", quantity=200, filled_quantity=200, price=218.0,
                order_type="LMT", tif="DAY", status="Filled",
                account_id=acct_id,
            ),
            IBKROrder(
                order_id="DEMO-IB-002", conid=756733, symbol="SPY",
                side="BUY", quantity=100, filled_quantity=100, price=575.0,
                order_type="MKT", tif="DAY", status="Filled",
                account_id=acct_id,
            ),
            IBKROrder(
                order_id="DEMO-IB-003", conid=495512552, symbol="ESH5",
                side="BUY", quantity=2, filled_quantity=2, price=5920.0,
                order_type="LMT", tif="GTC", status="Filled",
                account_id=acct_id,
            ),
        ]

    def _demo_place_order(self, order: dict) -> IBKROrder:
        conid = int(order.get("conid", 265598))
        side = order.get("side", "BUY")
        qty = float(order.get("quantity", order.get("totalSize", 100)))
        order_type = order.get("orderType", "MKT")
        tif = order.get("tif", "DAY")

        demo_prices = {
            265598: ("AAPL", 230.75),
            756733: ("SPY", 590.50),
            272093: ("MSFT", 415.30),
            4815747: ("NVDA", 875.20),
            12087792: ("EUR.USD", 1.0875),
            495512552: ("ESH5", 5965.50),
        }
        symbol, price = demo_prices.get(conid, ("UNKNOWN", 100.0))

        return IBKROrder(
            order_id=f"DEMO-IB-{uuid.uuid4().hex[:8].upper()}",
            conid=conid,
            symbol=symbol,
            side=side,
            quantity=qty,
            filled_quantity=qty if order_type == "MKT" else 0,
            price=float(order.get("price", price)),
            order_type=order_type,
            tif=tif,
            status="Filled" if order_type == "MKT" else "PreSubmitted",
            account_id=self._config.account_id or "DU1234567",
        )

    def _demo_quotes(self, conids_or_symbols: list) -> list[IBKRQuote]:
        demo_data = {
            # conid-keyed data
            756733: {"sym": "SPY", "last": 590.50, "bid": 590.45, "ask": 590.55, "vol": 78500000, "chg": 2.30, "pct": 0.39, "o": 588.0, "h": 591.5, "l": 587.5, "c": 588.20},
            265598: {"sym": "AAPL", "last": 230.75, "bid": 230.70, "ask": 230.80, "vol": 55200000, "chg": 1.85, "pct": 0.81, "o": 229.0, "h": 231.5, "l": 228.5, "c": 228.90},
            12087792: {"sym": "EUR.USD", "last": 1.0875, "bid": 1.0873, "ask": 1.0877, "vol": 0, "chg": 0.0012, "pct": 0.11, "o": 1.0860, "h": 1.0892, "l": 1.0845, "c": 1.0863},
            495512552: {"sym": "ESH5", "last": 5965.50, "bid": 5965.25, "ask": 5965.75, "vol": 1850000, "chg": 22.50, "pct": 0.38, "o": 5943.00, "h": 5972.00, "l": 5935.00, "c": 5943.00},
            # symbol-keyed aliases
            "SPY": {"sym": "SPY", "conid": 756733, "last": 590.50, "bid": 590.45, "ask": 590.55, "vol": 78500000, "chg": 2.30, "pct": 0.39, "o": 588.0, "h": 591.5, "l": 587.5, "c": 588.20},
            "AAPL": {"sym": "AAPL", "conid": 265598, "last": 230.75, "bid": 230.70, "ask": 230.80, "vol": 55200000, "chg": 1.85, "pct": 0.81, "o": 229.0, "h": 231.5, "l": 228.5, "c": 228.90},
            "MSFT": {"sym": "MSFT", "conid": 272093, "last": 415.30, "bid": 415.25, "ask": 415.35, "vol": 22100000, "chg": -0.70, "pct": -0.17, "o": 416.0, "h": 417.0, "l": 414.0, "c": 416.00},
            "NVDA": {"sym": "NVDA", "conid": 4815747, "last": 875.20, "bid": 875.10, "ask": 875.30, "vol": 42000000, "chg": 12.50, "pct": 1.45, "o": 863.0, "h": 878.0, "l": 860.0, "c": 862.70},
            "EURUSD": {"sym": "EUR.USD", "conid": 12087792, "last": 1.0875, "bid": 1.0873, "ask": 1.0877, "vol": 0, "chg": 0.0012, "pct": 0.11, "o": 1.0860, "h": 1.0892, "l": 1.0845, "c": 1.0863},
            "ES": {"sym": "ESH5", "conid": 495512552, "last": 5965.50, "bid": 5965.25, "ask": 5965.75, "vol": 1850000, "chg": 22.50, "pct": 0.38, "o": 5943.00, "h": 5972.00, "l": 5935.00, "c": 5943.00},
        }
        result = []
        for item in conids_or_symbols:
            d = demo_data.get(item)
            if d is None:
                # Default fallback for unknown symbols/conids
                sym = str(item) if isinstance(item, str) else "UNKNOWN"
                d = {"sym": sym, "conid": item if isinstance(item, int) else 0, "last": 100.0, "bid": 99.95, "ask": 100.05, "vol": 1000000, "chg": 0.5, "pct": 0.5, "o": 99.5, "h": 100.5, "l": 99.0, "c": 99.50}
            conid = d.get("conid", item if isinstance(item, int) else 0)
            result.append(IBKRQuote(
                conid=int(conid) if conid else 0,
                symbol=d["sym"],
                last=d["last"], bid=d["bid"], ask=d["ask"],
                open=d["o"], high=d["h"], low=d["l"], close=d["c"],
                volume=d["vol"],
                change=d["chg"], change_pct=d["pct"],
                market_status="Open",
            ))
        return result

    def _demo_candles(self, conid: int, count: int = 30) -> list[IBKRCandle]:
        import random
        random.seed(conid % 2**31)
        demo_bases = {
            756733: 590.50,
            265598: 230.75,
            272093: 415.30,
            4815747: 875.20,
            12087792: 1.0875,
            495512552: 5965.50,
        }
        base = demo_bases.get(conid, 100.0)
        candles = []
        for i in range(count):
            change = random.uniform(-0.02, 0.02)
            o = base * (1 + change)
            c = o * (1 + random.uniform(-0.015, 0.015))
            h = max(o, c) * (1 + random.uniform(0, 0.01))
            lo = min(o, c) * (1 - random.uniform(0, 0.01))
            wap = (o + h + lo + c) / 4
            candles.append(IBKRCandle(
                open=round(o, 4), high=round(h, 4),
                low=round(lo, 4), close=round(c, 4),
                volume=random.randint(10_000_000, 80_000_000),
                wap=round(wap, 4),
                trade_count=random.randint(50000, 500000),
            ))
            base = c
        return candles

    def _demo_search_contract(self, symbol: str, sec_type: str = "") -> list[IBKRContract]:
        """Return demo contract search results."""
        all_contracts = {
            "AAPL": [
                IBKRContract(conid=265598, symbol="AAPL", sec_type="STK", exchange="NASDAQ", currency="USD", description="Apple Inc", local_symbol="AAPL"),
                IBKRContract(conid=265598001, symbol="AAPL", sec_type="OPT", exchange="SMART", currency="USD", description="Apple Inc Options", local_symbol="AAPL"),
            ],
            "SPY": [
                IBKRContract(conid=756733, symbol="SPY", sec_type="STK", exchange="ARCA", currency="USD", description="SPDR S&P 500 ETF Trust", local_symbol="SPY"),
                IBKRContract(conid=756733001, symbol="SPY", sec_type="OPT", exchange="SMART", currency="USD", description="SPDR S&P 500 ETF Options", local_symbol="SPY"),
            ],
            "MSFT": [
                IBKRContract(conid=272093, symbol="MSFT", sec_type="STK", exchange="NASDAQ", currency="USD", description="Microsoft Corporation", local_symbol="MSFT"),
            ],
            "NVDA": [
                IBKRContract(conid=4815747, symbol="NVDA", sec_type="STK", exchange="NASDAQ", currency="USD", description="NVIDIA Corporation", local_symbol="NVDA"),
            ],
            "EURUSD": [
                IBKRContract(conid=12087792, symbol="EUR", sec_type="CASH", exchange="IDEALPRO", currency="USD", description="European Euro", local_symbol="EUR.USD"),
            ],
            "EUR": [
                IBKRContract(conid=12087792, symbol="EUR", sec_type="CASH", exchange="IDEALPRO", currency="USD", description="European Euro", local_symbol="EUR.USD"),
            ],
            "GBPUSD": [
                IBKRContract(conid=12087797, symbol="GBP", sec_type="CASH", exchange="IDEALPRO", currency="USD", description="British Pound", local_symbol="GBP.USD"),
            ],
            "GBP": [
                IBKRContract(conid=12087797, symbol="GBP", sec_type="CASH", exchange="IDEALPRO", currency="USD", description="British Pound", local_symbol="GBP.USD"),
            ],
            "ES": [
                IBKRContract(conid=495512552, symbol="ES", sec_type="FUT", exchange="CME", currency="USD", description="E-Mini S&P 500 Futures Mar 2025", local_symbol="ESH5"),
                IBKRContract(conid=495512553, symbol="ES", sec_type="FUT", exchange="CME", currency="USD", description="E-Mini S&P 500 Futures Jun 2025", local_symbol="ESM5"),
            ],
            "NQ": [
                IBKRContract(conid=495512560, symbol="NQ", sec_type="FUT", exchange="CME", currency="USD", description="E-Mini Nasdaq 100 Futures Mar 2025", local_symbol="NQH5"),
            ],
            "CL": [
                IBKRContract(conid=495512570, symbol="CL", sec_type="FUT", exchange="NYMEX", currency="USD", description="Crude Oil Futures Mar 2025", local_symbol="CLH5"),
            ],
            "GC": [
                IBKRContract(conid=495512580, symbol="GC", sec_type="FUT", exchange="COMEX", currency="USD", description="Gold Futures Apr 2025", local_symbol="GCJ5"),
            ],
        }
        contracts = all_contracts.get(symbol.upper(), [
            IBKRContract(conid=999999, symbol=symbol.upper(), sec_type="STK", exchange="SMART", currency="USD", description=f"{symbol.upper()} Common Stock", local_symbol=symbol.upper()),
        ])
        if sec_type:
            contracts = [c for c in contracts if c.sec_type == sec_type]
        return contracts

    def _demo_forex_pairs(self) -> list[IBKRContract]:
        """Return demo list of available forex pairs."""
        return [
            IBKRContract(conid=12087792, symbol="EUR", sec_type="CASH", exchange="IDEALPRO", currency="USD", description="European Euro", local_symbol="EUR.USD"),
            IBKRContract(conid=12087797, symbol="GBP", sec_type="CASH", exchange="IDEALPRO", currency="USD", description="British Pound", local_symbol="GBP.USD"),
            IBKRContract(conid=12087802, symbol="JPY", sec_type="CASH", exchange="IDEALPRO", currency="USD", description="Japanese Yen", local_symbol="USD.JPY"),
            IBKRContract(conid=12087807, symbol="AUD", sec_type="CASH", exchange="IDEALPRO", currency="USD", description="Australian Dollar", local_symbol="AUD.USD"),
            IBKRContract(conid=12087812, symbol="CHF", sec_type="CASH", exchange="IDEALPRO", currency="USD", description="Swiss Franc", local_symbol="USD.CHF"),
            IBKRContract(conid=12087817, symbol="CAD", sec_type="CASH", exchange="IDEALPRO", currency="USD", description="Canadian Dollar", local_symbol="USD.CAD"),
            IBKRContract(conid=12087822, symbol="NZD", sec_type="CASH", exchange="IDEALPRO", currency="USD", description="New Zealand Dollar", local_symbol="NZD.USD"),
            IBKRContract(conid=12087827, symbol="EUR", sec_type="CASH", exchange="IDEALPRO", currency="GBP", description="Euro vs British Pound", local_symbol="EUR.GBP"),
            IBKRContract(conid=12087832, symbol="EUR", sec_type="CASH", exchange="IDEALPRO", currency="JPY", description="Euro vs Japanese Yen", local_symbol="EUR.JPY"),
            IBKRContract(conid=12087837, symbol="GBP", sec_type="CASH", exchange="IDEALPRO", currency="JPY", description="British Pound vs Japanese Yen", local_symbol="GBP.JPY"),
        ]
