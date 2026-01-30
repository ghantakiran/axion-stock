"""Tests for the ML prediction engine."""

import numpy as np
import pandas as pd
import pytest
from datetime import date, timedelta

from src.ml.config import (
    MLConfig, RankingModelConfig, RegimeModelConfig,
    EarningsModelConfig, FactorTimingConfig, WalkForwardConfig,
    HybridScoringConfig,
)
from src.ml.features import FeatureEngineer
from src.ml.models.ranking import StockRankingModel
from src.ml.models.regime import RegimeClassifier, RegimePrediction
from src.ml.models.earnings import EarningsPredictionModel, EarningsPrediction
from src.ml.models.factor_timing import FactorTimingModel
from src.ml.training.walk_forward import WalkForwardValidator, Split
from src.ml.serving.hybrid_scorer import HybridScorer
from src.ml.monitoring.tracker import ModelPerformanceTracker
from src.ml.monitoring.degradation import DegradationDetector
from src.ml.explainability.explainer import ModelExplainer, Explanation


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_stock_data():
    """Generate sample stock features."""
    np.random.seed(42)
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "JNJ", "XOM", "PG",
               "BAC", "WMT", "DIS", "NFLX", "NVDA", "AMD", "TSLA",
               "META", "CRM", "INTC", "CSCO", "PFE"]

    rows = []
    for sym in symbols:
        rows.append({
            "symbol": sym,
            "value_score": np.random.uniform(0, 1),
            "momentum_score": np.random.uniform(0, 1),
            "quality_score": np.random.uniform(0, 1),
            "growth_score": np.random.uniform(0, 1),
            "volatility_score": np.random.uniform(0, 1),
            "technical_score": np.random.uniform(0, 1),
            "pe_ratio": np.random.uniform(10, 50),
            "pb_ratio": np.random.uniform(1, 10),
            "roe": np.random.uniform(0.05, 0.40),
            "beta": np.random.uniform(0.5, 2.0),
            "sector": np.random.choice(["Technology", "Financials", "Healthcare", "Energy"]),
        })

    df = pd.DataFrame(rows).set_index("symbol")
    # Ensure numeric columns are properly typed
    numeric_cols = [c for c in df.columns if c != "sector"]
    df[numeric_cols] = df[numeric_cols].astype(float)
    return df


@pytest.fixture
def sample_features_and_targets():
    """Generate sample features and targets for model training."""
    np.random.seed(42)
    n_samples = 200
    n_features = 15

    X = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=[f"feature_{i}" for i in range(n_features)],
    )
    # Target: quintile 1-5
    y = pd.Series(np.random.randint(1, 6, n_samples))

    return X, y


@pytest.fixture
def sample_regime_data():
    """Generate sample regime classification data."""
    np.random.seed(42)
    n_samples = 200

    X = pd.DataFrame({
        "sp500_return_20d": np.random.normal(0.01, 0.05, n_samples),
        "sp500_volatility_20d": np.random.uniform(0.1, 0.4, n_samples),
        "vix_level": np.random.uniform(12, 35, n_samples),
        "yield_curve_10y_2y": np.random.normal(0.5, 0.8, n_samples),
        "credit_spread": np.random.uniform(1, 5, n_samples),
    })

    # Labels based on simple rules
    conditions = [
        X["sp500_return_20d"] > 0.02,
        X["sp500_return_20d"] < -0.03,
        X["vix_level"] > 30,
    ]
    choices = ["bull", "bear", "crisis"]
    y = pd.Series(np.select(conditions, choices, default="sideways"))

    return X, y


@pytest.fixture
def sample_earnings_data():
    """Generate sample earnings prediction data."""
    np.random.seed(42)
    n_samples = 200

    X = pd.DataFrame({
        "beat_rate_4q": np.random.uniform(0, 1, n_samples),
        "avg_surprise_4q": np.random.normal(0.02, 0.05, n_samples),
        "estimate_revision_30d": np.random.normal(0, 0.03, n_samples),
        "pre_earnings_momentum": np.random.normal(0.01, 0.04, n_samples),
        "sector_beat_rate": np.random.uniform(0.4, 0.7, n_samples),
    })

    # Binary target: 1=beat, 0=miss (slightly biased toward beat)
    y = pd.Series((np.random.random(n_samples) < 0.55).astype(int))

    return X, y


# =============================================================================
# Test MLConfig
# =============================================================================

class TestMLConfig:
    def test_default_config(self):
        config = MLConfig()
        assert config.ranking.n_estimators == 500
        assert config.ranking.num_quintiles == 5
        assert config.hybrid_scoring.ml_weight == 0.30

    def test_custom_config(self):
        config = MLConfig(
            ranking=RankingModelConfig(n_estimators=300, max_depth=4)
        )
        assert config.ranking.n_estimators == 300
        assert config.ranking.max_depth == 4


# =============================================================================
# Test FeatureEngineer
# =============================================================================

class TestFeatureEngineer:
    def test_create_features(self, sample_stock_data):
        engineer = FeatureEngineer()
        features = engineer.create_features(raw_data=sample_stock_data)

        assert not features.empty
        assert len(features) == len(sample_stock_data)
        assert len(features.columns) > 0

    def test_rank_features(self, sample_stock_data):
        engineer = FeatureEngineer()
        features = engineer.create_features(raw_data=sample_stock_data)

        # Ranked features should be between 0 and 1
        rank_cols = [c for c in features.columns if c.endswith("_rank")]
        if rank_cols:
            for col in rank_cols:
                assert features[col].min() >= 0
                assert features[col].max() <= 1

    def test_interaction_features(self, sample_stock_data):
        engineer = FeatureEngineer()
        features = engineer.create_features(raw_data=sample_stock_data)

        interaction_cols = [c for c in features.columns if "_x_" in c]
        assert len(interaction_cols) > 0

    def test_feature_names_stored(self, sample_stock_data):
        engineer = FeatureEngineer()
        features = engineer.create_features(raw_data=sample_stock_data)

        assert len(engineer.feature_names) == len(features.columns)


# =============================================================================
# Test StockRankingModel
# =============================================================================

class TestStockRankingModel:
    def test_train_and_predict(self, sample_features_and_targets):
        X, y = sample_features_and_targets

        config = RankingModelConfig(n_estimators=50, n_ensemble=2)
        model = StockRankingModel(config=config)

        metrics = model.train(X[:150], y[:150], X_val=X[150:], y_val=y[150:])

        assert "accuracy" in metrics
        assert "information_coefficient" in metrics
        assert model.is_fitted

        predictions = model.predict(X[150:])
        assert "score" in predictions.columns
        assert "predicted_quintile" in predictions.columns
        assert len(predictions) == 50

    def test_predict_rank(self, sample_features_and_targets):
        X, y = sample_features_and_targets

        config = RankingModelConfig(n_estimators=50, n_ensemble=1)
        model = StockRankingModel(config=config)
        model.train(X[:150], y[:150])

        scores = model.predict_rank(X[150:])
        assert len(scores) == 50
        assert scores.min() >= 0
        assert scores.max() <= 1

    def test_feature_importance(self, sample_features_and_targets):
        X, y = sample_features_and_targets

        config = RankingModelConfig(n_estimators=50, n_ensemble=2)
        model = StockRankingModel(config=config)
        model.train(X, y)

        importance = model.get_feature_importance()
        assert len(importance) == X.shape[1]
        assert importance.sum() > 0

    def test_ensemble_averaging(self, sample_features_and_targets):
        X, y = sample_features_and_targets

        config = RankingModelConfig(n_estimators=50, n_ensemble=3)
        model = StockRankingModel(config=config)
        model.train(X, y)

        assert len(model.models) == 3


# =============================================================================
# Test RegimeClassifier
# =============================================================================

class TestRegimeClassifier:
    def test_train_and_predict(self, sample_regime_data):
        X, y = sample_regime_data

        model = RegimeClassifier()
        metrics = model.train(X, y)

        assert "accuracy" in metrics
        assert metrics["accuracy"] > 0

        predictions = model.predict(X[:10])
        assert "regime" in predictions.columns
        assert "confidence" in predictions.columns

    def test_predict_regime(self, sample_regime_data):
        X, y = sample_regime_data

        model = RegimeClassifier()
        model.train(X, y)

        result = model.predict_regime(X.tail(5))

        assert isinstance(result, RegimePrediction)
        assert result.regime in ["bull", "bear", "sideways", "crisis"]
        assert 0 <= result.confidence <= 1


# =============================================================================
# Test EarningsPredictionModel
# =============================================================================

class TestEarningsPredictionModel:
    def test_train_and_predict(self, sample_earnings_data):
        X, y = sample_earnings_data

        model = EarningsPredictionModel()
        metrics = model.train(X[:150], y[:150], X_val=X[150:], y_val=y[150:])

        assert "accuracy" in metrics
        assert "auc_roc" in metrics

        predictions = model.predict(X[150:])
        assert "beat_probability" in predictions.columns
        assert "predicted_beat" in predictions.columns

    def test_predict_single(self, sample_earnings_data):
        X, y = sample_earnings_data

        model = EarningsPredictionModel()
        model.train(X, y)

        result = model.predict_single("AAPL", X.iloc[0])

        assert isinstance(result, EarningsPrediction)
        assert result.symbol == "AAPL"
        assert 0 <= result.beat_probability <= 1


# =============================================================================
# Test FactorTimingModel
# =============================================================================

class TestFactorTimingModel:
    def test_train_and_predict(self):
        np.random.seed(42)
        n = 100

        X = pd.DataFrame({
            "vix": np.random.uniform(12, 30, n),
            "yield_curve": np.random.normal(0.5, 0.8, n),
            "sp500_return": np.random.normal(0.01, 0.05, n),
        })
        y = pd.DataFrame({
            "value": np.random.normal(0, 0.02, n),
            "momentum": np.random.normal(0.005, 0.03, n),
            "quality": np.random.normal(0.002, 0.01, n),
            "growth": np.random.normal(0, 0.025, n),
        })

        model = FactorTimingModel()
        metrics = model.train(X, y)

        assert model.is_fitted
        assert any("direction_accuracy" in k for k in metrics)

        predictions = model.predict(X.tail(5))
        assert not predictions.empty

    def test_get_factor_weights(self):
        np.random.seed(42)
        n = 100

        X = pd.DataFrame({
            "vix": np.random.uniform(12, 30, n),
            "yield_curve": np.random.normal(0.5, 0.8, n),
        })
        y = pd.DataFrame({
            "value": np.random.normal(0, 0.02, n),
            "momentum": np.random.normal(0.005, 0.03, n),
        })

        config = FactorTimingConfig(factors=["value", "momentum"])
        model = FactorTimingModel(config=config)
        model.train(X, y)

        weights = model.get_factor_weights(X.tail(1))

        assert "value" in weights
        assert "momentum" in weights
        assert abs(sum(weights.values()) - 1.0) < 0.01


# =============================================================================
# Test WalkForwardValidator
# =============================================================================

class TestWalkForwardValidator:
    def test_generate_splits(self):
        config = WalkForwardConfig(
            train_start=date(2015, 1, 1),
            initial_train_years=3,
            test_months=1,
            retrain_months=3,
        )
        validator = WalkForwardValidator(config=config)

        splits = validator.generate_splits(end_date=date(2020, 1, 1))

        assert len(splits) > 0
        for split in splits:
            assert split.train_start < split.train_end
            assert split.train_end <= split.test_start
            assert split.test_start < split.test_end

    def test_no_future_leakage(self):
        config = WalkForwardConfig(
            train_start=date(2015, 1, 1),
            initial_train_years=3,
            purge_days=5,
        )
        validator = WalkForwardValidator(config=config)
        splits = validator.generate_splits(end_date=date(2020, 1, 1))

        for split in splits:
            gap = (split.test_start - split.train_end).days
            assert gap >= config.purge_days

    def test_expanding_window(self):
        config = WalkForwardConfig(
            train_start=date(2015, 1, 1),
            initial_train_years=3,
            retrain_months=6,
        )
        validator = WalkForwardValidator(config=config)
        splits = validator.generate_splits(end_date=date(2022, 1, 1))

        # All splits start from the same date (expanding window)
        for split in splits:
            assert split.train_start == config.train_start

        # Later splits have more training data
        if len(splits) >= 2:
            assert splits[-1].train_days > splits[0].train_days


# =============================================================================
# Test HybridScorer
# =============================================================================

class TestHybridScorer:
    def test_hybrid_scoring(self):
        scorer = HybridScorer()

        rule_scores = pd.Series({"AAPL": 0.8, "MSFT": 0.6, "JPM": 0.4})
        ml_scores = pd.Series({"AAPL": 0.7, "MSFT": 0.9, "JPM": 0.3})

        hybrid = scorer.compute_hybrid_scores(rule_scores, ml_scores)

        assert len(hybrid) == 3
        assert hybrid.min() >= 0
        assert hybrid.max() <= 1

    def test_fallback_to_rules(self):
        scorer = HybridScorer()

        rule_scores = pd.Series({"AAPL": 0.8, "MSFT": 0.6})

        # No ML scores provided
        hybrid = scorer.compute_hybrid_scores(rule_scores, None)
        pd.testing.assert_series_equal(hybrid, rule_scores)

    def test_ml_deactivation(self):
        scorer = HybridScorer()

        # Deactivate ML due to poor performance
        scorer.update_ml_performance(ic=0.01)  # Below threshold
        assert not scorer.is_ml_active
        assert scorer.current_ml_weight == 0.0

    def test_ml_reactivation(self):
        scorer = HybridScorer()

        scorer.update_ml_performance(ic=0.01)
        assert not scorer.is_ml_active

        scorer.update_ml_performance(ic=0.05)
        assert scorer.is_ml_active

    def test_single_score(self):
        scorer = HybridScorer(HybridScoringConfig(ml_weight=0.3))

        hybrid = scorer.compute_hybrid_score_single(
            rule_score=0.8,
            ml_score=0.6,
        )

        expected = 0.7 * 0.8 + 0.3 * 0.6
        assert abs(hybrid - expected) < 0.01


# =============================================================================
# Test ModelPerformanceTracker
# =============================================================================

class TestModelPerformanceTracker:
    def test_record_and_calculate_ic(self):
        tracker = ModelPerformanceTracker()

        # Record predictions
        predictions = pd.Series({"AAPL": 0.8, "MSFT": 0.6, "JPM": 0.4, "JNJ": 0.7,
                                  "XOM": 0.3, "PG": 0.5, "BAC": 0.9, "WMT": 0.2,
                                  "DIS": 0.6, "NFLX": 0.8})
        tracker.record_prediction("ranking", predictions, date(2026, 1, 1))

        # Record actuals
        actuals = pd.Series({"AAPL": 5, "MSFT": 3, "JPM": 2, "JNJ": 4,
                              "XOM": 1, "PG": 3, "BAC": 5, "WMT": 1,
                              "DIS": 3, "NFLX": 4})
        tracker.record_actuals("ranking", actuals, date(2026, 1, 1))

        ic = tracker.calculate_ic("ranking")
        assert -1 <= ic <= 1

    def test_health_status(self):
        tracker = ModelPerformanceTracker()
        tracker.set_model_trained_date("ranking", "2026-01-01T00:00:00")

        status = tracker.get_health_status("ranking")
        assert status.model_name == "ranking"
        assert status.status in ["healthy", "warning", "degraded", "stale"]


# =============================================================================
# Test DegradationDetector
# =============================================================================

class TestDegradationDetector:
    def test_feature_drift_no_drift(self):
        np.random.seed(42)
        detector = DegradationDetector()

        # Same distribution
        ref = pd.DataFrame(np.random.randn(1000, 5), columns=[f"f{i}" for i in range(5)])
        cur = pd.DataFrame(np.random.randn(100, 5), columns=[f"f{i}" for i in range(5)])

        report = detector.check_feature_drift(ref, cur)
        assert report.overall_drift in ["none", "minor"]

    def test_feature_drift_with_drift(self):
        np.random.seed(42)
        detector = DegradationDetector()

        ref = pd.DataFrame(np.random.randn(1000, 5), columns=[f"f{i}" for i in range(5)])
        # Shifted distribution
        cur = pd.DataFrame(np.random.randn(100, 5) + 3, columns=[f"f{i}" for i in range(5)])

        report = detector.check_feature_drift(ref, cur)
        assert report.overall_drift in ["significant", "critical"]
        assert len(report.drifted_features) > 0

    def test_ic_trend(self):
        detector = DegradationDetector()

        # Declining IC
        monthly_ics = pd.Series([0.06, 0.05, 0.04, 0.03, 0.015, 0.01])
        result = detector.check_ic_trend(monthly_ics)

        assert result["trend"] == "declining"


# =============================================================================
# Test ModelExplainer
# =============================================================================

class TestModelExplainer:
    def test_explain_prediction(self, sample_features_and_targets):
        X, y = sample_features_and_targets

        config = RankingModelConfig(n_estimators=50, n_ensemble=1)
        model = StockRankingModel(config=config)
        model.train(X, y)

        explainer = ModelExplainer(model)
        explanation = explainer.explain("AAPL", X.iloc[0])

        assert isinstance(explanation, Explanation)
        assert explanation.symbol == "AAPL"
        assert len(explanation.feature_contributions) > 0

    def test_explanation_text(self, sample_features_and_targets):
        X, y = sample_features_and_targets

        config = RankingModelConfig(n_estimators=50, n_ensemble=1)
        model = StockRankingModel(config=config)
        model.train(X, y)

        explainer = ModelExplainer(model)
        explanation = explainer.explain("AAPL", X.iloc[0])

        text = explanation.to_text()
        assert "AAPL" in text
        assert "Quintile" in text


# =============================================================================
# Integration Test
# =============================================================================

class TestMLIntegration:
    def test_end_to_end_workflow(self, sample_features_and_targets):
        """Test the full ML workflow."""
        X, y = sample_features_and_targets

        # 1. Train model
        config = RankingModelConfig(n_estimators=50, n_ensemble=2)
        model = StockRankingModel(config=config)

        metrics = model.train(
            X[:150], y[:150],
            X_val=X[150:], y_val=y[150:],
        )

        assert model.is_fitted
        assert metrics["accuracy"] > 0

        # 2. Make predictions
        predictions = model.predict(X[150:])
        assert len(predictions) == 50

        # 3. Hybrid scoring
        rule_scores = pd.Series(np.random.uniform(0, 1, 50), index=X[150:].index)
        ml_scores = predictions["score"]

        scorer = HybridScorer()
        hybrid = scorer.compute_hybrid_scores(rule_scores, ml_scores)
        assert len(hybrid) == 50

        # 4. Explain predictions
        explainer = ModelExplainer(model)
        explanation = explainer.explain("stock_0", X.iloc[150])
        assert explanation.symbol == "stock_0"

        # 5. Monitor performance
        tracker = ModelPerformanceTracker()
        tracker.record_prediction("ranking", ml_scores, date.today())
        tracker.record_actuals("ranking", y[150:], date.today())

        ic = tracker.calculate_ic("ranking")
        assert -1 <= ic <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
