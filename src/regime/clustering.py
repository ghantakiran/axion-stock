"""Clustering-Based Regime Classifier.

Uses K-Means or agglomerative clustering on windowed features
(return, volatility, skewness) to classify market regimes.
"""

import logging
from typing import Optional

import numpy as np
from scipy.spatial.distance import cdist
from scipy.cluster.hierarchy import fcluster, linkage

from src.regime.config import ClusterConfig, ClusterMethod, RegimeType
from src.regime.models import RegimeState, RegimeHistory, RegimeSegment

logger = logging.getLogger(__name__)

REGIME_LABELS = [
    RegimeType.CRISIS.value,
    RegimeType.BEAR.value,
    RegimeType.SIDEWAYS.value,
    RegimeType.BULL.value,
]


class ClusterRegimeClassifier:
    """Classifies market regimes using clustering on rolling features."""

    def __init__(self, config: Optional[ClusterConfig] = None) -> None:
        self.config = config or ClusterConfig()
        self._centroids: Optional[np.ndarray] = None
        self._label_map: dict[int, str] = {}
        self._fitted = False

    def fit(self, returns: list[float]) -> "ClusterRegimeClassifier":
        """Fit clustering model on return series.

        Args:
            returns: List of period returns.

        Returns:
            self.
        """
        features = self._compute_features(returns)
        if features is None or len(features) < self.config.min_observations:
            return self

        n_clusters = min(self.config.n_clusters, len(features))

        if self.config.method == ClusterMethod.KMEANS:
            labels, centroids = self._kmeans(features, n_clusters)
        else:
            labels, centroids = self._agglomerative(features, n_clusters)

        self._centroids = centroids
        self._label_map = self._assign_regime_labels(centroids)
        self._fitted = True
        return self

    def classify(self, returns: list[float]) -> RegimeState:
        """Classify current regime from return series.

        Args:
            returns: List of period returns.

        Returns:
            RegimeState.
        """
        features = self._compute_features(returns)
        if features is None or len(features) < self.config.min_observations:
            return RegimeState(method="clustering")

        if not self._fitted:
            self.fit(returns)

        if not self._fitted:
            return RegimeState(method="clustering")

        # Assign last window to nearest centroid
        last_feature = features[-1:, :]
        distances = cdist(last_feature, self._centroids, metric="euclidean")[0]
        cluster_idx = int(np.argmin(distances))

        # Confidence from distance ratio (closer = higher confidence)
        min_dist = distances[cluster_idx]
        second_min = np.partition(distances, 1)[1] if len(distances) > 1 else min_dist + 1
        confidence = 1.0 - (min_dist / (min_dist + second_min)) if (min_dist + second_min) > 0 else 0.5

        # Probabilities via softmax of negative distances
        neg_dist = -distances
        exp_d = np.exp(neg_dist - neg_dist.max())
        probs = exp_d / exp_d.sum()
        prob_dict = {
            self._label_map.get(k, REGIME_LABELS[k % len(REGIME_LABELS)]): round(float(probs[k]), 4)
            for k in range(len(probs))
        }

        regime = self._label_map.get(cluster_idx, RegimeType.SIDEWAYS.value)

        # Duration
        all_labels = self._predict_all(features)
        duration = 1
        for i in range(len(all_labels) - 2, -1, -1):
            if all_labels[i] == regime:
                duration += 1
            else:
                break

        return RegimeState(
            regime=regime,
            confidence=round(confidence, 4),
            probabilities=prob_dict,
            duration=duration,
            method="clustering",
        )

    def classify_history(self, returns: list[float]) -> RegimeHistory:
        """Classify full regime history.

        Returns:
            RegimeHistory.
        """
        features = self._compute_features(returns)
        if features is None or len(features) < self.config.min_observations:
            return RegimeHistory(method="clustering")

        if not self._fitted:
            self.fit(returns)

        if not self._fitted:
            return RegimeHistory(method="clustering")

        labels = self._predict_all(features)

        # Pad beginning (features start after window_size)
        pad_len = len(returns) - len(labels)
        full_labels = [labels[0]] * pad_len + labels

        # Probabilities for each point
        all_probs = []
        for feat in features:
            distances = cdist(feat.reshape(1, -1), self._centroids, metric="euclidean")[0]
            neg_dist = -distances
            exp_d = np.exp(neg_dist - neg_dist.max())
            probs = exp_d / exp_d.sum()
            prob_dict = {
                self._label_map.get(k, REGIME_LABELS[k % len(REGIME_LABELS)]): round(float(probs[k]), 4)
                for k in range(len(probs))
            }
            all_probs.append(prob_dict)

        pad_probs = [all_probs[0]] * pad_len + all_probs
        segments = self._extract_segments(full_labels, returns)

        return RegimeHistory(
            regimes=full_labels,
            probabilities=pad_probs,
            segments=segments,
            method="clustering",
        )

    def silhouette_score(self, returns: list[float]) -> float:
        """Compute silhouette score for current clustering.

        Returns:
            Silhouette score [-1, 1], higher is better.
        """
        features = self._compute_features(returns)
        if features is None or not self._fitted or self._centroids is None:
            return 0.0

        labels = self._predict_all_indices(features)
        unique = set(labels)
        if len(unique) < 2:
            return 0.0

        # Simplified silhouette: average (b - a) / max(a, b)
        n = len(features)
        scores = []
        for i in range(n):
            own_cluster = [j for j in range(n) if labels[j] == labels[i] and j != i]
            if not own_cluster:
                scores.append(0.0)
                continue
            a = np.mean([np.linalg.norm(features[i] - features[j]) for j in own_cluster])

            b_min = float("inf")
            for c in unique:
                if c == labels[i]:
                    continue
                other = [j for j in range(n) if labels[j] == c]
                if other:
                    b = np.mean([np.linalg.norm(features[i] - features[j]) for j in other])
                    b_min = min(b_min, b)

            s = (b_min - a) / max(a, b_min) if max(a, b_min) > 0 else 0.0
            scores.append(s)

        return round(float(np.mean(scores)), 4)

    def _compute_features(self, returns: list[float]) -> Optional[np.ndarray]:
        """Compute rolling window features."""
        if len(returns) < self.config.window_size + 1:
            return None

        arr = np.array(returns)
        w = self.config.window_size
        features = []

        for i in range(w, len(arr)):
            window = arr[i - w : i]
            mean_ret = np.mean(window)
            vol = np.std(window, ddof=1) if len(window) > 1 else 0.0
            row = [mean_ret, vol]
            features.append(row)

        return np.array(features) if features else None

    def _kmeans(
        self, features: np.ndarray, k: int, max_iter: int = 100
    ) -> tuple[np.ndarray, np.ndarray]:
        """Simple K-Means clustering."""
        n = len(features)
        rng = np.random.RandomState(42)
        indices = rng.choice(n, size=k, replace=False)
        centroids = features[indices].copy()

        labels = np.zeros(n, dtype=int)

        for _ in range(max_iter):
            dists = cdist(features, centroids, metric="euclidean")
            new_labels = np.argmin(dists, axis=1)

            if np.array_equal(new_labels, labels):
                break
            labels = new_labels

            for c in range(k):
                mask = labels == c
                if mask.sum() > 0:
                    centroids[c] = features[mask].mean(axis=0)

        return labels, centroids

    def _agglomerative(
        self, features: np.ndarray, k: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Agglomerative clustering."""
        Z = linkage(features, method="ward")
        labels = fcluster(Z, t=k, criterion="maxclust") - 1  # 0-indexed

        centroids = np.zeros((k, features.shape[1]))
        for c in range(k):
            mask = labels == c
            if mask.sum() > 0:
                centroids[c] = features[mask].mean(axis=0)

        return labels, centroids

    def _assign_regime_labels(self, centroids: np.ndarray) -> dict[int, str]:
        """Assign regime labels by sorting centroids by mean return (col 0)."""
        order = np.argsort(centroids[:, 0])
        mapping = {}
        for rank, cluster_idx in enumerate(order):
            label = REGIME_LABELS[rank] if rank < len(REGIME_LABELS) else f"regime_{rank}"
            mapping[int(cluster_idx)] = label
        return mapping

    def _predict_all(self, features: np.ndarray) -> list[str]:
        """Predict regime labels for all feature rows."""
        if self._centroids is None:
            return [RegimeType.SIDEWAYS.value] * len(features)
        dists = cdist(features, self._centroids, metric="euclidean")
        indices = np.argmin(dists, axis=1)
        return [
            self._label_map.get(int(i), RegimeType.SIDEWAYS.value) for i in indices
        ]

    def _predict_all_indices(self, features: np.ndarray) -> list[int]:
        """Predict cluster indices for all rows."""
        if self._centroids is None:
            return [0] * len(features)
        dists = cdist(features, self._centroids, metric="euclidean")
        return list(np.argmin(dists, axis=1))

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

        seg_returns = returns[start:]
        segments.append(RegimeSegment(
            regime=current,
            start_idx=start,
            end_idx=len(labels) - 1,
            avg_return=round(float(np.mean(seg_returns)), 6) if seg_returns else 0.0,
            volatility=round(float(np.std(seg_returns, ddof=1)), 6) if len(seg_returns) > 1 else 0.0,
        ))

        return segments
