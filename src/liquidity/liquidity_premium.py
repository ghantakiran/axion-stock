"""Illiquidity Premium Estimation.

Estimates the return premium demanded by investors for holding illiquid
assets using the Amihud (2002) illiquidity ratio, Pastor-Stambaugh
liquidity factor, and cross-sectional premium analysis.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class AmihudRatio:
    """Amihud (2002) illiquidity ratio."""
    symbol: str = ""
    illiquidity_ratio: float = 0.0  # Avg |return| / dollar volume
    n_observations: int = 0
    log_illiquidity: float = 0.0  # ln(1 + ratio * 1e6)

    @property
    def is_illiquid(self) -> bool:
        return self.illiquidity_ratio > 0.001

    @property
    def illiquidity_rank_score(self) -> float:
        """Normalized score: higher = more illiquid."""
        return min(1.0, self.illiquidity_ratio * 1000)


@dataclass
class PastorStambaughFactor:
    """Pastor-Stambaugh (2003) liquidity risk factor."""
    symbol: str = ""
    liquidity_beta: float = 0.0  # Sensitivity to market liquidity
    avg_gamma: float = 0.0  # Average price reversal coefficient
    n_observations: int = 0

    @property
    def is_liquidity_sensitive(self) -> bool:
        return abs(self.liquidity_beta) > 0.5

    @property
    def reversal_strength(self) -> float:
        return abs(self.avg_gamma)


@dataclass
class IlliquidityPremium:
    """Estimated illiquidity premium for a security."""
    symbol: str = ""
    amihud_ratio: float = 0.0
    estimated_premium_annual_pct: float = 0.0
    estimated_premium_monthly_pct: float = 0.0
    liquidity_beta: float = 0.0
    premium_confidence: float = 0.0
    liquidity_quintile: int = 0  # 1 (most liquid) to 5 (least liquid)

    @property
    def premium_bps_annual(self) -> float:
        return self.estimated_premium_annual_pct * 10_000

    @property
    def is_significant_premium(self) -> bool:
        return self.estimated_premium_annual_pct > 0.005  # >50 bps


@dataclass
class CrossSectionalPremium:
    """Cross-sectional illiquidity premium analysis."""
    n_securities: int = 0
    avg_premium_pct: float = 0.0
    premium_spread_pct: float = 0.0  # Q5 - Q1 premium
    quintile_returns: dict[int, float] = field(default_factory=dict)
    is_premium_significant: bool = False
    r_squared: float = 0.0

    @property
    def premium_bps(self) -> float:
        return self.avg_premium_pct * 10_000

    @property
    def long_short_return_pct(self) -> float:
        return self.premium_spread_pct


# ---------------------------------------------------------------------------
# Illiquidity Premium Estimator
# ---------------------------------------------------------------------------
class IlliquidityPremiumEstimator:
    """Estimates illiquidity premia using Amihud and Pastor-Stambaugh models."""

    # Empirical coefficient: maps Amihud ratio to premium
    # Based on Amihud (2002): ~0.5-2% annual premium per unit of illiquidity
    PREMIUM_COEFFICIENT = 1.5

    def __init__(
        self,
        premium_coefficient: float = 1.5,
        min_observations: int = 60,
    ) -> None:
        self.premium_coefficient = premium_coefficient
        self.min_observations = min_observations

    def amihud_ratio(
        self,
        returns: list[float],
        dollar_volumes: list[float],
        symbol: str = "",
    ) -> AmihudRatio:
        """Compute Amihud (2002) illiquidity ratio.

        ILLIQ = (1/N) * Sum(|R_t| / DollarVolume_t)

        Args:
            returns: List of daily returns.
            dollar_volumes: List of daily dollar volumes.
            symbol: Ticker symbol.

        Returns:
            AmihudRatio with illiquidity measure.
        """
        if not returns or not dollar_volumes:
            return AmihudRatio(symbol=symbol)

        n = min(len(returns), len(dollar_volumes))
        rets = np.array(returns[:n], dtype=float)
        dvols = np.array(dollar_volumes[:n], dtype=float)

        # Filter out zero-volume days
        valid = dvols > 0
        if not valid.any():
            return AmihudRatio(symbol=symbol, n_observations=0)

        ratios = np.abs(rets[valid]) / dvols[valid]
        illiq = float(np.mean(ratios))
        log_illiq = float(np.log(1.0 + illiq * 1e6))

        return AmihudRatio(
            symbol=symbol,
            illiquidity_ratio=round(illiq, 10),
            n_observations=int(valid.sum()),
            log_illiquidity=round(log_illiq, 4),
        )

    def pastor_stambaugh_factor(
        self,
        returns: list[float],
        signed_volumes: list[float],
        market_returns: Optional[list[float]] = None,
        symbol: str = "",
    ) -> PastorStambaughFactor:
        """Compute Pastor-Stambaugh (2003) liquidity factor.

        Estimates gamma from return reversal associated with volume:
        r_{t+1} = a + b*r_t + gamma*sign(r_t)*volume_t + e

        Args:
            returns: List of daily returns.
            signed_volumes: List of signed daily volumes.
            market_returns: Optional market returns for beta.
            symbol: Ticker symbol.

        Returns:
            PastorStambaughFactor with reversal coefficient.
        """
        if len(returns) < self.min_observations:
            return PastorStambaughFactor(
                symbol=symbol, n_observations=len(returns),
            )

        rets = np.array(returns, dtype=float)
        vols = np.array(signed_volumes[:len(rets)], dtype=float)

        n = len(rets) - 1
        if n < 10:
            return PastorStambaughFactor(symbol=symbol, n_observations=n)

        # Dependent: r_{t+1}
        y = rets[1:]

        # Independent: sign(r_t) * |volume_t|
        sign_r = np.sign(rets[:-1])
        x_gamma = sign_r * np.abs(vols[:-1])

        # Simple regression for gamma
        x_mean = float(np.mean(x_gamma))
        y_mean = float(np.mean(y))
        cov_xy = float(np.mean((x_gamma - x_mean) * (y - y_mean)))
        var_x = float(np.var(x_gamma))

        gamma = cov_xy / var_x if var_x > 0 else 0.0

        # Liquidity beta (sensitivity to market liquidity)
        liq_beta = 0.0
        if market_returns and len(market_returns) >= len(returns):
            mkt = np.array(market_returns[:len(returns)], dtype=float)
            mkt_gamma_proxy = np.sign(mkt[:-1]) * np.abs(vols[:-1])
            cov_mb = float(np.mean(
                (mkt_gamma_proxy - np.mean(mkt_gamma_proxy)) * (y - y_mean)
            ))
            var_mb = float(np.var(mkt_gamma_proxy))
            liq_beta = cov_mb / var_mb if var_mb > 0 else 0.0

        return PastorStambaughFactor(
            symbol=symbol,
            liquidity_beta=round(liq_beta, 4),
            avg_gamma=round(gamma, 8),
            n_observations=n,
        )

    def estimate_premium(
        self,
        amihud: AmihudRatio,
        ps_factor: Optional[PastorStambaughFactor] = None,
    ) -> IlliquidityPremium:
        """Estimate illiquidity premium for a security.

        Premium = coefficient * Amihud_ratio * scaling_factor

        Args:
            amihud: Amihud illiquidity ratio.
            ps_factor: Optional Pastor-Stambaugh factor.

        Returns:
            IlliquidityPremium estimate.
        """
        # Annual premium estimate
        annual_premium = self.premium_coefficient * amihud.log_illiquidity / 100
        monthly_premium = annual_premium / 12

        # Adjust for liquidity beta if available
        liq_beta = 0.0
        if ps_factor:
            liq_beta = ps_factor.liquidity_beta
            # Higher sensitivity = higher premium
            beta_adj = 1.0 + abs(liq_beta) * 0.2
            annual_premium *= beta_adj
            monthly_premium *= beta_adj

        # Quintile assignment
        illiq_score = amihud.illiquidity_rank_score
        if illiq_score >= 0.8:
            quintile = 5
        elif illiq_score >= 0.6:
            quintile = 4
        elif illiq_score >= 0.4:
            quintile = 3
        elif illiq_score >= 0.2:
            quintile = 2
        else:
            quintile = 1

        # Confidence based on observations
        confidence = min(
            0.9,
            amihud.n_observations / (self.min_observations * 2),
        )

        return IlliquidityPremium(
            symbol=amihud.symbol,
            amihud_ratio=amihud.illiquidity_ratio,
            estimated_premium_annual_pct=round(annual_premium, 6),
            estimated_premium_monthly_pct=round(monthly_premium, 6),
            liquidity_beta=round(liq_beta, 4),
            premium_confidence=round(confidence, 4),
            liquidity_quintile=quintile,
        )

    def cross_sectional_analysis(
        self,
        premiums: list[IlliquidityPremium],
    ) -> CrossSectionalPremium:
        """Analyze illiquidity premium across securities.

        Args:
            premiums: List of per-security premium estimates.

        Returns:
            CrossSectionalPremium with quintile analysis.
        """
        if not premiums:
            return CrossSectionalPremium()

        sorted_p = sorted(premiums, key=lambda p: p.amihud_ratio)
        n = len(sorted_p)

        # Quintile returns
        quintile_size = max(1, n // 5)
        quintile_returns: dict[int, float] = {}
        for q in range(1, 6):
            start = (q - 1) * quintile_size
            end = min(n, q * quintile_size) if q < 5 else n
            subset = sorted_p[start:end]
            if subset:
                quintile_returns[q] = round(
                    float(np.mean([p.estimated_premium_annual_pct for p in subset])),
                    6,
                )
            else:
                quintile_returns[q] = 0.0

        avg_premium = float(np.mean([
            p.estimated_premium_annual_pct for p in premiums
        ]))
        spread = quintile_returns.get(5, 0.0) - quintile_returns.get(1, 0.0)

        # R-squared: correlation between Amihud ratio and premium
        amihuds = np.array([p.amihud_ratio for p in premiums])
        prems = np.array([p.estimated_premium_annual_pct for p in premiums])
        if len(amihuds) > 2 and np.std(amihuds) > 0 and np.std(prems) > 0:
            corr = float(np.corrcoef(amihuds, prems)[0, 1])
            r_sq = corr ** 2
        else:
            r_sq = 0.0

        return CrossSectionalPremium(
            n_securities=n,
            avg_premium_pct=round(avg_premium, 6),
            premium_spread_pct=round(spread, 6),
            quintile_returns=quintile_returns,
            is_premium_significant=spread > 0.005,
            r_squared=round(r_sq, 4),
        )
