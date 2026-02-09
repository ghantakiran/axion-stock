"""Dynamic parameter tuner based on recent trading performance.

Analyses the most recent trades and adjusts risk parameters up or down
depending on win/loss streaks and overall profitability, acting as an
intra-regime feedback loop on top of the regime-level profile.
"""

from __future__ import annotations

import copy
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ======================================================================
# Configuration
# ======================================================================


@dataclass
class TunerConfig:
    """Knobs for the performance tuner."""

    lookback_trades: int = 20
    tighten_after_losses: int = 3
    loosen_after_wins: int = 5
    max_tighten_factor: float = 0.5
    max_loosen_factor: float = 1.3
    performance_window_hours: float = 24.0


# ======================================================================
# Result Models
# ======================================================================


@dataclass
class TuningAdjustment:
    """A single field-level tuning change."""

    field: str = ""
    original_value: Any = None
    adjusted_value: Any = None
    reason: str = ""
    factor: float = 1.0


@dataclass
class TunerResult:
    """Outcome of a tuning pass."""

    adjustments: list[TuningAdjustment] = field(default_factory=list)
    performance_summary: dict = field(default_factory=dict)
    overall_factor: float = 1.0
    is_tightened: bool = False
    is_loosened: bool = False
    tuner_id: str = field(
        default_factory=lambda: str(uuid.uuid4())[:8]
    )
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        """Serialise the result to a plain dictionary."""
        return {
            "tuner_id": self.tuner_id,
            "adjustments": [
                {
                    "field": a.field,
                    "original_value": a.original_value,
                    "adjusted_value": a.adjusted_value,
                    "reason": a.reason,
                    "factor": a.factor,
                }
                for a in self.adjustments
            ],
            "performance_summary": self.performance_summary,
            "overall_factor": self.overall_factor,
            "is_tightened": self.is_tightened,
            "is_loosened": self.is_loosened,
            "timestamp": self.timestamp.isoformat(),
        }


# ======================================================================
# Fields the tuner can modify and their direction
# ======================================================================

# When tightening: these fields are *reduced* (multiplied by factor < 1)
_REDUCE_ON_TIGHTEN: list[str] = [
    "max_risk_per_trade",
    "daily_loss_limit",
    "max_concurrent_positions",
]

# When tightening: these fields are *increased* (divided by factor)
_INCREASE_ON_TIGHTEN: list[str] = [
    "reward_to_risk_target",
]


# ======================================================================
# PerformanceTuner
# ======================================================================


class PerformanceTuner:
    """Adjusts risk parameters based on recent trade outcomes.

    Call :meth:`record_trade` after each closed trade, then :meth:`tune`
    to get parameter adjustments that can be layered on top of the
    regime adapter's output.
    """

    def __init__(self, config: Optional[TunerConfig] = None) -> None:
        self._config = config or TunerConfig()
        self._trades: list[dict] = []

    # ------------------------------------------------------------------
    # Trade recording
    # ------------------------------------------------------------------

    def record_trade(
        self,
        pnl_pct: float,
        signal_type: str = "",
        regime: str = "",
    ) -> None:
        """Record a completed trade's PnL percentage.

        Parameters
        ----------
        pnl_pct:
            Profit/loss as a decimal fraction (e.g. 0.02 = +2 %).
        signal_type:
            Optional EMA signal type that generated the trade.
        regime:
            Optional regime label active at trade time.
        """
        self._trades.append(
            {
                "pnl_pct": pnl_pct,
                "signal_type": signal_type,
                "regime": regime,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trade_id": str(uuid.uuid4())[:8],
            }
        )

        # Cap stored history
        max_history = self._config.lookback_trades * 5
        if len(self._trades) > max_history:
            self._trades = self._trades[-max_history:]

    # ------------------------------------------------------------------
    # Tuning logic
    # ------------------------------------------------------------------

    def tune(self, current_config: dict) -> TunerResult:
        """Analyse recent trades and return parameter adjustments.

        Parameters
        ----------
        current_config:
            Dict of executor config fields to adjust.

        Returns
        -------
        TunerResult with adjustments (may be empty if no action needed).
        """
        window = self._trades[-self._config.lookback_trades:]
        if not window:
            return TunerResult(
                performance_summary=self._empty_summary(),
                overall_factor=1.0,
            )

        # Compute performance metrics
        pnls = [t["pnl_pct"] for t in window]
        wins = [p for p in pnls if p > 0]
        win_rate = len(wins) / len(pnls) if pnls else 0.0
        avg_pnl = sum(pnls) / len(pnls) if pnls else 0.0

        consecutive_losses = self._consecutive_tail(pnls, positive=False)
        consecutive_wins = self._consecutive_tail(pnls, positive=True)

        summary = {
            "win_rate": round(win_rate, 4),
            "avg_pnl": round(avg_pnl, 6),
            "consecutive_losses": consecutive_losses,
            "consecutive_wins": consecutive_wins,
            "total_trades": len(window),
        }

        adjustments: list[TuningAdjustment] = []
        overall_factor = 1.0
        is_tightened = False
        is_loosened = False

        # --- Tightening logic ---
        if consecutive_losses >= self._config.tighten_after_losses:
            tighten_factor = max(
                self._config.max_tighten_factor,
                1.0 - 0.1 * consecutive_losses,
            )
            overall_factor = tighten_factor
            is_tightened = True

            for fld in _REDUCE_ON_TIGHTEN:
                if fld not in current_config:
                    continue
                old_val = current_config[fld]
                new_val = old_val * tighten_factor
                if isinstance(old_val, int):
                    new_val = max(1, int(round(new_val)))
                else:
                    new_val = round(new_val, 6)
                if new_val != old_val:
                    adjustments.append(
                        TuningAdjustment(
                            field=fld,
                            original_value=old_val,
                            adjusted_value=new_val,
                            reason=(
                                f"{consecutive_losses} consecutive losses "
                                f"(factor={tighten_factor:.2f})"
                            ),
                            factor=tighten_factor,
                        )
                    )

            for fld in _INCREASE_ON_TIGHTEN:
                if fld not in current_config:
                    continue
                old_val = current_config[fld]
                # Increase by inverting the factor (e.g. 0.7 -> 1/0.7 = 1.43)
                increase_factor = 1.0 / tighten_factor if tighten_factor > 0 else 1.0
                new_val = old_val * increase_factor
                new_val = round(new_val, 4)
                if new_val != old_val:
                    adjustments.append(
                        TuningAdjustment(
                            field=fld,
                            original_value=old_val,
                            adjusted_value=new_val,
                            reason=(
                                f"{consecutive_losses} consecutive losses — "
                                f"require higher reward:risk "
                                f"(factor={increase_factor:.2f})"
                            ),
                            factor=increase_factor,
                        )
                    )

            logger.info(
                "PerformanceTuner TIGHTENED: %d consecutive losses, "
                "factor=%.2f, %d adjustments",
                consecutive_losses,
                tighten_factor,
                len(adjustments),
            )

        # --- Loosening logic ---
        elif (
            consecutive_wins >= self._config.loosen_after_wins
            and win_rate > 0.6
        ):
            loosen_factor = min(
                self._config.max_loosen_factor,
                1.0 + 0.05 * consecutive_wins,
            )
            overall_factor = loosen_factor
            is_loosened = True

            for fld in _REDUCE_ON_TIGHTEN:
                if fld not in current_config:
                    continue
                old_val = current_config[fld]
                new_val = old_val * loosen_factor
                if isinstance(old_val, int):
                    new_val = int(round(new_val))
                else:
                    new_val = round(new_val, 6)
                if new_val != old_val:
                    adjustments.append(
                        TuningAdjustment(
                            field=fld,
                            original_value=old_val,
                            adjusted_value=new_val,
                            reason=(
                                f"{consecutive_wins} consecutive wins, "
                                f"win_rate={win_rate:.1%} "
                                f"(factor={loosen_factor:.2f})"
                            ),
                            factor=loosen_factor,
                        )
                    )

            logger.info(
                "PerformanceTuner LOOSENED: %d consecutive wins (wr=%.1f%%), "
                "factor=%.2f, %d adjustments",
                consecutive_wins,
                win_rate * 100,
                loosen_factor,
                len(adjustments),
            )

        return TunerResult(
            adjustments=adjustments,
            performance_summary=summary,
            overall_factor=round(overall_factor, 4),
            is_tightened=is_tightened,
            is_loosened=is_loosened,
        )

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_trade_history(self) -> list[dict]:
        """Return a copy of all recorded trades."""
        return list(self._trades)

    def reset(self) -> None:
        """Clear all recorded trades."""
        self._trades.clear()
        logger.debug("PerformanceTuner state reset")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _consecutive_tail(pnls: list[float], positive: bool) -> int:
        """Count consecutive wins (positive=True) or losses from the tail."""
        count = 0
        for pnl in reversed(pnls):
            if positive and pnl > 0:
                count += 1
            elif not positive and pnl <= 0:
                count += 1
            else:
                break
        return count

    @staticmethod
    def _empty_summary() -> dict:
        """Return a zeroed-out performance summary."""
        return {
            "win_rate": 0.0,
            "avg_pnl": 0.0,
            "consecutive_losses": 0,
            "consecutive_wins": 0,
            "total_trades": 0,
        }
