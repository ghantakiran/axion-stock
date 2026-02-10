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
**Purpose:** Advance/decline tracking, McClellan Oscillator, percent above MA, new highs/lows, sector-level breadth.

### 4.2 correlation/ — Cross-Asset Correlation
**Purpose:** Rolling correlation matrices, regime detection, pair/cluster analysis, diversification scoring.

### 4.3 volatility/ — Volatility Analytics
**Purpose:** Historical/implied vol, GARCH forecasting, vol surface (SVI calibration), skew analysis, regime detection.

### 4.4 macro/ — Macro Economic
**Purpose:** FRED indicator tracking, yield curve analysis (inversion detection), regime classification, macro factor models.

### 4.5 microstructure/ — Market Microstructure
**Purpose:** Bid-ask spread decomposition, order book analysis, tick-level analytics, VWAP/TWAP benchmarking.

### 4.6 orderflow/ — Order Flow
**Purpose:** Order flow imbalance analysis, block trade detection, buying/selling pressure measurement.

### 4.7 pairs/ — Statistical Arbitrage
**Purpose:** Cointegration testing (Engle-Granger, Johansen), spread analysis, pair scoring across universe.

### 4.8 darkpool/ — Dark Pool Analytics
**Purpose:** Dark pool volume tracking, large print analysis, block detection, liquidity estimation.

### 4.9 fundflow/ — Fund Flows
**Purpose:** ETF/mutual fund flow tracking, institutional ownership analysis, rotation detection, smart money signals.

### 4.10 crowding/ — Crowding Detection
**Purpose:** Position crowding scores, portfolio overlap analysis, short interest analytics, consensus analysis.

### 4.11 regime/ — Regime Classification
**Purpose:** Gaussian HMM, cluster-based, and ensemble regime classification (bull/bear/sideways/crisis).

### 4.12 regime_signals/ — Regime-Aware Signals
**Purpose:** Generate regime-specific signals, parameter optimization per regime, performance tracking by regime.

### 4.13 charting/ — Technical Charting
**Purpose:** 50+ indicators (SMA, EMA, RSI, MACD, Bollinger, etc.), drawing tools, templates, multi-timeframe.

### 4.14 events/ — Event-Driven Analytics
**Purpose:** Earnings analysis, M&A probability modeling, corporate action tracking, event calendar analysis.

| Class | Key Methods |
|-------|-------------|
| `EarningsAnalyzer` | `analyze()`, `predict_reaction()` |
| `MergerAnalyzer` | `compute_completion_prob()`, `estimate_arb_spread()` |
| `DealProbabilityModeler` | `estimate_completion()` |
| `EventCalendarAnalyzer` | `detect_clusters()`, `analyze_cross_event_interactions()` |

### 4.15 economic/ — Economic Calendar
**Purpose:** Economic event calendar, Fed policy monitoring, market impact analysis, economic alerts.

### 4.16 insider/ — Insider Trading
**Purpose:** Transaction tracking, cluster buying detection, institutional holdings, insider signal generation.

### 4.17 sectors/ — Sector Rotation
**Purpose:** Sector ranking, rotation pattern detection, business cycle mapping, sector recommendations.

**Cycle Phases:** EARLY_EXPANSION, MID_EXPANSION, LATE_EXPANSION, SLOWDOWN, CONTRACTION, RECOVERY

### 4.18 earnings/ — Earnings Analysis
**Purpose:** Earnings calendar, estimate revision tracking, quality assessment (Beneish M-score), post-earnings reaction analysis.

### 4.19 dividends/ — Dividend Analytics
**Purpose:** Dividend calendar, income projection, safety analysis, growth assessment, DRIP simulation, tax analysis.

### 4.20 crossasset/ — Cross-Asset Signals
**Purpose:** Intermarket relationships, lead-lag detection, cross-asset momentum, composite signal generation.

### 4.21 multi_asset/ — Crypto/Futures/International
**Purpose:** Crypto 5-factor model, futures contract management, FX hedging, cross-asset optimization.

### 4.22 credit/ — Credit Risk
**Purpose:** Credit spread modeling, default probability (Merton model), rating migration tracking, debt structure analysis.

### 4.23 esg/ — ESG Scoring
**Purpose:** ESG scoring with E/S/G pillar breakdowns, carbon metrics, impact measurement, ESG screening.

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
**Purpose:** Per-endpoint rate limiting, user quotas, analytics, versioning, request validation.

### 5.6 backup/ — Disaster Recovery
**Purpose:** Full/incremental/snapshot backups, point-in-time recovery, replication monitoring, SLA compliance.

### 5.7 profiling/ — Performance Profiling
**Purpose:** Query fingerprinting (p95/p99), N+1 detection, index recommendation, connection pool monitoring.

### 5.8 archival/ — Data Archival & GDPR
**Purpose:** Archive to Parquet, retention policies, GDPR workflows (delete/export/anonymize), lifecycle management.

### 5.9 ws_scaling/ — WebSocket Scaling
**Purpose:** Distributed connection registry, pub/sub message routing, backpressure handling, reconnection management.

### 5.10 deployment/ — Deployment Strategies
**Purpose:** Rolling/blue-green/canary deployments, traffic management, rollback engine, deployment validation.

### 5.11 event_bus/ — Event-Driven Architecture
**Purpose:** Topic-based pub/sub, immutable event store, async consumer groups, schema registry with versioning.

| Class | Key Methods |
|-------|-------------|
| `EventBus` | `subscribe()`, `publish()` |
| `EventStore` | `append()`, `get_events()`, `get_snapshot()` |
| `SchemaRegistry` | `register_schema()`, `validate()` |

### 5.12 multi_tenancy/ — Row-Level Security
**Purpose:** Tenant context (thread-local), query filters, data isolation middleware, RBAC policy engine.

### 5.13 feature_store/ — ML Feature Store
**Purpose:** Feature catalog, offline store (point-in-time), online store (cache), lineage DAG tracking.

### 5.14 secrets_vault/ — Secrets Management
**Purpose:** Encrypted vault (envelope encryption), credential rotation, access control (glob patterns), client SDK.

### 5.15 billing/ — Usage Billing
**Purpose:** Usage metering, billing engine (tiers/discounts/credits), invoice management, cost analytics.

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

### 7.3 tax/ — Tax Management
**Purpose:** Tax lot management (FIFO/LIFO/MinTax), wash sale detection (30-day), Form 8949/Schedule D generation.

### 7.4 bots/ — Automated Trading Bots
**Purpose:** DCA, rebalancing, signal-based, and grid trading bots with cron scheduling.

### 7.5 research/ — AI Research Engine
**Purpose:** Automated stock analysis, DCF/comparable valuation, competitive analysis (Porter's Five Forces), thesis generation.

### 7.6 screener/ — Stock Screener
**Purpose:** 100+ filters, custom formula expressions, saved screens, backtesting, alerts.

### 7.7 scenarios/ — What-If Analysis
**Purpose:** Portfolio impact simulation, rebalancing scenarios, stress testing, goal-based planning.

### 7.8 watchlist/ — Watchlist Manager
**Purpose:** Price targets, alerts, notes, tags, sharing, performance tracking.

### 7.9 scanner/ — Market Scanner
**Purpose:** Real-time gap/volume/pattern detection, unusual activity identification, preset scanners.

### 7.10 journal/ — Trade Journal
**Purpose:** Trade journaling with analytics by setup, strategy, and emotion.

### 7.11 copilot/ — AI Copilot
**Purpose:** Claude-powered trade ideas, research summaries, portfolio analysis.

### 7.12 marketplace/ — Strategy Marketplace
**Purpose:** Strategy publishing, subscriptions, performance tracking, leaderboards, revenue sharing.

### 7.13 compliance_engine/ — Regulatory Compliance
**Purpose:** Trade surveillance, blackout windows, best execution monitoring, regulatory reporting.

### 7.14 system_dashboard/ — System Health
**Purpose:** Service health monitoring, metrics collection, system alerts, dependency tracking.

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
