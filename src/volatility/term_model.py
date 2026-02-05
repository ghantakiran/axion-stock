"""Volatility Term Structure Modeling.

Nelson-Siegel style term structure fitting, carry/roll-down
analysis, and contango/backwardation dynamics tracking.
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
class TermStructureFit:
    """Fitted term structure parameters (Nelson-Siegel style)."""
    symbol: str = ""
    beta0: float = 0.0  # Long-term level
    beta1: float = 0.0  # Slope (short - long)
    beta2: float = 0.0  # Curvature (hump)
    tau: float = 90.0  # Decay factor (days)
    rmse: float = 0.0
    n_points: int = 0

    @property
    def long_term_vol(self) -> float:
        return self.beta0

    @property
    def short_term_vol(self) -> float:
        return self.beta0 + self.beta1

    @property
    def slope(self) -> float:
        return -self.beta1  # Positive = contango

    @property
    def is_good_fit(self) -> bool:
        return self.rmse < 0.02 and self.n_points >= 3

    def predict(self, tenor_days: float) -> float:
        """Predict vol at given tenor."""
        if tenor_days <= 0:
            return self.short_term_vol
        x = tenor_days / self.tau
        ex = np.exp(-x)
        return float(
            self.beta0
            + self.beta1 * (1 - ex) / x
            + self.beta2 * ((1 - ex) / x - ex)
        )


@dataclass
class CarryRollDown:
    """Volatility carry and roll-down analysis."""
    symbol: str = ""
    tenor_days: int = 30
    current_iv: float = 0.0
    realized_vol: float = 0.0
    vol_carry: float = 0.0  # IV - RV (positive = selling vol profitable)
    roll_down: float = 0.0  # Vol change from passage of time
    total_pnl_bps: float = 0.0  # Combined carry + roll

    @property
    def is_positive_carry(self) -> bool:
        return self.vol_carry > 0.005

    @property
    def carry_signal(self) -> str:
        if self.total_pnl_bps > 50:
            return "strong_sell_vol"
        elif self.total_pnl_bps > 20:
            return "mild_sell_vol"
        elif self.total_pnl_bps < -50:
            return "strong_buy_vol"
        elif self.total_pnl_bps < -20:
            return "mild_buy_vol"
        return "neutral"


@dataclass
class TermDynamics:
    """Term structure dynamics over time."""
    symbol: str = ""
    current_shape: str = "flat"  # contango, backwardation, flat, humped
    shape_change: str = "stable"  # flattening, steepening, inverting, stable
    front_vol: float = 0.0
    back_vol: float = 0.0
    slope_current: float = 0.0
    slope_prior: float = 0.0
    n_observations: int = 0

    @property
    def is_transitioning(self) -> bool:
        return self.shape_change in ("inverting", "steepening")

    @property
    def slope_change(self) -> float:
        return self.slope_current - self.slope_prior


@dataclass
class TermComparison:
    """Cross-symbol term structure comparison."""
    symbols: list[str] = field(default_factory=list)
    fits: list[TermStructureFit] = field(default_factory=list)
    steepest: str = ""
    flattest: str = ""
    highest_level: str = ""
    lowest_level: str = ""

    @property
    def n_symbols(self) -> int:
        return len(self.symbols)


# ---------------------------------------------------------------------------
# Term Structure Modeler
# ---------------------------------------------------------------------------
class TermStructureModeler:
    """Models volatility term structure with Nelson-Siegel framework.

    Fits parametric curves, computes carry/roll-down, and
    tracks term structure dynamics over time.
    """

    def __init__(
        self,
        default_tau: float = 90.0,
        min_points: int = 3,
    ) -> None:
        self.default_tau = default_tau
        self.min_points = min_points
        self._shape_history: dict[str, list[str]] = {}

    def fit(
        self,
        tenor_vol: list[tuple[int, float]],
        symbol: str = "",
    ) -> TermStructureFit:
        """Fit Nelson-Siegel model to term structure data.

        Args:
            tenor_vol: List of (tenor_days, implied_vol) tuples.
            symbol: Ticker symbol.

        Returns:
            TermStructureFit with fitted parameters.
        """
        if len(tenor_vol) < self.min_points:
            return TermStructureFit(
                symbol=symbol,
                beta0=tenor_vol[-1][1] if tenor_vol else 0.0,
                n_points=len(tenor_vol),
            )

        tenors = np.array([t for t, _ in tenor_vol], dtype=float)
        vols = np.array([v for _, v in tenor_vol], dtype=float)

        # Grid search over tau, then least squares for betas
        best_rmse = float("inf")
        best_params = (float(np.mean(vols)), 0.0, 0.0, self.default_tau)

        for tau in [30.0, 60.0, 90.0, 120.0, 180.0, 252.0]:
            x = tenors / tau
            ex = np.exp(-x)

            # Build design matrix for Nelson-Siegel
            X = np.column_stack([
                np.ones(len(tenors)),  # beta0
                (1 - ex) / np.maximum(x, 1e-8),  # beta1
                (1 - ex) / np.maximum(x, 1e-8) - ex,  # beta2
            ])

            # Least squares fit
            try:
                betas, _, _, _ = np.linalg.lstsq(X, vols, rcond=None)
                pred = X @ betas
                rmse = float(np.sqrt(np.mean((pred - vols) ** 2)))

                if rmse < best_rmse:
                    best_rmse = rmse
                    best_params = (float(betas[0]), float(betas[1]),
                                   float(betas[2]), tau)
            except np.linalg.LinAlgError:
                continue

        b0, b1, b2, tau = best_params
        return TermStructureFit(
            symbol=symbol,
            beta0=round(b0, 6),
            beta1=round(b1, 6),
            beta2=round(b2, 6),
            tau=tau,
            rmse=round(best_rmse, 6),
            n_points=len(tenor_vol),
        )

    def carry_roll_down(
        self,
        fit: TermStructureFit,
        realized_vol: float,
        tenor_days: int = 30,
        horizon_days: int = 1,
    ) -> CarryRollDown:
        """Compute carry and roll-down for a position.

        Args:
            fit: Fitted term structure.
            realized_vol: Current realized volatility.
            tenor_days: Current tenor.
            horizon_days: Holding period.

        Returns:
            CarryRollDown with carry and roll PnL.
        """
        current_iv = fit.predict(tenor_days)
        future_iv = fit.predict(max(1, tenor_days - horizon_days))

        vol_carry = current_iv - realized_vol
        roll_down = current_iv - future_iv  # Positive = IV drops as time passes

        # Convert to approximate bps PnL (vega-weighted)
        # Rough approximation: 1% vol change ~ 40 bps for 30d option
        vega_mult = 40.0 * (tenor_days / 30.0) ** 0.5
        total_pnl = (vol_carry + roll_down) * vega_mult * 100

        return CarryRollDown(
            symbol=fit.symbol,
            tenor_days=tenor_days,
            current_iv=round(current_iv, 6),
            realized_vol=round(realized_vol, 6),
            vol_carry=round(vol_carry, 6),
            roll_down=round(roll_down, 6),
            total_pnl_bps=round(total_pnl, 2),
        )

    def classify_shape(
        self,
        tenor_vol: list[tuple[int, float]],
    ) -> str:
        """Classify term structure shape.

        Args:
            tenor_vol: List of (tenor_days, implied_vol) tuples.

        Returns:
            Shape: contango, backwardation, humped, or flat.
        """
        if len(tenor_vol) < 2:
            return "flat"

        sorted_pts = sorted(tenor_vol, key=lambda x: x[0])
        front = sorted_pts[0][1]
        back = sorted_pts[-1][1]

        if len(sorted_pts) >= 3:
            mid_idx = len(sorted_pts) // 2
            mid = sorted_pts[mid_idx][1]
            if mid > front + 0.005 and mid > back + 0.005:
                return "humped"

        diff = back - front
        if diff > 0.005:
            return "contango"
        elif diff < -0.005:
            return "backwardation"
        return "flat"

    def track_dynamics(
        self,
        current_vols: list[tuple[int, float]],
        prior_vols: list[tuple[int, float]],
        symbol: str = "",
    ) -> TermDynamics:
        """Track term structure dynamics between periods.

        Args:
            current_vols: Current (tenor, vol) pairs.
            prior_vols: Prior period (tenor, vol) pairs.
            symbol: Ticker symbol.

        Returns:
            TermDynamics with shape and slope changes.
        """
        current_shape = self.classify_shape(current_vols)
        prior_shape = self.classify_shape(prior_vols)

        # Slopes
        def calc_slope(pts: list[tuple[int, float]]) -> float:
            if len(pts) < 2:
                return 0.0
            s = sorted(pts, key=lambda x: x[0])
            return (s[-1][1] - s[0][1]) / max(1, s[-1][0] - s[0][0])

        slope_curr = calc_slope(current_vols)
        slope_prior = calc_slope(prior_vols)

        # Shape change
        slope_diff = slope_curr - slope_prior
        if current_shape != prior_shape:
            shape_change = "inverting"
        elif slope_diff > 0.0001:
            shape_change = "steepening"
        elif slope_diff < -0.0001:
            shape_change = "flattening"
        else:
            shape_change = "stable"

        # Track history
        self._shape_history.setdefault(symbol, []).append(current_shape)

        sorted_curr = sorted(current_vols, key=lambda x: x[0])

        return TermDynamics(
            symbol=symbol,
            current_shape=current_shape,
            shape_change=shape_change,
            front_vol=round(sorted_curr[0][1], 6) if sorted_curr else 0.0,
            back_vol=round(sorted_curr[-1][1], 6) if sorted_curr else 0.0,
            slope_current=round(slope_curr, 8),
            slope_prior=round(slope_prior, 8),
            n_observations=len(self._shape_history.get(symbol, [])),
        )

    def compare_term_structures(
        self,
        fits: list[TermStructureFit],
    ) -> TermComparison:
        """Compare term structures across symbols.

        Args:
            fits: List of TermStructureFit objects.

        Returns:
            TermComparison with ranking.
        """
        if not fits:
            return TermComparison()

        symbols = [f.symbol for f in fits]
        steepest = max(fits, key=lambda f: f.slope)
        flattest = min(fits, key=lambda f: abs(f.slope))
        highest = max(fits, key=lambda f: f.long_term_vol)
        lowest = min(fits, key=lambda f: f.long_term_vol)

        return TermComparison(
            symbols=symbols,
            fits=fits,
            steepest=steepest.symbol,
            flattest=flattest.symbol,
            highest_level=highest.symbol,
            lowest_level=lowest.symbol,
        )
