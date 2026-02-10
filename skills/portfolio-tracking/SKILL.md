---
name: axion-portfolio-tracking
description: >
  Build portfolio tracking features on the Axion trading platform using five
  integrated modules: watchlists with price alerts, a trade journal with
  analytics, paper-trading sessions with simulated execution, scenario
  analysis (what-if, rebalance, stress-test, goal planning), and an
  AI-powered copilot that generates trade ideas and portfolio reviews.
  Covers CRUD, performance metrics, emotion analysis, and Monte Carlo
  projections.
metadata:
  author: Axion Platform Team
  version: 1.0.0
---

# Portfolio Tracking on the Axion Platform

## When to use this skill

Use this skill when you need to:

- Create, manage, or query watchlists with price targets, alerts, and sharing.
- Record trades in a journal, close positions, and analyze performance by setup, strategy, day-of-week, or emotion.
- Run paper-trading sessions with simulated order execution, data feeds, and snapshot-based performance tracking.
- Perform what-if trade simulations, portfolio rebalancing, market stress tests, or goal-based financial planning.
- Interact with the AI Trading Copilot for trade ideas, symbol research, portfolio reviews, or market outlook.

## Step-by-step instructions

### 1. Watchlist management

Create a watchlist, add symbols with price targets, set alerts, and calculate performance.

```python
from src.watchlist import (
    WatchlistManager, AlertManager, NotesManager, SharingManager,
    Watchlist, WatchlistItem, AlertType, Permission,
)

# Initialize manager
manager = WatchlistManager()

# Create a watchlist
watchlist = manager.create_watchlist(
    name="Tech Stocks",
    description="Core technology holdings",
    is_default=True,
)

# Add items with conviction and price targets
manager.add_item(
    watchlist.watchlist_id,
    symbol="AAPL",
    company_name="Apple Inc.",
    current_price=185.0,
    buy_target=170.0,
    sell_target=200.0,
    conviction=4,
    tags=["mega-cap", "tech"],
)

# Set or update price targets
manager.set_targets(
    watchlist.watchlist_id, "AAPL",
    buy_target=168.0, sell_target=210.0, stop_loss=155.0,
)

# Bulk price update (symbol -> (price, change, change_pct))
manager.update_prices(watchlist.watchlist_id, {
    "AAPL": (192.0, 7.0, 0.038),
})

# Search across all watchlists
results = manager.search_items("apple")  # returns [(watchlist_id, WatchlistItem)]

# Filter by conviction level
high_conviction = manager.filter_by_conviction(watchlist.watchlist_id, min_conviction=4)

# Calculate watchlist performance
perf = manager.calculate_performance(watchlist.watchlist_id)
# perf.win_rate, perf.hypothetical_return_pct, perf.top_performers

# Set up price alerts
alert_mgr = AlertManager()
alert = alert_mgr.create_alert(
    watchlist_id=watchlist.watchlist_id,
    symbol="AAPL",
    alert_type=AlertType.PRICE_BELOW,
    threshold=170.0,
)

# Check alerts against live data
notifications = alert_mgr.check_alerts({"AAPL": {"price": 168.0}})
```

### 2. Trade journal

Record trades with emotional state, compute analytics, and generate insights.

```python
from datetime import datetime, date
from src.journal import JournalService, JournalAnalytics

# Requires a SQLAlchemy session
# service = JournalService(session=db_session)

# Initialize default setups (breakout, pullback, reversal, etc.)
service.initialize_default_setups()

# Create a trading strategy
strategy = service.create_strategy(
    name="EMA Cloud Trend",
    description="Follow EMA cloud crossover signals",
    entry_rules=["Cloud bullish crossover", "RSI > 50"],
    exit_rules=["Cloud bearish crossover", "Stop hit"],
    max_risk_per_trade=0.02,
    target_risk_reward=2.0,
)

# Create a journal entry
entry = service.create_entry(
    symbol="AAPL",
    direction="long",
    entry_date=datetime(2026, 2, 3, 10, 30),
    entry_price=185.0,
    entry_quantity=100,
    trade_type="swing",
    setup_id="breakout",
    strategy_id=strategy.strategy_id,
    pre_trade_emotion="confident",
    initial_stop=178.0,
    initial_target=200.0,
    tags=["tech", "earnings"],
    notes="Strong volume breakout above resistance",
)

# Close the trade
closed = service.close_entry(
    entry_id=entry.entry_id,
    exit_date=datetime(2026, 2, 7, 15, 45),
    exit_price=198.0,
    exit_reason="target_reached",
    fees=2.0,
    post_trade_emotion="satisfied",
    lessons_learned="Held to target despite pullback on day 2",
)
# closed.realized_pnl, closed.realized_pnl_pct, closed.risk_reward_actual

# Query entries with filters
entries = service.get_entries(
    symbol="AAPL", setup_id="breakout", open_only=False, limit=50,
)

# Create a daily review
review = service.create_daily_review(
    review_date=date(2026, 2, 7),
    followed_plan=True,
    mistakes_made=["Entered too large on second trade"],
    did_well=["Held winner to target"],
    overall_rating=4,
)

# --- Analytics ---
analytics = JournalAnalytics(session=db_session)

# Overall metrics
metrics = analytics.get_overall_metrics()
# metrics.win_rate, metrics.profit_factor, metrics.expectancy

# Breakdown by setup
by_setup = analytics.get_breakdown_by_setup()
# Each item: DimensionBreakdown(dimension, category, metrics)

# Breakdown by day of week
by_day = analytics.get_breakdown_by_day_of_week()

# Emotion analysis
emotions = analytics.analyze_emotions()
# emotions["pre_trade"] -> list of EmotionAnalysis

# Equity curve as DataFrame
equity_df = analytics.get_equity_curve()

# Drawdown analysis
dd = analytics.get_drawdown_analysis()
# dd["max_drawdown"], dd["max_drawdown_pct"]

# Auto-generated insights
insights = analytics.generate_insights()
# Each: PatternInsight(insight_type, title, description, confidence, supporting_data)

# Streak analysis
streaks = analytics.get_streak_analysis()
# streaks["max_win_streak"], streaks["current_streak"]

# R-multiple distribution
r_dist = analytics.get_r_multiple_distribution()
# r_dist["avg_r"], r_dist["median_r"]
```

### 3. Paper trading

Create sessions, execute simulated trades, track snapshots, and measure performance.

```python
from src.paper_trading import (
    SessionManager, SessionConfig, SessionStatus,
    DataFeedConfig, StrategyConfig, StrategyType,
)

manager = SessionManager()

# Create a session with custom config
session = manager.create_session(
    name="EMA Strategy Test",
    config=SessionConfig(
        initial_capital=100_000,
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN"],
        benchmark="SPY",
    ),
)

# Start the session
manager.start_session(session.session_id)

# Execute trades
buy = manager.execute_buy(session.session_id, "AAPL", qty=100, reason="signal")
sell = manager.execute_sell(session.session_id, "AAPL", qty=50, reason="take_profit")
# sell.pnl, sell.pnl_pct

# Advance the simulated data feed
prices = manager.advance_feed(session.session_id)

# Record portfolio snapshot for performance tracking
snapshot = manager.record_snapshot(session.session_id)
# snapshot.equity, snapshot.drawdown, snapshot.daily_return

# Run equal-weight rebalance
trades = manager.run_equal_weight_rebalance(session.session_id)

# Pause / resume / stop
manager.pause_session(session.session_id)
manager.resume_session(session.session_id)
manager.stop_session(session.session_id)  # computes final metrics

# Get performance metrics
metrics = manager.get_metrics(session.session_id)
# metrics["total_return"], metrics["sharpe_ratio"], metrics["max_drawdown"]

# Compare multiple sessions
comparison = manager.compare_sessions([session1.session_id, session2.session_id])
# comparison["winner_by_metric"], comparison["ranking"]

# List sessions
active = manager.list_sessions(status=SessionStatus.RUNNING)
```

### 4. Scenario analysis

Simulate trades, rebalance portfolios, run stress tests, and plan goals.

```python
from src.scenarios import (
    WhatIfAnalyzer, RebalanceSimulator, ScenarioAnalyzer, GoalPlanner,
    PortfolioComparer, PREDEFINED_SCENARIOS,
    Portfolio, Holding, ProposedTrade, TradeAction,
    TargetAllocation, InvestmentGoal, RebalanceStrategy,
)

# Build a portfolio
portfolio = Portfolio(
    name="My Portfolio",
    holdings=[
        Holding(symbol="AAPL", shares=100, current_price=185.0, cost_basis=15000),
        Holding(symbol="MSFT", shares=50, current_price=378.0, cost_basis=17000),
    ],
    cash=10_000,
)

# --- What-If Analysis ---
analyzer = WhatIfAnalyzer()
trade = ProposedTrade(symbol="GOOGL", action=TradeAction.BUY, dollar_amount=5000)
result = analyzer.simulate(portfolio, [trade])
# result.resulting_portfolio, result.risk_impact, result.tax_impact, result.total_cost

# Quick helpers
buy_sim = analyzer.quick_buy(portfolio, "NVDA", amount=3000, price=850.0)
sell_sim = analyzer.quick_sell(portfolio, "AAPL", sell_all=True)

# --- Rebalancing ---
rebal = RebalanceSimulator()
target = TargetAllocation(targets={"AAPL": 0.40, "MSFT": 0.40, "GOOGL": 0.20})
rebal_result = rebal.simulate(portfolio, target)
# rebal_result.required_trades, rebal_result.turnover

# --- Market Stress Tests ---
scenario_analyzer = ScenarioAnalyzer()
result = scenario_analyzer.run_scenario(portfolio, PREDEFINED_SCENARIOS["covid_crash"])
# result.portfolio_impact, result.position_impacts

# --- Goal Planning ---
planner = GoalPlanner()
goal = InvestmentGoal(
    name="Retirement",
    target_amount=1_000_000,
    target_date=date(2045, 1, 1),
    current_amount=100_000,
    monthly_contribution=1000,
)
projection = planner.project_goal(goal, monte_carlo=True)
# projection.probability_of_success, projection.projected_balance

# --- Portfolio Comparison ---
comparer = PortfolioComparer()
comparison = comparer.compare([portfolio_a, portfolio_b])
# comparison.metrics_table, comparison.winner_by_metric
```

### 5. AI Trading Copilot

Chat with the copilot, get trade ideas, research symbols, and review portfolios.

```python
from src.copilot import (
    CopilotEngine, AnalysisModule,
    CopilotPreferences, PortfolioContext, MarketContext,
    AnalysisType, RiskTolerance, InvestmentStyle,
)

engine = CopilotEngine()

# Create a session
session = engine.create_session(user_id="user_123")

# Set user preferences
prefs = CopilotPreferences(
    user_id="user_123",
    risk_tolerance=RiskTolerance.MODERATE,
    investment_style=InvestmentStyle.GROWTH,
)
engine.set_preferences(prefs)

# Chat interaction
response = engine.chat(
    session_id=session.session_id,
    user_message="What do you think about AAPL?",
    portfolio=PortfolioContext(total_value=250_000),
    market=MarketContext(spy_change_pct=0.5),
)
# response.content, response.extracted_symbols, response.extracted_actions

# Generate a trade idea
idea = engine.generate_trade_idea(
    user_id="user_123",
    sector="technology",
)
# idea.symbol, idea.action, idea.entry_price, idea.target_price, idea.stop_loss

# High-level analysis module
analysis = AnalysisModule(engine=engine)
research = analysis.research_symbol("NVDA")
# research.content, research.trade_ideas, research.confidence_score

review = analysis.review_portfolio(
    portfolio=PortfolioContext(total_value=250_000, holdings_summary="AAPL 40%, MSFT 30%"),
)

ideas = analysis.generate_trade_ideas(preferences=prefs, count=3)
```

## Key classes and methods

| Module | Class | Key Methods |
|--------|-------|-------------|
| `src.watchlist` | `WatchlistManager` | `create_watchlist()`, `add_item()`, `set_targets()`, `update_prices()`, `search_items()`, `filter_by_conviction()`, `calculate_performance()` |
| `src.watchlist` | `AlertManager` | `create_alert()`, `check_alerts()`, `subscribe()` |
| `src.watchlist` | `NotesManager` | Note CRUD for watchlist items |
| `src.watchlist` | `SharingManager` | Share watchlists with permissions |
| `src.journal` | `JournalService` | `create_entry()`, `close_entry()`, `get_entries()`, `create_daily_review()`, `create_periodic_review()`, `create_strategy()`, `initialize_default_setups()` |
| `src.journal` | `JournalAnalytics` | `get_overall_metrics()`, `get_breakdown_by_setup()`, `get_breakdown_by_strategy()`, `get_breakdown_by_day_of_week()`, `get_breakdown_by_hour()`, `analyze_emotions()`, `get_equity_curve()`, `get_drawdown_analysis()`, `generate_insights()`, `get_streak_analysis()`, `get_r_multiple_distribution()` |
| `src.paper_trading` | `SessionManager` | `create_session()`, `start_session()`, `pause_session()`, `stop_session()`, `execute_buy()`, `execute_sell()`, `advance_feed()`, `record_snapshot()`, `run_equal_weight_rebalance()`, `get_metrics()`, `compare_sessions()` |
| `src.paper_trading` | `PerformanceTracker` | `compute()`, `compare_sessions()` |
| `src.paper_trading` | `DataFeed` | `initialize()`, `get_price()`, `next_tick()` |
| `src.scenarios` | `WhatIfAnalyzer` | `simulate()`, `quick_buy()`, `quick_sell()` |
| `src.scenarios` | `RebalanceSimulator` | `simulate()` |
| `src.scenarios` | `ScenarioAnalyzer` | `run_scenario()` |
| `src.scenarios` | `GoalPlanner` | `project_goal()` |
| `src.scenarios` | `PortfolioComparer` | `compare()` |
| `src.copilot` | `CopilotEngine` | `create_session()`, `chat()`, `analyze()`, `generate_trade_idea()`, `set_preferences()`, `get_preferences()` |
| `src.copilot` | `AnalysisModule` | `research_symbol()`, `review_portfolio()`, `generate_trade_ideas()` |
| `src.copilot` | `PromptBuilder` | `build_system_prompt()`, `build_analysis_prompt()`, `extract_symbols()`, `extract_trade_action()` |

## Common patterns

### Dataclass models

All modules use dataclass models for data transport. Key models to know:

- **Watchlist**: `Watchlist`, `WatchlistItem`, `WatchlistAlert`, `AlertNotification`, `WatchlistPerformance`
- **Journal**: `PerformanceMetrics`, `DimensionBreakdown`, `EmotionAnalysis`, `PatternInsight` (from `src.journal.analytics`)
- **Paper Trading**: `PaperSession`, `SessionTrade`, `PortfolioPosition`, `SessionSnapshot`, `SessionMetrics`, `SessionComparison`
- **Scenarios**: `Portfolio`, `Holding`, `ProposedTrade`, `TradeSimulation`, `RiskImpact`, `TaxImpact`, `RebalanceSimulation`, `InvestmentGoal`, `GoalProjection`
- **Copilot**: `CopilotSession`, `CopilotMessage`, `TradeIdea`, `AnalysisRequest`, `AnalysisResponse`, `PortfolioContext`, `MarketContext`

### Enum-based configuration

Each module exposes enums for type-safe configuration:

```python
from src.watchlist.config import AlertType        # PRICE_ABOVE, PRICE_BELOW, PCT_CHANGE, VOLUME_SPIKE
from src.paper_trading.config import SessionStatus # CREATED, RUNNING, PAUSED, COMPLETED
from src.paper_trading.config import StrategyType  # MANUAL, EQUAL_WEIGHT, MOMENTUM, MEAN_REVERSION
from src.scenarios.config import TradeAction       # BUY, SELL, SELL_ALL
from src.scenarios.config import RebalanceStrategy # TARGET_WEIGHT, THRESHOLD, CALENDAR
from src.scenarios.config import GoalType          # RETIREMENT, EDUCATION, HOUSE, EMERGENCY, CUSTOM
from src.copilot.config import AnalysisType        # TRADE_IDEA, PORTFOLIO_REVIEW, SYMBOL_RESEARCH, MARKET_OUTLOOK, RISK_CHECK
from src.copilot.config import RiskTolerance       # CONSERVATIVE, MODERATE, AGGRESSIVE
from src.copilot.config import InvestmentStyle     # VALUE, GROWTH, MOMENTUM, INCOME, BALANCED
```

### Journal requires a database session

`JournalService` and `JournalAnalytics` both require a SQLAlchemy `Session` object. ORM models are defined in `src/db/models.py`: `JournalEntry`, `DailyReview`, `PeriodicReview`, `TradeSetup`, `TradingStrategy`.

### In-memory vs. persistent state

- `WatchlistManager`, `SessionManager`, and `CopilotEngine` store state in-memory (dictionaries). For persistence, integrate with the ORM layer in `src/db/models.py`.
- `JournalService` persists to PostgreSQL via SQLAlchemy.

### Cross-module integration

Combine modules for a complete workflow:

```python
# Watchlist -> Copilot research -> Scenario analysis -> Paper trade
symbol = "NVDA"

# 1. Add to watchlist
manager.add_item(wl.watchlist_id, symbol, current_price=850.0)

# 2. Get AI research
research = analysis_module.research_symbol(symbol)

# 3. Simulate the trade
sim = what_if.quick_buy(portfolio, symbol, amount=5000, price=850.0)

# 4. Paper trade if risk is acceptable
if sim.risk_impact.beta_change < 0.1:
    paper_mgr.execute_buy(session_id, symbol, qty=5, reason="copilot_idea")
```
