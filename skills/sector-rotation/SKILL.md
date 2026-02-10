---
name: sector-rotation
description: Rank sectors by momentum and relative strength, detect rotation patterns (risk-on/off, inflation trade, growth-to-value), map business cycle phases to sector preferences, compute market breadth health scores, and track fund flows with smart money detection. Use when analyzing sector positioning, cycle timing, or institutional flow signals.
metadata:
  author: axion-platform
  version: "1.0"
---

# Sector Rotation Analysis

## When to use this skill

Use this skill when you need to:
- Rank the 11 GICS sectors by momentum, relative strength, or return
- Detect named rotation patterns (risk-on, risk-off, inflation trade, growth-to-value)
- Map economic indicators to business cycle phases and sector preferences
- Compute composite market breadth health scores (0-100)
- Track institutional fund flows and detect smart money accumulation/distribution
- Generate sector overweight/underweight recommendations

## Step-by-step instructions

### 1. Sector rankings and performance

`SectorRankings` in `src/sectors/rankings.py` tracks all 11 GICS sectors with ETF proxies, computes momentum scores and relative strength rankings.

```python
from src.sectors.rankings import SectorRankings
from src.sectors.config import SectorName

rankings = SectorRankings()

# Update with market data (ETF symbol -> price data dict)
rankings.update_prices({
    "XLK": {"price": 200.0, "change_1d": 1.2, "change_1w": 2.5,
            "change_1m": 5.0, "change_3m": 12.0, "volume": 8000000},
    "XLF": {"price": 38.0, "change_1d": 0.8, "change_1w": 1.5,
            "change_1m": 3.5, "change_3m": 8.0, "volume": 10000000},
    "SPY": {"price": 480.0, "change_1m": 3.0},  # Benchmark
    # ... all 11 sector ETFs
})

# Top/bottom sectors by different criteria
top = rankings.get_top_sectors(limit=5, by="momentum")
bottom = rankings.get_bottom_sectors(limit=5, by="rs")

for sector in top:
    print(f"{sector.name.value}: RS rank #{sector.rs_rank}, "
          f"momentum={sector.momentum_score:.1f}, "
          f"1M={sector.change_1m:+.1f}%")

# Filter by characteristics
cyclicals = rankings.get_cyclical_sectors()
defensives = rankings.get_defensive_sectors()
outperformers = rankings.get_outperformers()  # RS ratio > 1.0
uptrending = rankings.get_uptrending()

# Performance spread analysis
spread = rankings.get_performance_spread()
print(f"1M spread: {spread['spread_1m']:.1f}% "
      f"(best: {spread['best_1m']:.1f}%, worst: {spread['worst_1m']:.1f}%)")
```

Momentum score formula: `change_1w * 0.2 + change_1m * 0.4 + change_3m * 0.3 + rs_ratio * 10`

Sector ETF mapping: XLK (Tech), XLV (Healthcare), XLF (Financials), XLY (Cons. Disc.), XLP (Cons. Staples), XLE (Energy), XLU (Utilities), XLRE (Real Estate), XLB (Materials), XLI (Industrials), XLC (Communication).

### 2. Rotation pattern detection

`RotationDetector` in `src/sectors/rotation.py` detects named rotation patterns from sector rankings.

```python
from src.sectors.rotation import RotationDetector

detector = RotationDetector(rankings)

# Detect rotation signals
signals = detector.detect_rotation(
    min_rs_change=0.03,
    lookback_periods=1,
)

for signal in signals:
    print(f"{signal.from_sector.value} -> {signal.to_sector.value}: "
          f"{signal.signal_strength.value} (confidence={signal.confidence}%)")

# Named patterns detected
patterns = detector.get_active_patterns()
for p in patterns:
    print(f"Pattern: {p.name} - {p.description}")
    print(f"  From: {[s.value for s in p.from_sectors]}")
    print(f"  To:   {[s.value for s in p.to_sectors]}")

# Rotation summary
summary = detector.get_rotation_summary()
print(f"Direction: {summary['direction']}")  # "Risk-On", "Risk-Off", "Mixed"
print(f"Active patterns: {summary['active_patterns']}")

# Quick checks
print(f"Risk-on mode: {detector.is_risk_on()}")
print(f"Risk-off mode: {detector.is_risk_off()}")
```

Built-in rotation patterns:
| Pattern | From Sectors | To Sectors |
|---------|-------------|------------|
| Risk-On | Utilities, Staples, Healthcare | Tech, Cons. Disc., Financials |
| Risk-Off | Tech, Cons. Disc., Financials | Utilities, Staples, Healthcare |
| Inflation Trade | Tech, Cons. Disc. | Energy, Materials, Financials |
| Growth to Value | Tech, Communication | Financials, Energy, Industrials |
| Rate Sensitive | Utilities, Real Estate | Financials, Tech |

### 3. Business cycle mapping

`CycleAnalyzer` in `src/sectors/cycle.py` maps economic indicators to 5 business cycle phases and derives sector preferences.

```python
from src.sectors.cycle import CycleAnalyzer
from src.sectors.config import Trend, CyclePhase

analyzer = CycleAnalyzer()

# Set economic indicators
analyzer.set_indicators(
    gdp_trend=Trend.UP,
    employment_trend=Trend.UP,
    inflation_trend=Trend.UP,
    yield_curve_trend=Trend.NEUTRAL,
    leading_indicators=0.6,
)

# Analyze cycle phase
cycle = analyzer.analyze()
print(f"Phase: {cycle.current_phase.value}")       # "mid_expansion"
print(f"Confidence: {cycle.phase_confidence:.0f}%")
print(f"Overweight: {[s.value for s in cycle.overweight_sectors]}")
print(f"Underweight: {[s.value for s in cycle.underweight_sectors]}")

# Phase descriptions
desc = analyzer.get_phase_description()
print(desc)  # "Sustained growth, moderate inflation"

# Predict next phase
next_phase, probability = analyzer.predict_next_phase()
print(f"Next: {next_phase.value} (probability: {probability:.0%})")

# Check sector-cycle alignment
alignment = analyzer.get_sector_cycle_alignment(SectorName.TECHNOLOGY)
print(f"Tech alignment: {alignment['alignment']} (score={alignment['score']})")
```

Cycle phases: `EARLY_EXPANSION`, `MID_EXPANSION`, `LATE_EXPANSION`, `EARLY_CONTRACTION`, `LATE_CONTRACTION`. Each phase has characteristic GDP, employment, inflation, and yield curve trends.

### 4. Market breadth health scoring

`BreadthIndicators` in `src/breadth/indicators.py` computes AD line, McClellan Oscillator, breadth thrust, and new highs/lows. `HealthScorer` in `src/breadth/health.py` produces a composite 0-100 score.

```python
from src.breadth.indicators import BreadthIndicators
from src.breadth.health import HealthScorer
from src.breadth.models import AdvanceDecline, NewHighsLows
from datetime import date

indicators = BreadthIndicators()
scorer = HealthScorer()

# Process daily breadth data
snapshot = indicators.process_day(
    ad=AdvanceDecline(
        date=date.today(),
        advancing=320,
        declining=180,
        up_volume=5_000_000_000,
        down_volume=2_500_000_000,
    ),
    nhnl=NewHighsLows(
        date=date.today(),
        new_highs=150,
        new_lows=30,
    ),
)

# McClellan Oscillator and Summation Index
print(f"McClellan: {snapshot.mcclellan.oscillator}")
print(f"Summation Index: {snapshot.mcclellan.summation_index}")
print(f"Cumulative AD: {indicators.cumulative_ad_line}")

# Breadth thrust detection
if snapshot.thrust.thrust_active:
    print("BREADTH THRUST detected!")

# Composite health score
health = scorer.score(snapshot)
print(f"Health: {health.score}/100 ({health.level.value})")
print(f"Signals: {[s.value for s in health.signals]}")
print(health.summary)
```

Health levels: `VERY_BULLISH` (>= 80), `BULLISH` (>= 60), `NEUTRAL` (>= 40), `BEARISH` (>= 25), `VERY_BEARISH` (< 25).

Component weights: AD (0.25), NHNL (0.20), McClellan (0.25), Thrust (0.15), Volume (0.15).

### 5. Fund flow tracking

`FlowTracker` in `src/fundflow/tracker.py` aggregates fund flows and computes momentum and strength.

```python
from src.fundflow.tracker import FlowTracker
from src.fundflow.models import FundFlow

tracker = FlowTracker()

# Add daily flow observations
tracker.add_flow(FundFlow(
    fund_name="XLK",
    inflow=500_000_000,
    outflow=200_000_000,
    aum=50_000_000_000,
))

# Summarize
summary = tracker.summarize("XLK")
print(f"Net flow: ${summary.net_flow:,.0f}")
print(f"Flow momentum: {summary.flow_momentum:.4f}")
print(f"Avg flow as % of AUM: {summary.avg_flow_pct:.2f}%")
print(f"Strength: {summary.strength.value}")  # STRONG / MODERATE / WEAK / NEUTRAL

# Summarize all tracked funds
all_summaries = tracker.summarize_all()
```

### 6. Smart money detection

`SmartMoneyDetector` in `src/fundflow/smartmoney.py` contrasts institutional vs. retail flows to detect accumulation/distribution.

```python
from src.fundflow.smartmoney import SmartMoneyDetector

detector = SmartMoneyDetector()

result = detector.analyze(
    institutional_flows=[100, 150, 200, -50, 300],  # Daily net flows
    retail_flows=[-50, -80, -100, 200, -150],
    prices=[100.0, 99.5, 99.0, 98.0, 100.5],       # For divergence
    symbol="AAPL",
)

print(f"Smart money score: {result.smart_money_score:.4f}")  # -1 to +1
print(f"Conviction: {result.conviction:.4f}")                 # 0 to 1
print(f"Signal: {result.signal.value}")     # ACCUMULATION / DISTRIBUTION / NEUTRAL
print(f"Divergence: {result.flow_price_divergence:.4f}")
print(f"Contrarian: {result.is_contrarian}")
```

Smart money score: -1 (strong distribution) to +1 (strong accumulation). Conviction increases when institutional flows are consistent in direction and large relative to average.

## Key classes and methods

| Class | File | Key Methods |
|-------|------|-------------|
| `SectorRankings` | `src/sectors/rankings.py` | `update_prices()`, `get_top_sectors()`, `get_bottom_sectors()`, `get_outperformers()`, `get_cyclical_sectors()` |
| `RotationDetector` | `src/sectors/rotation.py` | `detect_rotation()`, `get_signals()`, `get_active_patterns()`, `get_rotation_summary()`, `is_risk_on()` |
| `CycleAnalyzer` | `src/sectors/cycle.py` | `set_indicators()`, `analyze()`, `predict_next_phase()`, `get_favored_sectors()`, `get_sector_cycle_alignment()` |
| `BreadthIndicators` | `src/breadth/indicators.py` | `process_day()`, `get_nhnl_moving_average()`, `reset()` |
| `HealthScorer` | `src/breadth/health.py` | `score()` |
| `FlowTracker` | `src/fundflow/tracker.py` | `add_flow()`, `summarize()`, `summarize_all()` |
| `SmartMoneyDetector` | `src/fundflow/smartmoney.py` | `analyze()` |

## Common patterns

### Combined sector rotation analysis

```python
# 1. Rank sectors
rankings = SectorRankings()
rankings.update_prices(price_data)

# 2. Detect rotation
rotation = RotationDetector(rankings)
signals = rotation.detect_rotation()

# 3. Map to business cycle
analyzer = CycleAnalyzer()
analyzer.set_indicators(gdp_trend=Trend.UP, employment_trend=Trend.UP,
                        inflation_trend=Trend.NEUTRAL)
cycle = analyzer.analyze()

# 4. Check breadth health
health = scorer.score(breadth_snapshot)

# 5. Combine for recommendations
favored = set(s.value for s in cycle.overweight_sectors)
top_momentum = set(s.name.value for s in rankings.get_top_sectors(3))
consensus_overweight = favored & top_momentum
```

### Key data models

- `Sector`: name, etf_symbol, price, change_1d/1w/1m/3m/6m/ytd/1y, rs_ratio, rs_rank, momentum_score, trend
- `RotationSignal`: signal_date, from_sector, to_sector, signal_strength, confidence, rs_change
- `RotationPattern`: name, from_sectors, to_sectors, is_active, confidence
- `BusinessCycle`: current_phase, phase_confidence, overweight_sectors, underweight_sectors
- `BreadthSnapshot`: advance_decline, new_highs_lows, mcclellan, thrust, signals
- `MarketHealth`: score (0-100), level, component scores, signals, summary
- `FlowSummary`: net_flow, flow_momentum, avg_flow_pct, strength
- `SmartMoneyResult`: smart_money_score, conviction, signal, flow_price_divergence, is_contrarian

### Sector config enums

- `SectorName`: TECHNOLOGY, HEALTHCARE, FINANCIALS, CONSUMER_DISC, CONSUMER_STAPLES, ENERGY, UTILITIES, REAL_ESTATE, MATERIALS, INDUSTRIALS, COMMUNICATION
- `CyclePhase`: EARLY_EXPANSION, MID_EXPANSION, LATE_EXPANSION, EARLY_CONTRACTION, LATE_CONTRACTION
- `Trend`: UP, DOWN, NEUTRAL
- `SignalStrength`: WEAK, MODERATE, STRONG
- `MarketHealthLevel`: VERY_BULLISH, BULLISH, NEUTRAL, BEARISH, VERY_BEARISH
