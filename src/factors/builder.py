"""Custom Factor Builder.

Allows users to create, manage, and compute custom factors
by combining existing metrics with configurable weights and transformations.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable
from uuid import uuid4
from enum import Enum

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TransformType(Enum):
    """Available transformations for factor components."""
    RAW = "raw"
    PERCENTILE_RANK = "percentile_rank"
    ZSCORE = "zscore"
    LOG = "log"
    INVERSE = "inverse"
    ABS = "abs"


class AggregationMethod(Enum):
    """Methods for combining factor components."""
    WEIGHTED_AVERAGE = "weighted_average"
    EQUAL_WEIGHT = "equal_weight"
    MAX = "max"
    MIN = "min"
    GEOMETRIC_MEAN = "geometric_mean"


@dataclass
class FactorComponent:
    """A single component within a custom factor."""
    metric_name: str
    weight: float = 1.0
    transform: TransformType = TransformType.PERCENTILE_RANK
    direction: str = "positive"  # positive = higher is better

    def to_dict(self) -> dict:
        return {
            "metric_name": self.metric_name,
            "weight": self.weight,
            "transform": self.transform.value,
            "direction": self.direction,
        }


@dataclass
class CustomFactor:
    """A user-defined custom factor."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    created_by: str = ""
    components: list[FactorComponent] = field(default_factory=list)
    aggregation: AggregationMethod = AggregationMethod.WEIGHTED_AVERAGE
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    @property
    def n_components(self) -> int:
        return len(self.components)

    @property
    def total_weight(self) -> float:
        return sum(c.weight for c in self.components)

    @property
    def component_names(self) -> list[str]:
        return [c.metric_name for c in self.components]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_by": self.created_by,
            "n_components": self.n_components,
            "aggregation": self.aggregation.value,
            "components": [c.to_dict() for c in self.components],
            "is_active": self.is_active,
        }


@dataclass
class FactorResult:
    """Result of computing a custom factor."""
    factor_id: str
    factor_name: str
    scores: dict[str, float] = field(default_factory=dict)  # symbol -> score
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def n_scored(self) -> int:
        return len(self.scores)

    def top_n(self, n: int = 10) -> list[tuple[str, float]]:
        """Get top N symbols by score."""
        sorted_items = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:n]

    def bottom_n(self, n: int = 10) -> list[tuple[str, float]]:
        """Get bottom N symbols by score."""
        sorted_items = sorted(self.scores.items(), key=lambda x: x[1])
        return sorted_items[:n]

    def to_dict(self) -> dict:
        return {
            "factor_id": self.factor_id,
            "factor_name": self.factor_name,
            "n_scored": self.n_scored,
            "top_10": self.top_n(10),
        }


class CustomFactorBuilder:
    """Builder for creating and computing custom factors.

    Features:
    - Create custom factors from metric components
    - Apply transformations (percentile rank, z-score, log, inverse)
    - Combine with configurable aggregation (weighted avg, equal weight, geometric mean)
    - Compute scores across a universe of securities
    - CRUD operations for custom factor definitions
    """

    def __init__(self):
        self._factors: dict[str, CustomFactor] = {}
        self._data_provider: Optional[Callable] = None

    def create_factor(
        self,
        name: str,
        components: list[FactorComponent],
        description: str = "",
        created_by: str = "",
        aggregation: AggregationMethod = AggregationMethod.WEIGHTED_AVERAGE,
    ) -> CustomFactor:
        """Create a new custom factor.

        Args:
            name: Factor name.
            components: List of factor components.
            description: Factor description.
            created_by: User who created the factor.
            aggregation: How to combine components.

        Returns:
            Created CustomFactor.

        Raises:
            ValueError: If no components provided or name is empty.
        """
        if not name:
            raise ValueError("Factor name is required")
        if not components:
            raise ValueError("At least one component is required")

        factor = CustomFactor(
            name=name,
            description=description,
            created_by=created_by,
            components=components,
            aggregation=aggregation,
        )

        self._factors[factor.id] = factor
        return factor

    def update_factor(
        self,
        factor_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        components: Optional[list[FactorComponent]] = None,
        aggregation: Optional[AggregationMethod] = None,
    ) -> CustomFactor:
        """Update an existing custom factor.

        Args:
            factor_id: Factor ID to update.
            name: New name (optional).
            description: New description (optional).
            components: New components (optional).
            aggregation: New aggregation method (optional).

        Returns:
            Updated CustomFactor.
        """
        factor = self._factors.get(factor_id)
        if not factor:
            raise ValueError(f"Factor {factor_id} not found")

        if name is not None:
            factor.name = name
        if description is not None:
            factor.description = description
        if components is not None:
            factor.components = components
        if aggregation is not None:
            factor.aggregation = aggregation
        factor.updated_at = datetime.now()

        return factor

    def delete_factor(self, factor_id: str) -> bool:
        """Delete a custom factor."""
        if factor_id in self._factors:
            del self._factors[factor_id]
            return True
        return False

    def get_factor(self, factor_id: str) -> Optional[CustomFactor]:
        """Get a custom factor by ID."""
        return self._factors.get(factor_id)

    def list_factors(self, created_by: Optional[str] = None) -> list[CustomFactor]:
        """List all custom factors, optionally filtered by creator."""
        factors = list(self._factors.values())
        if created_by:
            factors = [f for f in factors if f.created_by == created_by]
        return factors

    def compute(
        self,
        factor_id: str,
        data: pd.DataFrame,
    ) -> FactorResult:
        """Compute custom factor scores for a universe.

        Args:
            factor_id: Factor ID to compute.
            data: DataFrame with columns matching component metric names,
                  indexed by symbol.

        Returns:
            FactorResult with scores per symbol.

        Raises:
            ValueError: If factor not found or required columns missing.
        """
        factor = self._factors.get(factor_id)
        if not factor:
            raise ValueError(f"Factor {factor_id} not found")

        # Validate required columns
        missing = [c.metric_name for c in factor.components if c.metric_name not in data.columns]
        if missing:
            raise ValueError(f"Missing columns in data: {missing}")

        # Compute transformed component scores
        component_scores = []
        weights = []

        for comp in factor.components:
            raw = data[comp.metric_name].copy().astype(float)

            # Apply direction
            if comp.direction == "negative":
                raw = -raw

            # Apply transformation
            transformed = self._apply_transform(raw, comp.transform)
            component_scores.append(transformed)
            weights.append(comp.weight)

        # Aggregate
        scores_df = pd.DataFrame(component_scores).T
        scores_df.index = data.index

        aggregated = self._aggregate(scores_df, weights, factor.aggregation)

        return FactorResult(
            factor_id=factor.id,
            factor_name=factor.name,
            scores=dict(zip(data.index, aggregated)),
        )

    def _apply_transform(self, series: pd.Series, transform: TransformType) -> pd.Series:
        """Apply transformation to a series."""
        if transform == TransformType.RAW:
            return series
        elif transform == TransformType.PERCENTILE_RANK:
            return series.rank(pct=True) * 100
        elif transform == TransformType.ZSCORE:
            mean = series.mean()
            std = series.std()
            return (series - mean) / std if std > 0 else series * 0
        elif transform == TransformType.LOG:
            return np.log1p(series.clip(lower=0))
        elif transform == TransformType.INVERSE:
            return 1.0 / series.replace(0, np.nan)
        elif transform == TransformType.ABS:
            return series.abs()
        return series

    def _aggregate(
        self,
        scores_df: pd.DataFrame,
        weights: list[float],
        method: AggregationMethod,
    ) -> pd.Series:
        """Aggregate component scores."""
        if method == AggregationMethod.WEIGHTED_AVERAGE:
            total_weight = sum(weights)
            if total_weight == 0:
                return scores_df.mean(axis=1)
            weighted = sum(scores_df.iloc[:, i] * w for i, w in enumerate(weights))
            return weighted / total_weight

        elif method == AggregationMethod.EQUAL_WEIGHT:
            return scores_df.mean(axis=1)

        elif method == AggregationMethod.MAX:
            return scores_df.max(axis=1)

        elif method == AggregationMethod.MIN:
            return scores_df.min(axis=1)

        elif method == AggregationMethod.GEOMETRIC_MEAN:
            # Shift to positive before geometric mean
            shifted = scores_df.clip(lower=0.01)
            return shifted.prod(axis=1) ** (1.0 / shifted.shape[1])

        return scores_df.mean(axis=1)
