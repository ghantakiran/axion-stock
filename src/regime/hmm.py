"""Hidden Markov Model Regime Detector.

Fits a Gaussian HMM on return/volatility features to classify
market regimes. Uses EM algorithm implemented with NumPy/SciPy
(no hmmlearn dependency).
"""

import logging
from typing import Optional

import numpy as np
from scipy import stats as sp_stats

from src.regime.config import HMMConfig, RegimeType
from src.regime.models import RegimeState, RegimeHistory, RegimeSegment

logger = logging.getLogger(__name__)

# Canonical regime ordering by mean return (lowest to highest)
REGIME_LABELS = [
    RegimeType.CRISIS.value,
    RegimeType.BEAR.value,
    RegimeType.SIDEWAYS.value,
    RegimeType.BULL.value,
]


class GaussianHMM:
    """Gaussian Hidden Markov Model for regime detection.

    Fits n_regimes Gaussian distributions to observed features and
    estimates transition probabilities using the EM algorithm.
    """

    def __init__(self, config: Optional[HMMConfig] = None) -> None:
        self.config = config or HMMConfig()
        self.n = self.config.n_regimes
        self._fitted = False

        # Model parameters (initialized during fit)
        self.means: Optional[np.ndarray] = None       # (n, d)
        self.covars: Optional[np.ndarray] = None       # (n, d, d)
        self.transmat: Optional[np.ndarray] = None     # (n, n)
        self.startprob: Optional[np.ndarray] = None    # (n,)
        self._label_order: list[str] = []

    def fit(self, observations: np.ndarray) -> "GaussianHMM":
        """Fit HMM to observation matrix.

        Args:
            observations: (T, d) array of feature observations.

        Returns:
            self.
        """
        T, d = observations.shape
        if T < self.config.min_observations:
            logger.warning("Insufficient observations (%d < %d)", T, self.config.min_observations)
            return self

        rng = np.random.RandomState(self.config.random_seed)

        # Initialize parameters via K-Means-style seeding
        self.startprob = np.ones(self.n) / self.n
        self.transmat = np.full((self.n, self.n), 1.0 / self.n)
        self.means = np.zeros((self.n, d))
        self.covars = np.zeros((self.n, d, d))

        # Sort observations, split into n quantile groups for initialization
        sort_idx = np.argsort(observations[:, 0])
        chunk = T // self.n
        for k in range(self.n):
            start = k * chunk
            end = T if k == self.n - 1 else (k + 1) * chunk
            subset = observations[sort_idx[start:end]]
            self.means[k] = subset.mean(axis=0)
            cov = np.cov(subset.T) if subset.shape[0] > 1 else np.eye(d) * 0.01
            if cov.ndim == 0:
                cov = np.array([[float(cov)]])
            self.covars[k] = cov + np.eye(d) * 1e-6

        # EM iterations
        prev_ll = -np.inf
        for iteration in range(self.config.n_iterations):
            # E-step: forward-backward
            log_lik = self._compute_log_likelihood(observations)
            alpha, scale = self._forward(log_lik)
            beta = self._backward(log_lik, scale)
            gamma = alpha * beta
            gamma /= gamma.sum(axis=1, keepdims=True) + 1e-300

            # Log-likelihood check
            ll = np.sum(np.log(scale + 1e-300))
            if abs(ll - prev_ll) < self.config.convergence_tol:
                break
            prev_ll = ll

            # Xi for transition matrix
            xi = np.zeros((self.n, self.n))
            for t in range(T - 1):
                for i in range(self.n):
                    for j in range(self.n):
                        xi[i, j] += (
                            alpha[t, i]
                            * self.transmat[i, j]
                            * np.exp(log_lik[t + 1, j])
                            * beta[t + 1, j]
                        )
            xi_row_sum = xi.sum(axis=1, keepdims=True)
            xi_row_sum[xi_row_sum == 0] = 1.0
            self.transmat = xi / xi_row_sum

            # M-step
            self.startprob = gamma[0] / (gamma[0].sum() + 1e-300)

            for k in range(self.n):
                weight = gamma[:, k]
                total_weight = weight.sum() + 1e-300
                self.means[k] = (weight[:, None] * observations).sum(axis=0) / total_weight
                diff = observations - self.means[k]
                self.covars[k] = (
                    (diff * weight[:, None]).T @ diff / total_weight
                    + np.eye(d) * 1e-6
                )

        # Label regimes by mean return (column 0)
        order = np.argsort(self.means[:, 0])
        self.means = self.means[order]
        self.covars = self.covars[order]
        self.transmat = self.transmat[order][:, order]
        self.startprob = self.startprob[order]
        self._label_order = REGIME_LABELS[: self.n]

        self._fitted = True
        return self

    def predict(self, observations: np.ndarray) -> list[str]:
        """Predict regime labels for observations.

        Args:
            observations: (T, d) feature array.

        Returns:
            List of regime label strings.
        """
        if not self._fitted:
            return [RegimeType.SIDEWAYS.value] * len(observations)

        log_lik = self._compute_log_likelihood(observations)
        alpha, scale = self._forward(log_lik)
        beta = self._backward(log_lik, scale)
        gamma = alpha * beta
        gamma /= gamma.sum(axis=1, keepdims=True) + 1e-300

        state_indices = np.argmax(gamma, axis=1)
        return [self._label_order[i] for i in state_indices]

    def predict_proba(self, observations: np.ndarray) -> list[dict[str, float]]:
        """Predict regime probabilities for each observation.

        Returns:
            List of dicts mapping regime label to probability.
        """
        if not self._fitted:
            uniform = {r: 1.0 / self.n for r in REGIME_LABELS[: self.n]}
            return [uniform] * len(observations)

        log_lik = self._compute_log_likelihood(observations)
        alpha, scale = self._forward(log_lik)
        beta = self._backward(log_lik, scale)
        gamma = alpha * beta
        gamma /= gamma.sum(axis=1, keepdims=True) + 1e-300

        results = []
        for t in range(len(observations)):
            probs = {
                self._label_order[k]: round(float(gamma[t, k]), 4)
                for k in range(self.n)
            }
            results.append(probs)
        return results

    def detect(self, returns: list[float], volatilities: Optional[list[float]] = None) -> RegimeState:
        """Detect current regime from return/volatility series.

        Args:
            returns: List of period returns.
            volatilities: Optional list of realized volatilities.

        Returns:
            RegimeState with current regime and confidence.
        """
        obs = self._build_features(returns, volatilities)
        if obs is None or len(obs) < self.config.min_observations:
            return RegimeState()

        if not self._fitted:
            self.fit(obs)

        proba = self.predict_proba(obs)
        labels = self.predict(obs)

        current_probs = proba[-1] if proba else {}
        current_regime = labels[-1] if labels else RegimeType.SIDEWAYS.value
        confidence = current_probs.get(current_regime, 0.0)

        # Duration of current regime
        duration = 1
        for i in range(len(labels) - 2, -1, -1):
            if labels[i] == current_regime:
                duration += 1
            else:
                break

        return RegimeState(
            regime=current_regime,
            confidence=round(confidence, 4),
            probabilities=current_probs,
            duration=duration,
            method="hmm",
        )

    def detect_history(
        self, returns: list[float], volatilities: Optional[list[float]] = None
    ) -> RegimeHistory:
        """Detect full regime history.

        Returns:
            RegimeHistory with regime labels, probabilities, and segments.
        """
        obs = self._build_features(returns, volatilities)
        if obs is None or len(obs) < self.config.min_observations:
            return RegimeHistory(method="hmm")

        if not self._fitted:
            self.fit(obs)

        labels = self.predict(obs)
        proba = self.predict_proba(obs)
        segments = self._extract_segments(labels, returns)

        return RegimeHistory(
            regimes=labels,
            probabilities=proba,
            segments=segments,
            method="hmm",
        )

    def _build_features(
        self, returns: list[float], volatilities: Optional[list[float]] = None
    ) -> Optional[np.ndarray]:
        """Build feature matrix from returns and optional volatilities."""
        if not returns:
            return None
        r = np.array(returns)
        if volatilities and len(volatilities) == len(returns):
            v = np.array(volatilities)
            return np.column_stack([r, v])
        return r.reshape(-1, 1)

    def _compute_log_likelihood(self, observations: np.ndarray) -> np.ndarray:
        """Compute log-likelihood of each observation under each state."""
        T, d = observations.shape
        log_lik = np.zeros((T, self.n))
        for k in range(self.n):
            try:
                rv = sp_stats.multivariate_normal(
                    mean=self.means[k], cov=self.covars[k], allow_singular=True
                )
                log_lik[:, k] = rv.logpdf(observations)
            except (np.linalg.LinAlgError, ValueError):
                log_lik[:, k] = -1e10
        return log_lik

    def _forward(self, log_lik: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Forward algorithm with scaling."""
        T = log_lik.shape[0]
        alpha = np.zeros((T, self.n))
        scale = np.zeros(T)

        alpha[0] = self.startprob * np.exp(log_lik[0])
        scale[0] = alpha[0].sum()
        if scale[0] > 0:
            alpha[0] /= scale[0]

        for t in range(1, T):
            alpha[t] = (alpha[t - 1] @ self.transmat) * np.exp(log_lik[t])
            scale[t] = alpha[t].sum()
            if scale[t] > 0:
                alpha[t] /= scale[t]

        return alpha, scale

    def _backward(self, log_lik: np.ndarray, scale: np.ndarray) -> np.ndarray:
        """Backward algorithm with scaling."""
        T = log_lik.shape[0]
        beta = np.zeros((T, self.n))
        beta[-1] = 1.0

        for t in range(T - 2, -1, -1):
            beta[t] = self.transmat @ (np.exp(log_lik[t + 1]) * beta[t + 1])
            if scale[t + 1] > 0:
                beta[t] /= scale[t + 1]

        return beta

    def _extract_segments(self, labels: list[str], returns: list[float]) -> list[RegimeSegment]:
        """Extract contiguous regime segments."""
        if not labels:
            return []

        segments = []
        start = 0
        current = labels[0]

        for i in range(1, len(labels)):
            if labels[i] != current:
                seg_returns = returns[start:i]
                segments.append(RegimeSegment(
                    regime=current,
                    start_idx=start,
                    end_idx=i - 1,
                    avg_return=round(float(np.mean(seg_returns)), 6) if seg_returns else 0.0,
                    volatility=round(float(np.std(seg_returns, ddof=1)), 6) if len(seg_returns) > 1 else 0.0,
                ))
                start = i
                current = labels[i]

        # Final segment
        seg_returns = returns[start:]
        segments.append(RegimeSegment(
            regime=current,
            start_idx=start,
            end_idx=len(labels) - 1,
            avg_return=round(float(np.mean(seg_returns)), 6) if seg_returns else 0.0,
            volatility=round(float(np.std(seg_returns, ddof=1)), 6) if len(seg_returns) > 1 else 0.0,
        ))

        return segments
