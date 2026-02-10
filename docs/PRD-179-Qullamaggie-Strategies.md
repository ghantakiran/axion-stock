# PRD-179: Qullamaggie Momentum Trading Strategies

## Overview

Implements Kristjan Kullamagi's (Qullamaggie) three core momentum trading strategies: **Breakout** (flag/consolidation breakout), **Episodic Pivot** (earnings gap-up), and **Parabolic Short** (exhaustion mean-reversion). Adds 5 scanner presets, indicator utilities, strategy selector routing, and 4 dashboard pages.

## Architecture

- **New module**: `src/qullamaggie/` (7 files)
- **Modified modules**: `src/strategies/`, `src/scanner/`, `src/strategy_selector/`, `src/bot_pipeline/`, `src/api/routes/`
- **Dependencies**: Scanner (PRD-08), EMA Signals (PRD-134), StrategySelector (PRD-165), StrategyBridge (PRD-173), StrategyRegistry (PRD-177)

### Signal Flow

```
Market Data (OHLCV)
  --> QullamaggieBreakoutStrategy / EpisodicPivotStrategy / ParabolicShortStrategy
    --> Indicator Engine (ADR, ATR, RSI, ADX, VWAP, consolidation detection)
    --> Conviction Scoring (60-90 range)
  --> StrategySelector (_try_qullamaggie routing, priority 75-85)
  --> StrategyBridge --> BotOrchestrator
```

## Strategies

### 1. Breakout Strategy (`src/qullamaggie/breakout_strategy.py`)

Detects flag/consolidation breakouts after a prior move of >=30% over 1-3 months.

| Parameter | Default | Description |
|-----------|---------|-------------|
| prior_gain_pct | 30 | Minimum prior move (%) |
| consolidation_min_bars | 10 | Minimum consolidation duration |
| consolidation_max_bars | 60 | Maximum consolidation duration |
| pullback_max_pct | 25 | Max pullback from high during consolidation |
| volume_contraction_ratio | 0.7 | Volume contraction threshold |
| breakout_volume_mult | 1.5 | Volume multiplier for breakout confirmation |
| adr_min_pct | 5.0 | Minimum ADR % filter |
| stop_atr_mult | 1.0 | Stop loss as ATR multiple |

**Entry**: Price breaks above consolidation high with volume >= 1.5x average.
**Stop**: Low of breakout day, capped at 1x ATR from entry.
**Trail**: 10 or 20 SMA (via exit_monitor metadata).
**Conviction**: Base 60 + volume bonus + ADR bonus + tightness bonus (capped 90).

### 2. Episodic Pivot Strategy (`src/qullamaggie/episodic_pivot_strategy.py`)

Catches gap-up moves driven by earnings/catalysts with volume explosion.

| Parameter | Default | Description |
|-----------|---------|-------------|
| gap_min_pct | 10.0 | Minimum gap-up percentage |
| volume_mult_min | 2.0 | Minimum volume multiple vs 20d avg |
| prior_flat_bars | 60 | Lookback for prior flatness check |
| adr_min_pct | 3.5 | Minimum ADR % filter |
| stop_at_lod | True | Use low of day as stop |
| earnings_only | False | Only trigger on earnings gaps |

**Entry**: Opening range high of gap day.
**Stop**: Low of the gap day.
**Conviction**: Gap size bonus + volume ratio bonus + flatness bonus (55-90).

### 3. Parabolic Short Strategy (`src/qullamaggie/parabolic_short_strategy.py`)

Identifies exhausted parabolic moves for mean-reversion short entries.

| Parameter | Default | Description |
|-----------|---------|-------------|
| surge_min_pct | 100.0 | Minimum surge percentage |
| surge_max_bars | 20 | Maximum bars for surge window |
| consecutive_up_days | 3 | Minimum consecutive green days |
| vwap_entry | True | Use VWAP as entry trigger |
| stop_at_hod | True | Use high of day as stop |
| target_sma_period | 20 | Target SMA for profit taking |

**Entry**: Close of first exhaustion bar (red candle or VWAP failure).
**Stop**: High of day.
**Target**: 10/20 SMA bounce zone.
**Direction**: Short.

## Indicators (`src/qullamaggie/indicators.py`)

| Function | Description |
|----------|-------------|
| `compute_adr(highs, lows, period=20)` | Average Daily Range as percentage |
| `compute_atr(highs, lows, closes, period=14)` | Average True Range |
| `compute_sma(values, period)` | Simple Moving Average |
| `compute_ema(values, period)` | Exponential Moving Average |
| `compute_rsi(closes, period=14)` | Relative Strength Index |
| `compute_adx(highs, lows, closes, period=14)` | Average Directional Index |
| `compute_vwap(highs, lows, closes, volumes)` | Volume-Weighted Average Price |
| `detect_consolidation(highs, lows, closes, config)` | Consolidation pattern detection |
| `detect_higher_lows(lows, lookback)` | Higher-low pattern detection |
| `volume_contraction(volumes, lookback=20)` | Volume contraction ratio |

## Scanner Presets (`src/qullamaggie/scanner.py`)

5 presets registered in the global `PRESET_SCANNERS` dict via lazy-merge:

| Preset Key | Name | Key Criteria |
|-----------|------|-------------|
| `qullamaggie_ep` | Episodic Pivot Scan | gap >= 10%, rel_vol >= 2x, price >= $5 |
| `qullamaggie_breakout` | Breakout Scan | 1M gain >= 30%, ADX >= 25, volume expanding |
| `qullamaggie_htf` | High Tight Flag | 1M gain >= 80%, pullback <= 25%, vol contraction |
| `qullamaggie_leaders` | Momentum Leaders | Above 200 SMA, ADR >= 5%, top gainers |
| `qullamaggie_parabolic` | Parabolic Scan | Up >= 100% in 20 bars, 3+ green days, RSI >= 80 |

### Lazy-Merge Pattern

Scanner presets use a deferred import to avoid circular dependency:
`src/scanner/presets.py::_ensure_extensions()` lazily imports `QULLAMAGGIE_PRESETS` from `src/qullamaggie/scanner` and merges them into `PRESET_SCANNERS` on first access.

## Integration Points

### Strategy Selector (`src/strategy_selector/selector.py`)

Added `_try_qullamaggie()` method between ADX gate and Ripster refinement:
- **Priority 85**: Breakout (consolidation detected + prior move)
- **Priority 80**: Episodic Pivot (gap >= 10% + volume explosion)
- **Priority 75**: Parabolic Short (surge + consecutive up days)

### Strategy Registry (`src/api/routes/strategies.py`)

All 3 strategies registered via `registry.register()` with category `"momentum"`.

### Bot Pipeline

- **StrategyBridge**: Updated `StrategyDecision.strategy` docstring for new names
- **FeedbackBridge**: Default weights include all 5 sources (ema_cloud, mean_reversion, + 3 Qullamaggie)
- **Orchestrator**: Signal source attribution tags positions with `_signal_source` from signal metadata

## Dashboard Pages

| Page | File | Tabs |
|------|------|------|
| Qullamaggie Breakout | `app/pages/qullamaggie_breakout.py` | Overview, Configuration, Backtest, Performance |
| Qullamaggie EP | `app/pages/qullamaggie_ep.py` | Overview, Configuration, Backtest, Performance |
| Parabolic Short | `app/pages/qullamaggie_parabolic.py` | Overview, Configuration, Backtest, Performance |
| Qullamaggie Scanner | `app/pages/qullamaggie_scanner.py` | Overview, Live Scan, Custom Scan, History |

All 4 pages added to "Trading & Execution" section in `app/nav_config.py` (total pages: 156).

## Testing

- **Test file**: `tests/test_qullamaggie.py`
- **Test count**: 77 tests across 10 classes
- **Coverage**: Imports, all 10 indicators, 3 config classes, 3 strategies (protocol compliance, signal detection, conviction scoring, edge cases), 5 scanner presets, strategy registry integration

## Files Changed

| File | Action |
|------|--------|
| `src/qullamaggie/__init__.py` | Created |
| `src/qullamaggie/config.py` | Created |
| `src/qullamaggie/indicators.py` | Created |
| `src/qullamaggie/breakout_strategy.py` | Created |
| `src/qullamaggie/episodic_pivot_strategy.py` | Created |
| `src/qullamaggie/parabolic_short_strategy.py` | Created |
| `src/qullamaggie/scanner.py` | Created |
| `src/strategies/__init__.py` | Modified |
| `src/api/routes/strategies.py` | Modified |
| `src/scanner/presets.py` | Modified |
| `src/scanner/config.py` | Modified |
| `src/strategy_selector/selector.py` | Modified |
| `src/bot_pipeline/strategy_bridge.py` | Modified |
| `app/pages/qullamaggie_breakout.py` | Created |
| `app/pages/qullamaggie_ep.py` | Created |
| `app/pages/qullamaggie_parabolic.py` | Created |
| `app/pages/qullamaggie_scanner.py` | Created |
| `app/nav_config.py` | Modified |
| `tests/test_qullamaggie.py` | Created |
| `tests/test_navigation.py` | Modified |
| `skills/qullamaggie-momentum/SKILL.md` | Created |
