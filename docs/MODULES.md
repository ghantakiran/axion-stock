# Axion Platform — Module Skills Reference

> **131 modules** | **~390K LOC** | **176 PRDs** | Auto-generated from source code analysis

This document catalogs every module in the Axion platform with its purpose, key classes, public API surface, and notable data models. Intended as a reference for developers, researchers, and onboarding resources.

---

## Table of Contents

1. [Core Data & Infrastructure](#1-core-data--infrastructure)
2. [Trading & Execution](#2-trading--execution)
3. [ML, Factors & Analysis](#3-ml-factors--analysis)
4. [Market Analysis](#4-market-analysis)
5. [Platform & Operations](#5-platform--operations)
6. [Strategy & Signals](#6-strategy--signals)
7. [Enterprise, Tools & Brokers](#7-enterprise-tools--brokers)

---

## 1. Core Data & Infrastructure

### 1.1 db/ — Database Layer
**Purpose:** SQLAlchemy ORM layer with async/sync PostgreSQL + TimescaleDB support. Defines all trading domain models.

| Class | Description |
|-------|-------------|
| `Base` | SQLAlchemy DeclarativeBase for all ORM models |
| `get_async_engine()` | Async engine (pool_size=20, max_overflow=10) |
| `get_sync_engine()` | Sync engine for migrations |
| `AsyncSessionLocal` / `SyncSessionLocal` | Session factories |

**ORM Models:** `Instrument` (tradeable symbols, GICS hierarchy), `PriceBar` (OHLCV hypertable), `Financial` (fundamentals), `FactorScore` (6-category scores), `EconomicIndicator` (FRED data), `MarketRegime` (regime classification), `TradeOrder` (order history), `TradeExecution` (fills)

**Enums:** `AssetType` (STOCK/ETF/INDEX), `MarketRegimeType` (BULL/BEAR/SIDEWAYS/CRISIS), `OrderSideType`, `OrderStatusType`, `OrderTypeEnum`

### 1.2 cache/ — Redis Caching
**Purpose:** Async/sync Redis client with DataFrame serialization, JSON storage, and TTL-based expiration.

| Class | Key Methods |
|-------|-------------|
| `RedisCache` (singleton: `cache`) | `get_dataframe()`, `set_dataframe()`, `get_json()`, `set_json()`, `get_quote()`, `invalidate_pattern()` |

**Cache Keys:** `axion:quote:{ticker}` (30s), `axion:prices:{ticker}:{tf}` (5min), `axion:fundamentals:{ticker}` (4hr), `axion:scores:all` (1hr), `axion:universe:{index}` (24hr)

### 1.3 services/ — Data Access Layer
**Purpose:** Multi-layer data resolution: Redis cache → PostgreSQL → External APIs (Polygon/YFinance/FRED).

| Class | Key Methods |
|-------|-------------|
| `DataService` | `get_universe()`, `get_prices()`, `get_fundamentals()`, `get_quote()`, `get_economic_indicator()`, `get_scores()` |
| `SyncDataService` (singleton) | Sync wrapper for backward compat |

### 1.4 quality/ — Data Validation
**Purpose:** Validates OHLCV and fundamental data integrity with gap detection.

| Class | Key Methods |
|-------|-------------|
| `PriceValidator` | `validate_ohlcv()` — checks positive prices, OHLC consistency, extreme moves, volume anomaly, stale prices |
| `FundamentalValidator` | `validate()` — checks completeness, PE sanity, ticker coverage |
| `GapDetector` | `detect_gaps()` — finds missing trading days vs US business calendar |

### 1.5 api/ — REST API Layer
**Purpose:** FastAPI application with auth, rate limiting, WebSocket, webhooks, and Python SDK.

| Component | Key Classes |
|-----------|-------------|
| **Auth** | `APIKeyManager` (create/validate/revoke/list keys), `RateLimiter` (per-minute + daily limits), `WebhookSigner` (HMAC) |
| **Config** | `APIConfig`, `APITier` (FREE/PRO/ENTERPRISE), rate limit tiers |
| **Models** | 30+ Pydantic models: `QuoteResponse`, `OHLCVResponse`, `FactorScoreResponse`, `CreateOrderRequest`, `BacktestRequest`, etc. |
| **WebSocket** | `WebSocketManager` — connection/subscription management, broadcast, heartbeat |
| **Webhooks** | `WebhookManager` — register, dispatch events, HMAC-signed delivery |
| **SDK** | `AxionClient` — Python SDK with `factors`, `orders`, `portfolio`, `ai`, `backtest` namespaces |
| **Dependencies** | `require_auth`, `require_scope(scope)`, `check_rate_limit` — FastAPI Depends |

### 1.6 notifications/ — Push Notifications
**Purpose:** Multi-platform push delivery (FCM, APNs, Web Push) with preference management and priority queuing.

| Class | Key Methods |
|-------|-------------|
| `DeviceManager` | `register_device()`, `get_user_devices()`, `unregister_device()` |
| `PreferenceManager` | `get_preference()`, `update_preference()`, `set_quiet_hours()`, `is_notification_allowed()` |
| `NotificationSender` | `send()` — checks preferences, targets devices, records stats |
| `NotificationQueue` | `enqueue()`, `dequeue()`, `get_batch()`, `mark_failed()` (retry with backoff) |

**Categories:** PRICE_ALERTS, TRADE_EXECUTIONS, PORTFOLIO, RISK_ALERTS, NEWS, SYSTEM, EARNINGS, DIVIDENDS

### 1.7 websocket/ — Real-time Streaming
**Purpose:** Distributed WebSocket infrastructure for market data and order/portfolio updates.

| Class | Key Methods |
|-------|-------------|
| `ConnectionManager` | `create_connection()`, `subscribe()`, `broadcast_to_channel()`, `send_to_user()` |
| `ChannelRouter` | `publish_quote()`, `publish_trade()`, `publish_bar()`, `publish_order_update()`, `publish_alert()` |
| `SubscriptionManager` | `subscribe()`, `add_symbols()`, `remove_symbols()` |

**Channels:** QUOTES, TRADES, BARS, ORDERS, PORTFOLIO, ALERTS, NEWS

---

## 2. Trading & Execution

### 2.1 execution/ — Core Execution Engine
**Purpose:** Abstract broker interface, paper trading, smart routing, position sizing, rebalancing, trade journaling.

| Class | Key Methods |
|-------|-------------|
| `BrokerInterface` (ABC) | `connect()`, `submit_order()`, `get_account()`, `get_positions()` |
| `PaperBroker` | Realistic simulation with slippage and commission |
| `AlpacaBroker` | Live/paper Alpaca integration |
| `PreTradeValidator` | `validate()` — buying power, position limits, PDT, rate limits |
| `PositionSizer` | `equal_weight()`, `score_weighted()`, `kelly_criterion()`, `risk_parity()` |
| `RebalanceEngine` | `preview_rebalance()`, `execute_rebalance()` |
| `TradingService` | `buy()`, `sell()` — high-level orchestrator |
| `TCAEngine` | Transaction cost analysis |

**Key Models:** `OrderRequest`, `Order`, `Position`, `AccountInfo`, `ExecutionResult`, `RebalanceProposal`
**Enums:** `OrderSide`, `OrderType` (6 types), `OrderStatus` (9 states), `OrderTimeInForce`

### 2.2 smart_router/ — Multi-Venue Routing
**Purpose:** Routes orders across lit markets, dark pools, midpoints based on cost/fill probability/latency.

| Class | Key Methods |
|-------|-------------|
| `SmartRouter` | `route_order()` → `RouteDecision` with splits and cost estimate |
| `RouteScorer` | `score_all_venues()` — fill probability, latency, spreads |
| `CostOptimizer` | `estimate_cost()`, `find_cheapest()` |

**Strategies:** BEST_PRICE, FASTEST_FILL, LOWEST_COST, SMART, LOWEST_IMPACT

### 2.3 brokers/ — Multi-Broker Abstraction
**Purpose:** Unified interface to 9 brokers with credential management and aggregated portfolio views.

| Class | Key Methods |
|-------|-------------|
| `BrokerManager` | `add_broker()`, `get_all_positions()`, `get_aggregated_account()`, `place_order_multi()` |
| `CredentialManager` | `store_credentials()`, `get_credentials()` |

**Broker Types:** ALPACA, INTERACTIVE_BROKERS, SCHWAB, ROBINHOOD, COINBASE, FIDELITY, IBKR, TASTYTRADE, WEBULL

### 2.4 trade_executor/ — Autonomous Execution
**Purpose:** Signal→order pipeline with 8-check risk gate, 7 exit strategies, instrument-aware routing (options/ETFs/stocks).

| Class | Key Methods |
|-------|-------------|
| `TradeExecutor` | `process_signal()` → `ExecutionResult` |
| `RiskGate` | `check()` — PDT, buying power, position limits, correlation, liquidity, VAR, regime, max positions |
| `ExitMonitor` | `check_all()` — profit target, stop loss, time stop, trailing stop, volatility stop, pattern stop, exit signal |
| `InstrumentRouter` | `route_signal()` → options/leveraged_etf/stock |

### 2.5 options_scalper/ — 0DTE Options Scalping
**Purpose:** 0DTE/1DTE options scalping with Greeks-aware validation, strike selection, and leveraged ETF scalping.

| Class | Key Methods |
|-------|-------------|
| `OptionsScalper` | `scalp()` → `ScalpResult` |
| `StrikeSelector` | `select_strikes()` based on delta target and IV rank |
| `GreeksGate` | `validate()` — gamma, theta, delta exposure checks |
| `ETFScalper` | `scalp_etf()` for 3x/2x leveraged ETFs |

### 2.6 bot_pipeline/ — Hardened Trading Pipeline
**Purpose:** Central 9-stage pipeline orchestrator (PRD-170/171) with thread-safety, persistent state, and full audit trail.

| Component | Key Classes & Methods |
|-----------|----------------------|
| **Orchestrator** | `BotOrchestrator.process_signal()`, `get_positions()`, `emergency_shutdown()` |
| **State Manager** | `PersistentStateManager` — file-backed kill switch, daily P&L, circuit breaker |
| **Order Validator** | `OrderValidator.validate_fill()` — detects rejected/zero-fill/stale/partial/slippage |
| **Position Reconciler** | `PositionReconciler.reconcile()` — ghosts, orphans, qty mismatches |
| **Signal Guard** | `SignalGuard.is_fresh()`, `is_duplicate()` — staleness + dedup |
| **Lifecycle Manager** | `LifecycleManager.update_prices()`, `check_exits()`, `emergency_close_all()` |
| **Regime Bridge** | `RegimeBridge.adapt_config()` — regime→executor config mutations |
| **Fusion Bridge** | `FusionBridge.fuse_signals()` — multi-source signal combination |
| **Strategy Bridge** | `StrategyBridge.select_strategy()` — ADX-gated routing |
| **Alert Bridge** | `BotAlertBridge.on_trade_executed()`, `on_kill_switch()`, etc. — 7 event handlers |
| **Feedback Bridge** | `FeedbackBridge.on_trade_closed()` — weight recalculation every N trades |

### 2.7 bot_dashboard/ — Bot Control Center
**Purpose:** Real-time bot control dashboard with state management, metrics, and chart rendering.

| Class | Key Methods |
|-------|-------------|
| `BotController` | `start()`, `stop()`, `pause()`, `resume()`, `kill()` |
| `BotMetricsCalculator` | `calculate_metrics()` → win rate, Sharpe, drawdown, profit factor |
| `BotChartRenderer` | `render_equity_curve()`, `render_daily_pnl()`, `render_position_heatmap()` |

### 2.8 bot_analytics/ — Live Performance Analytics
**Purpose:** Rolling equity curve, Sharpe/Sortino/Calmar metrics, per-signal and per-strategy breakdowns.

| Class | Key Methods |
|-------|-------------|
| `BotPerformanceTracker` | `record_trade()`, `get_snapshot()` → `PerformanceSnapshot` |

### 2.9 bot_backtesting/ — Strategy Backtesting
**Purpose:** Backtest bot strategies on OHLCV data with signal attribution and walk-forward optimization.

| Class | Key Methods |
|-------|-------------|
| `BotBacktestRunner` | `run()` → `EnrichedBacktestResult` |
| `SignalAttributor` | `attribute_performance()` — per-signal-type performance |
| `SignalReplay` | `replay_with_config()` — risk config A/B testing |

### 2.10 trade_pipeline/ — 5-Stage Order Pipeline
**Purpose:** validate → risk_check → route → execute → record with detailed audit trail.

| Class | Key Methods |
|-------|-------------|
| `PipelineExecutor` | `execute_order()`, `validate_order()`, `check_risk()`, `route_order()` |

### 2.11 position_calculator/ — Position Sizing Engine
**Purpose:** Fixed-risk, Kelly, fixed-dollar, fixed-share sizing with heat tracking and drawdown adjustment.

| Class | Key Methods |
|-------|-------------|
| `PositionSizingEngine` | `calculate()` → `SizingResult` |
| `HeatCalculator` | `calculate_heat()` — portfolio risk % |
| `DrawdownAnalyzer` | `get_drawdown_state()` → multiplier |

**Methods:** FIXED_RISK, KELLY, HALF_KELLY, QUARTER_KELLY, FIXED_DOLLAR, FIXED_SHARES

### 2.12 risk_manager/ — Portfolio Risk Monitor
**Purpose:** Leverage constraints, sector concentration, VIX-based sizing, circuit breaker, kill switch, market hours.

| Class | Key Methods |
|-------|-------------|
| `PortfolioRiskMonitor` | `assess_portfolio()` → `RiskSnapshot` |
| `VIXSizer` | `get_size_multiplier(vix_level)` → 0.5-1.5 |
| `EnhancedKillSwitch` | `trigger()`, `check_auto_trigger_conditions()` |
| `CircuitBreaker` | `check_conditions()` |

---

## 3. ML, Factors & Analysis

### 3.1 factors/ — Multi-Factor Model
**Purpose:** 6-category factor model (value, momentum, quality, growth, volatility, technical) with percentile ranking.

| Class | Key Methods |
|-------|-------------|
| `FactorRegistry` | `compute_all()`, `compute_category()` |
| `FactorCalculator` (ABC) | `compute()` → DataFrame with percentile scores [0,1] |

### 3.2 factor_engine/ — Advanced Factor Scoring
**Purpose:** Regime-aware composite scoring with adaptive weighting and sector-relative adjustments.

| Class | Key Methods |
|-------|-------------|
| `FactorEngineV2` | `compute_all_scores()` → DataFrame with value/momentum/quality/growth/volatility/technical/composite/regime |
| `RegimeDetector` | Classifies market regime (bull/bear/sideways/crisis) |
| `AdaptiveWeightManager` | Adjusts factor weights based on regime |

### 3.3 ml/ — ML Prediction Engine
**Purpose:** Stock ranking, regime classification, earnings prediction, factor timing with walk-forward validation.

| Class | Key Methods |
|-------|-------------|
| `StockRankingModel` | LightGBM ensemble → quintile ranking (1-5) |
| `RegimeClassifier` | GMM + Random Forest → regime classification |
| `EarningsPredictionModel` | XGBoost → earnings surprise prediction |
| `FactorTimingModel` | Multi-output LightGBM → factor weight predictions |
| `MLPredictor` | `predict_rankings()`, `predict_regime()`, `get_factor_timing_weights()` |
| `WalkForwardValidator` | `validate()` → expanding window cross-validation |
| `DegradationDetector` | `detect()` → `DriftReport` |
| `ModelExplainer` | SHAP-based feature importance |

### 3.4 sentiment/ — Sentiment Intelligence
**Purpose:** News, social, insider, analyst, earnings NLP combined into composite sentiment scores.

| Class | Key Methods |
|-------|-------------|
| `NewsSentimentEngine` | `analyze(text)` → FinBERT/keyword sentiment |
| `SocialMediaMonitor` | `get_mentions()`, `detect_trending()` |
| `InsiderTracker` | `get_filings()` |
| `AnalystConsensusTracker` | `get_consensus()` |
| `SentimentComposite` | `compute()` — multi-source composite |
| `SentimentFusionEngine` | `fuse()` — reliability-weighted fusion |

### 3.5 llm_sentiment/ — LLM-Powered Sentiment
**Purpose:** Multi-model sentiment analysis (Claude/GPT/Gemini/DeepSeek/Ollama) with aspect extraction and entity resolution.

| Class | Key Methods |
|-------|-------------|
| `LLMSentimentAnalyzer` | `analyze()` → sentiment, score, themes, urgency, time_horizon |
| `AspectExtractor` | `extract()` — thematic aspects (valuation, growth, risk) |
| `EntityResolver` | `resolve()` — entity identification and per-entity sentiment |
| `SentimentPredictor` | `forecast()` — momentum direction and probability |

### 3.6 altdata/ — Alternative Data
**Purpose:** Satellite imagery, web traffic, social sentiment signals with composite scoring.

| Class | Key Methods |
|-------|-------------|
| `SatelliteAnalyzer` | `analyze()` — parking lots, oil storage, shipping |
| `WebTrafficAnalyzer` | `analyze()` — web traffic growth metrics |
| `AltDataScorer` | `composite()` — combined alt-data score |

### 3.7 news/ — News & Events
**Purpose:** Multi-source news, earnings calendar, economic events, SEC filings, corporate events, alerts.

| Class | Key Methods |
|-------|-------------|
| `NewsFeedManager` | `add_article()`, `get_for_symbol()`, `search()` |
| `EarningsCalendar` | `get_upcoming()`, `get_surprise()` |
| `EconomicCalendar` | `get_high_impact_events()` |
| `SECFilingsTracker` | `get_recent_filings()` |

### 3.8 options/ — Options Platform
**Purpose:** Black-Scholes/Binomial/Monte Carlo pricing, vol surface, strategies, unusual activity, flow classification.

| Class | Key Methods |
|-------|-------------|
| `OptionsPricingEngine` | `black_scholes()`, `implied_volatility()` |
| `VolatilitySurfaceBuilder` | `build()` → vol surface with term/smile |
| `StrategyBuilder` | `build_spread()` → payoff, max_profit, max_loss |
| `UnusualActivityDetector` | `detect()` → volume/OI/PCR anomalies |
| `FlowDetector` | `classify()` → institutional/retail/hedging/speculation |

### 3.9 crypto_options/ — Crypto Derivatives
**Purpose:** Black-76 pricing for crypto options, funding rates, basis spreads, perpetual contracts.

### 3.10 optimizer/ — Portfolio Optimization
**Purpose:** Mean-variance, Black-Litterman, risk parity, HRP, tax-aware rebalancing.

| Class | Key Methods |
|-------|-------------|
| `MeanVarianceOptimizer` | `max_sharpe()`, `min_variance()` |
| `RiskParityOptimizer` | `optimize()` — equal risk contribution |
| `HRPOptimizer` | `optimize()` — hierarchical risk parity |
| `BlackLittermanModel` | `optimize()` — Bayesian with views |
| `TaxLossHarvester` | `identify_candidates()` |
| `TaxAwareRebalancer` | `rebalance_with_harvesting()` |

**Templates:** Conservative, Moderate, Aggressive, Income, Growth, Value

### 3.11 rebalancing/ — Portfolio Rebalancing
**Purpose:** Drift monitoring, threshold/calendar-based scheduling, cost/tax optimization.

| Class | Key Methods |
|-------|-------------|
| `DriftMonitor` | `compute_drift()` → `PortfolioDrift` |
| `RebalancePlanner` | `plan_threshold_rebalance()`, `plan_calendar_rebalance()` |

### 3.12 risk/ — Enterprise Risk Management
**Purpose:** VaR, stress testing, drawdown protection, pre-trade validation, Brinson/factor attribution.

| Class | Key Methods |
|-------|-------------|
| `RiskMetricsCalculator` | `compute()` → Sharpe, Sortino, Calmar, beta, VaR |
| `VaRCalculator` | `compute()` → historical/parametric/Monte Carlo VaR |
| `StressTestEngine` | `stress()` → scenario-based portfolio impact |
| `ShockPropagationEngine` | `propagate()` — factor shock propagation |
| `AttributionAnalyzer` | `brinson()` — Brinson-Fachler decomposition |

### 3.13 liquidity/ — Liquidity Analytics
**Purpose:** Multi-factor liquidity scoring, spread decomposition, market impact (Almgren-Chriss), slippage tracking.

### 3.14 tailrisk/ — Tail Risk Hedging
**Purpose:** CVaR (expected shortfall), tail dependence, hedge construction (puts, VIX, inverse ETFs), risk budgeting.

### 3.15 attribution/ — Performance Attribution
**Purpose:** Brinson-Fachler, Fama-French 5-factor, multi-period linking, geographic attribution, tear sheets.

| Class | Key Methods |
|-------|-------------|
| `TearSheetGenerator` | `generate()` — all metrics, monthly returns, drawdowns |
| `FamaFrenchAnalyzer` | `analyze()` — 5-factor exposures and alpha |
| `MultiPeriodAttribution` | `link_periods()` — cumulative attribution |

---

## 4. Market Analysis

### 4.1 breadth/ — Market Breadth
**Purpose:** Advance/decline tracking, McClellan Oscillator, breadth thrust detection, composite market health scoring.

| Class | Key Methods |
|-------|-------------|
| `BreadthIndicators` | `process_day()`, `get_nhnl_moving_average()`, `reset()` — computes A/D line, McClellan, thrust signals |
| `HealthScorer` | `score()` — combines 5 metrics (AD, NHNL, McClellan, thrust, volume) into 0-100 composite |
| `SectorBreadthAnalyzer` | `compute_sector_breadth()`, `rank_sectors()`, `get_strongest_sectors()`, `get_deteriorating_sectors()` |

**Models:** `AdvanceDecline`, `NewHighsLows`, `McClellanData`, `BreadthThrustData`, `BreadthSnapshot`, `SectorBreadth`, `MarketHealth`
**Enums:** `BreadthSignal` (OVERBOUGHT/OVERSOLD/BREADTH_THRUST/ZERO_CROSS_UP/DOWN), `MarketHealthLevel` (VERY_BULLISH→VERY_BEARISH)

### 4.2 correlation/ — Cross-Asset Correlation
**Purpose:** Rolling correlation matrices, regime detection, pair/cluster analysis, diversification scoring.

| Class | Key Methods |
|-------|-------------|
| `CorrelationEngine` | `compute_matrix()`, `get_top_pairs()`, `get_highly_correlated()`, `get_rolling_correlation()` |
| `CorrelationRegimeDetector` | `detect()`, `get_regime_transitions()` — normal/stressed/extreme regimes |
| `DiversificationAnalyzer` | `score()`, `analyze_portfolio()` — diversification level from correlation matrix |

**Models:** `CorrelationMatrix` (with `avg_correlation`, `get_pair()`), `CorrelationPair`, `RollingCorrelation`, `CorrelationRegime`, `DiversificationScore`
**Enums:** `CorrelationMethod` (PEARSON/SPEARMAN/KENDALL), `RegimeType` (NORMAL/STRESSED/EXTREME), `DiversificationLevel` (POOR→EXCELLENT)

### 4.3 volatility/ — Volatility Analytics
**Purpose:** Multi-method vol estimation, SVI surface calibration, skew analysis, regime detection, term structure modeling.

| Class | Key Methods |
|-------|-------------|
| `VolatilityEngine` | `compute_historical()`, `compute_ewma()`, `compute_parkinson()`, `compute_garman_klass()`, `compute_cone()` |
| `VolSurfaceAnalyzer` | `fit_smile()`, `compute_skew()`, `detect_wing_bias()` |
| `VolRegimeDetector` | `detect()`, `get_regime_signals()` — LOW/ELEVATED/CRISIS |
| `SVICalibrator` | `calibrate()`, `compute_implied_vol()` — SVI surface fitting |
| `SkewAnalyzer` | `analyze_skew()`, `compute_risk_reversal()`, `detect_skew_regime()` |
| `TermStructureModeler` | `analyze_term_structure()`, `compute_carry_roll_down()` |
| `VolRegimeSignalGenerator` | `generate_signals()`, `compute_vol_of_vol()`, `detect_mean_reversion()` |

**Models:** `VolEstimate`, `TermStructure`, `VolSmilePoint`, `VolSurface`, `VolRegimeState`, `VolConePoint`, `SVIParams`, `SVISurface`, `RiskReversal`, `SkewDynamics`, `CarryRollDown`, `VolOfVol`, `MeanReversionSignal`
**Enums:** `VolMethod` (HISTORICAL/EWMA/PARKINSON/GARMAN_KLASS), `VolRegime` (LOW/ELEVATED/CRISIS), `SurfaceInterpolation` (LINEAR/CUBIC_SPLINE/RBF)

### 4.4 macro/ — Macro Economic
**Purpose:** FRED indicator tracking, yield curve analysis (inversion detection), regime classification, macro factor models.

| Class | Key Methods |
|-------|-------------|
| `IndicatorTracker` | `add_indicator()`, `summarize()`, `get_surprises()` — leading/coincident/lagging aggregation |
| `YieldCurveAnalyzer` | `analyze()`, `detect_inversion()`, `compute_steepness()` |
| `RegimeDetector` | `detect()`, `compute_probability()` — expansion/contraction/stagnation/deflation |
| `MacroFactorModel` | `compute_factors()`, `get_factor_loadings()` — growth, inflation, rates, spreads, credit |

**Models:** `EconomicIndicator`, `IndicatorSummary`, `YieldCurveSnapshot`, `RegimeState`, `MacroFactorResult`
**Enums:** `RegimeType` (EXPANSION/CONTRACTION/STAGNATION/DEFLATION), `CurveShape` (NORMAL/FLAT/INVERTED/STEEP), `IndicatorType` (LEADING/COINCIDENT/LAGGING)

### 4.5 microstructure/ — Market Microstructure
**Purpose:** Bid-ask spread decomposition, order book analysis, tick-level analytics, VWAP computation, price impact estimation.

| Class | Key Methods |
|-------|-------------|
| `SpreadAnalyzer` | `analyze()`, `roll_estimator()` — quoted/effective/realized/roll spreads with adverse selection |
| `OrderBookAnalyzer` | `analyze()`, `compute_pressure()`, `compute_resilience()` — imbalance, depth, slope |
| `TickAnalyzer` | `analyze()`, `compute_vwap()`, `compute_kyle_lambda()` |
| `ImpactEstimator` | `estimate_impact()`, `compute_optimal_execution()` — permanent + temporary impact |

**Models:** `SpreadMetrics`, `BookLevel`, `OrderBookSnapshot`, `TickMetrics`, `Trade`, `ImpactEstimate`
**Enums:** `TradeClassification` (BUY/SELL/UNKNOWN), `SpreadType` (QUOTED/EFFECTIVE/REALIZED/ROLL), `ImpactModel` (LINEAR/SQUARE_ROOT/POWER_LAW)

### 4.6 orderflow/ — Order Flow
**Purpose:** Order flow imbalance analysis, block trade detection, buying/selling pressure measurement, smart money signals.

| Class | Key Methods |
|-------|-------------|
| `ImbalanceAnalyzer` | `compute_imbalance()`, `rolling_imbalance()` — bid/ask volume imbalance classification |
| `BlockDetector` | `detect()`, `score_blocks()` — institutional block identification |
| `PressureAnalyzer` | `compute_pressure()`, `rolling_pressure()` — cumulative order flow delta |

**Models:** `OrderBookSnapshot`, `BlockTrade`, `FlowPressure`, `SmartMoneySignal`, `OrderFlowSnapshot`
**Enums:** `FlowSignal` (BULLISH/BEARISH/NEUTRAL), `ImbalanceType` (BULLISH/BEARISH/BALANCED), `BlockSize` (SMALL/LARGE/INSTITUTIONAL)

### 4.7 pairs/ — Statistical Arbitrage
**Purpose:** Cointegration testing (Engle-Granger), spread z-score analysis, pair scoring and selection.

| Class | Key Methods |
|-------|-------------|
| `CointegrationTester` | `test_pair()`, `test_universe()` — ADF stationarity + OLS hedge ratio |
| `SpreadAnalyzer` | `analyze()`, `compute_zscore()`, `compute_hurst()`, `compute_half_life()` |
| `PairSelector` | `rank_pairs()`, `select_best_pairs()`, `filter_by_criteria()` |

**Models:** `CointegrationResult`, `SpreadAnalysis`, `PairScore`, `PairSignal`, `PairTrade`
**Enums:** `PairSignalType` (BUY_A_SELL_B/BUY_B_SELL_A/NO_SIGNAL), `HedgeMethod` (OLS/RIDGE/ROBUST), `PairStatus` (COINTEGRATED/WEAK_EVIDENCE/NOT_COINTEGRATED)

### 4.8 darkpool/ — Dark Pool Analytics
**Purpose:** Dark pool volume tracking, print analysis, block detection, hidden liquidity estimation.

| Class | Key Methods |
|-------|-------------|
| `VolumeTracker` | `add_record()`, `summarize()` — dark vs lit volume ratios with trend momentum |
| `PrintAnalyzer` | `analyze()`, `detect_patterns()` — timing patterns and institutional flow |
| `BlockDetector` | `detect_blocks()`, `classify_block()` — large block identification |
| `LiquidityEstimator` | `estimate_hidden_liquidity()`, `compute_liquidity_score()` |

**Models:** `DarkPoolVolume`, `VolumeSummary`, `DarkPrint`, `PrintSummary`, `DarkBlock`, `DarkLiquidity`
**Enums:** `BlockDirection` (BUY/SELL/UNKNOWN), `LiquidityLevel` (LOW/MODERATE/HIGH/ABUNDANT), `VenueTier` (TIER_1/TIER_2/REGIONAL/CBOE)

### 4.9 fundflow/ — Fund Flows
**Purpose:** ETF/mutual fund flow tracking, institutional ownership, rotation detection, smart money signals.

| Class | Key Methods |
|-------|-------------|
| `FlowTracker` | `add_flow()`, `summarize()`, `summarize_all()` — inflows/outflows with AUM-relative sizing |
| `InstitutionalAnalyzer` | `analyze_position()`, `compute_ownership_concentration()` |
| `RotationDetector` | `detect_rotation()`, `get_sector_flows()` — growth→value→defensive rotation |
| `SmartMoneyDetector` | `analyze()`, `detect_accumulation()`, `detect_distribution()` — institutional vs retail divergence |

**Models:** `FundFlow`, `FlowSummary`, `InstitutionalPosition`, `InstitutionalSummary`, `SectorRotation`, `SmartMoneyResult`
**Enums:** `FlowDirection` (INFLOW/OUTFLOW/NEUTRAL), `FlowStrength` (VERY_STRONG→VERY_WEAK), `RotationPhase` (GROWTH/VALUE/DEFENSIVE/CASH), `SmartMoneySignal` (STRONG_ACCUMULATION→STRONG_DISTRIBUTION)

### 4.10 crowding/ — Crowding Detection
**Purpose:** Position crowding scores, portfolio overlap analysis, short interest analytics, consensus divergence.

| Class | Key Methods |
|-------|-------------|
| `CrowdingDetector` | `score()` — 0-1 crowding from HHI concentration + holder breadth + momentum |
| `OverlapAnalyzer` | `compute_overlap()`, `analyze_universe()`, `get_highly_overlapped()` |
| `ShortInterestAnalyzer` | `analyze()`, `detect_squeeze_risk()`, `compute_short_ratio()` |
| `ConsensusAnalyzer` | `compute_consensus()`, `get_divergence_score()` |

**Models:** `CrowdingScore`, `FundOverlap`, `CrowdedName`, `ShortInterestData`, `ShortSqueezeScore`, `ConsensusSnapshot`
**Enums:** `CrowdingLevel` (LOW/MODERATE/HIGH/EXTREME), `SqueezeRisk` (LOW→CRITICAL), `OverlapMethod` (JACCARD/COSINE/SIMPLE_RATIO)

### 4.11 regime/ — Regime Classification
**Purpose:** Multi-method regime detection (HMM, clustering, rule-based) with ensemble, transition analysis, and allocation.

| Class | Key Methods |
|-------|-------------|
| `RegimeDetector` | `classify()` — rule-based from price, VIX, breadth, yield curve |
| `GaussianHMM` | `detect()`, `fit()`, `compute_probability()` — 3-4 state Hidden Markov Model |
| `ClusterRegimeClassifier` | `classify()`, `fit()` — K-means from returns + volatility features |
| `RegimeTransitionAnalyzer` | `detect_transition()`, `compute_persistence()` |
| `RegimeAllocator` | `allocate()`, `get_regime_weights()` — regime-adaptive allocation |
| `DynamicThresholdManager` | `get_threshold()`, `optimize_thresholds()` — signal thresholds per regime |
| `RegimeEnsemble` | `classify()`, `get_ensemble_confidence()` — combines all methods |
| `RegimeSignalGenerator` | `generate_signals()` — transition/persistence/alignment/divergence signals |

**Models:** `RegimeState`, `RegimeSegment`, `RegimeHistory`, `TransitionMatrix`, `RegimeStats`, `RegimeAllocation`, `ThresholdSet`, `EnsembleResult`, `RegimeSignalSummary`
**Enums:** `RegimeType` (BULL/BEAR/SIDEWAYS/CRISIS), `DetectionMethod` (RULE_BASED/HMM/CLUSTERING), `MarketRegime`

### 4.12 regime_signals/ — Regime-Aware Signals
**Purpose:** 8+ regime-conditional signal types with parameter optimization and per-regime performance tracking.

| Class | Key Methods |
|-------|-------------|
| `RegimeDetector` | `detect_regime()` — from price momentum, volatility, volume |
| `SignalGenerator` | `generate_signals()` — momentum, mean_reversion, breakout, trend_following, defensive, aggressive, volatility, counter_trend |
| `ParameterOptimizer` | `optimize()`, `backtest_parameters()` — maximize Sharpe per regime |
| `PerformanceTracker` | `record_outcome()`, `compute_stats()`, `track_win_rate()` |

**Models:** `RegimeState`, `RegimeSignal`, `SignalPerformance`, `RegimeParameter`, `SignalResult`
**Enums:** `RegimeType` (BULL_HIGH_VOL/BULL_LOW_VOL/BEAR_HIGH_VOL/BEAR_LOW_VOL/SIDEWAYS_HIGH_VOL/SIDEWAYS_LOW_VOL/CRISIS/RECOVERY), `SignalType` (8 types), `SignalOutcome` (WIN/LOSS/BREAKEVEN)

### 4.13 charting/ — Technical Charting
**Purpose:** 50+ indicators, chart pattern detection, trend analysis, support/resistance, Fibonacci, drawing tools, layouts.

| Class | Key Methods |
|-------|-------------|
| `IndicatorEngine` | `compute_sma()`, `compute_ema()`, `compute_rsi()`, `compute_macd()`, `compute_bollinger_bands()`, `compute_atr()` |
| `PatternDetector` | `detect_all()`, `detect_double_top()`, `detect_head_and_shoulders()`, `detect_triangle()` — with confidence scoring |
| `TrendAnalyzer` | `detect_trend()`, `compute_trend_strength()`, `find_support_resistance()` |
| `SupportResistanceDetector` | `find_levels()`, `compute_strength()`, `detect_bounces()` |
| `FibonacciAnalyzer` | `compute_levels()`, `project_targets()` |
| `DrawingManager` | `add_drawing()`, `get_drawings()`, `remove_drawing()` |
| `LayoutManager` | `create_layout()`, `save_layout()`, `load_layout()` |

**Models:** `ChartLayout`, `Drawing`, `IndicatorConfig`, `ChartTemplate`, `OHLCV`, `IndicatorResult`, `ChartPattern`
**Enums:** `ChartType` (CANDLESTICK/OHLC/BAR/LINE/RENKO), `Timeframe` (M1→M1_MONTHLY), `DrawingType` (7 types), `IndicatorCategory` (TREND/MOMENTUM/VOLATILITY/VOLUME/CYCLE)

### 4.14 events/ — Event-Driven Analytics
**Purpose:** Earnings analysis, M&A probability modeling, corporate action tracking, event calendar clustering.

| Class | Key Methods |
|-------|-------------|
| `EarningsAnalyzer` | `add_event()`, `summarize()`, `estimate_drift()`, `analyze_beats()` — classifies beat/meet/miss, tracks PEAD |
| `MergerAnalyzer` | `add_deal()`, `annualized_spread()`, `estimate_probability()`, `score_completion_likelihood()`, `get_arbitrage_opportunities()` |
| `CorporateActionTracker` | `add_action()`, `get_upcoming()`, `analyze_dividends()`, `get_split_adjusted_prices()` |
| `EventCalendarAnalyzer` | `analyze_calendar()`, `detect_clusters()`, `forecast_catalyst_timing()` |
| `DealProbabilityModeler` | `estimate_completion()`, `analyze_risk_factors()` |
| `CorporateActionImpactEstimator` | `estimate_dividend_impact()`, `estimate_split_impact()`, `estimate_buyback_impact()` |

**Models:** `EarningsEvent`, `EarningsSummary`, `MergerEvent`, `CorporateAction`, `EventSignal`, `CalendarEvent`, `EventCluster`, `CatalystTimeline`, `CrossEventInteraction`, `DealRiskFactors`, `CompletionEstimate`
**Enums:** `EventType` (EARNINGS/DIVIDEND/SPLIT/BUYBACK/SPINOFF/MERGER/DELISTING), `EarningsResult` (BEAT/MEET/MISS), `DealStatus` (ANNOUNCED→TERMINATED)

### 4.15 economic/ — Economic Calendar & Fed Watching
**Purpose:** Economic event calendar, Fed policy monitoring, market impact analysis by sector, economic alerts.

| Class | Key Methods |
|-------|-------------|
| `EconomicCalendar` | `add_event()`, `record_release()`, `get_day()`, `get_week()`, `get_month()`, `get_upcoming()` |
| `HistoryAnalyzer` | `add_history()`, `compute_stats()`, `analyze_surprise()`, `detect_pattern()` |
| `FedWatcher` | `add_meeting()`, `get_next_meeting()`, `add_rate_expectation()`, `get_rate_expectations()` |
| `ImpactAnalyzer` | `analyze_event()`, `compute_expected_volatility()`, `get_sector_sensitivity()` |
| `EconomicAlertManager` | `create_alert()`, `trigger_alert()`, `get_active_alerts()` |

**Models:** `EconomicEvent` (with `surprise`, `surprise_pct`, `beat_or_miss` properties), `HistoricalRelease`, `EventStats`, `FedMeeting`, `RateExpectation`, `MarketImpact`
**Enums:** `ImpactLevel` (LOW/MEDIUM/HIGH), `EventCategory` (EMPLOYMENT/INFLATION/GDP/HOUSING/CONSUMER/MANUFACTURING/RATES), `RateDecision` (CUT_50BPS→HIKE_50BPS), `AlertTrigger`

### 4.16 insider/ — Insider Trading
**Purpose:** Transaction tracking, cluster buying detection, institutional 13F holdings, insider signal generation.

| Class | Key Methods |
|-------|-------------|
| `TransactionTracker` | `add_transaction()`, `get_by_symbol()`, `get_by_insider()`, `get_large_transactions()`, `get_ceo_transactions()`, `get_summary()` |
| `ClusterDetector` | `detect_clusters()`, `score_cluster()`, `get_strongest_clusters()` — coordinated insider buying |
| `InstitutionalTracker` | `add_holding()`, `get_top_holders()`, `get_new_positions()`, `get_most_accumulated()` |
| `ProfileManager` | `build_profiles()`, `rank_insiders()`, `calculate_success_rate()` |
| `SignalGenerator` | `generate_signals()`, `score_transaction()`, `flag_unusual_activity()` |
| `AlertManager` | `add_alert()`, `check_alerts()`, `get_notifications()` |

**Models:** `InsiderTransaction`, `InsiderSummary`, `InsiderCluster`, `InstitutionalHolding`, `InstitutionalSummary`, `InsiderProfile`, `InsiderSignal`
**Enums:** `InsiderType` (CEO/CFO/COO/CTO/DIRECTOR/OFFICER/TEN_PCT_OWNER), `TransactionType` (BUY/SELL/OPTION_EXERCISE/GRANT/GIFT), `SignalStrength` (WEAK→VERY_STRONG), `FilingType` (FORM_3/FORM_4/FORM_5/FORM_13F/SC_13D)

### 4.17 sectors/ — Sector Rotation
**Purpose:** Sector ranking, rotation pattern detection, business cycle mapping, sector recommendations.

| Class | Key Methods |
|-------|-------------|
| `SectorRankings` | `update_sector()`, `get_top_sectors()`, `get_bottom_sectors()`, `get_cyclical_sectors()`, `get_defensive_sectors()`, `get_sector_correlations()` |
| `RotationDetector` | `detect_rotation()`, `get_active_patterns()`, `is_risk_on()`, `is_risk_off()` — money flowing between defensive/cyclical |
| `CycleAnalyzer` | `analyze()`, `get_favored_sectors()`, `get_unfavored_sectors()`, `predict_next_phase()` |

**Cycle Phases:** EARLY_EXPANSION, MID_EXPANSION, LATE_EXPANSION, EARLY_CONTRACTION, LATE_CONTRACTION
**Enums:** `SectorName` (11 GICS sectors), `Trend` (UP/DOWN/NEUTRAL), `Recommendation` (STRONG_BUY→STRONG_SELL), `Conviction` (LOW/MEDIUM/HIGH)

### 4.18 earnings/ — Earnings Analysis
**Purpose:** Earnings calendar, estimate revision tracking, quality assessment (Beneish M-score), post-earnings reaction analysis.

| Class | Key Methods |
|-------|-------------|
| `EarningsCalendar` | `add_event()`, `get_upcoming()`, `get_before_market()`, `get_after_market()`, `filter_by_portfolio()` |
| `EstimateTracker` | `add_estimate()`, `calculate_revision_momentum()`, `get_estimate_spread()`, `get_symbols_with_positive_revisions()` |
| `QualityAnalyzer` | `analyze()`, `compute_beneish_m_score()`, `detect_red_flags()` |
| `ReactionAnalyzer` | `record_reaction()`, `calculate_historical_stats()`, `analyze_reaction_by_surprise()`, `screen_for_drift()` |

**Models:** `EarningsEvent`, `EarningsEstimate`, `QuarterlyEarnings`, `EarningsHistory`, `EarningsQuality`, `EarningsReaction`
**Enums:** `EarningsTime` (BEFORE_MARKET/AFTER_MARKET/DURING_MARKET), `SurpriseType` (BEAT/MISS/MEET), `ReactionDirection` (POSITIVE_GAP/NEGATIVE_GAP/FADE/CONTINUE)

### 4.19 dividends/ — Dividend Analytics
**Purpose:** Dividend calendar, income projection, safety analysis, growth assessment, DRIP simulation, tax analysis.

| Class | Key Methods |
|-------|-------------|
| `DividendCalendar` | `add_event()`, `get_upcoming_ex_dates()`, `get_upcoming_payments()`, `get_monthly_summary()` |
| `IncomeProjector` | `project_holding()`, `project_portfolio()` — annual and monthly income |
| `SafetyAnalyzer` | `analyze()` — payout/coverage ratios, debt metrics, red flags → safety score |
| `GrowthAnalyzer` | CAGR, growth rate tracking, cut detection |
| `DRIPSimulator` | Reinvested dividend compounding simulation |
| `TaxAnalyzer` | Qualified vs ordinary classification, tax calculation |

**Models:** `DividendEvent`, `DividendHolding`, `DividendIncome`, `PortfolioIncome`, `DividendSafety`, `DividendGrowth`, `DRIPSimulation`, `DividendTaxAnalysis`, `FinancialMetrics`
**Enums:** `DividendFrequency` (MONTHLY/QUARTERLY/ANNUAL/SEMI_ANNUAL), `SafetyRating` (SAFE/CAUTION/AT_RISK/CUT), `DividendType` (CASH/STOCK/SPECIAL)

### 4.20 crossasset/ — Cross-Asset Signals
**Purpose:** Intermarket relationships, lead-lag detection, cross-asset momentum, composite signal generation.

| Class | Key Methods |
|-------|-------------|
| `IntermarketAnalyzer` | `rolling_correlation()`, `relative_strength()` — equity/bond/commodity relationships |
| `LeadLagDetector` | `detect()`, `detect_all_pairs()` — cross-correlation at various lags |
| `CrossAssetMomentum` | Multi-asset breakout and momentum signals |
| `CrossAssetSignalGenerator` | `generate()`, `combine_signals()`, `weight_by_correlation()` |

**Models:** `AssetPairCorrelation`, `RelativeStrength`, `LeadLagResult`, `MomentumSignal`, `CrossAssetSignal`
**Enums:** `AssetClass` (EQUITY/FIXED_INCOME/COMMODITY/CRYPTO/CURRENCY/REAL_ESTATE), `CorrelationRegime` (NORMAL/CONTAGION/DECORRELATION/DIVERGENCE)

### 4.21 multi_asset/ — Crypto/Futures/International
**Purpose:** Crypto 5-factor model, futures contract management with auto-roll, FX hedging, cross-asset optimization.

| Class | Key Methods |
|-------|-------------|
| `CryptoDataProvider` | `register_asset()`, `get_asset()`, `set_on_chain_metrics()`, `get_returns()` |
| `CryptoFactorModel` | `compute_scores()` — value (NVT, MVRV), momentum (30/90/180d), quality (TVL), sentiment (fear/greed), network (hashrate) |
| `FuturesManager` | `get_contract_spec()`, `should_roll()`, `generate_roll_order()`, `calculate_pnl()`, `check_margin_levels()` |
| `CrossAssetOptimizer` | `from_template()`, `optimize()` — stock/crypto/futures/intl allocation |
| `UnifiedRiskManager` | `compute_var()`, `compute_cvar()`, `check_correlation_regime()`, `get_position_size()` |

**Models:** `CryptoAsset`, `CryptoFactorScores`, `OnChainMetrics`, `FuturesContract`, `FuturesPosition`, `RollOrder`, `MarginStatus`, `MultiAssetPortfolio`, `CrossAssetRiskReport`
**Enums:** `CryptoCategory` (LAYER1/LAYER2/DEFI/STABLECOIN/MEMECOIN), `FuturesCategory` (INDEX/FX/ENERGY/METALS/RATES/AGRICULTURE), `MarginAlertLevel` (OK/WARNING/CRITICAL)

### 4.22 credit/ — Credit Risk
**Purpose:** Credit spread modeling, default probability estimation, rating migration tracking, debt structure analysis.

| Class | Key Methods |
|-------|-------------|
| `SpreadAnalyzer` | `add_spread()`, `analyze()`, `term_structure()`, `detect_widening()`, `get_sector_spreads()` — z-scores, percentiles, trend |
| `DefaultEstimator` | Default probability from spreads, Merton distance-to-default |
| `RatingTracker` | Credit rating migrations, outlook changes, transition matrix |
| `DebtAnalyzer` | Debt structure, seniority, covenant analysis, maturity ladder |

**Models:** `CreditSpread`, `SpreadSummary`, `DefaultProbability`, `RatingSnapshot`, `RatingTransition`, `DebtItem`, `DebtStructure`
**Enums:** `CreditRating` (AAA→D), `RatingOutlook` (POSITIVE/STABLE/NEGATIVE/DEVELOPING), `SpreadType` (OAS/Z_SPREAD/G_SPREAD), `DefaultModel` (MERTON/HISTORICAL/MARKET_IMPLIED)

### 4.23 esg/ — ESG Scoring
**Purpose:** ESG scoring with E/S/G pillar breakdowns, controversy penalties, carbon metrics, impact measurement.

| Class | Key Methods |
|-------|-------------|
| `ESGScorer` | `score_security()`, `apply_controversy_penalty()`, `screen_for_sins()`, `screen_for_fossil_fuels()`, `aggregate_portfolio()`, `get_sector_ranking()` |
| `ImpactTracker` | Carbon emissions, water usage, diversity metrics tracking |

**Models:** `ESGScore`, `PillarScore`, `ImpactMetric`, `ESGScreenResult`, `CarbonMetrics`, `ESGPortfolioSummary`
**Enums:** `ESGRating` (AAA→CCC), `ESGCategory` (CLIMATE/GOVERNANCE/SOCIAL/CONTROVERSIES), `ImpactCategory`

---

## 5. Platform & Operations

### 5.1 config_service/ — Configuration Management
**Purpose:** Feature flags (boolean/percentage/user-list), secrets management, environment-specific configs, validators.

| Class | Key Methods |
|-------|-------------|
| `ConfigStore` | `set()`, `get()`, `get_typed()`, `rollback()` |
| `FeatureFlagService` | `create_flag()`, `evaluate()`, `set_percentage()`, `add_user()` |
| `SecretsManager` | `store()`, `retrieve()`, `rotate()` |

### 5.2 pipeline/ — Data Pipeline Orchestration
**Purpose:** DAG-based execution, dependency resolution (Kahn's algorithm), scheduling, SLA tracking.

| Class | Key Methods |
|-------|-------------|
| `PipelineEngine` | `execute()` → `PipelineRun` |
| `Pipeline` | `add_node()`, `get_execution_order()`, `validate()` |
| `PipelineMonitor` | `check_freshness()`, `validate_sla()` |

### 5.3 model_registry/ — ML Model Registry
**Purpose:** Model versioning, stage workflow (draft→staging→production→archived), A/B testing, experiment tracking.

| Class | Key Methods |
|-------|-------------|
| `ModelRegistry` | `register()`, `get_production()`, `transition_stage()` |
| `ABTestManager` | `create_experiment()`, `record_result()` |

### 5.4 alerting/ — Alert System
**Purpose:** Alert management with dedup, routing rules, escalation policies, multi-channel dispatch.

| Class | Key Methods |
|-------|-------------|
| `AlertManager` | `fire()`, `acknowledge()`, `resolve()` |
| `RoutingEngine` | `add_rule()`, `route()` |
| `EscalationManager` | `escalate()` |

**Severities:** INFO, WARNING, ERROR, CRITICAL
**Channels:** EMAIL, SLACK, SMS, WEBHOOK, PAGERDUTY

### 5.5 api_gateway/ — API Gateway
**Purpose:** Central gateway with per-endpoint rate limiting, request validation, API versioning, analytics.

| Class | Key Methods |
|-------|-------------|
| `APIGateway` | `process_request()`, `add_pre_hook()`, `add_post_hook()`, `get_health()` |
| `GatewayRateLimiter` | `check_rate_limit()`, `add_endpoint_limit()`, `set_user_quota()`, `get_user_usage()` — sliding-window |
| `RequestValidator` | `validate_request()`, `add_ip_allowlist()`, `add_ip_blocklist()`, `check_payload_size()` |
| `VersionManager` | `resolve_version()`, `is_supported()` |
| `APIAnalytics` | `record_request()` — metrics by path/method/user |

**Models:** `RequestContext`, `GatewayResponse`, `RateLimitResult`, `EndpointRateLimit`, `EndpointStats`, `APIVersion`, `ValidationResult`

### 5.6 backup/ — Disaster Recovery
**Purpose:** Full/incremental/snapshot backups with compression + encryption, point-in-time recovery, replication monitoring.

| Class | Key Methods |
|-------|-------------|
| `BackupEngine` | `create_backup()`, `execute_job()`, `schedule_backup()`, `enforce_retention()`, `get_statistics()` |
| `RecoveryManager` | `generate_plan()`, `execute_recovery()`, `point_in_time_recovery()` |
| `ReplicationMonitor` | Tracks replication health across backup targets |

**Models:** `BackupArtifact`, `BackupJob`, `RecoveryPlan`, `RecoveryResult`, `Replica`, `SLAReport`
**Enums:** `BackupType` (FULL/INCREMENTAL/SNAPSHOT), `BackupStatus`, `StorageBackend`, `StorageTier`

### 5.7 profiling/ — Performance Profiling
**Purpose:** SQL query fingerprinting (p95/p99), N+1 detection, index recommendation, connection pool monitoring.

| Class | Key Methods |
|-------|-------------|
| `QueryProfiler` | `record_query()`, `get_slow_queries()`, `get_top_queries()`, `detect_regressions()` |
| `PerformanceAnalyzer` | `take_snapshot()`, `detect_n1_queries()`, `compare_snapshots()` |
| `IndexAdvisor` | Recommends missing indexes from query patterns |
| `ConnectionMonitor` | Tracks active connections, long-running queries, pool health |

**Models:** `QueryFingerprint`, `PerformanceSnapshot`, `IndexRecommendation`, `ConnectionStats`, `LongRunningQuery`
**Enums:** `QuerySeverity` (NORMAL/SLOW/CRITICAL)

### 5.8 archival/ — Data Archival & GDPR
**Purpose:** Parquet archival, retention policies, GDPR workflows (access/deletion/export), hot→warm→cold tiering.

| Class | Key Methods |
|-------|-------------|
| `ArchivalEngine` | `create_job()`, `execute_job()`, `restore_from_archive()`, `get_storage_stats()` |
| `RetentionManager` | Per-table retention policies |
| `GDPRManager` | `submit_request()`, `process_request()`, `generate_export()`, `generate_compliance_report()`, `get_deletion_log()` |
| `DataLifecycleManager` | Hot→warm→cold automatic transitions |

**Models:** `ArchivalJob`, `RetentionPolicy`, `GDPRRequest`, `TierStats`
**Enums:** `ArchivalFormat` (PARQUET/CSV/JSON), `GDPRRequestType` (ACCESS/DELETION/EXPORT), `GDPRRequestStatus`

### 5.9 ws_scaling/ — WebSocket Scaling
**Purpose:** Distributed connection registry, pub/sub message routing, backpressure handling, reconnection management.

| Class | Key Methods |
|-------|-------------|
| `ConnectionRegistry` | `register()`, `unregister()`, `get_user_connections()`, `update_heartbeat()`, `get_stale_connections()` |
| `MessageRouter` | `subscribe()`, `unsubscribe()`, `route_message()`, `broadcast()`, `unicast()`, `multicast()` |
| `BackpressureHandler` | `handle_backpressure()`, `get_queue_stats()` — drop/discard strategies |
| `ReconnectionManager` | `initiate_reconnection()`, `complete_reconnection()` — exponential backoff |

**Models:** `ConnectionInfo`, `Message`, `QueueStats`, `ReconnectionSession`
**Enums:** `ConnectionState` (CONNECTED/DISCONNECTED/RECONNECTING), `MessagePriority` (LOW/NORMAL/HIGH), `DropStrategy`

### 5.10 deployment/ — Deployment Strategies
**Purpose:** Rolling/blue-green/canary deployments, traffic management, rollback engine, deployment validation.

| Class | Key Methods |
|-------|-------------|
| `DeploymentOrchestrator` | `create_deployment()`, `start_deployment()`, `complete_deployment()`, `fail_deployment()` |
| `TrafficManager` | `split_traffic()`, `shift_traffic()` — gradual traffic shifting |
| `RollbackEngine` | `execute_rollback()`, `validate_rollback()` |
| `DeploymentValidator` | `validate_deployment()`, `validate_health_checks()` — pre/post checks |

**Models:** `Deployment`, `TrafficSplit`, `RollbackAction`, `ValidationCheck`
**Enums:** `DeploymentStrategy` (ROLLING/BLUE_GREEN/CANARY), `DeploymentStatus`, `ValidationStatus`

### 5.11 event_bus/ — Event-Driven Architecture
**Purpose:** Topic-based pub/sub, immutable event store, async consumer groups, schema registry with versioning.

| Class | Key Methods |
|-------|-------------|
| `EventBus` | `subscribe()`, `publish()` |
| `EventStore` | `append()`, `get_events()`, `get_snapshot()` |
| `SchemaRegistry` | `register_schema()`, `validate()` |

### 5.12 multi_tenancy/ — Row-Level Security
**Purpose:** Thread-local tenant context, query filters, data isolation middleware, RBAC policy engine.

| Class | Key Methods |
|-------|-------------|
| `TenantContextManager` | `set_context()`, `get_context()`, `require_context()`, `create_background_context()` |
| `TenantContext` | `has_role()`, `has_permission()`, `highest_role()`, `create_child_context()` — immutable per-request |
| `DataIsolationMiddleware` | Query filtering & audit for RLS |
| `PolicyEngine` | `evaluate()`, `can_access()` — RBAC with glob patterns |

**Models:** `TenantContext`, `QueryFilter`, `QueryAuditEntry`, `Policy`, `PolicyEvaluation`
**Enums:** `AccessLevel` (NONE/READ/WRITE/ADMIN), `ResourceType`, `PolicyAction`

### 5.13 feature_store/ — ML Feature Store
**Purpose:** Feature catalog with versioning, offline store (point-in-time), online store (cache), lineage DAG tracking.

| Class | Key Methods |
|-------|-------------|
| `FeatureCatalog` | `register()`, `search()`, `deprecate()`, `archive()`, `get_dependencies()`, `get_statistics()` |
| `OfflineFeatureStore` | `store()`, `get_latest()`, `get_point_in_time()`, `get_history()`, `get_training_dataset()` |
| `OnlineFeatureStore` | `get()`, `set()` — in-memory cache for low-latency serving |
| `FeatureLineage` | DAG tracking of feature dependencies |

**Models:** `FeatureDefinition`, `FeatureValue`, `CacheEntry`, `LineageNode`, `LineageEdge`
**Enums:** `FeatureType` (NUMERIC/CATEGORICAL/TEXT), `FeatureStatus` (ACTIVE/DEPRECATED/ARCHIVED), `ComputeMode`

### 5.14 secrets_vault/ — Secrets Management
**Purpose:** Encrypted versioned secrets, credential rotation, glob-pattern access control, client SDK with caching.

| Class | Key Methods |
|-------|-------------|
| `SecretsVault` | `put()`, `get()`, `get_value()`, `delete()`, `list_secrets()`, `rollback_version()`, `search()` |
| `CredentialRotation` | `rotate()`, `schedule_rotation()` — auto rotation with policies |
| `AccessControl` | `grant_access()`, `revoke_access()`, `audit_access()` — glob-pattern ACLs |
| `SecretsClient` | Client SDK with caching & automatic refresh |

**Models:** `SecretEntry`, `RotationPolicy`, `RotationResult`, `AccessPolicy`, `AccessAuditEntry`, `CacheEntry`
**Enums:** `SecretType` (API_KEY/PASSWORD/CERTIFICATE/OAUTH_TOKEN), `RotationStrategy`

### 5.15 billing/ — Usage Billing
**Purpose:** Usage metering with tiered pricing, billing engine, invoice lifecycle, cost analytics & forecasting.

| Class | Key Methods |
|-------|-------------|
| `UsageMeter` | `define_meter()`, `record_usage()`, `get_usage()`, `get_cost_summary()`, `reset_period()` |
| `BillingEngine` | `generate_bill()`, `apply_discount()`, `apply_credit()`, `finalize_bill()`, `get_revenue_summary()` |
| `InvoiceManager` | `create_invoice()`, `send_invoice()`, `track_payment()` |
| `CostAnalytics` | `forecast_costs()`, `analyze_trends()`, `get_breakdown()` |

**Models:** `MeterDefinition`, `UsageRecord`, `BillLineItem`, `Bill`, `Invoice`, `CostBreakdown`
**Enums:** `MeterType` (API_CALLS/DATA_TRANSFER/COMPUTE/STORAGE), `InvoiceStatus` (DRAFT/SENT/PAID), `BillingPeriod`

### 5.16 logging_config/ — Structured Logging
**Purpose:** JSON logging, request ID propagation, context preservation, performance timing.

**Key Function:** `configure_logging()`, `RequestTracingMiddleware`

### 5.17 resilience/ — Resilience Patterns
**Purpose:** Circuit breaker, retry (fixed/linear/exponential backoff), rate limiter, bulkhead.

| Pattern | Key Class | Decorator |
|---------|-----------|-----------|
| Circuit Breaker | `CircuitBreaker` (CLOSED→OPEN→HALF_OPEN) | `@circuit_breaker()` |
| Retry | `RetryStrategy` | `@retry()` |
| Rate Limiter | `RateLimiter` | — |
| Bulkhead | `Bulkhead` | `@bulkhead()` |

### 5.18 observability/ — Prometheus Metrics
**Purpose:** Counter/Gauge/Histogram metrics, trading/system metrics, Prometheus export.

| Class | Key Methods |
|-------|-------------|
| `MetricsRegistry` | `register_counter()`, `register_gauge()`, `register_histogram()` |
| `PrometheusExporter` | `export()` → Prometheus text format |

**Decorators:** `@track_latency()`, `@count_calls()`, `@track_errors()`

### 5.19 api_errors/ — Error Handling
**Purpose:** Exception hierarchy, structured error responses, input validation, request sanitization.

**Exceptions:** `ValidationError`, `AuthenticationError`, `AuthorizationError`, `NotFoundError`, `ConflictError`, `RateLimitError`

### 5.20 lifecycle/ — App Lifecycle
**Purpose:** Singleton manager, K8s-compatible health probes (liveness/readiness/startup), hooks, signal handling.

### 5.21 testing/ — Test Framework
**Purpose:** Integration test bases, mock broker/market/redis, load testing, benchmarks.

### 5.22 audit/ — Audit Trail
**Purpose:** Immutable events with SHA-256 hash chain, recorder, query builder, CSV/JSON export.

| Class | Key Methods |
|-------|-------------|
| `AuditRecorder` | `record()`, `verify_chain()` |
| `AuditQuery` | `filter_by_actor()`, `filter_by_resource()`, `time_range()` |

### 5.23 migration_safety/ — Migration Validation
**Purpose:** AST-based static analysis, destructive op detection, reversibility checks, configurable linter.

---

## 6. Strategy & Signals

### 6.1 strategy_optimizer/ — GA Parameter Tuning
**Purpose:** Genetic algorithm optimization of ~20 strategy parameters with composite scoring.

| Class | Key Methods |
|-------|-------------|
| `AdaptiveOptimizer` | `optimize()` → `OptimizationResult` |
| `StrategyEvaluator` | `evaluate()` → composite score (Sharpe 30%, return 20%, drawdown 20%, win rate 15%, profit factor 15%) |
| `ParameterSpace` | `add()`, `get_by_module()` |

### 6.2 regime_adaptive/ — Regime-Adaptive Strategy
**Purpose:** Dynamically adjusts trading parameters based on market regime. 4 built-in profiles.

| Class | Key Methods |
|-------|-------------|
| `RegimeAdapter` | `adapt()` — apply regime profile with smooth transitions |
| `ProfileRegistry` | `get_profile()`, `get_blended_profile()`, `register_custom()` |

**Profiles:** Bull (aggressive), Bear (defensive), Sideways (neutral), Crisis (protective)

### 6.3 agent_consensus/ — Multi-Agent Voting
**Purpose:** 10 AI agents vote on trade signals, consensus evaluation with veto support.

| Class | Key Methods |
|-------|-------------|
| `VoteCollector` | `collect_votes()` — deterministic rule-based votes from 10 agent types |
| `ConsensusEngine` | `evaluate()` → decision with approval_rate, weighted_score, veto handling |
| `DebateManager` | `conduct_debate()` — multi-round structured debate |

### 6.4 signal_fusion/ — Multi-Source Fusion
**Purpose:** Fuses 7 signal sources into unified recommendations with time decay and agreement scoring.

| Class | Key Methods |
|-------|-------------|
| `SignalFusion` | `fuse()` → `FusedSignal` (composite_score -100 to +100) |
| `TradeRecommender` | `recommend()` → STRONG_BUY/BUY/HOLD/SELL/STRONG_SELL |
| `FusionAgent` | `run_pipeline()` — full collection→fusion→recommendation |

**Sources & Weights:** EMA_CLOUD 0.25, FACTOR 0.20, SOCIAL 0.15, ML_RANKING 0.15, SENTIMENT 0.10, TECHNICAL 0.10, FUNDAMENTAL 0.05

### 6.5 signal_persistence/ — Signal Audit Trail
**Purpose:** Persists every signal, fusion, risk decision, and execution for compliance and replay.

**Record Chain:** `SignalRecord` → `FusionRecord` → `RiskDecisionRecord` → `ExecutionRecord`

### 6.6 signal_feedback/ — Adaptive Weighting
**Purpose:** Rolling Sharpe per source, adaptive weight adjustment, confidence decay for underperformers.

| Class | Key Methods |
|-------|-------------|
| `PerformanceTracker` | `record_trade()`, `get_source_performance()` |
| `WeightAdjuster` | `compute_weights()` — Sharpe-proportional allocation |
| `WeightStore` | `save_weights()`, `load_weights()` — file persistence |

### 6.7 signal_streaming/ — Real-Time Streaming
**Purpose:** Buffers high-frequency sentiment into windowed updates, broadcasts to WebSocket channels.

### 6.8 unified_risk/ — Consolidated Risk Context
**Purpose:** Single-pass risk assessment: correlation guard, VaR/CVaR sizing, regime-adaptive limits.

| Class | Key Methods |
|-------|-------------|
| `RiskContext` | `assess()` → `UnifiedRiskAssessment` (7 checks) |
| `CorrelationGuard` | `compute_matrix()` — Pearson correlation guard |
| `VaRPositionSizer` | `calculate_max_size()` — VaR-adjusted position sizing |

### 6.9 strategy_selector/ — ADX-Gated Routing
**Purpose:** Routes between EMA Cloud (trend) and mean-reversion (choppy) based on ADX strength.

| Class | Key Methods |
|-------|-------------|
| `StrategySelector` | `select()` → `StrategyChoice` |
| `ADXGate` | `compute_trend_strength()` → STRONG_TREND/MODERATE_TREND/NO_TREND/REVERSAL |
| `MeanReversionStrategy` | `generate_signal()` — RSI/Z-score/Bollinger |

### 6.10 enhanced_backtest/ — Production Backtesting
**Purpose:** Survivorship bias filter, Almgren-Chriss impact, Monte Carlo (1000+ paths), gap risk simulation.

| Class | Key Methods |
|-------|-------------|
| `MonteCarloSimulator` | `run()` → probability of profit/ruin, percentile outcomes |
| `SurvivorshipFilter` | `is_tradable()` at each date |
| `ConvexImpactModel` | `estimate_impact()` — non-linear slippage |

### 6.11 ema_signals/ — EMA Cloud Signals
**Purpose:** Ripster 4-layer EMA clouds, 10 signal types, 0-100 conviction scoring, multi-timeframe confluence.

| Class | Key Methods |
|-------|-------------|
| `SignalDetector` | `detect()` → `TradeSignal` |
| `EMACloudCalculator` | `compute_clouds()` |
| `ConvictionScorer` | `score()` → 0-100 |
| `MTFEngine` | `get_confluence()` |
| `UniverseScanner` | `scan()` |

**Signal Types:** CLOUD_CROSS_BULLISH/BEARISH, CLOUD_FLIP_BULLISH/BEARISH, CLOUD_BOUNCE_LONG/SHORT, TREND_ALIGNED_LONG/SHORT, MOMENTUM_EXHAUSTION, MTF_CONFLUENCE

### 6.12 tv_scanner/ — TradingView Scanner
**Purpose:** Live market screening via tvscreener library, 14 preset scans, custom scan builder.

**Presets:** momentum_breakout, value_stocks, oversold_bounce, volume_surge, golden_cross, death_cross, etc.

### 6.13 strategies/ — Multi-Strategy Framework
**Purpose:** BotStrategy protocol with pluggable strategies: VWAP (mean-reversion), ORB (breakout), RSI Divergence.

| Class | Key Methods |
|-------|-------------|
| `StrategyRegistry` | `register()`, `enable()`, `disable()`, `analyze_all()` |
| `BotStrategy` (Protocol) | `analyze(ticker, ohlcv)` → optional `TradeSignal` |

### 6.14 backtesting/ — Event-Driven Backtesting
**Purpose:** Professional backtesting with realistic execution, walk-forward optimization, Monte Carlo, tear sheets.

| Class | Key Methods |
|-------|-------------|
| `BacktestEngine` | `load_data()`, `run()` |
| `SimulatedBroker` | Realistic fills with slippage/commissions |
| `WalkForwardOptimizer` | `optimize()` — prevent overfitting |
| `TearSheetGenerator` | `generate()` |
| `StrategyComparator` | `compare()` — side-by-side |

### 6.15 agents/ — Multi-Agent AI
**Purpose:** 10 specialized agents with unique personalities, tool preferences, and persistent memory.

**Investment Style:** Alpha Strategist, Value Oracle, Growth Hunter, Momentum Rider, Income Architect
**Functional Role:** Research Analyst, Risk Sentinel, Portfolio Architect, Options Strategist, Market Scout

### 6.16 model_providers/ — Multi-LLM Interface
**Purpose:** Unified interface to 5 providers with tool-calling normalization and fallback chains.

| Provider | Models |
|----------|--------|
| Anthropic | Claude 3.5 Sonnet, Claude 3.5 Haiku |
| OpenAI | GPT-4o, GPT-4o mini |
| Google | Gemini Pro, Gemini Flash |
| DeepSeek | DeepSeek Chat |
| Ollama | Llama 2, Llama 3 (local) |

**Fallback Chains:** FLAGSHIP (Sonnet→GPT-4o→Gemini Pro), FAST (Haiku→mini→Flash), LOCAL (Llama)

### 6.17 influencer_intel/ — Influencer Intelligence
**Purpose:** Influencer discovery, performance tracking, co-mention network analysis, alert integration.

---

## 7. Enterprise, Tools & Brokers

### 7.1 enterprise/ — Multi-Tenant SaaS
**Purpose:** Auth (PBKDF2 + TOTP 2FA), RBAC, multi-account, workspaces, compliance, reporting.

| Class | Key Methods |
|-------|-------------|
| `AuthService` | `register()`, `login()`, `enable_totp()` |
| `AccountManager` | `create_account()`, `get_household_summary()` |
| `WorkspaceManager` | `create_workspace()`, `add_member()` |
| `ComplianceManager` | Pre-trade compliance checks |

### 7.2 paper_trading/ — Paper Trading
**Purpose:** Simulated trading sessions with data feeds, strategy automation, performance tracking.

| Class | Key Methods |
|-------|-------------|
| `SessionManager` | `create_session()`, `start_session()`, `execute_buy()`, `execute_sell()`, `advance_feed()`, `run_equal_weight_rebalance()` |
| `DataFeed` | `initialize()`, `next_tick()`, `get_price()` — simulated market data |
| `PerformanceTracker` | `compute()`, `compare_sessions()` — Sharpe, Sortino, drawdown |

**Models:** `PaperSession`, `SessionTrade`, `PortfolioPosition`, `SessionSnapshot`, `SessionMetrics`, `SessionComparison`
**Enums:** `SessionStatus` (CREATED/RUNNING/PAUSED/COMPLETED), `StrategyType`, `DataFeedType`

### 7.3 tax/ — Tax Management
**Purpose:** Tax lot management (FIFO/LIFO/MinTax), wash sale detection (30-day), Form 8949/Schedule D generation.

| Class | Key Methods |
|-------|-------------|
| `TaxLotManager` | `create_lot()`, `select_lots()`, `execute_sale()`, `adjust_lot_basis()`, `get_unrealized_gains()` |
| `WashSaleTracker` | `check_wash_sale()`, `adjust_for_wash_sale()` — 30-day IRS rule |
| `TaxLossHarvester` | `find_opportunities()`, `harvest_losses()` — substitute security suggestions |
| `TaxEstimator` | `estimate_liability()`, `project_taxes()` — federal + state + NIIT |
| `TaxReportGenerator` | `generate_form_8949()`, `generate_schedule_d()` |

**Models:** `TaxLot`, `RealizedGain`, `WashSale`, `HarvestOpportunity`, `GainLossReport`, `TaxEstimate`, `Form8949Entry`, `ScheduleD`
**Enums:** `HoldingPeriod` (SHORT_TERM/LONG_TERM), `LotSelectionMethod` (FIFO/LIFO/HIGH_COST/MAX_LOSS/MIN_TAX/SPEC_ID), `FilingStatus`

### 7.4 bots/ — Automated Trading Bots
**Purpose:** DCA, rebalancing, signal-based, and grid trading bots with cron scheduling.

| Class | Key Methods |
|-------|-------------|
| `BaseBot` (ABC) | `generate_orders()`, `execute()`, `get_positions()`, `get_performance()` |
| `DCABot` | Dollar-cost averaging with periodic allocations |
| `RebalanceBot` | Portfolio rebalancing to target weights |
| `SignalBot` | Signal-triggered order generation |
| `GridBot` | Grid trading with support/resistance levels |
| `BotScheduler` | `schedule_bot()`, `run_due_bots()` — cron-based |
| `BotEngine` | `create_bot()`, `run_bot()`, `pause_bot()`, `resume_bot()` |

**Models:** `BotOrder`, `BotExecution`, `BotPerformance`, `BotPosition`, `GridLevel`, `ScheduledRun`
**Enums:** `BotType`, `BotStatus` (ACTIVE/PAUSED/STOPPED), `ScheduleFrequency`

### 7.5 research/ — AI Research Engine
**Purpose:** Automated stock analysis, DCF/comparable valuation, competitive analysis, thesis generation.

| Class | Key Methods |
|-------|-------------|
| `ResearchEngine` | `generate_full_report()`, `format_report()` — main orchestrator |
| `FinancialAnalyzer` | `analyze()` — ratio & trend analysis |
| `ValuationEngine` | `value_stock()` — DCF & comparable valuation |
| `CompetitiveAnalyzer` | `analyze()` — moat rating, Porter's Five Forces |
| `RiskAnalyzer` | `analyze()` — multi-factor risk assessment |
| `ThesisGenerator` | `generate()`, `determine_rating()` — bull/base/bear cases, price targets, catalysts |
| `ReportGenerator` | `generate_report()`, `format_html()`, `format_markdown()` |

**Models:** `CompanyOverview`, `FinancialMetrics`, `DCFValuation`, `ComparableValuation`, `CompetitiveAnalysis`, `RiskAssessment`, `Catalyst`, `InvestmentThesis`, `ResearchReport`
**Enums:** `Rating` (STRONG_BUY/BUY/HOLD/SELL), `MoatRating`, `RiskLevel` (LOW/MEDIUM/HIGH)

### 7.6 screener/ — Stock Screener
**Purpose:** 100+ filters, custom formula expressions, saved screens, backtesting, alerts.

| Class | Key Methods |
|-------|-------------|
| `ScreenerEngine` | `run_screen()`, `validate_screen()`, `get_available_filters()` |
| `ScreenManager` | `save_screen()`, `get_screen()`, `delete_screen()`, `search_screens()`, `duplicate_screen()` |
| `ScreenAlertManager` | Alert generation on screen matches |
| `ScreenBacktester` | Backtest screen performance historically |
| `ExpressionParser` | Parse/evaluate custom formulas |

**Models:** `FilterDefinition`, `FilterCondition`, `CustomFormula`, `Screen`, `ScreenMatch`, `ScreenResult`, `ScreenBacktestResult`
**Enums:** `FilterCategory`, `Operator` (EQ/GT/LT/GTE/LTE/BETWEEN), `Universe`, `SortOrder`

### 7.7 scenarios/ — What-If Analysis
**Purpose:** Portfolio impact simulation, rebalancing scenarios, market stress testing, scenario comparison.

| Class | Key Methods |
|-------|-------------|
| `ScenarioEngine` | `create_scenario()`, `run_scenario()` |
| `WhatIfAnalyzer` | `analyze_price_change()`, `analyze_allocation_change()` — single-variable sensitivity |
| `RebalanceAnalyzer` | `analyze_rebalance()` — rebalancing impact modeling |
| `MarketScenarioAnalyzer` | `run_bull_case()`, `run_bear_case()` — pre-built scenarios |
| `ComparisonEngine` | `compare_scenarios()` — side-by-side |

**Models:** `Scenario`, `ScenarioResult`, `RebalanceScenario`, `MarketScenario`, `ScenarioComparison`

### 7.8 watchlist/ — Watchlist Manager
**Purpose:** Price targets, alerts, notes, tags, sharing, performance tracking.

| Class | Key Methods |
|-------|-------------|
| `WatchlistManager` | `create_watchlist()`, `add_symbol()`, `remove_symbol()`, `get_watchlist()` |
| `WatchlistAlerts` | Alert generation on price/technical level hits |
| `WatchlistNotes` | `add_note()`, `get_notes()` — per-symbol notes |
| `WatchlistSharing` | Share watchlists with users/teams |

**Models:** `Watchlist`, `WatchlistEntry`, `WatchlistAlert`, `WatchlistNote`

### 7.9 scanner/ — Market Scanner
**Purpose:** Real-time gap/volume/pattern detection, unusual activity identification, 14 preset scanners.

| Class | Key Methods |
|-------|-------------|
| `ScannerEngine` | `run_scan()`, `get_scan_results()` — market-wide pattern scanning |
| `UnusualActivityScanner` | Volume/price/volatility anomaly detection |
| `PatternScanner` | Technical pattern detection (gaps, reversals, breakouts) |
| `ScanPresets` | 14 built-in scans (momentum, value, growth, volume, technical, crypto) |

**Models:** `ScanResult`, `ScanMatch`, `PatternDetection`

### 7.10 journal/ — Trade Journal
**Purpose:** Trade journaling with analytics by setup, strategy, emotion, and timeframe.

| Class | Key Methods |
|-------|-------------|
| `JournalService` | `create_entry()`, `close_entry()`, `get_entries()`, `create_daily_review()`, `create_periodic_review()` |
| `JournalAnalytics` | Performance analytics by setup, strategy, emotion, timeframe |

**Models:** `JournalEntry`, `DailyReview`, `PeriodicReview`, `TradeSetup`, `TradingStrategy`

### 7.11 copilot/ — AI Copilot
**Purpose:** Claude-powered trade ideas, research summaries, portfolio analysis.

| Class | Key Methods |
|-------|-------------|
| `CopilotEngine` | `generate_insight()`, `generate_recommendation()` |
| `AnalysisModule` | Portfolio analysis, risk analysis, opportunity identification |

**Models:** `Insight`, `Recommendation`, `Analysis`

### 7.12 marketplace/ — Strategy Marketplace
**Purpose:** Strategy publishing, subscriptions, performance tracking, leaderboards, revenue sharing.

| Class | Key Methods |
|-------|-------------|
| `StrategyManager` | `create_strategy()`, `publish_strategy()`, `add_version()`, `feature_strategy()`, `get_creator_stats()` |
| `SubscriptionManager` | `subscribe()`, `unsubscribe()`, `get_subscriber_list()` |
| `PerformanceTracker` | `track_performance()`, `get_leaderboard()` |
| `StrategyDiscovery` | `search_strategies()`, `get_recommendations()` |

**Models:** `Strategy`, `StrategyVersion`, `Subscription`, `PerformanceSnapshot`, `Review`, `CreatorStats`, `LeaderboardEntry`
**Enums:** `StrategyCategory`, `PricingModel` (FREE/SUBSCRIPTION/PERFORMANCE/HYBRID), `SubscriptionStatus`

### 7.13 compliance_engine/ — Regulatory Compliance
**Purpose:** Trade surveillance (wash trades, layering, spoofing), blackout windows, best execution, regulatory reporting.

| Class | Key Methods |
|-------|-------------|
| `SurveillanceEngine` | `scan_trades()` — detects wash trades, layering, spoofing, excessive trading, marking close |
| `BlackoutManager` | `create_blackout()`, `check_blackout()` — trading blackout windows |
| `BestExecutionMonitor` | `analyze_execution()` — execution quality metrics |
| `RegulatoryReporter` | `generate_filing()` — regulatory report generation |

**Models:** `SurveillanceAlert`, `TradePattern`, `BlackoutWindow`, `PreClearanceRequest`, `BestExecutionReport`, `RegulatoryFiling`
**Enums:** `SurveillanceType` (WASH_TRADE/LAYERING/SPOOFING/EXCESSIVE_TRADING/MARKING_CLOSE), `AlertSeverity`, `BlackoutStatus`

### 7.14 system_dashboard/ — System Health
**Purpose:** Service health monitoring, metrics collection, system alerts, dependency tracking.

| Class | Key Methods |
|-------|-------------|
| `HealthChecker` | `check_service()`, `check_all_services()`, `check_data_freshness()`, `capture_snapshot()`, `get_summary()` |
| `MetricsCollector` | CPU, memory, disk, requests, response time, cache hits, DB connections |
| `SystemAlertManager` | `create_alert()`, `resolve_alert()` |

**Models:** `ServiceHealth`, `SystemMetrics`, `DataFreshness`, `HealthSnapshot`, `SystemAlert`, `DependencyStatus`, `SystemSummary`
**Enums:** `ServiceStatus` (HEALTHY/DEGRADED/DOWN), `HealthLevel`, `MetricType`

### 7.15 Broker Integrations

| Broker | Module | Key Features |
|--------|--------|-------------|
| **Alpaca** | `alpaca_live/` | Live trading, WebSocket streaming, position sync |
| **Schwab** | `schwab_broker/` | OAuth2, research tools, fundamentals |
| **Robinhood** | `robinhood_broker/` | Zero-commission, crypto, fractional shares |
| **Coinbase** | `coinbase_broker/` | Crypto-native, Advanced Trade API |
| **Fidelity** | `fidelity_broker/` | Mutual fund screening, research tools |
| **IBKR** | `ibkr_broker/` | Client Portal Gateway, forex/futures, global markets |
| **tastytrade** | `tastytrade_broker/` | Options-first, multi-leg, IV rank/percentile |
| **Webull** | `webull_broker/` | Extended hours 4am-8pm, device auth, built-in screener |
| **Multi-Broker** | `multi_broker/` | Smart routing, failover, unified portfolio view |

### 7.16 Social Platform

| Module | Purpose |
|--------|---------|
| `social_crawler/` | Multi-platform crawling (Twitter, Discord, Telegram, Reddit, WhatsApp) |
| `social_intelligence/` | Signal scoring, volume anomaly detection, influencer tracking |
| `social_backtester/` | Signal archive, outcome validation, lag correlation analysis |
| `social/` | Community social trading, profiles, copy trading, leaderboards |

### 7.17 Additional Modules

| Module | Purpose |
|--------|---------|
| `trade_attribution/` | Trade→signal linking (fuzzy match), P&L decomposition, rolling signal performance |
| `alert_network/` | Multi-channel distributed alerts with rules, throttling, quiet hours, digests |
| `alerts/` | Condition-based alerting with templates, multi-channel delivery |
| `reconciliation/` | Trade matching (exact/fuzzy), T+2 settlement tracking, break management |
| `workflow/` | State machine, multi-level approvals (single/dual/committee), templates |
| `anomaly_detection/` | Z-score, IQR, isolation forest detection; stream monitoring; pattern analysis |
| `data_contracts/` | Schema governance, backward/forward/full compatibility checks, SLA monitoring |
| `capacity/` | Resource monitoring, demand forecasting, auto-scaling policies, cost optimization |
| `blockchain/` | Blockchain settlement, token transfers, atomic swaps |
| `performance_report/` | GIPS-compliant reporting, composite returns, dispersion analysis |

---

## Architecture Patterns

| Pattern | Where Used |
|---------|-----------|
| **Singleton** | `LifecycleManager`, `AuditRecorder`, `RedisCache`, `DataService` |
| **Registry** | `ModelRegistry`, `MetricsRegistry`, `FactorRegistry`, `StrategyRegistry`, `ProviderRegistry` |
| **Bridge Adapter** | `RegimeBridge`, `FusionBridge`, `StrategyBridge`, `AlertBridge`, `FeedbackBridge` |
| **Protocol** | `BotStrategy`, `BrokerInterface` |
| **Thread-Safety** | RLock in `BotOrchestrator`, `PersistentStateManager`, `SignalGuard` |
| **Atomic Writes** | `PersistentStateManager` (write .tmp → rename) |
| **Hash Chain** | `AuditRecorder` (SHA-256 immutable audit) |
| **Pipeline** | `BotOrchestrator` (9-stage), `PipelineExecutor` (5-stage) |

---

*Generated 2026-02-09 from source code analysis of 131 modules across ~390K LOC*
