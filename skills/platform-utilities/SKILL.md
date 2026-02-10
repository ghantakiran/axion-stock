---
name: platform-utilities
description: >
  Axion platform utility, data, and tool modules covering database ORM (218 tables),
  Redis caching, data services, TradingView scanner, stock screener, market scanner,
  AI copilot, paper trading, watchlists, dividends, crowding analysis, scenario
  analysis, and strategy marketplace. Use when working with data persistence layers,
  cache management, market screening and scanning, trading simulations, portfolio
  tools, or AI-assisted trading features.
metadata:
  author: axion-platform
  version: "1.0"
---

# Platform Utilities & Tools

## When to Use This Skill

- Setting up or querying the PostgreSQL/TimescaleDB database layer (ORM models, sessions, engines)
- Configuring or debugging the Redis caching layer (TTL, DataFrame serialization, JSON cache)
- Using the multi-layer data service (cache -> DB -> external API resolution)
- Running TradingView scans with preset or custom filters across 6 asset classes
- Building stock screens with 100+ filters or running real-time market scans
- Implementing AI copilot features for trade idea generation or portfolio review
- Managing paper trading sessions with simulated execution and performance tracking
- Working with watchlists, price alerts, dividend tracking, or crowding analysis
- Running what-if scenarios, rebalance simulations, or goal-based planning
- Publishing or subscribing to strategies in the marketplace

## Database & ORM Layer

Module: `src/db/` -- SQLAlchemy ORM with 218 tables in `src/db/models.py`. Async and sync engines.

```python
from src.db import (
    Base,                # Declarative base for all ORM models
    get_async_engine,    # Async SQLAlchemy engine (pool_size=20)
    get_sync_engine,     # Sync engine (backward compat)
    AsyncSessionLocal,   # Async session factory
    SyncSessionLocal,    # Sync session factory
    Instrument,          # Stock/ETF instrument record
    PriceBar,            # OHLCV price bar record
    Financial,           # Fundamental financial data
    FactorScore,         # Factor model scores
    EconomicIndicator,   # Macro economic indicators
    DataQualityLog,      # Data quality audit entries
)
```

```python
# Usage
session_factory = AsyncSessionLocal()
async with session_factory() as session:
    result = await session.execute(select(Instrument))
```

Notes: `metadata` is reserved in SQLAlchemy. Models `RegimeStateRecord`, `LiquidityScoreRecord`, `DeploymentRecord`, `TenantAuditLogRecord`, `FeatureDefinitionRecord` use `extra_metadata = Column("metadata", Text)`. Engine settings from `src/settings.py`.

## Caching Layer

Module: `src/cache/` -- Redis with async/sync dual-mode, DataFrame pickling, JSON serialization.

```python
from src.cache import RedisCache, cache  # cache is module-level singleton
```

**RedisCache methods** (each has async and sync variants):

| Method | Mode | Description |
|--------|------|-------------|
| `get_dataframe(key)` / `set_dataframe(key, df, ttl)` | async | Pickled DataFrame storage |
| `get_json(key)` / `set_json(key, data, ttl)` | async | JSON value storage |
| `get_quote(ticker)` / `set_quote(ticker, data)` | async | Stock quote shortcuts |
| `get_dataframe_sync(key)` / `set_dataframe_sync(key, df, ttl)` | sync | Sync DataFrame ops |
| `get_json_sync(key)` / `set_json_sync(key, data, ttl)` | sync | Sync JSON ops |

```python
# Async
await cache.set_dataframe("axion:prices:AAPL", price_df, ttl=3600)
# Sync
quote = cache.get_json_sync("axion:quote:AAPL")
```

## Service Layer

Module: `src/services/` -- Multi-layer data resolution: Redis (hot) -> PostgreSQL (warm) -> External API (cold).

- `DataService` (`data_service.py`) -- Async data service with cache-first resolution
- `SyncDataService` (`sync_adapter.py`) -- Sync wrapper, drop-in replacement for legacy code

```python
# Async
from src.services.data_service import DataService
service = DataService()
tickers = await service.get_universe(index="sp500")
prices = await service.get_prices(tickers, period="14mo")

# Sync (backward-compatible, same API as src/data_fetcher.py)
from src.services.sync_adapter import sync_data_service as ds
tickers = ds.build_universe()
prices = ds.download_price_data(tickers)
```

## Stock Universe

Module: `src/universe.py` (single-file) -- S&P 500 scraping and ETF universe management.

```python
from src.universe import (
    build_universe,        # Build full universe (S&P 500 + dedup)
    fetch_sp500_tickers,   # Scrape S&P 500 from Wikipedia
    fetch_sp400_tickers,   # Scrape S&P 400 MidCap
    get_etf_tickers,       # Curated equity ETF list (18 ETFs)
    EQUITY_ETFS,           # ['SPY', 'QQQ', 'IWM', 'DIA', 'VTI', ...]
)
```

## TradingView Scanner

Module: `src/tv_scanner/` -- Live screening via tvscreener library. 6 asset classes, 14 presets, custom scans, streaming, cross-module bridge.

```python
from src.tv_scanner import (
    TVScannerEngine,       # Main scanning engine
    TVDataBridge,          # Bridge to scanner/screener/EMA modules
    AssetClass,            # STOCK, CRYPTO, FOREX, BOND, FUTURES, COIN
    TVScanCategory,        # MOMENTUM, VALUE, VOLUME, TECHNICAL, GROWTH, CRYPTO
    TVScannerConfig,       # Engine configuration
    TVScanReport,          # Full scan report with TVScanResult items
    TVFilterCriterion,     # Custom filter condition
    TVPreset,              # Preset scan definition
    PRESET_TV_SCANS,       # Dict of 14 preset scans
    get_tv_preset,         # Get preset by name
    get_tv_presets_by_category,
)

engine = TVScannerEngine()
report = engine.run_preset("momentum_breakout")
for r in report.results:
    print(f"{r.symbol}: ${r.price} RSI={r.rsi} strength={r.signal_strength}")
```

**14 Presets**: momentum_breakout, relative_strength, deep_value, dividend_value, volume_surge, unusual_volume, golden_cross, oversold_bounce, ema_cloud_bullish, ema_cloud_bearish, high_growth, crypto_momentum, crypto_volume, crypto_breakout.

## Stock Screener

Module: `src/screener/` -- 100+ filters, custom formulas, saved screens, alerts, backtesting.

```python
from src.screener import (
    ScreenerEngine,        # Run screens against stock data
    ScreenManager,         # Save/load/manage screens
    FilterRegistry,        # Registry of available filters
    FILTER_REGISTRY,       # Singleton instance
    ExpressionParser,      # Custom formula parser
    Screen,                # Screen definition with filters
    FilterCondition,       # Single filter (filter_id, operator, value)
    ScreenResult,          # Full screen results
    Operator,              # LT, GT, EQ, BETWEEN, etc.
    Universe,              # SP500, SP400, RUSSELL2000, etc.
    PRESET_SCREENS,        # Built-in screens
    ScreenAlertManager,    # Alert on screen matches
    ScreenBacktester,      # Backtest screen performance
)

screen = Screen(name="Value", filters=[
    FilterCondition(filter_id="pe_ratio", operator=Operator.LT, value=15),
    FilterCondition(filter_id="dividend_yield", operator=Operator.GT, value=2.0),
])
result = ScreenerEngine().run_screen(screen, stock_data)
```

## Market Scanner

Module: `src/scanner/` -- Real-time scanning for setups, unusual activity, and chart patterns.

```python
from src.scanner import (
    ScannerEngine,             # Main scan execution engine
    create_scanner,            # Factory function
    UnusualActivityDetector,   # Unusual volume/price detection
    PatternDetector,           # Chart and candlestick patterns
    Scanner,                   # Scanner definition
    ScanCriterion,             # Single scan condition
    ScanResult,                # Scan hit result
    ScanCategory,              # GAP, MOMENTUM, VOLUME, TECHNICAL
    SignalStrength,             # WEAK, MODERATE, STRONG
    PRESET_SCANNERS,           # 10 built-in scanners
    get_preset_scanner,        # Get by name
)

engine = ScannerEngine()
engine.add_scanner(get_preset_scanner("gap_up"))
results = engine.run_scan(get_preset_scanner("gap_up"), market_data)
```

**10 Presets**: GAP_UP_SCAN, GAP_DOWN_SCAN, NEW_HIGH_SCAN, NEW_LOW_SCAN, VOLUME_SPIKE_SCAN, RSI_OVERSOLD_SCAN, RSI_OVERBOUGHT_SCAN, MACD_BULLISH_SCAN, BIG_GAINERS_SCAN, BIG_LOSERS_SCAN.

## AI Trading Copilot

Module: `src/copilot/` -- Claude-powered assistant for trade ideas, research, portfolio analysis.

```python
from src.copilot import (
    CopilotEngine,         # Main AI engine (Claude-backed)
    AnalysisModule,        # Analysis execution
    PromptBuilder,         # Prompt template builder
    CopilotConfig,         # Engine configuration
    RiskTolerance,         # CONSERVATIVE, MODERATE, AGGRESSIVE
    InvestmentStyle,       # VALUE, GROWTH, MOMENTUM, etc.
    AnalysisType,          # STOCK, SECTOR, PORTFOLIO, MARKET
    CopilotSession,        # Conversation session
    TradeIdea,             # Generated trade idea
    PortfolioContext,      # Portfolio state for AI context
    MarketContext,         # Market conditions for AI context
    AnalysisRequest,       # Analysis input
    AnalysisResponse,      # Analysis output
)
```

## Paper Trading

Module: `src/paper_trading/` -- Simulated execution, session management, performance tracking.

```python
from src.paper_trading import (
    SessionManager,        # Create/start/stop sessions, execute trades
    DataFeed,              # Simulated market data feed
    PerformanceTracker,    # Metrics calculation
    SessionConfig,         # Config (initial_capital, symbols, etc.)
    SessionStatus,         # CREATED, RUNNING, PAUSED, STOPPED
    PaperSession,          # Session state
    SessionTrade,          # Executed trade record
    PortfolioPosition,     # Current position
    SessionMetrics,        # Performance metrics
    SessionComparison,     # Compare multiple sessions
)

manager = SessionManager()
session = manager.create_session("Test", SessionConfig(
    initial_capital=100_000, symbols=["AAPL", "MSFT"],
))
manager.start_session(session.session_id)
manager.execute_buy(session.session_id, "AAPL", 100)
```

## Watchlist Management

Module: `src/watchlist/` -- CRUD, price targets, alerts, notes, tags, sharing.

```python
from src.watchlist import (
    WatchlistManager,      # Create/update/delete watchlists and items
    AlertManager,          # Price alert CRUD and evaluation
    NotesManager,          # Notes and annotations
    SharingManager,        # Share watchlists with permissions
    Watchlist,             # Watchlist container
    WatchlistItem,         # Individual watched stock
    WatchlistAlert,        # Price alert definition
    AlertType,             # PRICE_ABOVE, PRICE_BELOW, PERCENT_CHANGE
    Permission,            # VIEW, EDIT, ADMIN
    ConvictionLevel,       # 1-5 conviction rating
)
```

## Dividend Tracking

Module: `src/dividends/` -- Calendar, income projection, safety, growth, DRIP, tax analysis.

```python
from src.dividends import (
    DividendCalendar,      # Ex-date tracking, upcoming dividends
    IncomeProjector,       # Project portfolio dividend income
    SafetyAnalyzer,        # Payout ratio, coverage, safety rating
    GrowthAnalyzer,        # Dividend growth rate, streak tracking
    DRIPSimulator,         # Reinvestment simulation over time
    TaxAnalyzer,           # Qualified vs ordinary, tax impact
    DividendEvent,         # Single dividend event
    DividendHolding,       # Holding with dividend info
    PortfolioIncome,       # Projected portfolio income
    DividendFrequency,     # MONTHLY, QUARTERLY, SEMI_ANNUAL, ANNUAL
    SafetyRating,          # VERY_SAFE, SAFE, BORDERLINE, UNSAFE, CUT_RISK
)
```

## Crowding Analysis

Module: `src/crowding/` -- Position concentration, hedge fund overlap, short interest, consensus.

```python
from src.crowding import (
    CrowdingDetector,       # Position crowding score (0-100)
    OverlapAnalyzer,        # Hedge fund overlap scoring
    ShortInterestAnalyzer,  # Short squeeze risk assessment
    ConsensusAnalyzer,      # Analyst consensus divergence
    CrowdingScore,          # Score with CrowdingLevel
    ShortSqueezeScore,      # Squeeze risk with SqueezeRisk level
    CrowdingLevel,          # LOW, MODERATE, HIGH, EXTREME
    SqueezeRisk,            # LOW, MODERATE, HIGH, EXTREME
    ConsensusRating,        # STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL
    OverlapMethod,          # JACCARD, COSINE, WEIGHT_OVERLAP
)
```

## Scenario Analysis

Module: `src/scenarios/` -- What-if trades, rebalance planning, stress tests, goal planning.

```python
from src.scenarios import (
    WhatIfAnalyzer,         # Simulate proposed trades
    RebalanceSimulator,     # Test rebalance strategies
    ScenarioAnalyzer,       # Run market stress scenarios
    PortfolioComparer,      # Compare portfolio versions
    GoalPlanner,            # Goal-based financial planning
    PREDEFINED_SCENARIOS,   # Built-in market scenarios
    Portfolio,              # Portfolio with holdings and cash
    Holding,                # Individual position
    ProposedTrade,          # Hypothetical trade
    TradeAction,            # BUY, SELL
    ScenarioType,           # RECESSION, RATE_HIKE, CRASH, CUSTOM
    GoalType,               # RETIREMENT, HOUSE, EDUCATION, CUSTOM
)

portfolio = Portfolio(name="My Portfolio",
    holdings=[Holding(symbol="AAPL", shares=100, current_price=185)], cash=10_000)
result = WhatIfAnalyzer().simulate(portfolio, [
    ProposedTrade(symbol="GOOGL", action=TradeAction.BUY, dollar_amount=5000)])
```

## Strategy Marketplace

Module: `src/marketplace/` -- Publishing, discovery, subscriptions, leaderboards, reviews.

```python
from src.marketplace import (
    StrategyManager,        # Publish, version, manage strategies
    SubscriptionManager,    # Subscribe/unsubscribe, billing
    PerformanceTracker,     # Track strategy returns
    StrategyDiscovery,      # Search, filter, rank strategies
    Strategy,               # Published strategy
    Subscription,           # User subscription
    LeaderboardEntry,       # Leaderboard row
    StrategyCategory,       # MOMENTUM, VALUE, ARBITRAGE, etc.
    PricingModel,           # FREE, MONTHLY, ANNUAL, PAY_PER_TRADE
    SubscriptionStatus,     # ACTIVE, CANCELLED, EXPIRED
)
```

## Key Classes Reference

| Module | Primary Classes | Purpose |
|--------|----------------|---------|
| `src/db` | `Base`, `AsyncSessionLocal`, `SyncSessionLocal` | ORM base, session factories |
| `src/cache` | `RedisCache`, `cache` | Redis caching singleton |
| `src/services` | `DataService`, `SyncDataService` | Multi-layer data resolution |
| `src/universe` | `build_universe()`, `EQUITY_ETFS` | S&P 500 / ETF ticker lists |
| `src/tv_scanner` | `TVScannerEngine`, `TVDataBridge` | TradingView market scans |
| `src/screener` | `ScreenerEngine`, `ScreenManager`, `FilterRegistry` | Multi-criteria screening |
| `src/scanner` | `ScannerEngine`, `UnusualActivityDetector`, `PatternDetector` | Real-time scanning |
| `src/copilot` | `CopilotEngine`, `AnalysisModule`, `PromptBuilder` | AI trading assistant |
| `src/paper_trading` | `SessionManager`, `DataFeed`, `PerformanceTracker` | Simulated trading |
| `src/watchlist` | `WatchlistManager`, `AlertManager`, `SharingManager` | Watchlist CRUD + alerts |
| `src/dividends` | `DividendCalendar`, `IncomeProjector`, `DRIPSimulator` | Dividend analytics |
| `src/crowding` | `CrowdingDetector`, `ShortInterestAnalyzer`, `OverlapAnalyzer` | Position crowding |
| `src/scenarios` | `WhatIfAnalyzer`, `ScenarioAnalyzer`, `GoalPlanner` | Portfolio scenarios |
| `src/marketplace` | `StrategyManager`, `StrategyDiscovery`, `SubscriptionManager` | Strategy marketplace |

## Common Patterns

### Screening vs Scanning

- **Screener** (`src/screener/`): Fundamental + technical filters. Batch. Custom formulas. Backtesting.
- **Scanner** (`src/scanner/`): Real-time intraday gaps, patterns, unusual activity. Event-driven.
- **TV Scanner** (`src/tv_scanner/`): External TradingView data. 14 presets, 6 asset classes. No auth.

### Module Structure Convention

Every module follows: `config.py` (enums, defaults) + `models.py` (dataclasses) + engine/manager class + optional presets.

```python
from src.<module> import <Engine>, <Model>
from src.<module>.config import DEFAULT_<MODULE>_CONFIG
```
