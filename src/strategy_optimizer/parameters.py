"""Strategy parameter space definitions for adaptive optimization.

Defines tunable strategy parameters across all trading modules including
EMA cloud settings, risk gate thresholds, signal weights, and position sizing.
Each parameter has type constraints, valid ranges, defaults, and module origin.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class ParamType(Enum):
    """Parameter value type."""

    CONTINUOUS = "continuous"
    INTEGER = "integer"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"


@dataclass
class ParamDef:
    """Definition of a single tunable parameter.

    Attributes:
        name: Unique parameter identifier (e.g. ``ema_fast_period``).
        param_type: Value type governing mutation / crossover behaviour.
        min_val: Lower bound (CONTINUOUS / INTEGER).
        max_val: Upper bound (CONTINUOUS / INTEGER).
        choices: Allowed values (CATEGORICAL).
        default: Default / initial value.
        description: Human-readable explanation.
        module: Source module that owns this parameter.
    """

    name: str
    param_type: ParamType
    min_val: float | None = None
    max_val: float | None = None
    choices: list[Any] | None = None
    default: Any = None
    description: str = ""
    module: str = ""

    # ------------------------------------------------------------------
    def validate(self) -> bool:
        """Return *True* if the definition is internally consistent."""
        if self.param_type in (ParamType.CONTINUOUS, ParamType.INTEGER):
            if self.min_val is None or self.max_val is None:
                return False
            if self.min_val > self.max_val:
                return False
        if self.param_type == ParamType.CATEGORICAL:
            if not self.choices:
                return False
        return True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["param_type"] = self.param_type.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> ParamDef:
        d = dict(d)
        d["param_type"] = ParamType(d["param_type"])
        return cls(**d)


class ParameterSpace:
    """Collection of tunable strategy parameters.

    Provides add / lookup / serialisation helpers used by the optimiser
    and the dashboard.
    """

    def __init__(self) -> None:
        self._params: dict[str, ParamDef] = {}

    # -- mutators -------------------------------------------------------

    def add(self, param_def: ParamDef) -> None:
        """Register a parameter definition."""
        self._params[param_def.name] = param_def

    def remove(self, name: str) -> None:
        self._params.pop(name, None)

    # -- accessors -------------------------------------------------------

    def get(self, name: str) -> ParamDef | None:
        return self._params.get(name)

    def get_all(self) -> list[ParamDef]:
        return list(self._params.values())

    def get_by_module(self, module: str) -> list[ParamDef]:
        return [p for p in self._params.values() if p.module == module]

    def get_names(self) -> list[str]:
        return list(self._params.keys())

    def __len__(self) -> int:
        return len(self._params)

    # -- serialisation ---------------------------------------------------

    def to_dict(self) -> dict:
        return {name: p.to_dict() for name, p in self._params.items()}

    @classmethod
    def from_dict(cls, d: dict) -> ParameterSpace:
        space = cls()
        for _name, pdict in d.items():
            space.add(ParamDef.from_dict(pdict))
        return space

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, s: str) -> ParameterSpace:
        return cls.from_dict(json.loads(s))

    def get_defaults(self) -> dict[str, Any]:
        """Return mapping of param name -> default value."""
        return {name: p.default for name, p in self._params.items()}


# ── Default parameter catalog (~20 params) ─────────────────────────────


def build_default_parameter_space() -> ParameterSpace:
    """Construct the platform-wide default tunable parameter space."""

    space = ParameterSpace()

    # -- EMA Cloud params (module: ema_signals) --------------------------
    space.add(ParamDef(
        name="ema_fast_period",
        param_type=ParamType.INTEGER,
        min_val=3, max_val=15, default=5,
        description="Fast EMA period for cloud layer 1",
        module="ema_signals",
    ))
    space.add(ParamDef(
        name="ema_mid_period",
        param_type=ParamType.INTEGER,
        min_val=8, max_val=21, default=13,
        description="Mid EMA period for cloud layer 2",
        module="ema_signals",
    ))
    space.add(ParamDef(
        name="ema_slow_period",
        param_type=ParamType.INTEGER,
        min_val=21, max_val=55, default=34,
        description="Slow EMA period for cloud layer 3",
        module="ema_signals",
    ))
    space.add(ParamDef(
        name="ema_anchor_period",
        param_type=ParamType.INTEGER,
        min_val=50, max_val=200, default=100,
        description="Anchor EMA period for trend bias",
        module="ema_signals",
    ))
    space.add(ParamDef(
        name="conviction_threshold",
        param_type=ParamType.INTEGER,
        min_val=50, max_val=90, default=65,
        description="Minimum conviction score to generate a trade signal",
        module="ema_signals",
    ))

    # -- Trade Executor params (module: trade_executor) ------------------
    space.add(ParamDef(
        name="max_positions",
        param_type=ParamType.INTEGER,
        min_val=5, max_val=20, default=10,
        description="Maximum concurrent open positions",
        module="trade_executor",
    ))
    space.add(ParamDef(
        name="position_weight",
        param_type=ParamType.CONTINUOUS,
        min_val=0.02, max_val=0.20, default=0.05,
        description="Target allocation per position (fraction of equity)",
        module="trade_executor",
    ))
    space.add(ParamDef(
        name="stop_loss_pct",
        param_type=ParamType.CONTINUOUS,
        min_val=1.0, max_val=10.0, default=3.0,
        description="Stop-loss trigger percentage from entry",
        module="trade_executor",
    ))
    space.add(ParamDef(
        name="reward_ratio",
        param_type=ParamType.CONTINUOUS,
        min_val=1.5, max_val=4.0, default=2.0,
        description="Risk-reward ratio for take-profit calculation",
        module="trade_executor",
    ))
    space.add(ParamDef(
        name="trailing_stop_pct",
        param_type=ParamType.CONTINUOUS,
        min_val=1.0, max_val=8.0, default=2.5,
        description="Trailing stop distance as percentage",
        module="trade_executor",
    ))

    # -- Risk Gate params (module: risk) ---------------------------------
    space.add(ParamDef(
        name="max_daily_loss_pct",
        param_type=ParamType.CONTINUOUS,
        min_val=1.0, max_val=5.0, default=2.0,
        description="Maximum daily portfolio loss before kill-switch",
        module="risk",
    ))
    space.add(ParamDef(
        name="max_sector_exposure",
        param_type=ParamType.CONTINUOUS,
        min_val=0.1, max_val=0.5, default=0.25,
        description="Maximum allocation to a single sector",
        module="risk",
    ))
    space.add(ParamDef(
        name="max_correlation",
        param_type=ParamType.CONTINUOUS,
        min_val=0.4, max_val=0.9, default=0.7,
        description="Maximum pairwise correlation allowed",
        module="risk",
    ))

    # -- Signal Fusion params (module: signal_fusion) --------------------
    space.add(ParamDef(
        name="ema_signal_weight",
        param_type=ParamType.CONTINUOUS,
        min_val=0.1, max_val=0.6, default=0.35,
        description="Weight for EMA cloud signals in fusion",
        module="signal_fusion",
    ))
    space.add(ParamDef(
        name="sentiment_weight",
        param_type=ParamType.CONTINUOUS,
        min_val=0.0, max_val=0.3, default=0.10,
        description="Weight for sentiment signals in fusion",
        module="signal_fusion",
    ))
    space.add(ParamDef(
        name="volume_weight",
        param_type=ParamType.CONTINUOUS,
        min_val=0.05, max_val=0.3, default=0.15,
        description="Weight for volume signals in fusion",
        module="signal_fusion",
    ))
    space.add(ParamDef(
        name="momentum_weight",
        param_type=ParamType.CONTINUOUS,
        min_val=0.1, max_val=0.5, default=0.25,
        description="Weight for momentum signals in fusion",
        module="signal_fusion",
    ))

    # -- Scanner params (module: scanner) --------------------------------
    space.add(ParamDef(
        name="scan_interval_seconds",
        param_type=ParamType.INTEGER,
        min_val=30, max_val=600, default=120,
        description="Interval between universe scans in seconds",
        module="scanner",
    ))
    space.add(ParamDef(
        name="min_volume_filter",
        param_type=ParamType.INTEGER,
        min_val=100_000, max_val=5_000_000, default=500_000,
        description="Minimum average daily volume to include a ticker",
        module="scanner",
    ))

    # -- Regime awareness (module: regime) -------------------------------
    space.add(ParamDef(
        name="regime_mode",
        param_type=ParamType.CATEGORICAL,
        choices=["bull", "bear", "sideways", "auto"],
        default="auto",
        description="Market regime assumption or auto-detect",
        module="regime",
    ))

    return space


DEFAULT_PARAM_COUNT = 20
