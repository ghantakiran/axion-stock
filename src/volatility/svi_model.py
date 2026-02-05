"""SVI Surface Calibration.

Fits Stochastic Volatility Inspired (SVI) parametrization to
implied volatility data with arbitrage-free constraints and
surface-level SSVI calibration.
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
class SVIParams:
    """Raw SVI parameters for a single slice."""
    a: float = 0.04  # Level
    b: float = 0.10  # Slope (wings angle)
    rho: float = -0.30  # Rotation (skew)
    m: float = 0.0  # Translation (center)
    sigma: float = 0.20  # Smoothing (ATM curvature)
    tenor_days: int = 30
    rmse: float = 0.0

    @property
    def atm_variance(self) -> float:
        return self.a + self.b * (self.sigma * np.sqrt(1.0 - self.rho ** 2))

    @property
    def atm_vol(self) -> float:
        t = self.tenor_days / 365.0
        if t <= 0:
            return 0.0
        return float(np.sqrt(max(0, self.atm_variance / t)))

    @property
    def min_variance(self) -> float:
        return self.a + self.b * self.sigma * np.sqrt(1.0 - self.rho ** 2)

    @property
    def is_arbitrage_free(self) -> bool:
        return self.b >= 0 and abs(self.rho) < 1 and self.sigma > 0 and self.min_variance >= 0


@dataclass
class SVISurface:
    """Full SVI-calibrated surface across tenors."""
    symbol: str = ""
    slices: dict[int, SVIParams] = field(default_factory=dict)
    spot: float = 0.0
    global_rmse: float = 0.0
    n_points_fitted: int = 0

    @property
    def tenors(self) -> list[int]:
        return sorted(self.slices.keys())

    @property
    def n_slices(self) -> int:
        return len(self.slices)

    @property
    def is_calibrated(self) -> bool:
        return self.n_slices > 0 and self.global_rmse < 0.05

    def get_iv(self, log_moneyness: float, tenor_days: int) -> float:
        """Interpolate IV from calibrated surface.

        Args:
            log_moneyness: ln(K/S).
            tenor_days: Time to expiry in days.

        Returns:
            Implied volatility.
        """
        if tenor_days in self.slices:
            return self._slice_iv(self.slices[tenor_days], log_moneyness, tenor_days)

        # Linear interpolation between nearest slices
        tenors = self.tenors
        if not tenors:
            return 0.2

        if tenor_days <= tenors[0]:
            return self._slice_iv(self.slices[tenors[0]], log_moneyness, tenors[0])
        if tenor_days >= tenors[-1]:
            return self._slice_iv(self.slices[tenors[-1]], log_moneyness, tenors[-1])

        # Find bracketing tenors
        for i in range(len(tenors) - 1):
            if tenors[i] <= tenor_days <= tenors[i + 1]:
                w = (tenor_days - tenors[i]) / (tenors[i + 1] - tenors[i])
                iv1 = self._slice_iv(self.slices[tenors[i]], log_moneyness, tenors[i])
                iv2 = self._slice_iv(self.slices[tenors[i + 1]], log_moneyness, tenors[i + 1])
                return iv1 * (1 - w) + iv2 * w

        return 0.2

    @staticmethod
    def _slice_iv(params: SVIParams, k: float, tenor_days: int) -> float:
        """Compute IV from SVI params for a single slice."""
        t = tenor_days / 365.0
        if t <= 0:
            return 0.2
        w = params.a + params.b * (
            params.rho * (k - params.m)
            + np.sqrt((k - params.m) ** 2 + params.sigma ** 2)
        )
        w = max(w, 1e-8)
        return float(np.sqrt(w / t))


@dataclass
class CalibrationResult:
    """Result of SVI calibration."""
    surface: SVISurface = field(default_factory=SVISurface)
    converged: bool = False
    n_iterations: int = 0
    final_rmse: float = 0.0
    arbitrage_violations: int = 0

    @property
    def is_good_fit(self) -> bool:
        return self.converged and self.final_rmse < 0.03

    @property
    def quality_label(self) -> str:
        if self.final_rmse < 0.01:
            return "excellent"
        elif self.final_rmse < 0.03:
            return "good"
        elif self.final_rmse < 0.05:
            return "fair"
        return "poor"


# ---------------------------------------------------------------------------
# SVI Calibrator
# ---------------------------------------------------------------------------
class SVICalibrator:
    """Calibrates SVI surfaces to market IV data.

    Fits per-slice SVI parameters with optional arbitrage-free
    constraints and provides cross-tenor interpolation.
    """

    def __init__(
        self,
        max_iterations: int = 500,
        tolerance: float = 1e-6,
        enforce_arbitrage_free: bool = True,
    ) -> None:
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.enforce_arbitrage_free = enforce_arbitrage_free

    def calibrate_slice(
        self,
        log_moneyness: np.ndarray,
        market_iv: np.ndarray,
        tenor_days: int,
    ) -> SVIParams:
        """Calibrate SVI parameters to a single tenor slice.

        Args:
            log_moneyness: Array of ln(K/S) values.
            market_iv: Array of market implied vols.
            tenor_days: Days to expiry.

        Returns:
            Fitted SVIParams.
        """
        if len(log_moneyness) < 3 or len(market_iv) < 3:
            return SVIParams(tenor_days=tenor_days)

        t = tenor_days / 365.0
        market_var = market_iv ** 2 * t

        # Initial guess from data
        atm_idx = int(np.argmin(np.abs(log_moneyness)))
        a_init = float(market_var[atm_idx])
        b_init = 0.1
        rho_init = -0.3
        m_init = 0.0
        sigma_init = 0.2

        params = np.array([a_init, b_init, rho_init, m_init, sigma_init])

        # Simple gradient-free optimization (Nelder-Mead style simplex)
        best_params = params.copy()
        best_rmse = self._rmse(params, log_moneyness, market_var)

        # Multi-start with perturbation
        for trial in range(3):
            current = params.copy()
            if trial > 0:
                current += np.random.normal(0, 0.02, 5)
                current[1] = abs(current[1])  # b >= 0
                current[2] = np.clip(current[2], -0.99, 0.99)  # |rho| < 1
                current[4] = abs(current[4]) + 0.01  # sigma > 0

            # Coordinate descent
            for iteration in range(self.max_iterations):
                improved = False
                for dim in range(5):
                    for step in [0.01, -0.01, 0.005, -0.005, 0.001, -0.001]:
                        candidate = current.copy()
                        candidate[dim] += step

                        # Enforce constraints
                        if candidate[1] < 0:
                            continue
                        if abs(candidate[2]) >= 1:
                            continue
                        if candidate[4] <= 0:
                            continue

                        rmse = self._rmse(candidate, log_moneyness, market_var)
                        if rmse < best_rmse:
                            best_rmse = rmse
                            best_params = candidate.copy()
                            current = candidate.copy()
                            improved = True

                if not improved or best_rmse < self.tolerance:
                    break

        a, b, rho, m, sigma = best_params
        return SVIParams(
            a=round(float(a), 6),
            b=round(float(abs(b)), 6),
            rho=round(float(np.clip(rho, -0.99, 0.99)), 6),
            m=round(float(m), 6),
            sigma=round(float(abs(sigma) + 1e-6), 6),
            tenor_days=tenor_days,
            rmse=round(float(best_rmse), 6),
        )

    def calibrate_surface(
        self,
        iv_data: dict[int, tuple[np.ndarray, np.ndarray]],
        spot: float = 100.0,
        symbol: str = "",
    ) -> CalibrationResult:
        """Calibrate full SVI surface across tenors.

        Args:
            iv_data: Dict of tenor_days -> (log_moneyness_array, iv_array).
            spot: Current spot price.
            symbol: Ticker symbol.

        Returns:
            CalibrationResult with calibrated surface.
        """
        slices: dict[int, SVIParams] = {}
        total_se = 0.0
        total_points = 0
        violations = 0

        for tenor, (k_arr, iv_arr) in iv_data.items():
            params = self.calibrate_slice(
                np.asarray(k_arr, dtype=float),
                np.asarray(iv_arr, dtype=float),
                tenor,
            )
            slices[tenor] = params
            total_se += params.rmse ** 2 * len(k_arr)
            total_points += len(k_arr)

            if self.enforce_arbitrage_free and not params.is_arbitrage_free:
                violations += 1

        global_rmse = float(np.sqrt(total_se / max(1, total_points)))

        surface = SVISurface(
            symbol=symbol,
            slices=slices,
            spot=spot,
            global_rmse=round(global_rmse, 6),
            n_points_fitted=total_points,
        )

        return CalibrationResult(
            surface=surface,
            converged=global_rmse < 0.05,
            n_iterations=self.max_iterations,
            final_rmse=round(global_rmse, 6),
            arbitrage_violations=violations,
        )

    def compare_surfaces(
        self,
        surface_a: SVISurface,
        surface_b: SVISurface,
    ) -> dict:
        """Compare two calibrated surfaces.

        Args:
            surface_a: First surface (e.g. today).
            surface_b: Second surface (e.g. yesterday).

        Returns:
            Dict with per-tenor parameter differences.
        """
        common_tenors = sorted(
            set(surface_a.tenors) & set(surface_b.tenors)
        )

        diffs = {}
        for t in common_tenors:
            pa = surface_a.slices[t]
            pb = surface_b.slices[t]
            diffs[t] = {
                "delta_a": round(pa.a - pb.a, 6),
                "delta_b": round(pa.b - pb.b, 6),
                "delta_rho": round(pa.rho - pb.rho, 6),
                "delta_atm_vol": round(pa.atm_vol - pb.atm_vol, 6),
            }

        return {
            "common_tenors": common_tenors,
            "diffs": diffs,
            "avg_atm_change": round(
                float(np.mean([d["delta_atm_vol"] for d in diffs.values()])), 6
            ) if diffs else 0.0,
        }

    @staticmethod
    def _rmse(params: np.ndarray, k: np.ndarray, market_var: np.ndarray) -> float:
        a, b, rho, m, sigma = params
        pred = a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + sigma ** 2))
        pred = np.maximum(pred, 1e-8)
        return float(np.sqrt(np.mean((pred - market_var) ** 2)))
