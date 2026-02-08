"""Request validation: payload size, content-type, IP lists, required headers."""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .config import GatewayConfig

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Outcome of request validation."""

    valid: bool = True
    errors: List[str] = field(default_factory=list)


class RequestValidator:
    """Validates inbound requests against configurable rules."""

    def __init__(self, config: Optional[GatewayConfig] = None) -> None:
        self._config = config or GatewayConfig()
        self._ip_allowlist: Set[str] = set()
        self._ip_blocklist: Set[str] = set()
        self._required_headers: Dict[str, List[str]] = {}

    # ── main validation ──────────────────────────────────────────────

    def validate_request(self, ctx: "RequestContext") -> ValidationResult:  # noqa: F821 – forward ref
        """Run all validation checks on the request context.

        Checks (in order):
        1. Payload size
        2. IP blocklist / allowlist
        3. Required headers per path
        """
        errors: List[str] = []

        # 1. Payload size
        if not self.check_payload_size(ctx.body_size):
            errors.append(
                f"Payload size {ctx.body_size} exceeds max {self._config.max_payload_bytes}"
            )

        # 2. IP checks (headers may contain X-Forwarded-For)
        client_ip = ctx.headers.get("X-Forwarded-For", ctx.headers.get("x-forwarded-for", ""))
        if not client_ip:
            client_ip = ctx.headers.get("remote_addr", "")

        if self._ip_blocklist and client_ip in self._ip_blocklist:
            errors.append(f"IP {client_ip} is blocked")

        if self._ip_allowlist and client_ip and client_ip not in self._ip_allowlist:
            errors.append(f"IP {client_ip} is not in allowlist")

        # 3. Required headers
        for pattern, required in self._required_headers.items():
            if ctx.path.startswith(pattern):
                for h in required:
                    if h not in ctx.headers:
                        errors.append(f"Missing required header '{h}' for path {pattern}")

        result = ValidationResult(valid=len(errors) == 0, errors=errors)
        if not result.valid:
            logger.warning("Validation failed for %s %s: %s", ctx.method, ctx.path, errors)
        return result

    # ── IP management ────────────────────────────────────────────────

    def add_ip_allowlist(self, ip: str) -> None:
        self._ip_allowlist.add(ip)
        logger.info("Added %s to IP allowlist", ip)

    def add_ip_blocklist(self, ip: str) -> None:
        self._ip_blocklist.add(ip)
        logger.info("Added %s to IP blocklist", ip)

    def remove_ip_allowlist(self, ip: str) -> None:
        self._ip_allowlist.discard(ip)
        logger.info("Removed %s from IP allowlist", ip)

    def remove_ip_blocklist(self, ip: str) -> None:
        self._ip_blocklist.discard(ip)
        logger.info("Removed %s from IP blocklist", ip)

    # ── header requirements ──────────────────────────────────────────

    def add_required_headers(self, path: str, headers: List[str]) -> None:
        """Register headers that must be present for a path prefix."""
        self._required_headers[path] = headers
        logger.info("Required headers for %s: %s", path, headers)

    # ── helpers ──────────────────────────────────────────────────────

    def check_payload_size(self, size: int) -> bool:
        """Return True if the payload size is within limits."""
        return size <= self._config.max_payload_bytes

    def get_ip_lists(self) -> Dict[str, List[str]]:
        """Return current allowlist and blocklist."""
        return {
            "allowlist": sorted(self._ip_allowlist),
            "blocklist": sorted(self._ip_blocklist),
        }
