"""API versioning with lifecycle management (RFC 8594 Sunset headers)."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .config import VersionStatus

logger = logging.getLogger(__name__)


@dataclass
class APIVersion:
    """Metadata for a single API version."""

    version: str = ""
    status: VersionStatus = VersionStatus.ACTIVE
    released_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sunset_at: Optional[datetime] = None
    description: str = ""
    changelog: List[str] = field(default_factory=list)


class VersionManager:
    """Manages API versions and their lifecycle transitions."""

    def __init__(self, default_version: str = "v1") -> None:
        self._versions: Dict[str, APIVersion] = {}
        self._default_version: str = default_version

    # ── lifecycle ────────────────────────────────────────────────────

    def register_version(
        self,
        version: str,
        description: str = "",
        changelog: Optional[List[str]] = None,
    ) -> APIVersion:
        """Register a new API version as ACTIVE."""
        v = APIVersion(
            version=version,
            status=VersionStatus.ACTIVE,
            description=description,
            changelog=changelog or [],
        )
        self._versions[version] = v
        logger.info("Registered API version %s", version)
        return v

    def deprecate_version(self, version: str, sunset_at: Optional[datetime] = None) -> None:
        """Mark a version as DEPRECATED with an optional sunset date."""
        v = self._require_version(version)
        v.status = VersionStatus.DEPRECATED
        v.sunset_at = sunset_at
        logger.info("Deprecated API version %s (sunset: %s)", version, sunset_at)

    def sunset_version(self, version: str) -> None:
        """Move a version to SUNSET (read-only / no new features)."""
        v = self._require_version(version)
        v.status = VersionStatus.SUNSET
        if v.sunset_at is None:
            v.sunset_at = datetime.now(timezone.utc)
        logger.info("Sunset API version %s", version)

    def retire_version(self, version: str) -> None:
        """Fully retire a version -- requests will be rejected."""
        v = self._require_version(version)
        v.status = VersionStatus.RETIRED
        logger.info("Retired API version %s", version)

    # ── resolution ───────────────────────────────────────────────────

    def resolve_version(self, requested_version: Optional[str]) -> Tuple[str, Dict[str, str]]:
        """Resolve the effective version and return any warning headers.

        Returns:
            (resolved_version, extra_headers) -- extra_headers may include
            Sunset / Deprecation per RFC 8594.
        """
        version_str = requested_version or self._default_version
        headers: Dict[str, str] = {}

        v = self._versions.get(version_str)
        if v is None:
            # Fallback to default
            logger.warning("Unknown version %s, falling back to %s", version_str, self._default_version)
            return self._default_version, headers

        if v.status == VersionStatus.RETIRED:
            logger.warning("Requested retired version %s", version_str)
            return version_str, {"X-API-Warn": f"Version {version_str} is retired"}

        if v.status in (VersionStatus.DEPRECATED, VersionStatus.SUNSET):
            headers.update(self.get_sunset_headers(version_str))

        return version_str, headers

    def get_version(self, version: str) -> Optional[APIVersion]:
        """Return version metadata (or None)."""
        return self._versions.get(version)

    def get_active_versions(self) -> List[APIVersion]:
        """Return all versions that are ACTIVE or DEPRECATED (still usable)."""
        return [
            v
            for v in self._versions.values()
            if v.status in (VersionStatus.ACTIVE, VersionStatus.DEPRECATED)
        ]

    def get_sunset_headers(self, version: str) -> Dict[str, str]:
        """Build RFC 8594 Sunset + Deprecation headers."""
        v = self._versions.get(version)
        if v is None:
            return {}
        headers: Dict[str, str] = {}
        if v.sunset_at:
            headers["Sunset"] = v.sunset_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
        if v.status == VersionStatus.DEPRECATED:
            headers["Deprecation"] = "true"
        return headers

    def is_supported(self, version: str) -> bool:
        """Return True if the version exists and is not RETIRED."""
        v = self._versions.get(version)
        if v is None:
            return False
        return v.status != VersionStatus.RETIRED

    # ── internals ────────────────────────────────────────────────────

    def _require_version(self, version: str) -> APIVersion:
        v = self._versions.get(version)
        if v is None:
            raise ValueError(f"Unknown API version: {version}")
        return v
