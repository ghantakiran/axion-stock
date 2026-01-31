"""Position Sizing Engine.

Calculates trade-level position sizes based on risk parameters,
Kelly Criterion, and portfolio constraints.
"""

import logging
import math
from typing import Optional

from src.position_calculator.config import (
    SizingConfig,
    KellyConfig,
    SizingMethod,
    InstrumentType,
    DEFAULT_SIZING_CONFIG,
    DEFAULT_KELLY_CONFIG,
)
from src.position_calculator.models import SizingInputs, SizingResult

logger = logging.getLogger(__name__)


class PositionSizingEngine:
    """Calculates position sizes for individual trades.

    Supports risk-based, Kelly Criterion, fixed-dollar, and
    fixed-share sizing methods with constraint enforcement.
    """

    def __init__(
        self,
        config: Optional[SizingConfig] = None,
        kelly_config: Optional[KellyConfig] = None,
    ) -> None:
        self.config = config or DEFAULT_SIZING_CONFIG
        self.kelly_config = kelly_config or DEFAULT_KELLY_CONFIG

    def calculate(
        self,
        inputs: SizingInputs,
        method: Optional[SizingMethod] = None,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        current_heat_pct: float = 0.0,
        heat_limit_pct: float = 6.0,
        drawdown_multiplier: float = 1.0,
    ) -> SizingResult:
        """Calculate position size for a trade.

        Args:
            inputs: Sizing inputs (account, entry, stop, etc.).
            method: Sizing method override.
            win_rate: Win rate for Kelly sizing.
            avg_win: Average win % for Kelly.
            avg_loss: Average loss % for Kelly.
            current_heat_pct: Current portfolio heat %.
            heat_limit_pct: Max portfolio heat %.
            drawdown_multiplier: Size multiplier from drawdown state (0-1).

        Returns:
            SizingResult with position size and metadata.
        """
        method = method or self.config.default_sizing_method
        result = SizingResult(sizing_method=method)
        warnings: list[str] = []

        # Validate inputs
        if inputs.entry_price <= 0:
            warnings.append("Entry price must be positive")
            result.warnings = warnings
            return result

        if inputs.risk_per_share == 0:
            warnings.append("Entry and stop price are equal; no risk defined")
            result.warnings = warnings
            return result

        # Calculate raw position size
        if method == SizingMethod.FIXED_RISK:
            raw_size = self._fixed_risk_size(inputs)
        elif method in (SizingMethod.KELLY, SizingMethod.HALF_KELLY, SizingMethod.QUARTER_KELLY):
            raw_size = self._kelly_size(inputs, method, win_rate, avg_win, avg_loss, warnings)
        elif method == SizingMethod.FIXED_DOLLAR:
            raw_size = self._fixed_dollar_size(inputs)
        elif method == SizingMethod.FIXED_SHARES:
            raw_size = inputs.contract_multiplier  # Use multiplier as share count
        else:
            raw_size = self._fixed_risk_size(inputs)

        # Apply drawdown adjustment
        if drawdown_multiplier < 1.0:
            raw_size = raw_size * drawdown_multiplier
            result.drawdown_adjusted = True
            warnings.append(f"Size reduced by drawdown (multiplier={drawdown_multiplier:.2f})")

        # Round down to whole shares/contracts
        if self.config.round_down:
            position_size = max(0, math.floor(raw_size))
        else:
            position_size = max(0, round(raw_size))

        # Apply max position constraint
        max_position_value = inputs.account_value * (self.config.max_position_pct / 100.0)
        position_value = position_size * inputs.entry_price * inputs.contract_multiplier

        if position_value > max_position_value:
            position_size = math.floor(max_position_value / (inputs.entry_price * inputs.contract_multiplier))
            position_value = position_size * inputs.entry_price * inputs.contract_multiplier
            result.exceeds_max_position = True
            warnings.append(f"Size capped at max position ({self.config.max_position_pct}%)")

        # Apply minimum position value
        if position_value < self.config.min_position_value and position_size > 0:
            warnings.append(f"Position value ${position_value:.0f} below minimum ${self.config.min_position_value:.0f}")

        # Check portfolio heat
        trade_heat_pct = (inputs.risk_per_share * position_size * inputs.contract_multiplier / inputs.account_value) * 100
        if current_heat_pct + trade_heat_pct > heat_limit_pct:
            result.exceeds_portfolio_heat = True
            warnings.append(
                f"Trade would push heat to {current_heat_pct + trade_heat_pct:.1f}% "
                f"(limit={heat_limit_pct:.1f}%)"
            )

        # Compute risk/reward
        risk_amount = inputs.risk_per_share * position_size * inputs.contract_multiplier
        risk_pct = (risk_amount / inputs.account_value * 100) if inputs.account_value > 0 else 0.0

        risk_reward = None
        if inputs.target_price is not None and inputs.risk_per_share > 0:
            reward_per_share = abs(inputs.target_price - inputs.entry_price)
            risk_reward = reward_per_share / inputs.risk_per_share

        # Populate result
        result.position_size = position_size
        result.position_value = position_size * inputs.entry_price * inputs.contract_multiplier
        result.risk_amount = risk_amount
        result.risk_pct = risk_pct
        result.risk_reward_ratio = risk_reward
        result.r_multiple = 1.0  # 1R = initial risk
        result.warnings = warnings

        return result

    def _fixed_risk_size(self, inputs: SizingInputs) -> float:
        """Calculate size based on fixed risk per trade."""
        risk_dollars = inputs.risk_dollars

        # Cap at max risk
        max_risk = inputs.account_value * (self.config.max_risk_pct / 100.0)
        risk_dollars = min(risk_dollars, max_risk)

        risk_per_unit = inputs.risk_per_share * inputs.contract_multiplier
        if risk_per_unit <= 0:
            return 0.0

        return risk_dollars / risk_per_unit

    def _kelly_size(
        self,
        inputs: SizingInputs,
        method: SizingMethod,
        win_rate: Optional[float],
        avg_win: Optional[float],
        avg_loss: Optional[float],
        warnings: list[str],
    ) -> float:
        """Calculate size using Kelly Criterion."""
        if not win_rate or not avg_win or not avg_loss:
            warnings.append("Kelly requires win_rate, avg_win, avg_loss; falling back to fixed risk")
            return self._fixed_risk_size(inputs)

        if win_rate < self.kelly_config.min_win_rate:
            warnings.append(f"Win rate {win_rate:.1%} below Kelly minimum {self.kelly_config.min_win_rate:.1%}")
            return self._fixed_risk_size(inputs)

        # Kelly: f* = (p*b - q) / b
        b = avg_win / avg_loss if avg_loss > 0 else 0
        if b <= 0:
            warnings.append("Invalid win/loss ratio for Kelly")
            return self._fixed_risk_size(inputs)

        p = win_rate
        q = 1 - p
        kelly_full = (p * b - q) / b

        if kelly_full <= 0:
            warnings.append("Kelly fraction is negative (no edge); falling back to fixed risk")
            return self._fixed_risk_size(inputs)

        # Apply Kelly fraction
        if method == SizingMethod.HALF_KELLY:
            fraction = 0.5
        elif method == SizingMethod.QUARTER_KELLY:
            fraction = 0.25
        else:
            fraction = self.kelly_config.kelly_fraction

        kelly_pct = kelly_full * fraction * 100
        kelly_pct = min(kelly_pct, self.kelly_config.max_kelly_pct)

        risk_dollars = inputs.account_value * (kelly_pct / 100.0)
        risk_per_unit = inputs.risk_per_share * inputs.contract_multiplier

        if risk_per_unit <= 0:
            return 0.0

        return risk_dollars / risk_per_unit

    def _fixed_dollar_size(self, inputs: SizingInputs) -> float:
        """Calculate size based on fixed dollar amount."""
        dollars = inputs.risk_per_trade_dollars or inputs.risk_dollars
        price = inputs.entry_price * inputs.contract_multiplier
        if price <= 0:
            return 0.0
        return dollars / price

    def compute_stop_price(
        self,
        entry_price: float,
        stop_type: str,
        is_long: bool = True,
        percent: float = 2.0,
        atr_value: Optional[float] = None,
        atr_multiplier: float = 2.0,
        fixed_stop: Optional[float] = None,
    ) -> float:
        """Compute stop price from various methods.

        Args:
            entry_price: Trade entry price.
            stop_type: "fixed", "percent", or "atr_based".
            is_long: True for long trades.
            percent: Stop distance as percentage.
            atr_value: ATR value for ATR-based stops.
            atr_multiplier: ATR multiplier.
            fixed_stop: Fixed stop price.

        Returns:
            Computed stop price.
        """
        if stop_type == "fixed" and fixed_stop is not None:
            return fixed_stop

        if stop_type == "percent":
            distance = entry_price * (percent / 100.0)
            if is_long:
                return round(entry_price - distance, 2)
            else:
                return round(entry_price + distance, 2)

        if stop_type == "atr_based" and atr_value is not None:
            distance = atr_value * atr_multiplier
            if is_long:
                return round(entry_price - distance, 2)
            else:
                return round(entry_price + distance, 2)

        return entry_price  # Fallback (no risk)
