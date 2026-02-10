---
name: options-analysis
description: Options pricing (Black-Scholes, Binomial, Monte Carlo) with full Greeks, IV solver, vol surface building, strategy construction (14 templates including iron condor, straddle, jade lizard), unusual activity detection, options flow classification, and 0DTE/1DTE scalping with Greeks-aware validation and strike selection. Use for pricing, strategy analysis, flow scanning, or automated scalping.
metadata:
  author: axion-platform
  version: "1.0"
---

# Options Analysis

## When to use this skill

Use this skill when you need to:
- Price options using Black-Scholes, Binomial Tree, or Monte Carlo methods
- Calculate full Greeks (delta, gamma, theta, vega, rho) and implied volatility
- Build and analyze multi-leg strategies with payoff diagrams and probability of profit
- Construct vol surfaces from chain data with SVI fitting
- Detect unusual options activity (volume spikes, OI surges, sweeps, large blocks)
- Classify options flow events and compute net premium sentiment
- Execute 0DTE/1DTE options scalps with Greeks-aware validation

## Step-by-step instructions

### 1. Options pricing with Greeks

`OptionsPricingEngine` in `src/options/pricing.py` provides Black-Scholes, Binomial Tree, and Monte Carlo pricing.

```python
from src.options.pricing import OptionsPricingEngine, OptionPrice

engine = OptionsPricingEngine()

# Black-Scholes with full Greeks
result = engine.black_scholes(
    S=100.0,          # Underlying price
    K=105.0,          # Strike price
    T=0.25,           # Time to expiry (years)
    r=0.05,           # Risk-free rate
    sigma=0.20,       # Volatility
    option_type="call",
    q=0.01,           # Dividend yield
)
print(f"Price: ${result.price:.2f}")
print(f"Delta: {result.delta:.4f}")
print(f"Gamma: {result.gamma:.4f}")
print(f"Theta: {result.theta:.4f} (per day)")
print(f"Vega:  {result.vega:.4f} (per 1% vol)")
print(f"Rho:   {result.rho:.4f}")

# Binomial Tree (supports American early exercise)
american = engine.binomial_tree(
    S=100, K=95, T=0.5, r=0.05, sigma=0.25,
    option_type="put", american=True, n_steps=200,
)
print(f"American put: ${american.price:.2f}")

# Monte Carlo (for exotic/path-dependent)
mc = engine.monte_carlo(
    S=100, K=100, T=0.25, r=0.05, sigma=0.20,
    option_type="call", n_simulations=100_000,
)

# Unified interface
result = engine.price_option(
    S=100, K=105, T=0.25, sigma=0.20,
    model="black_scholes",  # or "binomial" or "monte_carlo"
    american=False,
)
```

### 2. Implied volatility solver

Newton-Raphson IV solver built into the pricing engine:

```python
iv = engine.implied_volatility(
    market_price=5.50,
    S=100.0,
    K=105.0,
    T=0.25,
    r=0.05,
    option_type="call",
)
print(f"Implied vol: {iv:.4f}")  # ~0.2500
```

### 3. Volatility surface construction

`VolatilitySurfaceBuilder` in `src/options/volatility.py` builds IV surfaces from chain data with SVI parametrization.

```python
import pandas as pd
from src.options.volatility import VolatilitySurfaceBuilder

builder = VolatilitySurfaceBuilder()

# Build from options chain DataFrame
chain = pd.DataFrame([
    {"strike": 95, "dte": 30, "mid_price": 7.50, "option_type": "call"},
    {"strike": 100, "dte": 30, "mid_price": 4.20, "option_type": "call"},
    {"strike": 105, "dte": 30, "mid_price": 2.10, "option_type": "call"},
    {"strike": 95, "dte": 60, "mid_price": 9.00, "option_type": "call"},
    {"strike": 100, "dte": 60, "mid_price": 5.80, "option_type": "call"},
    {"strike": 105, "dte": 60, "mid_price": 3.50, "option_type": "call"},
])
surface = builder.build_from_chain(chain, spot_price=100.0, risk_free_rate=0.05)

# Interpolate IV at any point
iv = surface.get_iv(moneyness=0.95, dte=45)

# Or build from pre-computed IVs
surface = builder.build_from_ivs([
    {"moneyness": 0.90, "dte": 30, "iv": 0.28},
    {"moneyness": 1.00, "dte": 30, "iv": 0.20},
    {"moneyness": 1.10, "dte": 30, "iv": 0.22},
])

# Compute analytics
analytics = builder.compute_analytics(
    surface,
    price_history=price_series,   # For realized vol
    iv_history=iv_series,         # For IV percentile/rank
)
print(f"ATM IV: {analytics.atm_iv:.4f}")
print(f"25d skew: {analytics.iv_skew_25d:.4f}")
print(f"IV percentile: {analytics.iv_percentile:.2f}")
print(f"IV rank: {analytics.iv_rank:.2f}")
print(f"HV-IV spread: {analytics.hv_iv_spread:.4f}")
print(f"RV 30d: {analytics.realized_vol_30d:.4f}")

# Volatility cone
vol_cone = builder.get_vol_cone(price_history=price_series)
# DataFrame with columns: window, current, min, percentile_25, median, ...
```

### 4. Strategy building and analysis

`StrategyBuilder` in `src/options/strategies.py` has 14 pre-built templates and custom strategy support.

```python
from src.options.strategies import StrategyBuilder, StrategyType

builder = StrategyBuilder()

# Pre-built strategies
legs = builder.build_iron_condor(
    spot=100, put_width=10, call_width=10,
    wing_width=5, dte=30, iv=0.25,
)

legs = builder.build_bull_call_spread(spot=100, width=5, dte=30, iv=0.25)
legs = builder.build_bear_put_spread(spot=100, width=5, dte=30, iv=0.25)
legs = builder.build_straddle(spot=100, dte=30, iv=0.25)
legs = builder.build_strangle(spot=100, put_offset=5, call_offset=5, dte=30, iv=0.25)
legs = builder.build_iron_butterfly(spot=100, wing_width=10, dte=30, iv=0.25)
legs = builder.build_covered_call(spot=100, call_strike=105, dte=30, iv=0.25)
legs = builder.build_cash_secured_put(spot=100, put_strike=95, dte=30, iv=0.25)
legs = builder.build_jade_lizard(
    spot=100, put_strike=90, call_sell_strike=105,
    call_buy_strike=110, dte=30, iv=0.25,
)

# Full strategy analysis
analysis = builder.analyze(legs, spot=100, iv=0.25, name="Iron Condor")
print(f"Max profit: ${analysis.max_profit:.2f}")
print(f"Max loss:   ${analysis.max_loss:.2f}")
print(f"Breakevens: {analysis.breakeven_points}")
print(f"PoP:        {analysis.probability_of_profit:.1%}")
print(f"R/R ratio:  {analysis.risk_reward_ratio:.2f}")
print(f"Capital:    ${analysis.capital_required:.2f}")
print(f"Ann. return: {analysis.annualized_return_max:.1%}")
print(f"Net delta:  {analysis.net_delta:.4f}")
print(f"Net theta:  {analysis.net_theta:.4f}")
print(f"Net vega:   {analysis.net_vega:.4f}")

# Payoff diagram
payoff = builder.payoff_diagram(legs, spot=100, price_range_pct=0.30)
# payoff.prices: np.ndarray of underlying prices
# payoff.pnl: np.ndarray of P&L at each price
# payoff.breakeven_points: list of breakeven prices

# Monte Carlo probability of profit
pop = builder.probability_of_profit(legs, spot=100, iv=0.25, dte=30)

# Compare strategies side-by-side
comparison = builder.compare_strategies(
    strategies={
        "Iron Condor": ic_legs,
        "Straddle": straddle_legs,
        "Bull Call": bcs_legs,
    },
    spot=100, iv=0.25,
)
# Returns DataFrame with Max Profit, Max Loss, PoP, R/R, Capital, etc.
```

Available strategy templates: `build_long_call()`, `build_long_put()`, `build_covered_call()`, `build_cash_secured_put()`, `build_bull_call_spread()`, `build_bear_put_spread()`, `build_iron_condor()`, `build_iron_butterfly()`, `build_straddle()`, `build_strangle()`, `build_jade_lizard()`.

### 5. Unusual activity detection

`UnusualActivityDetector` in `src/options/activity.py` scans flow data for volume spikes, OI surges, IV spikes, large blocks, and sweeps.

```python
import pandas as pd
from src.options.activity import UnusualActivityDetector

detector = UnusualActivityDetector()

flow_data = pd.DataFrame([
    {"symbol": "AAPL", "option_type": "call", "strike": 180, "expiry": "2026-03-21",
     "volume": 15000, "oi": 2000, "premium": 500000, "iv": 0.35, "dte": 30,
     "avg_volume": 1000, "avg_oi": 1500, "iv_rank": 0.85},
])

signals = detector.scan(flow_data)
for sig in signals:
    print(f"[{sig.severity}] {sig.symbol}: {sig.signal_type} - {sig.description}")

# Put/call ratio scanning
pc_signals = detector.scan_put_call_ratio(flow_data)

# Summarize by symbol
summaries = detector.summarize(signals)
for symbol, summary in summaries.items():
    print(f"{symbol}: {summary.total_signals} signals, "
          f"sentiment={summary.net_sentiment}, "
          f"premium=${summary.total_premium:,.0f}")
```

Signal types: `VOLUME_SPIKE`, `OI_SURGE`, `IV_SPIKE`, `LARGE_BLOCK`, `SWEEP`, `PUT_CALL_SKEW`, `NEAR_EXPIRY`.

### 6. Options flow classification

`FlowDetector` in `src/options/flow.py` classifies individual flow events (sweep, block, split) and computes net sentiment.

```python
from src.options.flow import FlowDetector
from src.options.pricing import OptionType

flow = FlowDetector()

# Classify a flow event
event = flow.classify_flow(
    size=500,
    price=3.50,
    n_exchanges=4,           # Multi-exchange = sweep
    option_type=OptionType.CALL,
    strike=180.0,
    expiry_days=30,
    side="buy",
    symbol="AAPL",
)
print(f"Type: {event.flow_type.value}")      # SWEEP / BLOCK / SPLIT / NORMAL
print(f"Sentiment: {event.sentiment.value}") # BULLISH / BEARISH / NEUTRAL
print(f"Premium: ${event.premium:,.0f}")

# Detect unusual from contract data
unusual = flow.detect_unusual(contracts=option_contracts, symbol="AAPL")
for u in unusual:
    print(f"Strike {u.strike}: vol/OI={u.vol_oi_ratio:.1f}x, "
          f"level={u.activity_level.value}, score={u.score:.0f}")

# Net premium sentiment
sentiment, net_premium = flow.compute_net_sentiment()
print(f"Net sentiment: {sentiment.value}, premium: ${net_premium:,.0f}")
```

### 7. 0DTE/1DTE options scalping

`OptionsScalper` in `src/options_scalper/scalper.py` converts EMA signals into options trades with full risk controls.

```python
from src.options_scalper.scalper import OptionsScalper, ScalpConfig

scalper = OptionsScalper(config=ScalpConfig(
    scalp_tickers=["SPY", "QQQ", "NVDA", "TSLA"],
    target_delta_min=0.30,
    target_delta_max=0.50,
    max_risk_per_scalp=0.02,
    max_loss_pct=0.50,
    profit_target_pct=0.25,
    max_concurrent_scalps=3,
    max_iv_rank=0.80,
    max_theta_burn_pct=0.05,
))

# Process an EMA signal
result = scalper.process_signal(
    signal=ema_signal,
    account_equity=100_000.0,
    chain_data=option_chain,  # Optional: list of contract dicts
)

if result.success:
    pos = result.position
    print(f"Opened: {pos.direction} {pos.ticker} "
          f"${pos.strike} strike, {pos.contracts} contracts @ ${pos.entry_price}")
else:
    print(f"Rejected: {result.rejection_reason}")

# Check exits on all positions
exits = scalper.check_exits()
for exit in exits:
    print(f"Exit: {exit['reason']} - P&L: ${exit['position'].unrealized_pnl:.2f}")
```

The scalp pipeline: Signal -> StrikeSelector -> GreeksGate -> ScalpSizer -> OrderRouter.

### 8. Strike selection

`StrikeSelector` in `src/options_scalper/strike_selector.py` selects optimal strikes by delta, spread, OI, and volume.

```python
from src.options_scalper.strike_selector import StrikeSelector

selector = StrikeSelector(config=scalp_config)

selection = selector.select(
    ticker="SPY",
    direction="long",
    chain_data=option_chain,       # List of contract dicts
    underlying_price=480.0,
)

if selection:
    print(f"Strike: {selection.strike}, DTE: {selection.dte}")
    print(f"Delta: {selection.delta}, Theta: {selection.theta}")
    print(f"Mid: ${selection.mid}, Spread: {selection.spread_pct:.1%}")
    print(f"Score: {selection.score:.0f}/100")
```

Scoring: Delta proximity to 0.40 (40 pts), spread tightness (30 pts), volume (15 pts), OI (15 pts).

### 9. Greeks gate validation

`GreeksGate` in `src/options_scalper/greeks_gate.py` runs 5 checks before allowing entry.

```python
from src.options_scalper.greeks_gate import GreeksGate

gate = GreeksGate(config=scalp_config)
decision = gate.validate(selection=strike_selection, signal=ema_signal)

if decision.approved:
    print("Greeks check PASSED")
else:
    print(f"REJECTED: {decision.reason}")
    if decision.adjustments:
        print(f"Suggested: {decision.adjustments}")
```

5 checks: (1) IV rank < 80% (skip for 0DTE), (2) theta burn < 5% of premium (skip 0DTE), (3) bid-ask spread, (4) delta in range, (5) gamma < 0.15 (skip 0DTE).

## Key classes and methods

| Class | File | Key Methods |
|-------|------|-------------|
| `OptionsPricingEngine` | `src/options/pricing.py` | `black_scholes()`, `binomial_tree()`, `monte_carlo()`, `implied_volatility()`, `price_option()` |
| `VolatilitySurfaceBuilder` | `src/options/volatility.py` | `build_from_chain()`, `build_from_ivs()`, `compute_analytics()`, `get_vol_cone()` |
| `StrategyBuilder` | `src/options/strategies.py` | `build_iron_condor()`, `build_straddle()`, `analyze()`, `payoff_diagram()`, `probability_of_profit()`, `compare_strategies()` |
| `UnusualActivityDetector` | `src/options/activity.py` | `scan()`, `scan_put_call_ratio()`, `summarize()` |
| `FlowDetector` | `src/options/flow.py` | `classify_flow()`, `detect_unusual()`, `compute_net_sentiment()` |
| `OptionsScalper` | `src/options_scalper/scalper.py` | `process_signal()`, `check_exits()` |
| `StrikeSelector` | `src/options_scalper/strike_selector.py` | `select()` |
| `GreeksGate` | `src/options_scalper/greeks_gate.py` | `validate()` |

## Common patterns

### Strategy analysis workflow

```python
engine = OptionsPricingEngine()
builder = StrategyBuilder(pricing_engine=engine)

# Build and compare multiple strategies
strats = {
    "Iron Condor": builder.build_iron_condor(spot=480, dte=30, iv=0.18),
    "Straddle": builder.build_straddle(spot=480, dte=30, iv=0.18),
    "Bull Call": builder.build_bull_call_spread(spot=480, width=5, dte=30, iv=0.18),
}
comparison = builder.compare_strategies(strats, spot=480, iv=0.18)
```

### Unusual activity scanning pipeline

```python
# 1. Scan for unusual activity
detector = UnusualActivityDetector()
signals = detector.scan(flow_df)

# 2. Classify individual flows
flow_det = FlowDetector()
for _, row in large_trades.iterrows():
    event = flow_det.classify_flow(
        size=row["volume"], price=row["premium"],
        n_exchanges=row["exchanges"], option_type=OptionType.CALL,
        side="buy", symbol=row["symbol"],
    )

# 3. Compute net sentiment
sentiment, net = flow_det.compute_net_sentiment()
```

### Key data models

- `OptionPrice`: price, delta, gamma, theta, vega, rho, option_type, model
- `OptionLeg`: option_type, strike, premium, quantity, expiry_days, iv, greeks
- `StrategyAnalysis`: max_profit, max_loss, breakevens, PoP, R/R, net Greeks
- `VolAnalytics`: atm_iv, iv_skew_25d, iv_percentile, iv_rank, hv_iv_spread
- `ActivitySignal`: symbol, signal_type, severity, volume, premium, description
- `OptionsFlow`: flow_type (SWEEP/BLOCK/SPLIT/NORMAL), sentiment, premium
- `ScalpPosition`: ticker, option_symbol, strike, contracts, entry_price, delta, theta, pnl
- `StrikeSelection`: strike, expiry, dte, delta, theta, iv, mid, spread_pct, score
- `GreeksDecision`: approved (bool), reason, adjustments

## See Also
- **order-execution** — InstrumentRouter handles options order routing and Greeks validation
- **broker-integration** — Options-first brokers (tastytrade, IBKR) with multi-leg order support
- **risk-assessment** — Greeks-based risk checks for options positions
