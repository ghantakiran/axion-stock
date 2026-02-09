"""Signal freshness and deduplication guard.

Prevents two classes of bugs that cause real-money losses:

1. **Stale signals**: A signal generated 10 minutes ago (e.g. during a
   processing backlog) passes all risk gates even though the market has
   moved.  SignalGuard rejects signals older than `max_age_seconds`.

2. **Duplicate signals**: The same EMA cloud signal fires on consecutive
   ticks for the same bar, causing multiple entries on the same setup.
   SignalGuard tracks (ticker, signal_type, direction) tuples and rejects
   repeats within `dedup_window_seconds`.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.ema_signals.detector import TradeSignal

logger = logging.getLogger(__name__)


@dataclass
class GuardConfig:
    """Configuration for the signal guard.

    Attributes:
        max_age_seconds: Maximum age of a signal before it's considered stale.
        dedup_window_seconds: Window within which identical signals are rejected.
    """

    max_age_seconds: float = 120.0
    dedup_window_seconds: float = 300.0


class SignalGuard:
    """Gate that rejects stale and duplicate trade signals.

    Thread-safe: uses a lock for the deduplication cache.

    Args:
        max_age_seconds: Signals older than this are rejected.
        dedup_window_seconds: Same (ticker, type, direction) within this
            window is rejected as duplicate.

    Example:
        guard = SignalGuard(max_age_seconds=60, dedup_window_seconds=300)
        if not guard.is_fresh(signal):
            return  # signal too old
        if guard.is_duplicate(signal):
            return  # already processed this setup
    """

    def __init__(
        self,
        max_age_seconds: float = 120.0,
        dedup_window_seconds: float = 300.0,
    ) -> None:
        self.max_age_seconds = max_age_seconds
        self.dedup_window_seconds = dedup_window_seconds
        self._lock = threading.Lock()
        # Key: (ticker, signal_type_str, direction) → timestamp (monotonic)
        self._seen: dict[tuple[str, str, str], float] = {}

    def is_fresh(self, signal: TradeSignal) -> bool:
        """Return True if the signal is within the max age window.

        Compares signal.timestamp against current UTC time.
        """
        now = datetime.now(timezone.utc)
        age = (now - signal.timestamp).total_seconds()
        if age > self.max_age_seconds:
            logger.info(
                "Stale signal rejected: %s %s %s age=%.1fs (max=%ds)",
                signal.ticker, signal.direction,
                signal.signal_type.value if hasattr(signal.signal_type, "value") else str(signal.signal_type),
                age, self.max_age_seconds,
            )
            return False
        return True

    def is_duplicate(self, signal: TradeSignal) -> bool:
        """Return True if this signal is a duplicate within the dedup window.

        A signal is a duplicate if the same (ticker, signal_type, direction)
        tuple was seen within dedup_window_seconds.

        Side effect: records the signal in the seen cache if not duplicate.
        """
        sig_type = signal.signal_type.value if hasattr(signal.signal_type, "value") else str(signal.signal_type)
        key = (signal.ticker, sig_type, signal.direction)
        now = time.monotonic()

        with self._lock:
            self._evict_expired(now)

            last_seen = self._seen.get(key)
            if last_seen is not None and (now - last_seen) < self.dedup_window_seconds:
                logger.info(
                    "Duplicate signal rejected: %s %s %s (seen %.1fs ago, window=%ds)",
                    signal.ticker, signal.direction, sig_type,
                    now - last_seen, self.dedup_window_seconds,
                )
                return True

            # Record this signal
            self._seen[key] = now
            return False

    def check(self, signal: TradeSignal) -> Optional[str]:
        """Combined freshness + dedup check.

        Returns:
            None if signal passes all checks.
            Rejection reason string if signal should be rejected.
        """
        if not self.is_fresh(signal):
            return f"Stale signal: age exceeds {self.max_age_seconds}s"
        if self.is_duplicate(signal):
            return f"Duplicate signal within {self.dedup_window_seconds}s window"
        return None

    def get_stats(self) -> dict:
        """Return guard statistics."""
        with self._lock:
            self._evict_expired(time.monotonic())
            return {
                "active_dedup_entries": len(self._seen),
                "max_age_seconds": self.max_age_seconds,
                "dedup_window_seconds": self.dedup_window_seconds,
            }

    def clear(self) -> None:
        """Clear the dedup cache."""
        with self._lock:
            self._seen.clear()

    def _evict_expired(self, now: float) -> None:
        """Remove entries older than dedup_window_seconds."""
        expired = [
            k for k, ts in self._seen.items()
            if (now - ts) >= self.dedup_window_seconds
        ]
        for k in expired:
            del self._seen[k]
