"""Model Degradation Detection.

Detects when models degrade via:
- Rolling IC monitoring
- Feature distribution drift (PSI)
- Comparison against random baseline
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.ml.config import MonitoringConfig

logger = logging.getLogger(__name__)


@dataclass
class DriftReport:
    """Feature drift analysis report."""

    overall_drift: str = "none"  # none, minor, significant, critical
    psi_scores: dict[str, float] = field(default_factory=dict)
    drifted_features: list[str] = field(default_factory=list)
    message: str = ""


class DegradationDetector:
    """Detect model degradation and feature drift.

    Monitors model performance and feature distributions to
    identify when models need retraining.

    Example:
        detector = DegradationDetector()
        drift = detector.check_feature_drift(
            train_features=X_train,
            current_features=X_current,
        )
    """

    def __init__(self, config: Optional[MonitoringConfig] = None):
        self.config = config or MonitoringConfig()
        self._baseline_distributions: dict[str, dict] = {}

    def check_feature_drift(
        self,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame,
        n_features: Optional[int] = None,
    ) -> DriftReport:
        """Check for feature distribution drift using PSI.

        Population Stability Index (PSI) measures how much
        the distribution has shifted.

        Args:
            reference_data: Training data features.
            current_data: Current/production features.
            n_features: Number of features to check (top N by variance).

        Returns:
            DriftReport with PSI scores and drift assessment.
        """
        report = DriftReport()
        n_check = n_features or self.config.psi_check_features

        # Select top features by variance
        common_cols = reference_data.columns.intersection(current_data.columns)
        if len(common_cols) == 0:
            report.message = "No common features between reference and current data"
            return report

        # Sort by variance in reference data
        variances = reference_data[common_cols].var().sort_values(ascending=False)
        check_cols = list(variances.index[:n_check])

        for col in check_cols:
            ref_values = reference_data[col].dropna()
            cur_values = current_data[col].dropna()

            if len(ref_values) < 10 or len(cur_values) < 10:
                continue

            psi = self._calculate_psi(ref_values, cur_values)
            report.psi_scores[col] = psi

            if psi > self.config.psi_threshold:
                report.drifted_features.append(col)

        # Overall drift assessment
        if not report.psi_scores:
            report.overall_drift = "none"
            report.message = "Insufficient data for drift analysis"
        elif len(report.drifted_features) == 0:
            report.overall_drift = "none"
            report.message = "No significant feature drift detected"
        elif len(report.drifted_features) <= 2:
            report.overall_drift = "minor"
            report.message = f"Minor drift in {len(report.drifted_features)} feature(s)"
        elif len(report.drifted_features) <= 5:
            report.overall_drift = "significant"
            report.message = f"Significant drift in {len(report.drifted_features)} features, consider retraining"
        else:
            report.overall_drift = "critical"
            report.message = f"Critical drift in {len(report.drifted_features)} features, retraining recommended"

        return report

    def check_prediction_quality(
        self,
        predictions: pd.Series,
        actuals: pd.Series,
        baseline: str = "random",
    ) -> dict:
        """Compare model predictions against a baseline.

        Args:
            predictions: Model predictions.
            actuals: Actual outcomes.
            baseline: Baseline type ('random' or 'naive').

        Returns:
            Dict with comparison metrics.
        """
        from scipy.stats import spearmanr

        # Align
        common = predictions.index.intersection(actuals.index)
        if len(common) < 10:
            return {"error": "Insufficient data"}

        preds = predictions.loc[common]
        acts = actuals.loc[common]

        # Model IC
        model_ic, model_pval = spearmanr(preds, acts)

        # Baseline IC
        if baseline == "random":
            np.random.seed(42)
            random_preds = pd.Series(np.random.randn(len(acts)), index=acts.index)
            baseline_ic, _ = spearmanr(random_preds, acts)
        else:
            # Naive: use lagged actuals
            baseline_ic = 0.0

        return {
            "model_ic": float(model_ic),
            "model_pval": float(model_pval),
            "baseline_ic": float(baseline_ic),
            "ic_lift": float(model_ic - baseline_ic),
            "beats_baseline": model_ic > baseline_ic,
            "statistically_significant": model_pval < 0.05,
        }

    def check_ic_trend(
        self,
        monthly_ics: pd.Series,
        alert_months: Optional[int] = None,
    ) -> dict:
        """Check if IC is trending downward.

        Args:
            monthly_ics: Monthly IC values.
            alert_months: Number of months below threshold to trigger alert.

        Returns:
            Dict with trend analysis.
        """
        alert_months = alert_months or self.config.ic_alert_months

        if len(monthly_ics) < alert_months:
            return {"trend": "insufficient_data", "alert": False}

        recent = monthly_ics.iloc[-alert_months:]

        # Check if consistently below threshold
        below_threshold = (recent < self.config.ic_degraded).all()

        # Linear trend
        x = np.arange(len(monthly_ics))
        if len(x) > 1:
            slope = np.polyfit(x, monthly_ics.values, 1)[0]
        else:
            slope = 0

        return {
            "trend": "declining" if slope < -0.001 else "improving" if slope > 0.001 else "stable",
            "slope": float(slope),
            "recent_mean": float(recent.mean()),
            "recent_min": float(recent.min()),
            "alert": bool(below_threshold),
            "alert_message": (
                f"IC below {self.config.ic_degraded} for {alert_months} consecutive months"
                if below_threshold else ""
            ),
        }

    def _calculate_psi(
        self,
        reference: pd.Series,
        current: pd.Series,
        n_bins: int = 10,
    ) -> float:
        """Calculate Population Stability Index.

        PSI < 0.1: No significant shift
        PSI 0.1-0.25: Moderate shift
        PSI > 0.25: Significant shift

        Args:
            reference: Reference distribution.
            current: Current distribution.
            n_bins: Number of bins for discretization.

        Returns:
            PSI value.
        """
        # Create bins from reference data
        try:
            bins = pd.qcut(reference, q=n_bins, duplicates="drop", retbins=True)[1]
        except ValueError:
            return 0.0

        # Bin both distributions
        ref_binned = pd.cut(reference, bins=bins, include_lowest=True)
        cur_binned = pd.cut(current, bins=bins, include_lowest=True)

        ref_counts = ref_binned.value_counts(normalize=True).sort_index()
        cur_counts = cur_binned.value_counts(normalize=True).sort_index()

        # Align
        all_bins = ref_counts.index.union(cur_counts.index)
        ref_pct = ref_counts.reindex(all_bins, fill_value=0.001)  # Avoid log(0)
        cur_pct = cur_counts.reindex(all_bins, fill_value=0.001)

        # PSI = sum((current - reference) * ln(current / reference))
        psi = ((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)).sum()

        return float(max(psi, 0))
