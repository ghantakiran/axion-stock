"""Greeks-based validation for options scalps.

Validates that option Greeks are favorable before entry:
IV rank, theta burn, bid-ask spread, delta range, gamma limits.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from src.ema_signals.detector import TradeSignal
from src.options_scalper.strike_selector import StrikeSelection

logger = logging.getLogger(__name__)


@dataclass
class GreeksDecision:
    """Result of Greeks-based validation."""

    approved: bool
    reason: Optional[str] = None
    adjustments: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "reason": self.reason,
            "adjustments": self.adjustments,
        }


class GreeksGate:
    """Validate that option Greeks are favorable for a scalp trade.

    Checks:
    1. IV rank < 80th percentile (avoid IV crush)
       Exception: IV rank doesn't matter for 0DTE (theta dominates)
    2. Theta: daily theta burn < 5% of premium for 1DTE+
    3. Bid-ask spread < max_spread_pct
    4. Delta within target range (0.30-0.50)
    5. Gamma check: avoid extreme gamma (>0.15) unless 0DTE
    """

    def __init__(self, config):
        self.config = config

    def validate(
        self, selection: StrikeSelection, signal: TradeSignal
    ) -> GreeksDecision:
        """Run all Greeks checks."""
        checks = [
            self._check_iv_rank,
            self._check_theta_burn,
            self._check_spread,
            self._check_delta,
            self._check_gamma,
        ]

        for check_fn in checks:
            decision = check_fn(selection)
            if not decision.approved:
                logger.info(
                    "Greeks REJECTED for %s: %s", signal.ticker, decision.reason
                )
                return decision

        return GreeksDecision(approved=True)

    def _check_iv_rank(self, selection: StrikeSelection) -> GreeksDecision:
        """1. IV rank check — skip for 0DTE."""
        if selection.dte == 0:
            return GreeksDecision(approved=True)

        if selection.iv > self.config.max_iv_rank:
            return GreeksDecision(
                approved=False,
                reason=f"IV too high: {selection.iv:.2f} > {self.config.max_iv_rank:.2f}",
                adjustments={"reduce_size": True},
            )
        return GreeksDecision(approved=True)

    def _check_theta_burn(self, selection: StrikeSelection) -> GreeksDecision:
        """2. Theta burn < 5% of premium for 1DTE+."""
        if selection.dte == 0:
            return GreeksDecision(approved=True)

        if selection.mid > 0:
            theta_pct = abs(selection.theta) / selection.mid
            if theta_pct > self.config.max_theta_burn_pct:
                return GreeksDecision(
                    approved=False,
                    reason=f"Theta burn too high: {theta_pct:.1%} > {self.config.max_theta_burn_pct:.0%}",
                )
        return GreeksDecision(approved=True)

    def _check_spread(self, selection: StrikeSelection) -> GreeksDecision:
        """3. Bid-ask spread within limits."""
        if selection.spread_pct > self.config.max_spread_pct:
            return GreeksDecision(
                approved=False,
                reason=f"Spread too wide: {selection.spread_pct:.1%} > {self.config.max_spread_pct:.0%}",
            )
        return GreeksDecision(approved=True)

    def _check_delta(self, selection: StrikeSelection) -> GreeksDecision:
        """4. Delta within target range."""
        abs_delta = abs(selection.delta)
        if abs_delta < self.config.target_delta_min or abs_delta > self.config.target_delta_max:
            return GreeksDecision(
                approved=False,
                reason=f"Delta {abs_delta:.2f} outside range [{self.config.target_delta_min:.2f}, {self.config.target_delta_max:.2f}]",
            )
        return GreeksDecision(approved=True)

    def _check_gamma(self, selection: StrikeSelection) -> GreeksDecision:
        """5. Gamma check — avoid extreme gamma unless 0DTE."""
        if selection.dte == 0:
            return GreeksDecision(approved=True)

        if selection.gamma > self.config.max_gamma:
            return GreeksDecision(
                approved=False,
                reason=f"Gamma too high: {selection.gamma:.3f} > {self.config.max_gamma:.3f}",
            )
        return GreeksDecision(approved=True)
