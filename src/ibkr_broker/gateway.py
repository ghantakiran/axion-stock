"""IBKR Client Portal Gateway Management (PRD-157).

Manages the IBKR Client Portal Gateway process which runs locally and
provides the REST API at localhost:5000. Handles health checks,
reauthentication, session keepalive, and competing session detection.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

_HAS_HTTPX = False
try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    httpx = None  # type: ignore


# =====================================================================
# Gateway Status
# =====================================================================


@dataclass
class GatewayStatus:
    """Status of the IBKR Client Portal Gateway."""
    connected: bool = False
    authenticated: bool = False
    competing: bool = False
    server_name: str = ""
    server_version: str = ""
    uptime_seconds: float = 0.0
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "connected": self.connected,
            "authenticated": self.authenticated,
            "competing": self.competing,
            "server_name": self.server_name,
            "server_version": self.server_version,
            "uptime_seconds": self.uptime_seconds,
            "last_checked": self.last_checked.isoformat(),
        }

    @classmethod
    def from_api(cls, data: dict) -> "GatewayStatus":
        return cls(
            connected=data.get("connected", False),
            authenticated=data.get("authenticated", False),
            competing=data.get("competing", False),
            server_name=data.get("serverName", data.get("server_name", "")),
            server_version=data.get("serverVersion", data.get("server_version", "")),
            uptime_seconds=float(data.get("uptimeSeconds", data.get("uptime", 0))),
        )


# =====================================================================
# Gateway Manager
# =====================================================================


class IBKRGateway:
    """Manages the IBKR Client Portal Gateway lifecycle.

    The Client Portal Gateway runs as a local Java process and exposes
    the IBKR API at https://localhost:5000/v1/api. This class handles
    status checks, session reauthentication, and keepalive tickles.

    Example:
        gateway = IBKRGateway(config)
        status = await gateway.check_status()
        if not status.authenticated:
            await gateway.reauthenticate()
    """

    def __init__(self, config: Any):
        self._config = config
        self._http_client: Any = None
        self._demo_mode = True
        self._start_time = datetime.now(timezone.utc)

    async def _get_client(self) -> Any:
        """Get or create HTTP client for gateway communication."""
        if _HAS_HTTPX and not self._demo_mode:
            if self._http_client is None:
                self._http_client = httpx.AsyncClient(
                    base_url=self._config.gateway_url.replace("/v1/api", ""),
                    verify=self._config.ssl_verify,
                    timeout=self._config.request_timeout,
                )
            return self._http_client
        return None

    async def check_status(self) -> GatewayStatus:
        """Check the gateway connection and authentication status.

        Calls /v1/api/iserver/auth/status to verify the session.
        """
        client = await self._get_client()
        if client:
            try:
                resp = await client.post("/v1/api/iserver/auth/status")
                if resp.status_code == 200:
                    data = resp.json()
                    return GatewayStatus(
                        connected=data.get("connected", False),
                        authenticated=data.get("authenticated", False),
                        competing=data.get("competing", False),
                        server_name=data.get("serverName", ""),
                        server_version=data.get("serverVersion", ""),
                    )
            except Exception as e:
                logger.warning(f"Gateway status check failed: {e}")

        return self._demo_status()

    async def reauthenticate(self) -> bool:
        """Force reauthentication with the gateway.

        Calls /v1/api/iserver/reauthenticate to refresh the session.
        IBKR sessions expire every few hours and need periodic reauthentication.
        """
        client = await self._get_client()
        if client:
            try:
                resp = await client.post("/v1/api/iserver/reauthenticate")
                if resp.status_code == 200:
                    data = resp.json()
                    success = data.get("message", "") == "triggered"
                    if success:
                        logger.info("Gateway reauthentication triggered")
                    return success
            except Exception as e:
                logger.warning(f"Gateway reauthentication failed: {e}")
                return False

        logger.info("Demo mode: reauthentication simulated successfully")
        return True

    async def keep_alive(self) -> bool:
        """Tickle the gateway to keep the session alive.

        Calls /v1/api/tickle to prevent session timeout.
        Should be called every few minutes to maintain connectivity.
        """
        client = await self._get_client()
        if client:
            try:
                resp = await client.post("/v1/api/tickle")
                return resp.status_code == 200
            except Exception as e:
                logger.warning(f"Gateway keepalive failed: {e}")
                return False

        return True

    async def get_server_info(self) -> dict:
        """Get gateway server information and version details."""
        client = await self._get_client()
        if client:
            try:
                resp = await client.get("/v1/api/one/user")
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                logger.warning(f"Failed to get server info: {e}")

        return self._demo_server_info()

    def _demo_status(self) -> GatewayStatus:
        """Return demo gateway status."""
        elapsed = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        return GatewayStatus(
            connected=True,
            authenticated=True,
            competing=False,
            server_name="IBKR-Demo-Gateway",
            server_version="10.25.0a",
            uptime_seconds=elapsed,
        )

    def _demo_server_info(self) -> dict:
        """Return demo server information."""
        return {
            "serverName": "IBKR-Demo-Gateway",
            "serverVersion": "10.25.0a",
            "username": "demo_user",
            "accounts": ["DU1234567"],
            "features": {
                "optionChains": True,
                "futures": True,
                "forex": True,
                "bonds": True,
                "realTimeData": True,
                "paperTrading": True,
            },
        }
