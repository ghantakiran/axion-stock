"""Portfolio Comparison.

Compare multiple portfolios on various metrics.
"""

from typing import Optional
import logging

from src.scenarios.config import SECTOR_BETAS
from src.scenarios.models import (
    Portfolio,
    PortfolioMetrics,
    PortfolioComparison,
)

logger = logging.getLogger(__name__)


class PortfolioComparer:
    """Compares multiple portfolios.
    
    Calculates and compares metrics across portfolios to help
    users make informed decisions.
    
    Example:
        comparer = PortfolioComparer()
        
        comparison = comparer.compare([portfolio1, portfolio2])
        print(f"Better portfolio: {comparison.recommended_index}")
    """
    
    def __init__(self):
        pass
    
    def compare(
        self,
        portfolios: list[Portfolio],
        names: Optional[list[str]] = None,
    ) -> PortfolioComparison:
        """Compare multiple portfolios.
        
        Args:
            portfolios: List of portfolios to compare.
            names: Optional names for each portfolio.
            
        Returns:
            PortfolioComparison with analysis.
        """
        if len(portfolios) < 2:
            raise ValueError("Need at least 2 portfolios to compare")
        
        names = names or [f"Portfolio {i+1}" for i in range(len(portfolios))]
        
        comparison = PortfolioComparison(
            portfolios=portfolios,
            portfolio_names=names,
        )
        
        # Calculate metrics for each portfolio
        metrics_list = []
        for portfolio in portfolios:
            metrics = self.calculate_metrics(portfolio)
            metrics_list.append(metrics)
        
        comparison.metrics = metrics_list
        
        # Calculate weight differences
        all_symbols = set()
        for p in portfolios:
            all_symbols.update(p.get_weights().keys())
        
        weight_diffs = {}
        for symbol in all_symbols:
            weights = [p.get_weight(symbol) for p in portfolios]
            weight_diffs[symbol] = weights
        
        comparison.weight_differences = weight_diffs
        
        # Make recommendation
        comparison.recommended_index, comparison.recommendation_reason = \
            self._make_recommendation(metrics_list, names)
        
        return comparison
    
    def calculate_metrics(self, portfolio: Portfolio) -> PortfolioMetrics:
        """Calculate metrics for a portfolio.
        
        Args:
            portfolio: Portfolio to analyze.
            
        Returns:
            PortfolioMetrics object.
        """
        metrics = PortfolioMetrics(portfolio_id=portfolio.portfolio_id)
        
        total_value = portfolio.total_value
        metrics.total_value = total_value
        
        if total_value == 0:
            return metrics
        
        # Cash weight
        metrics.cash_weight = portfolio.cash / total_value
        
        # Holdings analysis
        metrics.num_holdings = len(portfolio.holdings)
        
        weights = portfolio.get_weights()
        if weights:
            metrics.top_holding_weight = max(weights.values())
            
            # HHI (Herfindahl-Hirschman Index)
            metrics.concentration_hhi = sum(w ** 2 for w in weights.values())
        
        # Sector weights
        sector_weights = {}
        for holding in portfolio.holdings:
            sector = holding.sector or "Unknown"
            weight = holding.market_value / total_value
            sector_weights[sector] = sector_weights.get(sector, 0) + weight
        metrics.sector_weights = sector_weights
        
        # Beta (weighted average)
        weighted_beta = 0.0
        for holding in portfolio.holdings:
            weight = holding.market_value / total_value
            beta = SECTOR_BETAS.get(holding.sector, 1.0)
            weighted_beta += weight * beta
        metrics.beta = weighted_beta
        
        # Estimated volatility (simplified)
        # In production, would use historical returns
        metrics.volatility = weighted_beta * 0.15  # Assume 15% market vol
        
        # VaR 95% (simplified parametric)
        metrics.var_95 = total_value * metrics.volatility * 1.65 * (1/12**0.5)
        
        return metrics
    
    def _make_recommendation(
        self,
        metrics_list: list[PortfolioMetrics],
        names: list[str],
    ) -> tuple[Optional[int], str]:
        """Make a recommendation based on metrics.
        
        Uses a simple scoring system considering:
        - Diversification (lower HHI is better)
        - Risk (lower beta/volatility)
        - Balance (reasonable cash allocation)
        
        Returns:
            Tuple of (recommended index, reason).
        """
        scores = []
        
        for i, m in enumerate(metrics_list):
            score = 0
            
            # Diversification score (lower HHI better)
            if m.concentration_hhi < 0.10:
                score += 3
            elif m.concentration_hhi < 0.15:
                score += 2
            elif m.concentration_hhi < 0.25:
                score += 1
            
            # Number of holdings score
            if 10 <= m.num_holdings <= 30:
                score += 2
            elif 5 <= m.num_holdings <= 50:
                score += 1
            
            # Beta score (prefer moderate beta)
            if 0.8 <= m.beta <= 1.2:
                score += 2
            elif 0.6 <= m.beta <= 1.4:
                score += 1
            
            # Cash allocation score
            if 0.02 <= m.cash_weight <= 0.15:
                score += 2
            elif m.cash_weight <= 0.25:
                score += 1
            
            # Top holding concentration score
            if m.top_holding_weight < 0.15:
                score += 2
            elif m.top_holding_weight < 0.25:
                score += 1
            
            scores.append(score)
        
        # Find best
        max_score = max(scores)
        best_idx = scores.index(max_score)
        
        # Build reason
        best_m = metrics_list[best_idx]
        reasons = []
        
        if best_m.concentration_hhi < min(m.concentration_hhi for m in metrics_list if m != best_m):
            reasons.append("better diversification")
        
        if best_m.beta < min(m.beta for m in metrics_list if m != best_m):
            reasons.append("lower risk (beta)")
        
        if len(reasons) == 0:
            reasons.append("overall balanced metrics")
        
        reason = f"{names[best_idx]} recommended due to {', '.join(reasons)}"
        
        return best_idx, reason
    
    def generate_comparison_table(
        self,
        comparison: PortfolioComparison,
    ) -> list[dict]:
        """Generate comparison table data.
        
        Args:
            comparison: Portfolio comparison result.
            
        Returns:
            List of dicts for table display.
        """
        rows = []
        
        metric_labels = [
            ("total_value", "Total Value", "${:,.0f}"),
            ("num_holdings", "Holdings", "{}"),
            ("cash_weight", "Cash %", "{:.1%}"),
            ("top_holding_weight", "Top Holding %", "{:.1%}"),
            ("concentration_hhi", "Concentration (HHI)", "{:.3f}"),
            ("beta", "Beta", "{:.2f}"),
            ("volatility", "Est. Volatility", "{:.1%}"),
            ("var_95", "VaR 95% (monthly)", "${:,.0f}"),
        ]
        
        for attr, label, fmt in metric_labels:
            row = {"Metric": label}
            for i, metrics in enumerate(comparison.metrics):
                value = getattr(metrics, attr, 0)
                row[comparison.portfolio_names[i]] = fmt.format(value)
            rows.append(row)
        
        return rows
