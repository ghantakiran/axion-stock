"""Valuation Models Module.

DCF, comparable analysis, and other valuation methods.
"""

from typing import Optional
import logging
import math

from src.research.config import (
    ResearchConfig,
    DEFAULT_RESEARCH_CONFIG,
    DEFAULT_RISK_FREE_RATE,
    DEFAULT_MARKET_PREMIUM,
    DEFAULT_BETA,
    MIN_TERMINAL_GROWTH,
    MAX_TERMINAL_GROWTH,
    ValuationMethod,
)
from src.research.models import (
    DCFValuation,
    ComparableValuation,
    ValuationSummary,
    FinancialMetrics,
)

logger = logging.getLogger(__name__)


class ValuationEngine:
    """Performs stock valuations using multiple methods.
    
    Features:
    - Discounted Cash Flow (DCF)
    - Comparable company analysis
    - Dividend Discount Model
    - Sensitivity analysis
    
    Example:
        engine = ValuationEngine()
        valuation = engine.value_stock(symbol, metrics, market_data)
    """
    
    def __init__(self, config: Optional[ResearchConfig] = None):
        self.config = config or DEFAULT_RESEARCH_CONFIG
        self._dcf_config = self.config.dcf
    
    def value_stock(
        self,
        symbol: str,
        metrics: FinancialMetrics,
        market_data: dict,
        peer_data: Optional[dict] = None,
    ) -> ValuationSummary:
        """Perform comprehensive valuation.
        
        Args:
            symbol: Stock symbol.
            metrics: Financial metrics.
            market_data: Market data (price, beta, etc.).
            peer_data: Peer company data for comparables.
            
        Returns:
            ValuationSummary with multiple methods.
        """
        current_price = market_data.get("price", 0)
        shares_outstanding = market_data.get("shares_outstanding", 1e9)
        
        # DCF valuation
        dcf = self.dcf_valuation(
            metrics=metrics,
            market_data=market_data,
            shares_outstanding=shares_outstanding,
        )
        
        # Comparable valuation
        comparable = None
        if peer_data:
            comparable = self.comparable_valuation(
                metrics=metrics,
                market_data=market_data,
                peer_data=peer_data,
                shares_outstanding=shares_outstanding,
            )
        
        # DDM if applicable
        ddm_value = None
        dividend_yield = market_data.get("dividend_yield", 0)
        if dividend_yield > 0:
            ddm_value = self.ddm_valuation(
                current_dividend=current_price * dividend_yield,
                growth_rate=min(metrics.eps_growth_yoy, 0.08),
                discount_rate=self._calculate_wacc(market_data),
            )
        
        # Weighted fair value
        dcf_weight = 0.5
        comparable_weight = 0.35 if comparable else 0
        ddm_weight = 0.15 if ddm_value else 0
        
        total_weight = dcf_weight + comparable_weight + ddm_weight
        
        fair_value = (
            (dcf.fair_value_per_share * dcf_weight +
             (comparable.implied_value_ev_ebitda if comparable else 0) * comparable_weight +
             (ddm_value or 0) * ddm_weight)
            / total_weight
        )
        
        # Calculate range
        values = [dcf.fair_value_per_share]
        if comparable:
            values.extend([
                comparable.implied_value_pe,
                comparable.implied_value_ev_ebitda,
            ])
        if ddm_value:
            values.append(ddm_value)
        
        values = [v for v in values if v > 0]
        
        upside = (fair_value - current_price) / current_price * 100 if current_price > 0 else 0
        
        # Confidence based on value dispersion
        if len(values) > 1:
            cv = (max(values) - min(values)) / (sum(values) / len(values))
            confidence = max(0.3, min(0.9, 1 - cv))
        else:
            confidence = 0.5
        
        return ValuationSummary(
            symbol=symbol,
            current_price=current_price,
            dcf_value=dcf.fair_value_per_share,
            comparable_value=comparable.implied_value_ev_ebitda if comparable else 0,
            ddm_value=ddm_value,
            fair_value=fair_value,
            upside_pct=upside,
            confidence=confidence,
            valuation_range_low=min(values) if values else 0,
            valuation_range_high=max(values) if values else 0,
            dcf=dcf,
            comparable=comparable,
        )
    
    def dcf_valuation(
        self,
        metrics: FinancialMetrics,
        market_data: dict,
        shares_outstanding: float,
        revenue_growth_override: Optional[list[float]] = None,
    ) -> DCFValuation:
        """Perform DCF valuation.
        
        Args:
            metrics: Financial metrics.
            market_data: Market data.
            shares_outstanding: Shares outstanding.
            revenue_growth_override: Custom growth rates.
            
        Returns:
            DCFValuation object.
        """
        dcf = DCFValuation()
        dcf.projection_years = self._dcf_config.projection_years
        
        # Calculate WACC
        wacc = self._calculate_wacc(market_data)
        dcf.wacc = wacc
        
        # Growth assumptions
        if revenue_growth_override:
            dcf.revenue_growth_rates = revenue_growth_override
        else:
            dcf.revenue_growth_rates = self._estimate_growth_rates(metrics)
        
        dcf.terminal_growth_rate = self._dcf_config.terminal_growth_rate
        dcf.operating_margin_target = self._estimate_target_margin(metrics)
        dcf.tax_rate = self._dcf_config.tax_rate
        
        # Project revenues
        current_revenue = metrics.revenue_ttm
        dcf.projected_revenues = [current_revenue]
        
        for i, growth in enumerate(dcf.revenue_growth_rates):
            next_rev = dcf.projected_revenues[-1] * (1 + growth)
            dcf.projected_revenues.append(next_rev)
        
        dcf.projected_revenues = dcf.projected_revenues[1:]  # Remove base year
        
        # Project EBIT and FCF
        dcf.projected_ebit = []
        dcf.projected_fcf = []
        
        current_margin = metrics.operating_margin
        margin_improvement = (dcf.operating_margin_target - current_margin) / dcf.projection_years
        
        for i, revenue in enumerate(dcf.projected_revenues):
            margin = current_margin + margin_improvement * (i + 1)
            ebit = revenue * margin
            dcf.projected_ebit.append(ebit)
            
            # FCF = EBIT * (1 - tax) + D&A - CapEx - Change in WC
            # Simplified: FCF ≈ NOPAT * conversion rate
            nopat = ebit * (1 - dcf.tax_rate)
            fcf_conversion = 0.85  # Assume 85% conversion
            fcf = nopat * fcf_conversion
            dcf.projected_fcf.append(fcf)
        
        # Present value of FCF
        pv_fcf = 0
        for i, fcf in enumerate(dcf.projected_fcf):
            pv_fcf += fcf / ((1 + wacc) ** (i + 1))
        dcf.pv_fcf = pv_fcf
        
        # Terminal value (Gordon Growth)
        terminal_fcf = dcf.projected_fcf[-1] * (1 + dcf.terminal_growth_rate)
        dcf.terminal_value = terminal_fcf / (wacc - dcf.terminal_growth_rate)
        dcf.pv_terminal_value = dcf.terminal_value / ((1 + wacc) ** dcf.projection_years)
        
        # Enterprise and equity value
        dcf.enterprise_value = dcf.pv_fcf + dcf.pv_terminal_value
        net_debt = metrics.total_debt - metrics.cash_and_equivalents
        dcf.equity_value = dcf.enterprise_value - net_debt
        dcf.fair_value_per_share = dcf.equity_value / shares_outstanding
        
        # Sensitivity analysis
        dcf.sensitivity_matrix = self._build_sensitivity_matrix(
            base_fcf=dcf.projected_fcf[-1],
            base_wacc=wacc,
            base_terminal_growth=dcf.terminal_growth_rate,
            projection_years=dcf.projection_years,
            pv_fcf=dcf.pv_fcf,
            net_debt=net_debt,
            shares=shares_outstanding,
        )
        
        return dcf
    
    def comparable_valuation(
        self,
        metrics: FinancialMetrics,
        market_data: dict,
        peer_data: dict,
        shares_outstanding: float,
    ) -> ComparableValuation:
        """Perform comparable company analysis.
        
        Args:
            metrics: Target company metrics.
            market_data: Target company market data.
            peer_data: Dict of peer symbol -> metrics.
            shares_outstanding: Target shares outstanding.
            
        Returns:
            ComparableValuation object.
        """
        comp = ComparableValuation()
        comp.peer_group = list(peer_data.keys())
        
        current_price = market_data.get("price", 0)
        market_cap = current_price * shares_outstanding
        
        # Target multiples
        if metrics.eps_ttm > 0:
            comp.pe_ratio = current_price / metrics.eps_ttm
        
        ebitda = metrics.operating_income * 1.15  # Approximate
        ev = market_cap + metrics.net_debt
        if ebitda > 0:
            comp.ev_ebitda = ev / ebitda
        
        if metrics.revenue_ttm > 0:
            comp.ev_revenue = ev / metrics.revenue_ttm
            comp.ps_ratio = market_cap / metrics.revenue_ttm
        
        if metrics.total_equity > 0:
            comp.pb_ratio = market_cap / metrics.total_equity
        
        # Peer multiples
        peer_pes = []
        peer_ev_ebitdas = []
        peer_ev_revenues = []
        peer_pbs = []
        peer_pss = []
        
        for peer_symbol, peer_metrics in peer_data.items():
            if isinstance(peer_metrics, dict):
                if peer_metrics.get("pe", 0) > 0:
                    peer_pes.append(peer_metrics["pe"])
                if peer_metrics.get("ev_ebitda", 0) > 0:
                    peer_ev_ebitdas.append(peer_metrics["ev_ebitda"])
                if peer_metrics.get("ev_revenue", 0) > 0:
                    peer_ev_revenues.append(peer_metrics["ev_revenue"])
                if peer_metrics.get("pb", 0) > 0:
                    peer_pbs.append(peer_metrics["pb"])
                if peer_metrics.get("ps", 0) > 0:
                    peer_pss.append(peer_metrics["ps"])
                
                comp.peer_data[peer_symbol] = peer_metrics
        
        # Peer averages (use median for robustness)
        comp.peer_avg_pe = self._median(peer_pes) if peer_pes else 0
        comp.peer_avg_ev_ebitda = self._median(peer_ev_ebitdas) if peer_ev_ebitdas else 0
        comp.peer_avg_ev_revenue = self._median(peer_ev_revenues) if peer_ev_revenues else 0
        comp.peer_avg_pb = self._median(peer_pbs) if peer_pbs else 0
        comp.peer_avg_ps = self._median(peer_pss) if peer_pss else 0
        
        # Implied values
        if comp.peer_avg_pe > 0 and metrics.eps_ttm > 0:
            comp.implied_value_pe = comp.peer_avg_pe * metrics.eps_ttm
        
        if comp.peer_avg_ev_ebitda > 0 and ebitda > 0:
            implied_ev = comp.peer_avg_ev_ebitda * ebitda
            comp.implied_value_ev_ebitda = (implied_ev - metrics.net_debt) / shares_outstanding
        
        if comp.peer_avg_ev_revenue > 0 and metrics.revenue_ttm > 0:
            implied_ev = comp.peer_avg_ev_revenue * metrics.revenue_ttm
            comp.implied_value_ev_revenue = (implied_ev - metrics.net_debt) / shares_outstanding
        
        if comp.peer_avg_pb > 0 and metrics.total_equity > 0:
            comp.implied_value_pb = (comp.peer_avg_pb * metrics.total_equity) / shares_outstanding
        
        # Premium/discount to peers
        if comp.peer_avg_pe > 0 and comp.pe_ratio > 0:
            comp.premium_to_peers_pct = (comp.pe_ratio / comp.peer_avg_pe - 1) * 100
        
        return comp
    
    def ddm_valuation(
        self,
        current_dividend: float,
        growth_rate: float,
        discount_rate: float,
    ) -> float:
        """Dividend Discount Model valuation.
        
        Args:
            current_dividend: Current annual dividend.
            growth_rate: Expected dividend growth rate.
            discount_rate: Required rate of return.
            
        Returns:
            Fair value per share.
        """
        if discount_rate <= growth_rate:
            return 0  # Model not valid
        
        # Gordon Growth Model
        next_dividend = current_dividend * (1 + growth_rate)
        fair_value = next_dividend / (discount_rate - growth_rate)
        
        return fair_value
    
    def _calculate_wacc(self, market_data: dict) -> float:
        """Calculate weighted average cost of capital."""
        beta = market_data.get("beta", DEFAULT_BETA)
        risk_free = self._dcf_config.risk_free_rate
        market_premium = self._dcf_config.market_premium
        
        # Cost of equity (CAPM)
        cost_of_equity = risk_free + beta * market_premium
        
        # Simplified: assume 80% equity, 20% debt
        # In practice, would use actual capital structure
        cost_of_debt = risk_free + 0.02  # Risk-free + spread
        tax_rate = self._dcf_config.tax_rate
        
        equity_weight = 0.80
        debt_weight = 0.20
        
        wacc = (
            equity_weight * cost_of_equity +
            debt_weight * cost_of_debt * (1 - tax_rate)
        )
        
        return wacc
    
    def _estimate_growth_rates(self, metrics: FinancialMetrics) -> list[float]:
        """Estimate future growth rates."""
        years = self._dcf_config.projection_years
        
        # Start with recent growth, fade to terminal
        current_growth = max(-0.10, min(0.30, metrics.revenue_growth_yoy))
        terminal_growth = self._dcf_config.terminal_growth_rate
        
        # Linear fade
        growth_rates = []
        for i in range(years):
            progress = i / (years - 1) if years > 1 else 1
            rate = current_growth * (1 - progress) + terminal_growth * progress * 2
            growth_rates.append(max(terminal_growth, rate))
        
        return growth_rates
    
    def _estimate_target_margin(self, metrics: FinancialMetrics) -> float:
        """Estimate target operating margin."""
        current = metrics.operating_margin
        
        # Assume some margin expansion for growing companies
        if metrics.revenue_growth_yoy > 0.10:
            target = min(current * 1.15, 0.35)
        else:
            target = current
        
        return max(0.05, target)
    
    def _build_sensitivity_matrix(
        self,
        base_fcf: float,
        base_wacc: float,
        base_terminal_growth: float,
        projection_years: int,
        pv_fcf: float,
        net_debt: float,
        shares: float,
    ) -> dict[str, dict[str, float]]:
        """Build WACC vs terminal growth sensitivity matrix."""
        wacc_range = [base_wacc - 0.02, base_wacc - 0.01, base_wacc, 
                      base_wacc + 0.01, base_wacc + 0.02]
        growth_range = [base_terminal_growth - 0.01, base_terminal_growth - 0.005,
                        base_terminal_growth, base_terminal_growth + 0.005,
                        base_terminal_growth + 0.01]
        
        matrix = {}
        for wacc in wacc_range:
            wacc_key = f"{wacc:.1%}"
            matrix[wacc_key] = {}
            
            for growth in growth_range:
                if wacc <= growth:
                    continue
                
                terminal_fcf = base_fcf * (1 + growth)
                terminal_value = terminal_fcf / (wacc - growth)
                pv_terminal = terminal_value / ((1 + wacc) ** projection_years)
                
                ev = pv_fcf + pv_terminal
                equity_value = ev - net_debt
                fair_value = equity_value / shares
                
                growth_key = f"{growth:.1%}"
                matrix[wacc_key][growth_key] = round(fair_value, 2)
        
        return matrix
    
    def _median(self, values: list) -> float:
        """Calculate median of a list."""
        if not values:
            return 0
        sorted_values = sorted(values)
        n = len(sorted_values)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_values[mid - 1] + sorted_values[mid]) / 2
        return sorted_values[mid]
