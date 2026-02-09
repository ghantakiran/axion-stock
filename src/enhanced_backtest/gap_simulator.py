"""Gap Simulator — models overnight and event-driven price gaps.

Simulates realistic gap scenarios for stop-loss slippage modeling:
- Overnight gaps (market close → open)
- Earnings gaps (post-announcement jumps)
- News-driven gaps (sudden moves)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class GapConfig:
    """Configuration for gap simulation.

    Attributes:
        overnight_gap_probability: Probability of an overnight gap on any day.
        earnings_gap_probability: Probability of a gap on earnings days.
        avg_overnight_gap_pct: Average overnight gap magnitude.
        avg_earnings_gap_pct: Average earnings gap magnitude.
        max_gap_pct: Maximum gap percentage (circuit breaker level).
        stop_slippage_multiplier: How much worse stops fill during gaps (1-5).
        gap_std_multiplier: Standard deviation of gap size (as fraction of avg).
    """

    overnight_gap_probability: float = 0.10
    earnings_gap_probability: float = 0.85
    avg_overnight_gap_pct: float = 1.5
    avg_earnings_gap_pct: float = 5.0
    max_gap_pct: float = 20.0
    stop_slippage_multiplier: float = 2.5
    gap_std_multiplier: float = 0.5


@dataclass
class GapEvent:
    """A simulated gap event.

    Attributes:
        ticker: Symbol that gapped.
        gap_pct: Gap magnitude as percentage.
        gap_type: Type of gap (overnight, earnings, news).
        prev_close: Previous closing price.
        gap_open: Opening price after gap.
        stop_fill_price: Where a stop order would have filled.
        stop_slippage_pct: Additional slippage on stop fills.
        is_adverse: Whether gap was against the position.
    """

    ticker: str = ""
    gap_pct: float = 0.0
    gap_type: str = "overnight"
    prev_close: float = 0.0
    gap_open: float = 0.0
    stop_fill_price: float = 0.0
    stop_slippage_pct: float = 0.0
    is_adverse: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "gap_pct": round(self.gap_pct, 2),
            "gap_type": self.gap_type,
            "prev_close": round(self.prev_close, 2),
            "gap_open": round(self.gap_open, 2),
            "stop_fill_price": round(self.stop_fill_price, 2),
            "stop_slippage_pct": round(self.stop_slippage_pct, 2),
            "is_adverse": self.is_adverse,
        }


class GapSimulator:
    """Simulates price gaps for realistic backtesting.

    Models both random overnight gaps and scheduled earnings gaps.
    When a gap occurs, stop-loss orders fill at the gap-open price
    (or worse), not at the stop price — this is critical for
    accurate risk modeling.

    Args:
        config: GapConfig with probabilities and magnitudes.

    Example:
        sim = GapSimulator()
        event = sim.simulate_overnight_gap("AAPL", prev_close=185.0, position_side="long")
        if event.is_adverse:
            print(f"Adverse gap: stop would fill at {event.stop_fill_price:.2f}")
    """

    def __init__(self, config: GapConfig | None = None, seed: int | None = None) -> None:
        self.config = config or GapConfig()
        self._rng = random.Random(seed)

    def simulate_overnight_gap(
        self,
        ticker: str,
        prev_close: float,
        position_side: str = "long",
        stop_price: float | None = None,
    ) -> GapEvent | None:
        """Simulate a potential overnight gap.

        Args:
            ticker: Symbol.
            prev_close: Previous day's closing price.
            position_side: "long" or "short".
            stop_price: Current stop-loss price (if any).

        Returns:
            GapEvent if a gap occurred, None otherwise.
        """
        if self._rng.random() > self.config.overnight_gap_probability:
            return None

        return self._generate_gap(
            ticker, prev_close, "overnight",
            self.config.avg_overnight_gap_pct,
            position_side, stop_price,
        )

    def simulate_earnings_gap(
        self,
        ticker: str,
        prev_close: float,
        position_side: str = "long",
        stop_price: float | None = None,
    ) -> GapEvent:
        """Simulate an earnings-related gap (always occurs on earnings day).

        Args:
            ticker: Symbol.
            prev_close: Previous day's closing price.
            position_side: "long" or "short".
            stop_price: Current stop-loss price.

        Returns:
            GapEvent with earnings gap.
        """
        if self._rng.random() > self.config.earnings_gap_probability:
            # Small move on earnings (rare no-gap case)
            return self._generate_gap(
                ticker, prev_close, "earnings",
                0.5, position_side, stop_price,
            )

        return self._generate_gap(
            ticker, prev_close, "earnings",
            self.config.avg_earnings_gap_pct,
            position_side, stop_price,
        )

    def apply_stop_slippage(
        self,
        stop_price: float,
        gap_open: float,
        position_side: str,
    ) -> float:
        """Calculate where a stop order fills during a gap.

        During gaps, stops fill at the gap-open price (or worse),
        not at the stop price.

        Args:
            stop_price: The stop-loss price.
            gap_open: The opening price after the gap.
            position_side: "long" or "short".

        Returns:
            The actual fill price for the stop order.
        """
        if position_side == "long":
            # For long positions, adverse gap is down
            if gap_open < stop_price:
                # Stop triggered, fills at gap open or worse
                slippage = abs(gap_open - stop_price) * (self.config.stop_slippage_multiplier - 1)
                return gap_open - slippage * 0.1  # Some additional slippage
            return stop_price
        else:
            # For short positions, adverse gap is up
            if gap_open > stop_price:
                slippage = abs(gap_open - stop_price) * (self.config.stop_slippage_multiplier - 1)
                return gap_open + slippage * 0.1
            return stop_price

    def _generate_gap(
        self,
        ticker: str,
        prev_close: float,
        gap_type: str,
        avg_gap_pct: float,
        position_side: str,
        stop_price: float | None,
    ) -> GapEvent:
        """Generate a gap event with random direction and magnitude."""
        # Random direction with slight upward bias (markets tend up)
        direction = 1 if self._rng.random() < 0.55 else -1

        # Gap magnitude (log-normal distribution for realistic fat tails)
        std = avg_gap_pct * self.config.gap_std_multiplier
        gap_pct = self._rng.gauss(avg_gap_pct, std)
        gap_pct = max(0.01, min(self.config.max_gap_pct, abs(gap_pct)))
        gap_pct *= direction

        gap_open = prev_close * (1 + gap_pct / 100)

        # Check if gap is adverse to position
        is_adverse = (
            (position_side == "long" and gap_pct < 0)
            or (position_side == "short" and gap_pct > 0)
        )

        # Stop fill price
        stop_fill = gap_open
        stop_slippage = 0.0
        if stop_price and is_adverse:
            stop_fill = self.apply_stop_slippage(stop_price, gap_open, position_side)
            if prev_close > 0:
                stop_slippage = abs(stop_fill - stop_price) / prev_close * 100

        return GapEvent(
            ticker=ticker,
            gap_pct=gap_pct,
            gap_type=gap_type,
            prev_close=prev_close,
            gap_open=gap_open,
            stop_fill_price=stop_fill,
            stop_slippage_pct=stop_slippage,
            is_adverse=is_adverse,
        )
