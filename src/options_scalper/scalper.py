"""Options scalping engine for 0DTE/1DTE trades.

Converts EMA cloud signals on 1-min charts into options trades
with Greeks-aware validation and risk-controlled sizing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Literal, Optional

from src.ema_signals.detector import TradeSignal
from src.trade_executor.router import Order, OrderResult, OrderRouter

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ScalpConfig:
    """Configuration for the options & ETF scalping engine."""

    # Instrument tickers
    scalp_tickers: list[str] = field(
        default_factory=lambda: ["SPY", "QQQ", "NVDA", "TSLA", "AAPL", "MSFT", "META", "AMZN"]
    )
    allow_spx: bool = True

    # Strike selection
    target_delta_min: float = 0.30
    target_delta_max: float = 0.50
    max_spread_pct: float = 0.10
    min_open_interest: int = 1000
    min_volume: int = 500

    # Risk
    max_risk_per_scalp: float = 0.02
    max_loss_pct: float = 0.50
    profit_target_pct: float = 0.25
    max_concurrent_scalps: int = 3
    no_average_up: bool = True

    # Greeks
    max_iv_rank: float = 0.80
    max_theta_burn_pct: float = 0.05
    max_gamma: float = 0.15

    # Timing
    scalp_start_time: str = "09:35"
    zero_dte_cutoff: str = "14:00"
    one_dte_cutoff: str = "15:30"
    no_scalp_around_fomc: bool = True

    # Execution
    entry_order_type: str = "limit"
    limit_offset: float = 0.02
    fill_timeout_seconds: int = 15

    # Conviction
    min_conviction_to_scalp: int = 50
    require_macro_alignment: bool = True

    # Leveraged ETF settings
    etf_max_risk_per_scalp: float = 0.03
    etf_stop_loss_pct: float = 0.02
    etf_profit_target_pct: float = 0.02
    etf_max_concurrent_scalps: int = 5
    etf_min_daily_volume: float = 10_000_000
    etf_max_spread_pct: float = 0.05
    etf_prefer_3x: bool = True
    etf_sector_mapping_enabled: bool = True


# ═══════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ScalpPosition:
    """An open options scalp position."""

    ticker: str
    option_symbol: str
    option_type: Literal["call", "put"]
    strike: float
    expiry: date
    dte: int
    direction: Literal["long_call", "long_put"]
    contracts: int
    entry_price: float
    current_price: float
    delta: float
    theta: float
    iv: float
    entry_time: datetime
    signal_id: str = ""

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.contracts * 100

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.entry_price <= 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "option_symbol": self.option_symbol,
            "option_type": self.option_type,
            "strike": self.strike,
            "dte": self.dte,
            "direction": self.direction,
            "contracts": self.contracts,
            "entry_price": round(self.entry_price, 2),
            "current_price": round(self.current_price, 2),
            "pnl": round(self.unrealized_pnl, 2),
            "pnl_pct": round(self.unrealized_pnl_pct, 4),
            "delta": round(self.delta, 3),
            "theta": round(self.theta, 3),
            "iv": round(self.iv, 4),
        }


@dataclass
class ScalpResult:
    """Result of an options scalp attempt."""

    success: bool
    position: Optional[ScalpPosition] = None
    order_result: Optional[OrderResult] = None
    rejection_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "rejection_reason": self.rejection_reason,
            "position": self.position.to_dict() if self.position else None,
        }


# ═══════════════════════════════════════════════════════════════════════
# Options Scalper
# ═══════════════════════════════════════════════════════════════════════


class OptionsScalper:
    """0DTE/1DTE options scalping engine.

    Converts 1-min EMA cloud signals into options trades:
    1. Determine call/put based on signal direction
    2. Select optimal strike (StrikeSelector)
    3. Validate Greeks (GreeksGate)
    4. Size position (ScalpSizer)
    5. Submit order via OrderRouter
    """

    def __init__(
        self,
        config: Optional[ScalpConfig] = None,
        router: Optional[OrderRouter] = None,
    ):
        self.config = config or ScalpConfig()
        self.router = router or OrderRouter(paper_mode=True)
        self.positions: list[ScalpPosition] = []
        self.closed_trades: list[dict] = []

    def process_signal(
        self,
        signal: TradeSignal,
        account_equity: float = 100_000.0,
        chain_data: Optional[list] = None,
    ) -> ScalpResult:
        """Convert EMA signal to options order."""
        from src.options_scalper.strike_selector import StrikeSelector
        from src.options_scalper.greeks_gate import GreeksGate
        from src.options_scalper.sizing import ScalpSizer

        # Pre-filter
        if not self._should_scalp(signal):
            return ScalpResult(success=False, rejection_reason="Signal filtered out")

        if len(self.positions) >= self.config.max_concurrent_scalps:
            return ScalpResult(success=False, rejection_reason="Max concurrent scalps reached")

        # No averaging up
        if self.config.no_average_up:
            for pos in self.positions:
                if pos.ticker == signal.ticker and pos.unrealized_pnl < 0:
                    return ScalpResult(
                        success=False,
                        rejection_reason=f"Existing losing position in {signal.ticker}",
                    )

        # Determine call/put
        option_type: Literal["call", "put"] = "call" if signal.direction == "long" else "put"
        direction: Literal["long_call", "long_put"] = f"long_{option_type}"

        # Strike selection
        selector = StrikeSelector(self.config)
        selection = selector.select(
            ticker=signal.ticker,
            direction=signal.direction,
            chain_data=chain_data,
            underlying_price=signal.entry_price,
        )

        if selection is None:
            return ScalpResult(success=False, rejection_reason="No suitable strike found")

        # Greeks gate
        gate = GreeksGate(self.config)
        greeks_decision = gate.validate(selection, signal)

        if not greeks_decision.approved:
            return ScalpResult(success=False, rejection_reason=greeks_decision.reason)

        # Size position
        sizer = ScalpSizer(self.config)
        contracts = sizer.calculate(selection.mid, signal.conviction, account_equity)

        if contracts <= 0:
            return ScalpResult(success=False, rejection_reason="Position size too small")

        # Submit order
        order = Order(
            ticker=selection.option_symbol,
            side="buy",
            qty=contracts,
            order_type=self.config.entry_order_type,
            limit_price=round(selection.mid + self.config.limit_offset, 2),
            signal_id=signal.metadata.get("signal_id", ""),
        )
        order_result = self.router.submit_order(order)

        if order_result.status == "rejected":
            return ScalpResult(
                success=False,
                order_result=order_result,
                rejection_reason=order_result.rejection_reason,
            )

        # Create position
        position = ScalpPosition(
            ticker=signal.ticker,
            option_symbol=selection.option_symbol,
            option_type=option_type,
            strike=selection.strike,
            expiry=selection.expiry,
            dte=selection.dte,
            direction=direction,
            contracts=contracts,
            entry_price=order_result.filled_price or selection.mid,
            current_price=order_result.filled_price or selection.mid,
            delta=selection.delta,
            theta=selection.theta,
            iv=selection.iv,
            entry_time=datetime.now(timezone.utc),
            signal_id=signal.metadata.get("signal_id", ""),
        )

        self.positions.append(position)
        logger.info(
            "Scalp opened: %s %s %.0f strike, %d contracts @ $%.2f",
            direction, signal.ticker, selection.strike,
            contracts, position.entry_price,
        )
        return ScalpResult(success=True, position=position, order_result=order_result)

    def check_exits(self) -> list[dict]:
        """Check all open scalp positions for exit conditions."""
        exits = []
        for pos in list(self.positions):
            reason = self._check_exit(pos)
            if reason:
                exits.append({"position": pos, "reason": reason})
                self._close_position(pos, reason)
        return exits

    def _check_exit(self, pos: ScalpPosition) -> Optional[str]:
        """Check exit conditions for a single position."""
        # Profit target
        if pos.unrealized_pnl_pct >= self.config.profit_target_pct:
            return "profit_target"

        # Stop loss
        if pos.unrealized_pnl_pct <= -self.config.max_loss_pct:
            return "stop_loss"

        # Time decay cutoff
        now_utc = datetime.now(timezone.utc)
        et_hour = (now_utc.hour - 5) % 24
        et_minute = now_utc.minute

        if pos.dte == 0:
            parts = self.config.zero_dte_cutoff.split(":")
            if et_hour > int(parts[0]) or (et_hour == int(parts[0]) and et_minute >= int(parts[1])):
                return "zero_dte_cutoff"

        return None

    def _close_position(self, pos: ScalpPosition, reason: str) -> None:
        """Close a scalp position."""
        self.positions.remove(pos)
        self.closed_trades.append({
            "ticker": pos.ticker,
            "option_symbol": pos.option_symbol,
            "direction": pos.direction,
            "contracts": pos.contracts,
            "entry_price": pos.entry_price,
            "exit_price": pos.current_price,
            "pnl": pos.unrealized_pnl,
            "pnl_pct": pos.unrealized_pnl_pct,
            "exit_reason": reason,
        })
        logger.info(
            "Scalp closed: %s %s P&L $%.2f (%s)",
            pos.direction, pos.ticker, pos.unrealized_pnl, reason,
        )

    def _should_scalp(self, signal: TradeSignal) -> bool:
        """Pre-filter: only scalp if conviction is high enough."""
        if signal.conviction < self.config.min_conviction_to_scalp:
            return False
        if signal.ticker not in self.config.scalp_tickers:
            return False
        return True
