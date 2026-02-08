"""Composite management for GIPS compliance."""

from datetime import date
from typing import Dict, List, Optional
import uuid

from .config import CompositeConfig, CompositeMembership
from .models import (
    CompositeDefinition,
    CompositeReturn,
    PerformanceRecord,
    PortfolioAssignment,
)


class CompositeManager:
    """Manages GIPS composites — creation, membership, and return aggregation."""

    def __init__(self, config: Optional[CompositeConfig] = None):
        self.config = config or CompositeConfig()
        self._composites: Dict[str, CompositeDefinition] = {}

    def create_composite(
        self,
        name: str,
        strategy: str,
        benchmark_name: str,
        inception_date: date,
        description: str = "",
        creation_date: Optional[date] = None,
    ) -> CompositeDefinition:
        composite_id = str(uuid.uuid4())[:8]
        composite = CompositeDefinition(
            composite_id=composite_id,
            name=name,
            strategy=strategy,
            benchmark_name=benchmark_name,
            inception_date=inception_date,
            creation_date=creation_date or date.today(),
            description=description,
            currency=self.config.currency,
            membership_rules={
                "rule": self.config.membership_rule.value,
                "min_size": self.config.min_portfolio_size,
            },
        )
        self._composites[composite_id] = composite
        return composite

    def get_composite(self, composite_id: str) -> Optional[CompositeDefinition]:
        return self._composites.get(composite_id)

    def list_composites(self) -> List[CompositeDefinition]:
        return list(self._composites.values())

    def add_portfolio(
        self,
        composite_id: str,
        portfolio_id: str,
        join_date: date,
        market_value: float = 0.0,
    ) -> Optional[PortfolioAssignment]:
        composite = self._composites.get(composite_id)
        if not composite:
            return None

        # Check minimum size
        if market_value < self.config.min_portfolio_size:
            return None

        # Check not already assigned
        for p in composite.portfolios:
            if p.portfolio_id == portfolio_id and p.is_active:
                return None

        assignment = PortfolioAssignment(
            portfolio_id=portfolio_id,
            composite_id=composite_id,
            join_date=join_date,
            market_value=market_value,
        )
        composite.portfolios.append(assignment)
        return assignment

    def remove_portfolio(
        self, composite_id: str, portfolio_id: str, leave_date: date
    ) -> bool:
        composite = self._composites.get(composite_id)
        if not composite:
            return False

        for p in composite.portfolios:
            if p.portfolio_id == portfolio_id and p.is_active:
                p.is_active = False
                p.leave_date = leave_date
                return True
        return False

    def calculate_composite_return(
        self,
        composite_id: str,
        portfolio_records: List[PerformanceRecord],
        benchmark_return: float = 0.0,
        firm_assets: float = 0.0,
    ) -> Optional[CompositeReturn]:
        composite = self._composites.get(composite_id)
        if not composite or not portfolio_records:
            return None

        active_ids = {p.portfolio_id for p in composite.active_portfolios}
        eligible = [r for r in portfolio_records if r.portfolio_id in active_ids]

        if not eligible:
            return None

        # Check membership rule
        if self.config.membership_rule == CompositeMembership.FULL_PERIOD:
            eligible = [
                r for r in eligible
                if r.beginning_value > 0
            ]

        if not eligible:
            return None

        # Asset-weighted return
        total_weight = sum(r.beginning_value for r in eligible)
        if total_weight <= 0:
            return None

        gross = sum(r.gross_return * r.beginning_value for r in eligible) / total_weight
        net = sum(r.net_return * r.beginning_value for r in eligible) / total_weight
        composite_assets = sum(r.ending_value for r in eligible)

        period_start = min(r.period_start for r in eligible)
        period_end = max(r.period_end for r in eligible)

        pct_firm = (composite_assets / firm_assets * 100) if firm_assets > 0 else 0.0

        return CompositeReturn(
            composite_id=composite_id,
            period_start=period_start,
            period_end=period_end,
            gross_return=gross,
            net_return=net,
            benchmark_return=benchmark_return,
            n_portfolios=len(eligible),
            composite_assets=composite_assets,
            firm_assets=firm_assets,
            pct_firm_assets=pct_firm,
        )

    def archive_composite(self, composite_id: str) -> bool:
        composite = self._composites.get(composite_id)
        if not composite:
            return False
        composite.is_active = False
        for p in composite.portfolios:
            p.is_active = False
        return True

    @staticmethod
    def generate_sample_composite() -> "CompositeManager":
        """Generate a sample composite for demo purposes."""
        manager = CompositeManager(CompositeConfig(
            name="US Large Cap Growth",
            strategy="Large Cap Growth Equity",
            benchmark_name="Russell 1000 Growth",
            min_portfolio_size=250_000,
        ))

        composite = manager.create_composite(
            name="US Large Cap Growth",
            strategy="Large Cap Growth Equity",
            benchmark_name="Russell 1000 Growth",
            inception_date=date(2018, 1, 1),
            description="Concentrated large cap growth strategy targeting 25-35 holdings",
        )

        for i in range(8):
            manager.add_portfolio(
                composite_id=composite.composite_id,
                portfolio_id=f"PORT-{i+1:03d}",
                join_date=date(2018 + i // 3, 1, 1),
                market_value=500_000 + i * 200_000,
            )

        return manager
