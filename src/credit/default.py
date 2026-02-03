"""Default Probability Estimator.

Estimates probability of default using Merton structural model,
CDS-implied probabilities, and statistical (Altman-style) scoring.
"""

import logging
from typing import Optional

import numpy as np
from scipy import stats

from src.credit.config import DefaultModel, DefaultConfig, DEFAULT_CREDIT_CONFIG
from src.credit.models import DefaultProbability

logger = logging.getLogger(__name__)


class DefaultEstimator:
    """Estimates default probabilities."""

    def __init__(self, config: Optional[DefaultConfig] = None) -> None:
        self.config = config or DEFAULT_CREDIT_CONFIG.default

    def merton_model(
        self,
        symbol: str,
        equity_value: float,
        debt_face: float,
        equity_vol: float,
        risk_free: Optional[float] = None,
        maturity: Optional[float] = None,
    ) -> DefaultProbability:
        """Estimate PD using Merton's structural model.

        The firm defaults when asset value falls below debt at maturity.
        Distance to default: DD = (ln(V/D) + (r - 0.5*σ²)*T) / (σ*√T)
        PD = N(-DD)

        Args:
            symbol: Issuer symbol.
            equity_value: Market value of equity.
            debt_face: Face value of debt.
            equity_vol: Annualized equity volatility.
            risk_free: Risk-free rate (default: config).
            maturity: Time horizon in years (default: config).

        Returns:
            DefaultProbability with distance-to-default and PD.
        """
        rf = risk_free if risk_free is not None else self.config.risk_free_rate
        T = maturity if maturity is not None else self.config.default_maturity

        if equity_value <= 0 or debt_face <= 0 or equity_vol <= 0 or T <= 0:
            return DefaultProbability(
                symbol=symbol, model=DefaultModel.MERTON,
            )

        # Approximate asset value as equity + debt
        asset_value = equity_value + debt_face

        # Approximate asset volatility
        leverage = equity_value / asset_value
        asset_vol = equity_vol * leverage

        if asset_vol <= 0:
            return DefaultProbability(
                symbol=symbol, model=DefaultModel.MERTON,
            )

        # Distance to default
        dd = (
            np.log(asset_value / debt_face)
            + (rf - 0.5 * asset_vol ** 2) * T
        ) / (asset_vol * np.sqrt(T))

        pd_1y = float(stats.norm.cdf(-dd))

        # 5Y PD (assuming constant hazard rate)
        if pd_1y > 0 and pd_1y < 1:
            hazard = -np.log(1 - pd_1y)
            pd_5y = float(1 - np.exp(-hazard * 5))
        else:
            pd_5y = min(pd_1y * 5, 1.0)

        return DefaultProbability(
            symbol=symbol,
            pd_1y=round(pd_1y, 6),
            pd_5y=round(pd_5y, 6),
            model=DefaultModel.MERTON,
            distance_to_default=round(float(dd), 4),
            recovery_rate=self.config.default_recovery_rate,
        )

    def cds_implied(
        self,
        symbol: str,
        cds_spread_bps: float,
        recovery_rate: Optional[float] = None,
    ) -> DefaultProbability:
        """Estimate PD from CDS spread.

        PD ≈ CDS_spread / (1 - recovery_rate)

        Args:
            symbol: Issuer symbol.
            cds_spread_bps: CDS spread in basis points.
            recovery_rate: Recovery rate assumption.

        Returns:
            DefaultProbability.
        """
        rr = recovery_rate if recovery_rate is not None else self.config.default_recovery_rate

        if cds_spread_bps <= 0 or rr >= 1.0:
            return DefaultProbability(
                symbol=symbol, model=DefaultModel.CDS_IMPLIED,
                recovery_rate=rr,
            )

        spread_decimal = cds_spread_bps / 10_000.0
        pd_1y = spread_decimal / (1.0 - rr)
        pd_1y = min(pd_1y, 1.0)

        # 5Y cumulative
        if pd_1y < 1.0:
            pd_5y = 1.0 - (1.0 - pd_1y) ** 5
        else:
            pd_5y = 1.0

        return DefaultProbability(
            symbol=symbol,
            pd_1y=round(pd_1y, 6),
            pd_5y=round(pd_5y, 6),
            model=DefaultModel.CDS_IMPLIED,
            recovery_rate=rr,
        )

    def statistical_model(
        self,
        symbol: str,
        working_capital_to_assets: float = 0.0,
        retained_earnings_to_assets: float = 0.0,
        ebit_to_assets: float = 0.0,
        equity_to_debt: float = 0.0,
        sales_to_assets: float = 0.0,
    ) -> DefaultProbability:
        """Estimate PD using Altman Z-score variant.

        Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5

        Z > 2.99 → safe, Z < 1.81 → distress

        Args:
            symbol: Issuer symbol.
            working_capital_to_assets: X1.
            retained_earnings_to_assets: X2.
            ebit_to_assets: X3.
            equity_to_debt: X4.
            sales_to_assets: X5.

        Returns:
            DefaultProbability with Z-score as distance_to_default.
        """
        z = (
            1.2 * working_capital_to_assets
            + 1.4 * retained_earnings_to_assets
            + 3.3 * ebit_to_assets
            + 0.6 * equity_to_debt
            + 1.0 * sales_to_assets
        )

        # Map Z-score to PD using logistic function
        # Higher Z = lower PD
        pd_1y = float(1.0 / (1.0 + np.exp(z - 2.0)))
        pd_1y = round(min(max(pd_1y, 0.0), 1.0), 6)

        if pd_1y < 1.0:
            pd_5y = round(1.0 - (1.0 - pd_1y) ** 5, 6)
        else:
            pd_5y = 1.0

        return DefaultProbability(
            symbol=symbol,
            pd_1y=pd_1y,
            pd_5y=pd_5y,
            model=DefaultModel.STATISTICAL,
            distance_to_default=round(z, 4),
            recovery_rate=self.config.default_recovery_rate,
        )
