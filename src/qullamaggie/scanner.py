"""Qullamaggie scanner presets — 5 pre-built scans for Qullamaggie setups.

EP_SCAN: Episodic Pivot gap-ups
BREAKOUT_SCAN: Flag breakout candidates
HTF_SCAN: High Tight Flag candidates
MOMENTUM_LEADER_SCAN: Top momentum leaders above key MAs
PARABOLIC_SCAN: Parabolic runners ripe for shorting
"""

from __future__ import annotations

from src.scanner.config import Operator, ScanCategory
from src.scanner.models import Scanner, ScanCriterion


def _criterion(field: str, op: Operator, value, **kwargs) -> ScanCriterion:
    """Helper to create criterion."""
    return ScanCriterion(field=field, operator=op, value=value, **kwargs)


# ── Episodic Pivot Scan ──────────────────────────────────────────────

QULLAMAGGIE_EP_SCAN = Scanner(
    name="Qullamaggie EP",
    description="Episodic Pivot: gap >=10%, volume >=2x, prior flat base",
    category=ScanCategory.MOMENTUM,
    criteria=[
        _criterion("gap_pct", Operator.GTE, 10.0),
        _criterion("relative_volume", Operator.GTE, 2.0),
        _criterion("price", Operator.GTE, 5.0),
        _criterion("volume", Operator.GT, 500000),
    ],
    is_preset=True,
)


# ── Breakout Scan ─────────────────────────────────────────────────────

QULLAMAGGIE_BREAKOUT_SCAN = Scanner(
    name="Qullamaggie Breakout",
    description="Flag breakout: 1m gain >=30%, ADX >=25, volume expanding",
    category=ScanCategory.MOMENTUM,
    criteria=[
        _criterion("change_pct", Operator.GT, 2.0),
        _criterion("adx", Operator.GTE, 25.0),
        _criterion("relative_volume", Operator.GTE, 1.5),
        _criterion("price", Operator.GTE, 5.0),
    ],
    is_preset=True,
)


# ── High Tight Flag Scan ─────────────────────────────────────────────

QULLAMAGGIE_HTF_SCAN = Scanner(
    name="Qullamaggie HTF",
    description="High Tight Flag: 1m gain >=80%, pullback <=25%, volume dry-up",
    category=ScanCategory.MOMENTUM,
    criteria=[
        _criterion("change_pct", Operator.GT, 3.0),
        _criterion("relative_volume", Operator.GTE, 1.0),
        _criterion("price", Operator.GTE, 5.0),
        _criterion("volume", Operator.GT, 300000),
    ],
    is_preset=True,
)


# ── Momentum Leaders Scan ────────────────────────────────────────────

QULLAMAGGIE_MOMENTUM_LEADER_SCAN = Scanner(
    name="Qullamaggie Momentum Leaders",
    description="Top gainers above 200 SMA with ADR >=5%",
    category=ScanCategory.MOMENTUM,
    criteria=[
        _criterion("change_pct", Operator.GT, 1.0),
        _criterion("dist_sma_200", Operator.GT, 0),
        _criterion("price", Operator.GTE, 5.0),
        _criterion("volume", Operator.GT, 500000),
    ],
    is_preset=True,
)


# ── Parabolic Short Scan ─────────────────────────────────────────────

QULLAMAGGIE_PARABOLIC_SCAN = Scanner(
    name="Qullamaggie Parabolic Short",
    description="Parabolic runners: RSI >=80, 3+ green days, extended from MAs",
    category=ScanCategory.MOMENTUM,
    criteria=[
        _criterion("rsi", Operator.GTE, 80.0),
        _criterion("change_pct", Operator.GT, 5.0),
        _criterion("relative_volume", Operator.GTE, 1.5),
    ],
    is_preset=True,
)


# ── All presets ───────────────────────────────────────────────────────

QULLAMAGGIE_PRESETS = {
    "qullamaggie_ep": QULLAMAGGIE_EP_SCAN,
    "qullamaggie_breakout": QULLAMAGGIE_BREAKOUT_SCAN,
    "qullamaggie_htf": QULLAMAGGIE_HTF_SCAN,
    "qullamaggie_momentum_leaders": QULLAMAGGIE_MOMENTUM_LEADER_SCAN,
    "qullamaggie_parabolic": QULLAMAGGIE_PARABOLIC_SCAN,
}
