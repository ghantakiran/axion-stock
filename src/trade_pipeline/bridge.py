"""Signal Bridge — normalizes diverse signal types into PipelineOrder.

Converts Recommendation (signal_fusion), SocialTradingSignal (social_intelligence),
and TradeSignal (ema_signals) into a unified PipelineOrder format that the
pipeline executor can validate, risk-check, and route to a broker.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════


class SignalType(str, Enum):
    """Source of the original signal."""

    FUSION = "fusion"
    SOCIAL = "social"
    EMA_CLOUD = "ema_cloud"
    MANUAL = "manual"


class OrderSide(str, Enum):
    """Trade direction."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order execution type."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


# ═══════════════════════════════════════════════════════════════════════
# PipelineOrder — unified order format
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class PipelineOrder:
    """Unified order produced by the signal bridge.

    This is the single currency of the pipeline: every signal type
    gets normalized into a PipelineOrder before validation and execution.

    Attributes:
        order_id: Unique pipeline order identifier.
        symbol: Ticker symbol (e.g., "AAPL").
        side: Buy or sell.
        order_type: Market, limit, stop, stop_limit.
        qty: Number of shares/contracts.
        limit_price: Limit price (for limit/stop_limit orders).
        stop_price: Stop price (for stop/stop_limit orders).
        asset_type: Asset class for broker routing.
        signal_type: Source of this order.
        confidence: Signal confidence 0.0 – 1.0.
        position_size_pct: Suggested portfolio weight (%).
        stop_loss_pct: Stop loss as percentage from entry.
        take_profit_pct: Take profit as percentage from entry.
        time_horizon: 'intraday', 'swing', or 'position'.
        risk_level: 'low', 'medium', or 'high'.
        reasoning: Human-readable signal reasoning.
        source_data: Original signal dict for audit trail.
        created_at: When this order was created.
    """

    order_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    qty: float = 0.0
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    asset_type: str = "stock"
    signal_type: SignalType = SignalType.MANUAL
    confidence: float = 0.0
    position_size_pct: float = 0.0
    stop_loss_pct: float = 3.0
    take_profit_pct: float = 6.0
    time_horizon: str = "swing"
    risk_level: str = "medium"
    reasoning: str = ""
    source_data: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_broker_order(self) -> dict[str, Any]:
        """Convert to the flat dict expected by MultiBrokerExecutor.execute()."""
        order: dict[str, Any] = {
            "symbol": self.symbol,
            "side": self.side.value,
            "qty": self.qty,
            "order_type": self.order_type.value,
            "asset_type": self.asset_type,
            "pipeline_order_id": self.order_id,
        }
        if self.limit_price is not None:
            order["limit_price"] = self.limit_price
        if self.stop_price is not None:
            order["stop_price"] = self.stop_price
        return order

    def to_dict(self) -> dict[str, Any]:
        """Full serialization for logging and persistence."""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "qty": self.qty,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "asset_type": self.asset_type,
            "signal_type": self.signal_type.value,
            "confidence": round(self.confidence, 4),
            "position_size_pct": round(self.position_size_pct, 2),
            "stop_loss_pct": round(self.stop_loss_pct, 2),
            "take_profit_pct": round(self.take_profit_pct, 2),
            "time_horizon": self.time_horizon,
            "risk_level": self.risk_level,
            "reasoning": self.reasoning,
            "created_at": self.created_at.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════
# Signal Bridge
# ═══════════════════════════════════════════════════════════════════════


# Action → side mappings for each signal source
_FUSION_BUY_ACTIONS = {"STRONG_BUY", "BUY"}
_FUSION_SELL_ACTIONS = {"SELL", "STRONG_SELL"}
_SOCIAL_BUY_ACTIONS = {"strong_buy", "buy"}
_SOCIAL_SELL_ACTIONS = {"sell", "strong_sell"}


class SignalBridge:
    """Normalizes heterogeneous signals into PipelineOrder objects.

    Supports three signal formats:
      1. Recommendation (from signal_fusion/recommender.py)
      2. SocialTradingSignal (from social_intelligence/generator.py)
      3. TradeSignal (from ema_signals/detector.py)

    Also supports a raw dict for manual / ad-hoc orders.

    Example:
        bridge = SignalBridge(account_equity=100_000)
        order = bridge.from_recommendation(rec)
        order = bridge.from_social_signal(social_sig)
        order = bridge.from_trade_signal(ema_sig, current_price=185.50)
    """

    def __init__(self, account_equity: float = 100_000.0) -> None:
        self._equity = account_equity

    @property
    def account_equity(self) -> float:
        return self._equity

    @account_equity.setter
    def account_equity(self, value: float) -> None:
        self._equity = max(0.0, value)

    # ── Recommendation (signal_fusion) ───────────────────────────────

    def from_recommendation(self, rec: Any) -> Optional[PipelineOrder]:
        """Convert a signal_fusion Recommendation into a PipelineOrder.

        Args:
            rec: Recommendation with .symbol, .action, .position_size_pct, etc.

        Returns:
            PipelineOrder or None if HOLD action.
        """
        action = getattr(rec, "action", "HOLD")
        if action == "HOLD":
            return None

        if action in _FUSION_BUY_ACTIONS:
            side = OrderSide.BUY
        elif action in _FUSION_SELL_ACTIONS:
            side = OrderSide.SELL
        else:
            return None

        # High-conviction signals get market orders, others get limit
        fused = getattr(rec, "fused_signal", None)
        confidence = getattr(fused, "confidence", 0.5) if fused else 0.5
        order_type = OrderType.MARKET if action.startswith("STRONG") else OrderType.LIMIT

        pos_size_pct = getattr(rec, "position_size_pct", 5.0)
        qty = self._pct_to_shares(pos_size_pct)

        return PipelineOrder(
            symbol=getattr(rec, "symbol", ""),
            side=side,
            order_type=order_type,
            qty=qty,
            asset_type="stock",
            signal_type=SignalType.FUSION,
            confidence=confidence,
            position_size_pct=pos_size_pct,
            stop_loss_pct=getattr(rec, "stop_loss_pct", 3.0),
            take_profit_pct=getattr(rec, "take_profit_pct", 6.0),
            time_horizon=getattr(rec, "time_horizon", "swing"),
            risk_level=getattr(rec, "risk_level", "medium"),
            reasoning=getattr(rec, "reasoning", ""),
            source_data=rec.to_dict() if hasattr(rec, "to_dict") else {"action": action},
        )

    # ── SocialTradingSignal (social_intelligence) ────────────────────

    def from_social_signal(self, sig: Any) -> Optional[PipelineOrder]:
        """Convert a SocialTradingSignal into a PipelineOrder.

        Args:
            sig: SocialTradingSignal with .symbol, .action, .confidence, etc.

        Returns:
            PipelineOrder or None if HOLD/WATCH action.
        """
        action_val = getattr(sig, "action", None)
        if action_val is None:
            return None

        # Handle both Enum and string
        action_str = action_val.value if hasattr(action_val, "value") else str(action_val)

        if action_str in _SOCIAL_BUY_ACTIONS:
            side = OrderSide.BUY
        elif action_str in _SOCIAL_SELL_ACTIONS:
            side = OrderSide.SELL
        else:
            return None

        confidence = getattr(sig, "confidence", 0.0) / 100.0  # 0-100 → 0-1
        confidence = max(0.0, min(1.0, confidence))

        # Size based on confidence: 2-10% of equity
        pos_size_pct = max(2.0, min(10.0, confidence * 12.0))
        qty = self._pct_to_shares(pos_size_pct)

        order_type = OrderType.MARKET if action_str.startswith("strong") else OrderType.LIMIT

        reasons = getattr(sig, "reasons", [])
        reasoning = "; ".join(reasons) if reasons else f"Social signal: {action_str}"

        return PipelineOrder(
            symbol=getattr(sig, "symbol", ""),
            side=side,
            order_type=order_type,
            qty=qty,
            asset_type="stock",
            signal_type=SignalType.SOCIAL,
            confidence=confidence,
            position_size_pct=pos_size_pct,
            stop_loss_pct=4.0,  # Social signals use wider stops
            take_profit_pct=8.0,
            time_horizon="swing",
            risk_level="high" if confidence < 0.5 else "medium",
            reasoning=reasoning,
            source_data={"action": action_str, "final_score": getattr(sig, "final_score", 0.0)},
        )

    # ── TradeSignal (ema_signals) ────────────────────────────────────

    def from_trade_signal(
        self, sig: Any, current_price: float = 0.0
    ) -> Optional[PipelineOrder]:
        """Convert an EMA TradeSignal into a PipelineOrder.

        Args:
            sig: TradeSignal with .ticker, .direction, .conviction, etc.
            current_price: Current market price for qty calculation.

        Returns:
            PipelineOrder or None if conviction is too low.
        """
        conviction = getattr(sig, "conviction", 0)
        if conviction < 30:
            return None

        direction = getattr(sig, "direction", "long")
        side = OrderSide.BUY if direction == "long" else OrderSide.SELL

        confidence = conviction / 100.0
        pos_size_pct = max(2.0, min(15.0, confidence * 15.0))
        qty = self._pct_to_shares(pos_size_pct, current_price or getattr(sig, "entry_price", 100.0))

        entry_price = getattr(sig, "entry_price", 0.0)
        stop_loss = getattr(sig, "stop_loss", 0.0)
        target = getattr(sig, "target_price", None)

        # Calculate stop loss percentage
        if entry_price > 0 and stop_loss > 0:
            stop_loss_pct = abs(entry_price - stop_loss) / entry_price * 100.0
        else:
            stop_loss_pct = 3.0

        # Calculate take profit percentage
        if entry_price > 0 and target and target > 0:
            take_profit_pct = abs(target - entry_price) / entry_price * 100.0
        else:
            take_profit_pct = stop_loss_pct * 2.0  # Default 2:1 R:R

        order_type = OrderType.MARKET if conviction >= 70 else OrderType.LIMIT

        sig_type_val = getattr(sig, "signal_type", "")
        sig_type_str = sig_type_val.value if hasattr(sig_type_val, "value") else str(sig_type_val)

        return PipelineOrder(
            symbol=getattr(sig, "ticker", ""),
            side=side,
            order_type=order_type,
            qty=qty,
            limit_price=entry_price if order_type == OrderType.LIMIT and entry_price > 0 else None,
            stop_price=stop_loss if stop_loss > 0 else None,
            asset_type="stock",
            signal_type=SignalType.EMA_CLOUD,
            confidence=confidence,
            position_size_pct=pos_size_pct,
            stop_loss_pct=round(stop_loss_pct, 2),
            take_profit_pct=round(take_profit_pct, 2),
            time_horizon=getattr(sig, "timeframe", "1d"),
            risk_level="low" if conviction >= 70 else ("medium" if conviction >= 50 else "high"),
            reasoning=f"EMA signal: {sig_type_str} (conviction={conviction})",
            source_data=sig.to_dict() if hasattr(sig, "to_dict") else {"conviction": conviction},
        )

    # ── Raw dict ─────────────────────────────────────────────────────

    def from_dict(self, data: dict) -> PipelineOrder:
        """Create a PipelineOrder from a raw dictionary.

        Args:
            data: Dict with at minimum 'symbol' and 'side'.

        Returns:
            PipelineOrder populated from dict values.
        """
        side_str = data.get("side", "buy").lower()
        side = OrderSide.SELL if side_str == "sell" else OrderSide.BUY

        otype_str = data.get("order_type", "market").lower()
        order_type_map = {
            "market": OrderType.MARKET,
            "limit": OrderType.LIMIT,
            "stop": OrderType.STOP,
            "stop_limit": OrderType.STOP_LIMIT,
        }
        order_type = order_type_map.get(otype_str, OrderType.MARKET)

        return PipelineOrder(
            symbol=data.get("symbol", ""),
            side=side,
            order_type=order_type,
            qty=float(data.get("qty", 0)),
            limit_price=data.get("limit_price"),
            stop_price=data.get("stop_price"),
            asset_type=data.get("asset_type", "stock"),
            signal_type=SignalType.MANUAL,
            confidence=float(data.get("confidence", 0.5)),
            position_size_pct=float(data.get("position_size_pct", 5.0)),
            stop_loss_pct=float(data.get("stop_loss_pct", 3.0)),
            take_profit_pct=float(data.get("take_profit_pct", 6.0)),
            time_horizon=data.get("time_horizon", "swing"),
            risk_level=data.get("risk_level", "medium"),
            reasoning=data.get("reasoning", "Manual order"),
            source_data=data,
        )

    # ── internals ────────────────────────────────────────────────────

    def _pct_to_shares(
        self, pct: float, price: float = 100.0
    ) -> float:
        """Convert a portfolio percentage to approximate share count.

        Args:
            pct: Portfolio percentage (e.g. 5.0 for 5%).
            price: Estimated share price.

        Returns:
            Number of shares (integer-like float).
        """
        if price <= 0:
            price = 100.0
        dollar_amount = self._equity * (pct / 100.0)
        shares = dollar_amount / price
        return max(1.0, round(shares))
