# PRD-05: Machine Learning Prediction Engine

**Priority**: P1 | **Phase**: 3 | **Status**: Draft

---

## Problem Statement

Axion's factor model uses static, hand-coded rules. Academic research and top quant funds demonstrate that machine learning models can capture non-linear factor interactions, regime-dependent alpha, and complex cross-sectional patterns that linear models miss. The next alpha frontier for Axion is ML-enhanced prediction.

---

## Goals

1. **ML factor combination** that outperforms static weighted composite
2. **Return prediction** (next 1-month cross-sectional rank)
3. **Regime classification** with >70% accuracy
4. **Feature importance** explanations for every prediction
5. **Walk-forward validation** to prevent overfitting
6. **Production ML pipeline** with monitoring and retraining

---

## Non-Goals

- Deep reinforcement learning for order execution
- Tick-level prediction (HFT)
- Unstructured data ML (NLP for news handled in PRD-07)

---

## Detailed Requirements

### R1: ML Model Suite

#### R1.1: Cross-Sectional Stock Ranking Model
**Objective**: Predict next-month relative performance ranking of each stock.

**Model**: LightGBM (gradient boosted trees)
**Why LightGBM**:
- Handles tabular data better than neural networks
- Native handling of missing values
- Fast training (minutes, not hours)
- Feature importance built-in
- Battle-tested in quant finance (Kaggle, production)

**Target Variable**: Next 21-trading-day return quintile (1-5)
```python
# Label: Forward 21-day return, ranked into quintiles
y = forward_returns.rank(pct=True).apply(
    lambda x: int(x * 5) + 1  # 1 (worst) to 5 (best)
)
```

**Feature Set** (80+ features):
```python
features = {
    # Factor Scores (from PRD-02)
    'value_score', 'momentum_score', 'quality_score',
    'growth_score', 'volatility_score', 'technical_score',

    # Sub-factors (raw values)
    'pe_ratio', 'pb_ratio', 'ev_ebitda', 'fcf_yield',
    'roe', 'roa', 'roic', 'debt_equity',
    'revenue_growth', 'eps_growth', 'fcf_growth',
    'return_6m', 'return_12m', 'return_3m',
    'rsi_14', 'macd_signal', 'price_to_sma200',
    'realized_vol_60d', 'beta', 'idio_vol',

    # Cross-sectional features
    'sector_rank', 'industry_rank',
    'sector_momentum', 'sector_dispersion',

    # Macro features
    'vix', 'yield_curve_slope', 'credit_spread',
    'sp500_return_20d', 'market_breadth',

    # Interaction features
    'value_x_momentum', 'quality_x_growth',
    'momentum_x_volatility',

    # Lagged features (avoid look-ahead)
    'composite_score_lag1m', 'return_lag1m', 'volume_change_20d',

    # Time features
    'month_of_year', 'quarter', 'days_since_earnings',
}
```

#### R1.2: Regime Classification Model
**Objective**: Classify market into Bull/Bear/Sideways/Crisis.

**Model**: Hidden Markov Model (HMM) + Random Forest ensemble

**Features**:
```python
regime_features = {
    'sp500_return_20d',
    'sp500_return_60d',
    'sp500_volatility_20d',
    'vix_level',
    'vix_term_structure',  # VIX - VIX3M
    'yield_curve_10y_2y',
    'credit_spread_hy_ig',
    'advance_decline_10d',
    'pct_above_200sma',
    'put_call_ratio',
    'new_highs_new_lows',
    'margin_debt_change',
}
```

**Output**: Regime probability vector
```python
# Example output
{
    'bull': 0.65,
    'bear': 0.10,
    'sideways': 0.20,
    'crisis': 0.05,
    'confidence': 0.65
}
```

#### R1.3: Earnings Surprise Prediction Model
**Objective**: Predict probability of earnings beat/miss.

**Model**: XGBoost classifier

**Features**:
- Historical beat/miss pattern (last 8 quarters)
- Analyst estimate revisions (30-day trend)
- Pre-earnings price momentum
- Options-implied move vs historical move
- Sector peer earnings results (if already reported)
- Revenue estimate dispersion
- Short interest changes pre-earnings

**Output**:
```python
{
    'beat_probability': 0.72,
    'expected_surprise_pct': +3.2,
    'predicted_move_pct': +2.1,
    'confidence': 'medium'
}
```

#### R1.4: Factor Timing Model
**Objective**: Predict which factors will outperform next month.

**Model**: Multi-output LightGBM

**Target**: Next-month return of factor long-short portfolios
```python
# For each factor, predict: outperform / neutral / underperform
factor_targets = {
    'value_next_month': return_of_value_quintile5 - return_of_value_quintile1,
    'momentum_next_month': ...,
    'quality_next_month': ...,
    'growth_next_month': ...,
}
```

**Use**: Dynamic factor weight adjustment (overlay on PRD-02 regime weights)

### R2: Training Pipeline

#### R2.1: Walk-Forward Validation
```python
class WalkForwardValidator:
    """Prevent overfitting with expanding window validation."""

    def __init__(self,
                 train_start: date = date(2005, 1, 1),
                 initial_train_years: int = 5,
                 test_months: int = 1,
                 retrain_months: int = 3):
        self.config = {...}

    def generate_splits(self, end_date: date) -> list[Split]:
        """
        Example splits:
        Split 1: Train [2005-2010], Test [2010-Jan]
        Split 2: Train [2005-2010-Apr], Test [2010-Apr]
        ...
        Split N: Train [2005-2025-Dec], Test [2026-Jan]
        """
        splits = []
        train_end = self.config.train_start + timedelta(
            days=365 * self.config.initial_train_years
        )
        while train_end < end_date:
            test_end = train_end + timedelta(days=30 * self.config.test_months)
            splits.append(Split(
                train=(self.config.train_start, train_end),
                test=(train_end, min(test_end, end_date))
            ))
            train_end += timedelta(days=30 * self.config.retrain_months)
        return splits
```

#### R2.2: Hyperparameter Optimization
```python
search_space = {
    'n_estimators': [200, 500, 1000],
    'max_depth': [4, 6, 8],
    'learning_rate': [0.01, 0.05, 0.1],
    'min_child_samples': [20, 50, 100],
    'subsample': [0.7, 0.8, 0.9],
    'colsample_bytree': [0.7, 0.8, 0.9],
    'reg_alpha': [0, 0.1, 1.0],
    'reg_lambda': [0, 0.1, 1.0],
}
# Optuna Bayesian optimization with walk-forward CV
```

#### R2.3: Feature Engineering Pipeline
```python
class FeatureEngineer:
    def create_features(self, date: date) -> pd.DataFrame:
        """All features use only data available before `date`."""
        raw = self._get_raw_features(date)

        # Cross-sectional normalization
        ranked = raw.rank(pct=True)

        # Sector-relative
        sector_ranked = raw.groupby('sector').rank(pct=True)

        # Interactions
        interactions = self._create_interactions(ranked)

        # Lagged features (1m, 3m lookback of factor scores)
        lagged = self._create_lags(ranked, lags=[21, 63])

        # Rolling statistics
        rolling = self._create_rolling_stats(raw)

        return pd.concat([ranked, sector_ranked, interactions,
                          lagged, rolling], axis=1)
```

### R3: Model Monitoring & Governance

#### R3.1: Model Performance Dashboard
```
MODEL PERFORMANCE MONITOR
═══════════════════════════════════════════
Stock Ranking Model (LightGBM)
├── Walk-Forward IC:     0.052 (good: >0.03)
├── Top Quintile Return: +2.1% monthly
├── Bottom Quintile:     -0.8% monthly
├── Long-Short Spread:   +2.9% monthly
├── Turnover:            35% monthly
├── Last Retrained:      2026-01-15
└── Status:              ✅ In production

Regime Model (HMM + RF)
├── Accuracy:            73% (target: >70%)
├── Current Regime:      BULL (65% confidence)
├── Regime Duration:     47 days
├── Last Retrained:      2026-01-01
└── Status:              ✅ In production

Earnings Model (XGBoost)
├── Beat Accuracy:       64% (target: >60%)
├── Miss Accuracy:       58%
├── AUC-ROC:            0.67
├── Last Retrained:      2026-01-10
└── Status:              ✅ In production
```

#### R3.2: Model Degradation Detection
- Track rolling Information Coefficient (IC)
- Alert when IC drops below 0.02 for 3 consecutive months
- Compare live predictions vs random baseline
- Monitor feature distribution drift (PSI > 0.25 triggers alert)
- Automatic fallback to rule-based model if ML degrades

#### R3.3: Explainability
```python
class ModelExplainer:
    def explain_prediction(self, symbol: str, date: date) -> Explanation:
        """SHAP-based explanation for individual predictions."""
        features = self.feature_engineer.create_features(date).loc[symbol]
        shap_values = self.explainer.shap_values(features)

        return Explanation(
            prediction=self.model.predict(features),
            top_positive_factors=[
                ('momentum_12m', +0.15),
                ('roe', +0.08),
                ('earnings_surprise', +0.06),
            ],
            top_negative_factors=[
                ('pe_ratio', -0.04),
                ('realized_vol', -0.03),
            ],
            feature_contributions=dict(zip(
                self.feature_names, shap_values
            ))
        )
```

### R4: Integration with Platform

#### R4.1: Score Blending
```python
class HybridScorer:
    """Blend rule-based and ML scores."""

    def compute_hybrid_score(self, symbol: str, date: date) -> float:
        rule_score = self.factor_engine.get_composite(symbol, date)
        ml_score = self.ml_model.predict_rank(symbol, date)

        # Blend with configurable weight
        # Start with 70% rules / 30% ML, increase ML over time
        blend_weight = self.config.ml_weight  # default: 0.30
        return (1 - blend_weight) * rule_score + blend_weight * ml_score
```

#### R4.2: Claude Integration
Claude can query ML predictions:
```
User: "What does the ML model think about NVDA?"

Claude: The ML ranking model places NVDA in the top quintile (rank score: 0.89).

Key drivers (SHAP analysis):
• Strong momentum (12m return: +180%) → +0.15
• High quality (ROIC: 45%) → +0.08
• Earnings momentum (3 consecutive beats) → +0.06
• Offset by: High valuation (P/E: 65) → -0.04

The regime model classifies the current market as BULL (65% confidence),
which favors momentum-heavy names like NVDA.

Earnings prediction: 72% probability of beat on next report.
```

---

## Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| ML Framework | LightGBM + XGBoost | Best for tabular financial data |
| Explainability | SHAP | Industry standard for feature attribution |
| Hyperparameter Tuning | Optuna | Bayesian optimization, efficient |
| Experiment Tracking | MLflow | Model versioning, metrics logging |
| Feature Store | Feast (or custom) | Feature consistency train/serve |
| Model Serving | FastAPI + Redis | Low-latency predictions |
| Orchestration | Airflow / Prefect | Scheduled retraining pipelines |

---

## Anti-Overfitting Safeguards

1. **Walk-forward only**: No in-sample evaluation ever reported
2. **Feature selection**: Max 80 features, remove collinear (>0.9 corr)
3. **Regularization**: L1 + L2 regularization always enabled
4. **Ensemble**: Bag 5 models with different seeds
5. **Simplicity preference**: Fewer trees > more trees if similar IC
6. **Transaction cost penalty**: Penalize turnover in objective function
7. **Decay test**: Model must outperform 6 months after training
8. **Benchmark**: Must beat equal-weighted factor composite

---

## Success Metrics

| Metric | Rule-Based Baseline | ML Target |
|--------|-------------------|-----------|
| Information Coefficient (monthly) | ~0.03 | >0.05 |
| Top Quintile Monthly Return | ~1.2% | >1.8% |
| Long-Short Spread | ~1.5% | >2.5% |
| Sharpe (L/S portfolio) | ~0.8 | >1.2 |
| Regime Accuracy | N/A | >70% |
| Earnings Beat Prediction | 50% (random) | >62% |

---

## Dependencies

- PRD-01 (Data Infrastructure) for 20+ years of historical data
- PRD-02 (Factor Engine) for feature inputs
- PRD-09 (Backtesting) for walk-forward validation
- MLflow instance for experiment tracking
- GPU access for hyperparameter tuning (optional, CPU sufficient)

---

*Owner: ML Engineering Lead*
*Last Updated: January 2026*
