# PRD-37: Correlation Matrix & Diversification Analysis

**Priority**: P1 | **Phase**: 25 | **Status**: Draft

---

## Problem Statement

Understanding correlations between assets is fundamental to portfolio construction and risk management. During market stress, correlations tend to spike — the very time diversification is needed most. A correlation analysis module helps traders identify truly diversifying assets, detect correlation regime shifts, find pairs for relative value trades, and score overall portfolio diversification.

---

## Goals

1. **Correlation Matrices** — Compute Pearson, Spearman, and Kendall correlation matrices across asset universes
2. **Rolling Correlations** — Track how correlations evolve over configurable time windows
3. **Pair Identification** — Find highest/lowest correlated pairs for pair trading or diversification
4. **Correlation Regimes** — Detect regime shifts (normal vs. crisis) where correlations change structurally
5. **Diversification Scoring** — Score portfolio diversification quality and identify concentration risks
6. **Cross-Asset Analysis** — Correlations across stocks, sectors, indices, and asset classes

---

## Detailed Requirements

### R1: Correlation Matrix Computation

#### R1.1: Methods
| Method | Use Case |
|--------|----------|
| **Pearson** | Linear relationships (default) |
| **Spearman** | Monotonic/rank relationships |
| **Kendall** | Concordance-based, robust to outliers |

#### R1.2: Features
- N×N matrix for any set of assets
- Heatmap-ready output format
- Eigenvalue decomposition for risk analysis
- Statistical significance (p-values)

### R2: Rolling Correlations

#### R2.1: Configuration
- Configurable window sizes (20, 60, 120, 252 days)
- Expanding window option
- Exponentially weighted (half-life parameter)

#### R2.2: Output
- Time series of pairwise correlations
- Correlation change detection (significant moves)
- Historical percentile ranking

### R3: Pair Identification

#### R3.1: Discovery
- Top N most correlated pairs
- Top N least correlated / negatively correlated pairs
- Correlation stability score (low variance over time)

### R4: Correlation Regimes

#### R4.1: Detection
- Average correlation level classification (low/normal/high/crisis)
- Regime change detection using rolling statistics
- Dispersion index (standard deviation of pairwise correlations)

### R5: Diversification Score

#### R5.1: Metrics
- Diversification ratio = (weighted avg vol) / (portfolio vol)
- Effective number of bets (ENB)
- Maximum correlation within portfolio
- Average pairwise correlation

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Matrix computation (100 assets) | <500ms |
| Regime detection accuracy | >70% |
| Diversification score utility | Correlates with future drawdown reduction |

---

## Dependencies

- Data infrastructure (PRD-01)
- Risk management (PRD-04, PRD-17)
- Portfolio optimizer (PRD-08)

---

*Owner: Product Engineering Lead*
*Last Updated: January 2026*
