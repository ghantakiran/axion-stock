# PRD-88: Quantitative Research Tools

## Overview
Quantitative research framework with multi-factor scoring engine, regime-aware signal generation, custom factor builder, research report generation, backtesting, and statistical analysis tools.

## Components

### 1. Factor Engine V2 (`src/factor_engine_v2.py`)
- **FactorEngineV2** — 12+ factor multi-factor scoring with regime-aware weights
- 6 categories: Value, Momentum, Quality, Growth, Volatility, Technical
- Sector-relative scoring, adaptive weight adjustment
- V1/V2 backward compatibility switching

### 2. Factor Calculators (`src/factors/`)
- **ValueFactors** — PE, PB, EV/EBITDA, dividend yield
- **MomentumFactors** — 6m/12m returns, factor momentum
- **QualityFactors** — ROE, ROA, ROIC, accruals, debt ratios
- **GrowthFactors** — Revenue, EPS, FCF growth
- **VolatilityFactors** — Realized vol, idiosyncratic vol, beta, drawdown
- **TechnicalFactors** — RSI, MACD, volume, moving averages
- **FactorRegistry** — Plugin-based factor management
- **CustomFactorBuilder** — User-defined factor construction

### 3. Regime Detection (`src/regime/`)
- **RegimeDetector** — VIX-based, SMA-based, breadth-based classification (BULL/BEAR/SIDEWAYS/CRISIS)
- **HMM** — Hidden Markov Model regime detection
- **Clustering** — K-means clustering for regime identification
- **Ensemble** — Multi-model ensemble classifier
- **RegimeSignalGenerator** — Transition, persistence, alignment, divergence signals
- **AdaptiveWeights** — Regime-dependent factor weight adjustment
- **RegimeTransitionDetector** — Transition probability tracking

### 4. Signal Generation
- **SignalBot** (`src/bots/signal.py`) — Rule-based trading signals
- **InsiderSignalGenerator** (`src/insider/signals.py`) — Insider trading signals
- **CrossAssetSignalGenerator** (`src/crossasset/signals.py`) — Cross-asset signals
- **EventSignals** (`src/events/signals.py`) — Event-driven signals
- **VolRegimeSignals** (`src/volatility/vol_regime_signals.py`) — Volatility regime signals

### 5. Research Module (`src/research/`)
- **ResearchEngine** — Full report generation orchestrator
- **FinancialAnalyzer** — Margin analysis, profitability trends, quality metrics
- **ValuationEngine** — DCF valuation, comparable company analysis
- **CompetitiveAnalyzer** — SWOT analysis, Porter's Five Forces
- **RiskAnalyzer** — Risk assessment and ESG evaluation
- **ThesisGenerator** — Investment thesis generation with bull/bear cases
- **ReportGenerator** — HTML/Markdown export

### 6. Backtesting
- **run_backtest()** (`src/backtest.py`) — Monthly rebalance with no look-ahead bias
- Metrics: CAGR, Sharpe ratio, max drawdown, win rate
- **OptionsBacktester** (`src/options/backtest.py`) — Options strategy backtesting
- **Walk-Forward Optimizer** (`src/ml/training/walk_forward.py`)

### 7. Attribution & Analytics
- **FactorAttribution** (`src/attribution/`) — Factor exposure and return decomposition
- **PortfolioAnalytics** (`src/optimizer/analytics.py`) — Risk contribution, portfolio X-ray
- **WhatIfAnalyzer** — Scenario analysis

## Database Tables
- Factor engine v2 (migration 004), backtesting (009/011/017)
- Cross-asset signals (042), event signals (046), regime signals (047/063)
- Custom factor builder (080)
- `research_reports` — Generated research report storage (migration 088)
- `alpha_signal_log` — Signal generation audit trail (migration 088)

## Dashboards
- `app/pages/research.py` — Research dashboard with financial analysis, valuation, competitive, risk, thesis
- `app/pages/factor_builder.py` — Custom factor construction UI
- `app/pages/backtesting.py` — Backtest runner with trade analysis

## Test Coverage
92 tests across 3 test files:
- `tests/test_research.py` — 22 tests (FinancialAnalyzer, ValuationEngine, CompetitiveAnalyzer, RiskAnalyzer, ThesisGenerator, ReportGenerator, ResearchEngine)
- `tests/test_regime_signals.py` — 39 tests (transition, persistence, alignment, divergence signals, generator)
- `tests/test_factor_engine_v2.py` — 31 tests (regime detection, adaptive weights, factor scoring, backward compatibility, edge cases)
