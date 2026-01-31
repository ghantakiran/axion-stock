"""Drawdown Monitor.

Tracks account drawdown and enforces drawdown-based
position sizing adjustments and trade blocking.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from src.position_calculator.config import (
    DrawdownConfig,
    DrawdownAction,
    DEFAULT_DRAWDOWN_CONFIG,
)
from src.position_calculator.models import DrawdownState

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DrawdownMonitor:
    """Monitors account drawdown and adjusts sizing.

    Tracks peak equity, computes drawdown, and provides
    size multipliers and trade-blocking signals based on
    configurable thresholds.
    """

    def __init__(self, config: Optional[DrawdownConfig] = None) -> None:
        self.config = config or DEFAULT_DRAWDOWN_CONFIG
        self._peak_value: float = 0.0
        self._peak_date: Optional[datetime] = None
        self._current_value: float = 0.0
        self._trough_date: Optional[datetime] = None

    def update(self, account_value: float) -> DrawdownState:
        """Update with current account value and return state.

        Args:
            account_value: Current account value.

        Returns:
            Current DrawdownState.
        """
        now = _utc_now()
        self._current_value = account_value

        # Update peak
        if account_value >= self._peak_value:
            self._peak_value = account_value
            self._peak_date = now
            self._trough_date = None
        else:
            self._trough_date = now

        return self.get_state()

    def get_state(self) -> DrawdownState:
        """Get current drawdown state without updating values."""
        if self._peak_value <= 0:
            return DrawdownState(limit_pct=self.config.max_drawdown_pct)

        dd_dollars = self._peak_value - self._current_value
        dd_pct = (dd_dollars / self._peak_value) * 100 if self._peak_value > 0 else 0.0

        # Determine size multiplier
        multiplier = 1.0
        blocked = False

        if self.config.drawdown_action == DrawdownAction.REDUCE_SIZE:
            if dd_pct >= self.config.block_at_pct:
                multiplier = 0.0
                blocked = True
            elif dd_pct >= self.config.reduce_at_pct:
                multiplier = self.config.size_reduction_factor
        elif self.config.drawdown_action == DrawdownAction.BLOCK_NEW:
            if dd_pct >= self.config.block_at_pct:
                blocked = True
                multiplier = 0.0

        at_limit = dd_pct >= self.config.max_drawdown_pct
        at_warning = dd_pct >= self.config.warn_drawdown_pct
        at_reduce = dd_pct >= self.config.reduce_at_pct

        return DrawdownState(
            peak_value=self._peak_value,
            current_value=self._current_value,
            drawdown_pct=round(dd_pct, 2),
            drawdown_dollars=round(dd_dollars, 2),
            at_limit=at_limit,
            at_warning=at_warning,
            at_reduce=at_reduce,
            limit_pct=self.config.max_drawdown_pct,
            size_multiplier=multiplier,
            blocked=blocked,
            peak_date=self._peak_date,
            trough_date=self._trough_date,
        )

    def get_size_multiplier(self) -> float:
        """Get current size multiplier based on drawdown.

        Returns:
            Multiplier between 0 and 1 (0 = blocked, 1 = full size).
        """
        return self.get_state().size_multiplier

    def is_blocked(self) -> bool:
        """Check if new trades are blocked due to drawdown."""
        return self.get_state().blocked

    def reset(self, initial_value: float = 0.0) -> None:
        """Reset drawdown tracking.

        Args:
            initial_value: Starting account value.
        """
        self._peak_value = initial_value
        self._current_value = initial_value
        self._peak_date = _utc_now() if initial_value > 0 else None
        self._trough_date = None

    @property
    def peak_value(self) -> float:
        return self._peak_value

    @property
    def current_value(self) -> float:
        return self._current_value
