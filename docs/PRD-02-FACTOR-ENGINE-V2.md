# PRD-02: Factor Engine v2.0

**Priority**: P0 | **Phase**: 1 | **Status**: Draft

---

## Problem Statement

The current factor model uses 4 static factors with fixed weights, no regime awareness, and basic percentile ranking. Top-tier quant platforms use adaptive multi-factor models with regime detection, factor timing, and dynamic weight allocation. Axion needs a next-generation factor engine to generate consistent alpha.

---

## Goals

1. Expand from 4 to **12+ factors** across 6 categories
2. **Adaptive weights** that shift based on market regime
3. **Factor decay** and **mean reversion** signals
4. **Sector-relative scoring** (not just universe-relative)
5. **Factor momentum** (factors that are working get higher weight)
6. **Sub-factor decomposition** for granular analysis

---

## Non-Goals

- Pure ML-based factor generation (covered in PRD-05)
- Options-specific factors (covered in PRD-06)
- Sentiment-based factors (covered in PRD-07)

---

## Current State vs Target

| Aspect | Current (v1) | Target (v2) |
|--------|-------------|-------------|
| Factor count | 4 | 12+ |
| Categories | Value, Momentum, Quality, Growth | + Volatility, Size, Dividend, Technical |
| Weighting | Static (25/30/25/20) | Adaptive (regime-based) |
| Scoring | Universe percentile | Sector-relative + universe |
| Regime awareness | None | Bull/Bear/Sideways/Crisis |
| Factor timing | None | Momentum of factor returns |
| Update frequency | Daily (batch) | Intraday (triggered) |
| Lookback | Single period | Multi-timeframe |

---

## Detailed Requirements

### R1: Expanded Factor Library

#### R1.1: Value Factors (Category)
| Factor | Formula | Rationale |
|--------|---------|-----------|
| Earnings Yield | EBIT / EV | Better than P/E for capital structure |
| Free Cash Flow Yield | FCF / Market Cap | Cash-based valuation |
| Book-to-Market | Book Value / Market Cap | Classic Fama-French HML |
| EV/EBITDA | Enterprise Value / EBITDA | Debt-inclusive valuation |
| Dividend Yield | Annual Div / Price | Income component |
| Forward P/E | Price / Forward EPS | Forward-looking value |

#### R1.2: Momentum Factors
| Factor | Formula | Rationale |
|--------|---------|-----------|
| 12-1 Month Momentum | Return[t-12 to t-1] | Classic cross-sectional momentum |
| 6-1 Month Momentum | Return[t-6 to t-1] | Medium-term trend |
| 3-Month Momentum | Return[t-3 to t] | Short-term trend |
| 52-Week High Proximity | Price / 52W High | George & Hwang (2004) |
| Earnings Momentum | SUE (Standardized Unexpected Earnings) | Post-earnings drift |
| Revenue Momentum | QoQ Revenue Growth Acceleration | Sales trend |

#### R1.3: Quality Factors
| Factor | Formula | Rationale |
|--------|---------|-----------|
| Return on Equity (ROE) | Net Income / Shareholders' Equity | Profitability |
| Return on Assets (ROA) | Net Income / Total Assets | Asset efficiency |
| Return on Invested Capital (ROIC) | NOPAT / Invested Capital | True returns on capital |
| Gross Profit / Assets | Gross Profit / Total Assets | Novy-Marx quality |
| Accruals | (Net Income - OCF) / Total Assets | Earnings quality |
| Debt/Equity | Total Debt / Equity | Leverage risk |
| Interest Coverage | EBIT / Interest Expense | Debt service ability |

#### R1.4: Growth Factors
| Factor | Formula | Rationale |
|--------|---------|-----------|
| Revenue Growth (YoY) | (Rev_t - Rev_t-4) / Rev_t-4 | Top-line growth |
| EPS Growth (YoY) | (EPS_t - EPS_t-4) / EPS_t-4 | Bottom-line growth |
| FCF Growth | (FCF_t - FCF_t-4) / FCF_t-4 | Cash flow growth |
| Revenue Growth Acceleration | Growth_t - Growth_t-1 | Improving trajectory |
| R&D Intensity | R&D / Revenue | Innovation investment |
| Asset Growth | (Assets_t - Assets_t-1) / Assets_t-1 | Expansion rate |

#### R1.5: Volatility Factors (New)
| Factor | Formula | Rationale |
|--------|---------|-----------|
| Realized Volatility (60d) | StdDev of daily returns, 60-day | Low-vol anomaly |
| Idiosyncratic Volatility | Residual vol after market beta | Stock-specific risk |
| Beta | Covariance(stock, market) / Var(market) | Systematic risk |
| Downside Beta | Beta using only negative market days | Tail risk |
| Max Drawdown (6m) | Peak-to-trough decline | Loss potential |

#### R1.6: Technical Factors (New)
| Factor | Formula | Rationale |
|--------|---------|-----------|
| RSI (14-day) | Relative Strength Index | Overbought/oversold |
| MACD Signal | MACD line - Signal line | Trend strength |
| Volume Trend | 20d avg volume / 60d avg volume | Volume breakout |
| Price vs 200 SMA | Price / 200-day SMA | Long-term trend |
| Price vs 50 SMA | Price / 50-day SMA | Medium-term trend |
| Bollinger Band %B | (Price - Lower) / (Upper - Lower) | Mean reversion |

### R2: Regime Detection System

#### R2.1: Market Regime Classification
Classify the market into one of 4 regimes using a Hidden Markov Model (HMM):

| Regime | Characteristics | Factor Emphasis |
|--------|----------------|-----------------|
| **Bull** | Rising prices, low VIX, positive breadth | Momentum, Growth |
| **Bear** | Falling prices, high VIX, negative breadth | Quality, Low-Vol, Value |
| **Sideways** | Range-bound, moderate VIX | Value, Dividend, Quality |
| **Crisis** | VIX >35, correlation spike, rapid decline | Minimum-Variance, Cash |

**Regime Inputs**:
- S&P 500 200-day trend direction
- VIX level and 20-day change
- Advance/Decline ratio (10-day MA)
- Yield curve slope (10Y - 2Y)
- Credit spreads (HY - IG)
- Market breadth (% above 200 SMA)

#### R2.2: Adaptive Weight System
```python
REGIME_WEIGHTS = {
    'bull': {
        'value': 0.10, 'momentum': 0.35, 'quality': 0.15,
        'growth': 0.25, 'volatility': 0.05, 'technical': 0.10
    },
    'bear': {
        'value': 0.25, 'momentum': 0.05, 'quality': 0.35,
        'growth': 0.05, 'volatility': 0.25, 'technical': 0.05
    },
    'sideways': {
        'value': 0.25, 'momentum': 0.15, 'quality': 0.25,
        'growth': 0.10, 'volatility': 0.15, 'technical': 0.10
    },
    'crisis': {
        'value': 0.05, 'momentum': 0.00, 'quality': 0.40,
        'growth': 0.00, 'volatility': 0.50, 'technical': 0.05
    }
}
```

#### R2.3: Factor Momentum Overlay
- Track trailing 3-month returns of each factor's long-short portfolio
- Tilt weights toward factors with positive recent performance
- Constraint: No single factor >50% or <0% weight
- Smoothing: Exponentially weighted moving average (half-life: 20 days)

### R3: Sector-Relative Scoring

#### R3.1: Dual Scoring System
Each stock receives two scores:
1. **Universe Score**: Percentile rank vs all 8,000+ stocks
2. **Sector Score**: Percentile rank vs same GICS sector peers

**Composite**:
```python
final_score = 0.60 * universe_score + 0.40 * sector_score
```

Sector-relative scoring prevents value traps (banks always look "cheap") and identifies true outperformers within each sector context.

#### R3.2: Sector Mapping
- GICS Level 1: 11 sectors
- GICS Level 2: 25 industry groups
- GICS Level 3: 74 industries
- GICS Level 4: 163 sub-industries

Score at Level 2 (industry group) for meaningful peer comparisons with adequate sample sizes.

### R4: Multi-Timeframe Analysis

#### R4.1: Timeframe Blending
Each factor calculated across multiple lookback periods:

| Timeframe | Weight | Purpose |
|-----------|--------|---------|
| Short (1-3 months) | 25% | Recent momentum/mean-reversion |
| Medium (3-12 months) | 50% | Core factor signal |
| Long (1-3 years) | 25% | Structural quality/value |

#### R4.2: Signal Decay
- Momentum signals decay with half-life of 63 trading days
- Value signals have minimal decay (slow mean reversion)
- Quality signals recalculated quarterly (earnings driven)
- Technical signals use exponential weighting (recent data weighted higher)

### R5: Factor Analytics Dashboard

#### R5.1: Factor Exposure Report
For any portfolio, show:
- Factor tilts vs benchmark (radar chart)
- Active factor bets (bar chart)
- Factor contribution to expected return
- Factor risk decomposition

#### R5.2: Factor Performance Monitor
- Trailing factor returns (1M, 3M, 6M, 1Y)
- Factor correlations matrix (rolling 60-day)
- Factor crowding indicators
- Factor drawdown history

#### R5.3: Stock-Level Factor Profile
```
AAPL Factor Profile
═══════════════════════════════════════
Value:      ████████░░  0.73  (Sector: 0.82)
Momentum:   █████████░  0.91  (Sector: 0.88)
Quality:    ██████████  0.97  (Sector: 0.95)
Growth:     ███████░░░  0.68  (Sector: 0.74)
Volatility: ██████░░░░  0.55  (Sector: 0.61)
Technical:  ████████░░  0.79  (Sector: 0.77)
─────────────────────────────────────
Composite:  █████████░  0.84  (Sector: 0.83)
Regime:     BULL → Momentum/Growth tilt active
```

---

## Technical Design

### Factor Computation Pipeline
```python
class FactorEngineV2:
    def __init__(self, data_service: DataService):
        self.data = data_service
        self.regime_model = RegimeDetector()
        self.factor_registry = FactorRegistry()

    async def compute_all_scores(self, date: date) -> pd.DataFrame:
        """Compute factor scores for entire universe."""
        # 1. Detect current regime
        regime = self.regime_model.classify(date)

        # 2. Get regime-adaptive weights
        weights = self.get_adaptive_weights(regime)

        # 3. Compute each factor category
        scores = pd.DataFrame()
        for category in self.factor_registry.categories:
            category_scores = await category.compute(date)
            scores[category.name] = category_scores

        # 4. Sector-relative adjustment
        scores = self.apply_sector_relative(scores)

        # 5. Composite score with adaptive weights
        scores['composite'] = sum(
            weights[cat] * scores[cat]
            for cat in weights
        )

        return scores
```

### Regime Detection Model
```python
class RegimeDetector:
    def classify(self, date: date) -> str:
        features = {
            'sp500_trend': self._sp500_above_200sma(date),
            'vix_level': self._get_vix(date),
            'vix_change': self._vix_20d_change(date),
            'advance_decline': self._advance_decline_10d(date),
            'yield_curve': self._yield_curve_slope(date),
            'breadth': self._pct_above_200sma(date),
        }

        # Rule-based classification (later: HMM)
        if features['vix_level'] > 35:
            return 'crisis'
        elif (features['sp500_trend'] and
              features['advance_decline'] > 1.0):
            return 'bull'
        elif (not features['sp500_trend'] and
              features['advance_decline'] < 0.8):
            return 'bear'
        else:
            return 'sideways'
```

---

## Migration Path from v1

### Phase A: Add New Factors (Non-Breaking)
1. Add volatility and technical factor categories to `factor_model.py`
2. Extend `FactorScores` dataclass with new fields
3. Keep existing composite calculation as default

### Phase B: Regime Detection
1. Implement `RegimeDetector` class
2. Add economic data fetching (VIX, yield curve)
3. Log regime classifications without changing weights

### Phase C: Adaptive Weights
1. Feature flag to toggle adaptive vs static weights
2. A/B test adaptive weights in backtest engine
3. Gradual rollout based on backtest results

### Phase D: Sector-Relative Scoring
1. Add GICS classification to instrument table
2. Implement sector-relative percentile ranking
3. Blend universe + sector scores

---

## Success Metrics

| Metric | v1 Baseline | v2 Target |
|--------|------------|-----------|
| Backtest Sharpe (5Y) | ~0.8 | >1.5 |
| Factor count | 4 | 12+ |
| Regime accuracy | N/A | >70% |
| Factor update latency | 24h | <5 min |
| Sector coverage | None | 100% GICS |

---

## Dependencies

- PRD-01 (Data Infrastructure) for expanded data sources
- GICS classification data
- VIX and yield curve data from FRED
- Sufficient historical data for regime model training

---

*Owner: Quant Engineering Lead*
*Last Updated: January 2026*
