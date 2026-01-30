"""Unified Cross-Asset Risk Management.

Cross-asset VaR, margin management, correlation regime detection,
and comprehensive risk reporting.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.multi_asset.config import (
    AssetClass,
    MarginAlertLevel,
    FuturesConfig,
)
from src.multi_asset.models import (
    MultiAssetPortfolio,
    CrossAssetRiskReport,
    MarginStatus,
)

logger = logging.getLogger(__name__)


class UnifiedRiskManager:
    """Unified risk management across all asset classes.

    Features:
    - Cross-asset Value-at-Risk (parametric and historical)
    - Risk contribution by asset class
    - Margin monitoring with alert levels
    - Correlation regime detection
    - Currency risk analysis
    - Leverage ratio calculation
    """

    def __init__(self, futures_config: Optional[FuturesConfig] = None):
        self.futures_config = futures_config or FuturesConfig()
        self._margin_status = MarginStatus()

    def compute_portfolio_risk(
        self,
        portfolio: MultiAssetPortfolio,
        returns: Optional[pd.DataFrame] = None,
        covariance: Optional[pd.DataFrame] = None,
    ) -> CrossAssetRiskReport:
        """Compute comprehensive cross-asset risk report.

        Args:
            portfolio: Multi-asset portfolio.
            returns: Historical daily returns DataFrame (symbol columns).
            covariance: Pre-computed covariance matrix.

        Returns:
            CrossAssetRiskReport.
        """
        report = CrossAssetRiskReport()

        weights = {a.symbol: a.weight for a in portfolio.allocations}
        classes = {a.symbol: a.asset_class for a in portfolio.allocations}

        if covariance is not None and len(covariance) > 0:
            report.total_var_95 = self._parametric_var(
                weights, covariance, confidence=0.95,
            )
            report.total_var_99 = self._parametric_var(
                weights, covariance, confidence=0.99,
            )

        if returns is not None and len(returns) > 0:
            report.max_drawdown = self._max_drawdown(weights, returns)

        report.risk_by_asset_class = self._risk_by_class(
            weights, classes, covariance,
        )

        report.currency_risk = self._currency_risk(portfolio)
        report.leverage_ratio = self._leverage_ratio(portfolio)
        report.margin_utilization = self._margin_status.utilization_pct

        if returns is not None and len(returns) > 1:
            report.correlation_regime = self._detect_correlation_regime(returns)

        return report

    def _parametric_var(
        self,
        weights: dict[str, float],
        covariance: pd.DataFrame,
        confidence: float = 0.95,
    ) -> float:
        """Compute parametric VaR.

        Args:
            weights: Symbol -> portfolio weight.
            covariance: Annualized covariance matrix.
            confidence: Confidence level.

        Returns:
            VaR as a negative percentage.
        """
        symbols = [s for s in weights if s in covariance.columns]
        if not symbols:
            return 0.0

        w = np.array([weights[s] for s in symbols])
        cov = covariance.loc[symbols, symbols].values

        port_vol = np.sqrt(w @ cov @ w)
        z = {0.95: 1.645, 0.99: 2.326}.get(confidence, 1.645)

        # Daily VaR (annualized vol / sqrt(252) * z-score)
        daily_var = port_vol / np.sqrt(252) * z
        return -daily_var

    def _max_drawdown(
        self,
        weights: dict[str, float],
        returns: pd.DataFrame,
    ) -> float:
        """Compute historical max drawdown for the portfolio.

        Args:
            weights: Symbol -> weight.
            returns: Daily returns DataFrame.

        Returns:
            Max drawdown as negative fraction.
        """
        common = [s for s in weights if s in returns.columns]
        if not common:
            return 0.0

        w = np.array([weights[s] for s in common])
        port_returns = (returns[common] * w).sum(axis=1)
        cumulative = (1 + port_returns).cumprod()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak

        return float(drawdown.min()) if len(drawdown) > 0 else 0.0

    def _risk_by_class(
        self,
        weights: dict[str, float],
        classes: dict[str, AssetClass],
        covariance: Optional[pd.DataFrame],
    ) -> dict[str, float]:
        """Compute risk contribution by asset class.

        Args:
            weights: Symbol -> weight.
            classes: Symbol -> asset class.
            covariance: Covariance matrix.

        Returns:
            Asset class -> risk contribution fraction.
        """
        if covariance is None or len(covariance) == 0:
            # Fall back to weight-based approximation
            class_weights: dict[str, float] = {}
            for sym, w in weights.items():
                ac = classes.get(sym, AssetClass.US_EQUITY).value
                class_weights[ac] = class_weights.get(ac, 0) + w
            return class_weights

        symbols = [s for s in weights if s in covariance.columns]
        if not symbols:
            return {}

        w = np.array([weights[s] for s in symbols])
        cov = covariance.loc[symbols, symbols].values

        port_var = w @ cov @ w
        if port_var <= 0:
            return {}

        # Marginal contribution to risk
        marginal = cov @ w
        risk_contrib = w * marginal / port_var

        # Aggregate by class
        class_risk: dict[str, float] = {}
        for i, sym in enumerate(symbols):
            ac = classes.get(sym, AssetClass.US_EQUITY).value
            class_risk[ac] = class_risk.get(ac, 0) + float(risk_contrib[i])

        return class_risk

    def _currency_risk(self, portfolio: MultiAssetPortfolio) -> float:
        """Estimate FX risk as fraction of non-USD exposure.

        Args:
            portfolio: Multi-asset portfolio.

        Returns:
            Non-USD weight fraction.
        """
        non_usd = sum(
            a.weight for a in portfolio.allocations
            if a.currency != "USD"
        )
        return non_usd

    def _leverage_ratio(self, portfolio: MultiAssetPortfolio) -> float:
        """Compute leverage ratio.

        For futures, notional value can exceed portfolio value.

        Args:
            portfolio: Multi-asset portfolio.

        Returns:
            Leverage ratio (1.0 = no leverage).
        """
        total_notional = sum(
            abs(a.value_usd) for a in portfolio.allocations
        )
        if portfolio.total_value_usd <= 0:
            return 0.0
        return total_notional / portfolio.total_value_usd

    def _detect_correlation_regime(self, returns: pd.DataFrame) -> str:
        """Detect if correlations are in a normal or stress regime.

        Uses rolling correlation to detect regime shifts.

        Args:
            returns: Daily returns DataFrame.

        Returns:
            'normal', 'elevated', or 'stress'.
        """
        if len(returns.columns) < 2 or len(returns) < 60:
            return "normal"

        # Recent 20-day correlation vs longer-term 120-day
        recent_corr = returns.tail(20).corr()
        if len(returns) >= 120:
            long_corr = returns.tail(120).corr()
        else:
            long_corr = returns.corr()

        # Average absolute correlation change
        mask = np.triu(np.ones_like(recent_corr, dtype=bool), k=1)
        recent_vals = recent_corr.values[mask]
        long_vals = long_corr.values[mask]

        if len(recent_vals) == 0:
            return "normal"

        avg_recent = float(np.mean(np.abs(recent_vals)))
        avg_long = float(np.mean(np.abs(long_vals)))

        diff = avg_recent - avg_long

        if diff > 0.20:
            return "stress"
        elif diff > 0.10:
            return "elevated"
        else:
            return "normal"

    def check_margin(
        self,
        total_required: float,
        total_available: float,
    ) -> MarginStatus:
        """Check margin status and return alerts.

        Args:
            total_required: Total margin required.
            total_available: Total margin available.

        Returns:
            MarginStatus with alert level.
        """
        self._margin_status.total_margin_required = total_required
        self._margin_status.total_margin_available = total_available
        self._margin_status.update()
        return self._margin_status

    def get_margin_alerts(self) -> list[dict]:
        """Get active margin alerts.

        Returns:
            List of alert dicts with level and message.
        """
        status = self._margin_status
        alerts = []

        if status.alert_level == MarginAlertLevel.LIQUIDATION:
            alerts.append({
                "level": "liquidation",
                "message": f"Margin utilization at {status.utilization_pct:.0%}. "
                           f"Auto-liquidation triggered.",
            })
        elif status.alert_level == MarginAlertLevel.MARGIN_CALL:
            alerts.append({
                "level": "margin_call",
                "message": f"Margin call: utilization at {status.utilization_pct:.0%}. "
                           f"Deposit funds or reduce positions.",
            })
        elif status.alert_level == MarginAlertLevel.CRITICAL:
            alerts.append({
                "level": "critical",
                "message": f"Margin utilization at {status.utilization_pct:.0%}. "
                           f"Approaching margin call.",
            })
        elif status.alert_level == MarginAlertLevel.WARNING:
            alerts.append({
                "level": "warning",
                "message": f"Margin utilization at {status.utilization_pct:.0%}. "
                           f"Monitor positions.",
            })

        return alerts
