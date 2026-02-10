---
name: backtesting-strategies
description: Run backtests with the event-driven BacktestEngine, EMA Cloud bot strategies via BotBacktestRunner, walk-forward optimization, Monte Carlo simulation, survivorship bias filtering, Almgren-Chriss convex market impact, gap risk simulation, and signal-type attribution. Use when validating strategies historically, running A/B signal tests, or assessing backtest robustness.
metadata:
  author: axion-platform
  version: "1.0"
---

# Backtesting Strategies

## When to use this skill

Use this skill when you need to:
- Run event-driven backtests with realistic execution modeling
- Backtest EMA Cloud bot strategies with OHLCV data
- Perform walk-forward optimization to prevent overfitting
- Run Monte Carlo simulations for confidence intervals
- Filter out survivorship bias from historical universes
- Apply convex (Almgren-Chriss) market impact models
- Simulate gap risk and stop-loss slippage
- Attribute P&L to specific signal types (cloud cross vs. bounce, etc.)
- Compare multiple strategies with tear sheet reporting

## Step-by-step instructions

### 1. Standard Event-Driven Backtest

The core backtesting engine processes bars sequentially through a Strategy protocol:

**Source files:**
- `src/backtesting/engine.py` -- BacktestEngine, Strategy protocol, HistoricalDataHandler
- `src/backtesting/config.py` -- BacktestConfig, CostModelConfig, WalkForwardConfig
- `src/backtesting/models.py` -- BarData, Signal, Order, Fill, Trade, BacktestResult
- `src/backtesting/execution.py` -- SimulatedBroker, CostModel, ExecutionSimulator
- `src/backtesting/portfolio.py` -- SimulatedPortfolio
- `src/backtesting/optimization.py` -- WalkForwardOptimizer, MonteCarloAnalyzer
- `src/backtesting/reporting.py` -- TearSheetGenerator, StrategyComparator

### 2. Bot Strategy Backtest (EMA Cloud)

For testing the autonomous trading bot's EMA cloud strategies:

**Source files:**
- `src/bot_backtesting/strategy.py` -- EMACloudStrategy adapter, StrategyConfig
- `src/bot_backtesting/runner.py` -- BotBacktestRunner, BotBacktestConfig
- `src/bot_backtesting/attribution.py` -- SignalAttributor, AttributionReport
- `src/bot_backtesting/replay.py` -- SignalReplay for risk config A/B testing

### 3. Enhanced Realism

Add production-grade realism layers on top of standard backtests:

**Source files:**
- `src/enhanced_backtest/survivorship.py` -- SurvivorshipFilter
- `src/enhanced_backtest/impact_model.py` -- ConvexImpactModel (Almgren-Chriss)
- `src/enhanced_backtest/monte_carlo.py` -- MonteCarloSimulator
- `src/enhanced_backtest/gap_simulator.py` -- GapSimulator

## Code examples

### Standard Backtest with Custom Strategy

```python
from datetime import date
from src.backtesting import (
    BacktestEngine,
    BacktestConfig,
    CostModelConfig,
    Strategy,
    Signal,
    OrderSide,
    OrderType,
    MarketEvent,
    SimulatedPortfolio,
    BacktestResult,
    TearSheetGenerator,
)

# Implement the Strategy protocol
class MomentumStrategy:
    """Simple momentum: buy when 20-day return > 5%, sell when < -3%."""

    def on_bar(self, event: MarketEvent, portfolio: SimulatedPortfolio) -> list[Signal]:
        signals = []
        for symbol, bar in event.bars.items():
            returns_20d = bar.metadata.get("return_20d", 0)
            pos = portfolio.get_position(symbol)

            if returns_20d > 0.05 and pos is None:
                signals.append(Signal(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    target_weight=0.10,
                ))
            elif returns_20d < -0.03 and pos is not None:
                signals.append(Signal(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    target_weight=0.0,
                ))
        return signals

    def on_fill(self, fill):
        pass

# Configure backtest
config = BacktestConfig(
    start_date=date(2020, 1, 1),
    end_date=date(2024, 12, 31),
    initial_capital=100_000,
    cost_model=CostModelConfig(
        commission_per_share=0.005,
        slippage_bps=2.0,
        min_commission=1.0,
    ),
)

# Run backtest
engine = BacktestEngine(config)
engine.load_data(price_data)  # Dict[str, pd.DataFrame] of OHLCV
result = engine.run(MomentumStrategy())

# Print metrics
m = result.metrics
print(f"Total Return: {m.total_return:.2%}")
print(f"CAGR: {m.cagr:.2%}")
print(f"Sharpe: {m.sharpe_ratio:.2f}")
print(f"Max Drawdown: {m.max_drawdown:.2%}")
print(f"Win Rate: {m.win_rate:.1%}")
print(f"Profit Factor: {m.profit_factor:.2f}")
print(f"Total Trades: {m.total_trades}")

# Generate tear sheet
tearsheet = TearSheetGenerator()
report = tearsheet.generate(result)
print(report)
```

### Bot EMA Cloud Backtest

```python
from src.bot_backtesting import (
    BotBacktestRunner,
    BotBacktestConfig,
    EMACloudStrategy,
    StrategyConfig,
    SignalAttributor,
    EnrichedBacktestResult,
)
from src.ema_signals import SignalType

# Configure bot backtest
config = BotBacktestConfig(
    start_date=date(2020, 1, 1),
    end_date=date(2024, 12, 31),
    initial_capital=100_000,
    tickers=["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
             "META", "TSLA", "JPM", "V", "JNJ"],
    min_conviction=50,
    enabled_signal_types=list(SignalType),  # All 10 signal types
    max_positions=10,
    max_position_weight=0.15,
    timeframe="1d",
)

# Run with OHLCV data
runner = BotBacktestRunner()
result = runner.run(
    config=config,
    ohlcv_data=ohlcv_dict,         # Dict[str, pd.DataFrame]
    benchmark=spy_price_series,     # Optional benchmark
)

# Access metrics
print(f"Return: {result.metrics.total_return:.2%}")
print(f"Sharpe: {result.metrics.sharpe_ratio:.2f}")
print(f"Trades: {result.metrics.total_trades}")

# Signal attribution: which signal types made/lost money?
report = result.attribution
print(f"\nBest signal type: {report.get_best_signal_type()}")
print(f"Worst signal type: {report.get_worst_signal_type()}")
print(f"Conversion rate: {report.conversion_rate:.1%}")

# Per-signal-type breakdown
df = report.to_dataframe()
print(df[["total_trades", "win_rate", "total_pnl", "avg_pnl", "profit_factor"]])

# Example output:
#                        total_trades  win_rate  total_pnl  avg_pnl  profit_factor
# cloud_cross_bullish           45     0.578    12500.00   277.78       1.85
# trend_aligned_long            28     0.643     8200.00   292.86       2.10
# cloud_bounce_long             32     0.500     2100.00    65.63       1.15
# momentum_exhaustion           18     0.444    -1500.00   -83.33       0.72
```

### Walk-Forward Optimization

```python
from src.backtesting import WalkForwardOptimizer, WalkForwardConfig

wf_config = WalkForwardConfig(
    n_splits=5,              # 5 in-sample/out-of-sample windows
    in_sample_pct=0.70,      # 70% training, 30% testing
    optimization_metric="sharpe_ratio",
    min_trades_per_window=20,
)

optimizer = WalkForwardOptimizer(config=wf_config)

# Define parameter grid to optimize
param_grid = {
    "min_conviction": [40, 50, 60, 70],
    "max_positions": [5, 8, 10],
    "max_position_weight": [0.10, 0.15, 0.20],
}

wf_result = optimizer.optimize(
    strategy_class=EMACloudStrategy,
    param_grid=param_grid,
    data=ohlcv_data,
    config=backtest_config,
)
print(f"Best params: {wf_result.best_params}")
print(f"In-sample Sharpe: {wf_result.in_sample_sharpe:.2f}")
print(f"Out-of-sample Sharpe: {wf_result.out_of_sample_sharpe:.2f}")
print(f"Degradation: {wf_result.degradation:.1%}")

# Per-window results
for window in wf_result.windows:
    print(f"  Window {window.period}: IS={window.in_sample_sharpe:.2f}, "
          f"OOS={window.out_of_sample_sharpe:.2f}")
```

### Monte Carlo Simulation

```python
from src.enhanced_backtest import (
    MonteCarloSimulator,
    MonteCarloConfig,
    MonteCarloResult,
)

mc_config = MonteCarloConfig(
    num_simulations=1000,
    confidence_levels=[0.05, 0.25, 0.50, 0.75, 0.95],
    shuffle_trades=True,
    resample_with_replacement=True,
    random_seed=42,
)

simulator = MonteCarloSimulator(config=mc_config)

# Run on completed trades from a backtest
mc_result = simulator.simulate(
    trades=result.trades,
    initial_equity=100_000,
)

print(f"Simulations: {mc_result.num_simulations}")
print(f"Median final equity: ${mc_result.median_final_equity:,.0f}")
print(f"P(profit): {mc_result.probability_of_profit:.1%}")
print(f"P(ruin): {mc_result.probability_of_ruin:.1%}")
print(f"Worst-case drawdown (95th pct): {mc_result.worst_case_drawdown:.1%}")
print(f"Return CI (90%): {mc_result.confidence_interval_return}")

# Percentile breakdown
for metric, pcts in mc_result.percentiles.items():
    print(f"\n{metric}:")
    for level, value in pcts.items():
        print(f"  {level}: {value:.2f}")
```

### Survivorship Bias Filter

```python
from datetime import date
from src.enhanced_backtest import SurvivorshipFilter, SurvivorshipConfig

filt = SurvivorshipFilter(SurvivorshipConfig(
    min_price=5.0,
    min_volume=500_000,
    min_market_cap=500.0,     # $500M minimum
    exclude_otc=True,
    require_continuous_data=True,
    max_gap_days=5,
))

# Register listing metadata
filt.add_listing("AAPL", listed_date=date(1980, 12, 12))
filt.add_listing("ENRON", listed_date=date(1985, 1, 1), delisted_date=date(2001, 12, 2))
filt.add_listing("TSLA", listed_date=date(2010, 6, 29))

# Bulk registration
filt.add_listings_bulk([
    {"ticker": "META", "listed_date": date(2012, 5, 18)},
    {"ticker": "COIN", "listed_date": date(2021, 4, 14)},
])

# Filter universe at a specific date in the backtest
tradable = filt.filter_universe(
    tickers=["AAPL", "ENRON", "TSLA", "META"],
    as_of=date(2023, 6, 1),
    prices={"AAPL": 180.0, "TSLA": 250.0, "META": 280.0},
    volumes={"AAPL": 50_000_000, "TSLA": 80_000_000, "META": 30_000_000},
)
# Returns ["AAPL", "TSLA", "META"] -- ENRON excluded (delisted 2001)
```

### Convex Market Impact Model (Almgren-Chriss)

```python
from src.enhanced_backtest import ConvexImpactModel, ImpactConfig

model = ConvexImpactModel(ImpactConfig(
    temporary_impact_coeff=0.1,    # eta
    permanent_impact_coeff=0.05,   # gamma
    volatility_scale=True,
    min_spread_bps=1.0,
    urgency_penalty=1.0,
))

# Estimate impact for an order
result = model.estimate(
    order_size=10_000,          # shares
    daily_volume=5_000_000,     # average daily volume
    price=185.0,                # current price
    volatility=0.02,            # daily volatility
    side="buy",
)

print(f"Total impact: {result.total_impact_bps:.1f} bps")
print(f"  Temporary: {result.temporary_impact_bps:.1f} bps")
print(f"  Permanent: {result.permanent_impact_bps:.1f} bps")
print(f"  Spread: {result.spread_cost_bps:.1f} bps")
print(f"Effective price: ${result.effective_price:.4f}")
print(f"Slippage cost: ${result.slippage_dollars:.2f}")
print(f"Participation rate: {result.participation_rate:.2%}")

# Impact formula:
#   temporary = eta * sigma * sqrt(Q/V)     -- Convex (square root)
#   permanent = gamma * sigma * (Q/V)       -- Linear
#   total = temporary + permanent + spread
```

### Signal Replay (A/B Testing Risk Configs)

```python
from src.bot_backtesting import SignalReplay, ReplayResult

replay = SignalReplay()

# Replay historical signals with different risk configurations
result_a = replay.replay(
    signal_log=historical_signals,
    ohlcv_data=ohlcv_dict,
    risk_config={"max_positions": 5, "daily_loss_limit": 0.05},
)
result_b = replay.replay(
    signal_log=historical_signals,
    ohlcv_data=ohlcv_dict,
    risk_config={"max_positions": 10, "daily_loss_limit": 0.10},
)

print(f"Config A: Return={result_a.total_return:.2%}, "
      f"Sharpe={result_a.sharpe:.2f}, DD={result_a.max_drawdown:.2%}")
print(f"Config B: Return={result_b.total_return:.2%}, "
      f"Sharpe={result_b.sharpe:.2f}, DD={result_b.max_drawdown:.2%}")
```

### Strategy Comparison

```python
from src.backtesting import StrategyComparator

comparator = StrategyComparator()
comparison = comparator.compare(
    results={
        "EMA Cloud": ema_result,
        "Momentum": momentum_result,
        "VWAP Reversion": vwap_result,
    },
    benchmark=spy_returns,
)

# Comparison table
for name, metrics in comparison.items():
    print(f"{name}: Sharpe={metrics['sharpe']:.2f}, "
          f"Return={metrics['return']:.2%}, "
          f"DD={metrics['max_dd']:.2%}")
```

## Key classes and methods

### Core Backtesting (`src/backtesting/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `BacktestEngine` | `load_data(data)`, `run(strategy)` | Event-driven backtest execution |
| `Strategy` (Protocol) | `on_bar(event, portfolio)`, `on_fill(fill)` | Strategy interface |
| `BacktestRiskManager` | `validate(signals, portfolio)`, `check_stop_losses()` | In-backtest risk rules |
| `SimulatedBroker` | `submit_order()`, `process_fills()` | Realistic order fills |
| `SimulatedPortfolio` | `get_position()`, `update()`, `drawdown` | Portfolio state tracking |
| `WalkForwardOptimizer` | `optimize(strategy_class, param_grid, data)` | Prevent overfitting |
| `MonteCarloAnalyzer` | `analyze(trades, initial_equity)` | Statistical significance |
| `TearSheetGenerator` | `generate(result)` | Performance report |
| `StrategyComparator` | `compare(results, benchmark)` | Multi-strategy comparison |

### Bot Backtesting (`src/bot_backtesting/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `EMACloudStrategy` | `on_bar()` (Strategy adapter) | Adapts EMA engine for BacktestEngine |
| `BotBacktestRunner` | `run(config, ohlcv_data, benchmark)` | OHLCV-native backtest runner |
| `SignalAttributor` | `compute(signal_log, trades)` | Per-signal-type P&L attribution |
| `SignalReplay` | `replay(signal_log, data, risk_config)` | A/B test risk configurations |

### Enhanced Realism (`src/enhanced_backtest/`)

| Class | Key Methods | Purpose |
|---|---|---|
| `SurvivorshipFilter` | `add_listing()`, `filter_universe(tickers, as_of, prices, volumes)` | Prevent survivorship bias |
| `ConvexImpactModel` | `estimate(order_size, volume, price, volatility, side)` | Almgren-Chriss impact |
| `MonteCarloSimulator` | `simulate(trades, initial_equity)` | Trade sequence permutations |
| `GapSimulator` | `simulate_gap(position, gap_event)` | Overnight/earnings gap risk |

## Common patterns

### BacktestConfig Key Defaults

```python
BacktestConfig(
    start_date=date(2020, 1, 1),
    end_date=date(2024, 12, 31),
    initial_capital=100_000,
    bar_type=BarType.DAILY,
    rebalance_frequency=RebalanceFrequency.DAILY,
)
CostModelConfig(
    commission_per_share=0.005,
    slippage_bps=2.0,
    min_commission=1.0,
    market_impact_pct=0.0,
)
WalkForwardConfig(
    n_splits=5,
    in_sample_pct=0.70,
    optimization_metric="sharpe_ratio",
)
MonteCarloConfig(
    num_simulations=1000,
    shuffle_trades=True,
    resample_with_replacement=True,
)
```

### Signal Attribution Metrics

The `SignalAttributor` produces these metrics per signal type:

| Metric | Description |
|---|---|
| `total_trades` | Trades triggered by this signal type |
| `win_rate` | Fraction of profitable trades |
| `total_pnl` | Aggregate P&L |
| `avg_pnl` | Average P&L per trade |
| `profit_factor` | Sum of wins / abs(sum of losses) |
| `avg_conviction` | Average conviction score |
| `avg_hold_bars` | Average hold duration in bars |
| `best_trade_pnl` | Largest winning trade |
| `worst_trade_pnl` | Largest losing trade |

### Realism Enhancement Layers

Apply these in order for maximum fidelity:

1. **Survivorship filter** -- Only trade tickers that were actually listed
2. **Convex impact** -- Non-linear slippage scaled by order size and volatility
3. **Gap simulator** -- Model overnight gaps and earnings surprises
4. **Monte Carlo** -- Test whether results are statistically significant

### Typical Backtest Workflow

1. Define strategy (`on_bar`, `on_fill`), configure `BacktestConfig`, run `BacktestEngine.run()`
2. Analyze `BacktestResult.metrics` (Sharpe, drawdown, win rate)
3. Run `WalkForwardOptimizer` and `MonteCarloSimulator` for robustness
4. Use `SignalAttributor` and `SignalReplay` for attribution and A/B testing
5. Generate tear sheet and apply `SurvivorshipFilter` + `ConvexImpactModel` for realism

### Bot Backtest vs. Standard Backtest

`BacktestEngine` uses a generic `Strategy` protocol with `BacktestResult`. `BotBacktestRunner` uses `EMACloudStrategy` with `EnrichedBacktestResult` (per-signal-type attribution + `SignalReplay` A/B testing).

## See Also
- **trading-signal-generation** — Signal sources and fusion weights that feed into backtests
- **risk-assessment** — Risk parameters (VaR, drawdown limits) used in backtest configuration
