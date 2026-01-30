"""Portfolio Constraint Framework.

Provides position, sector, factor, turnover, ESG,
and liquidity constraints for portfolio optimization.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.optimizer.config import ConstraintConfig

logger = logging.getLogger(__name__)


@dataclass
class Constraint:
    """Base constraint definition."""

    name: str = ""
    constraint_type: str = ""  # position, sector, factor, turnover, esg, liquidity
    active: bool = True

    def check(self, weights: pd.Series, **context) -> bool:
        """Check if constraint is satisfied."""
        return True

    def violation(self, weights: pd.Series, **context) -> float:
        """Return magnitude of violation (0 = satisfied)."""
        return 0.0


@dataclass
class PositionConstraint(Constraint):
    """Position size limits."""

    min_pct: float = 0.0
    max_pct: float = 0.15

    def __post_init__(self):
        self.constraint_type = "position"

    def check(self, weights: pd.Series, **context) -> bool:
        non_zero = weights[weights > 1e-6]
        if len(non_zero) == 0:
            return True
        return bool(non_zero.min() >= self.min_pct - 1e-6 and non_zero.max() <= self.max_pct + 1e-6)

    def violation(self, weights: pd.Series, **context) -> float:
        v = 0.0
        for w in weights:
            if w > 1e-6:
                if w < self.min_pct:
                    v += self.min_pct - w
                if w > self.max_pct:
                    v += w - self.max_pct
        return v


@dataclass
class SectorConstraint(Constraint):
    """Sector allocation limits."""

    max_pct: float = 0.35

    def __post_init__(self):
        self.constraint_type = "sector"

    def check(self, weights: pd.Series, **context) -> bool:
        sectors = context.get("sectors", {})
        if not sectors:
            return True
        sector_weights = {}
        for symbol, w in weights.items():
            sector = sectors.get(symbol, "Unknown")
            sector_weights[sector] = sector_weights.get(sector, 0) + w
        return all(sw <= self.max_pct + 1e-6 for sw in sector_weights.values())

    def violation(self, weights: pd.Series, **context) -> float:
        sectors = context.get("sectors", {})
        if not sectors:
            return 0.0
        sector_weights = {}
        for symbol, w in weights.items():
            sector = sectors.get(symbol, "Unknown")
            sector_weights[sector] = sector_weights.get(sector, 0) + w
        return sum(max(0, sw - self.max_pct) for sw in sector_weights.values())


@dataclass
class TurnoverConstraint(Constraint):
    """Portfolio turnover limit."""

    max_one_way: float = 0.30

    def __post_init__(self):
        self.constraint_type = "turnover"

    def check(self, weights: pd.Series, **context) -> bool:
        current_weights = context.get("current_weights", pd.Series(dtype=float))
        if current_weights.empty:
            return True
        turnover = self._compute_turnover(weights, current_weights)
        return turnover <= self.max_one_way + 1e-6

    def violation(self, weights: pd.Series, **context) -> float:
        current_weights = context.get("current_weights", pd.Series(dtype=float))
        if current_weights.empty:
            return 0.0
        turnover = self._compute_turnover(weights, current_weights)
        return max(0, turnover - self.max_one_way)

    def _compute_turnover(self, new: pd.Series, old: pd.Series) -> float:
        all_symbols = set(new.index) | set(old.index)
        turnover = 0.0
        for s in all_symbols:
            turnover += abs(new.get(s, 0) - old.get(s, 0))
        return turnover / 2  # One-way


@dataclass
class CountConstraint(Constraint):
    """Number of positions limit."""

    min_n: int = 10
    max_n: int = 30

    def __post_init__(self):
        self.constraint_type = "count"

    def check(self, weights: pd.Series, **context) -> bool:
        n = (weights > 1e-6).sum()
        return self.min_n <= n <= self.max_n

    def violation(self, weights: pd.Series, **context) -> float:
        n = (weights > 1e-6).sum()
        if n < self.min_n:
            return float(self.min_n - n)
        if n > self.max_n:
            return float(n - self.max_n)
        return 0.0


class ConstraintEngine:
    """Manage and validate portfolio constraints.

    Example:
        engine = ConstraintEngine()
        engine.add(PositionConstraint(max_pct=0.10))
        engine.add(SectorConstraint(max_pct=0.30))
        violations = engine.validate(weights, sectors=sector_map)
    """

    def __init__(self, config: Optional[ConstraintConfig] = None):
        self.config = config or ConstraintConfig()
        self._constraints: list[Constraint] = []

    def add(self, constraint: Constraint) -> None:
        """Add a constraint."""
        self._constraints.append(constraint)

    def add_default_constraints(self) -> None:
        """Add default constraints from config."""
        self._constraints.extend([
            PositionConstraint(
                name="position_size",
                min_pct=self.config.min_weight,
                max_pct=self.config.max_weight,
            ),
            SectorConstraint(
                name="sector_limit",
                max_pct=self.config.max_sector_pct,
            ),
            CountConstraint(
                name="position_count",
                min_n=self.config.min_positions,
                max_n=self.config.max_positions,
            ),
            TurnoverConstraint(
                name="turnover_limit",
                max_one_way=self.config.max_turnover,
            ),
        ])

    def validate(
        self,
        weights: pd.Series,
        **context,
    ) -> list[dict]:
        """Validate weights against all constraints.

        Args:
            weights: Portfolio weights.
            **context: Additional context (sectors, current_weights, etc.).

        Returns:
            List of violation dicts. Empty list = all satisfied.
        """
        violations = []

        for c in self._constraints:
            if not c.active:
                continue
            if not c.check(weights, **context):
                violations.append({
                    "constraint": c.name or c.constraint_type,
                    "type": c.constraint_type,
                    "violation": c.violation(weights, **context),
                })

        return violations

    def is_feasible(self, weights: pd.Series, **context) -> bool:
        """Check if weights satisfy all constraints."""
        return len(self.validate(weights, **context)) == 0

    def get_constraints(self) -> list[Constraint]:
        """Get all active constraints."""
        return [c for c in self._constraints if c.active]
