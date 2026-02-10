---
name: qullamaggie-momentum
description: >
  Qullamaggie (Kristjan Kullamagi) momentum trading strategies for the Axion
  autonomous bot. Covers breakout, episodic pivot, parabolic short setups,
  5 scanner presets, position sizing, and risk management.
metadata:
  author: axion-platform
  version: "1.0"
---

## 1. When to Use This Skill
- Swing trading momentum stocks (breakout from consolidation)
- Earnings season catalyst plays (episodic pivots)
- Shorting parabolic/exhaustion moves
- Scanning for Qullamaggie-style setups across the market
- Configuring bot strategies for autonomous momentum trading

## 2. Breakout Strategy
The core Qullamaggie setup. Prior move (30%+ gain in 1-3 months) → consolidation (2-8 weeks, tight flag, higher lows, volume contraction) → breakout on high volume.

**Entry**: Price closes above consolidation high with volume >= 1.5x average.
**Stop**: Low of day, capped at 1x ATR from entry.
**Trail**: 10 or 20 SMA (whichever acts as support).
**Conviction**: 60-90 based on volume ratio, ADR, consolidation tightness, higher lows.

Source: `src/qullamaggie/breakout_strategy.py`
Config: `src/qullamaggie/config.py` → `BreakoutConfig`

Key defaults table:
| Parameter | Default | Description |
|-----------|---------|-------------|
| prior_gain_pct | 30.0 | Min prior move % |
| consolidation_min_bars | 10 | Min consolidation duration |
| consolidation_max_bars | 60 | Max consolidation duration |
| pullback_max_pct | 25.0 | Max pullback from high |
| volume_contraction_ratio | 0.7 | Volume must contract below this |
| breakout_volume_mult | 1.5 | Breakout volume multiplier |
| adr_min_pct | 5.0 | Min Average Daily Range % |
| stop_atr_mult | 1.0 | Stop distance in ATR |
| price_min | 5.0 | Min share price |
| avg_volume_min | 300,000 | Min 20d avg volume |

## 3. Episodic Pivot (EP) Strategy
A stock from a flat base gaps up 10%+ on a catalyst with 2x+ volume.

**Entry**: Above opening range high (high of gap day).
**Stop**: Low of the gap day.
**Trail**: 10/20 EMA.
**Conviction**: 55-90 based on gap size, volume multiple, base flatness, ADR.

Source: `src/qullamaggie/episodic_pivot_strategy.py`
Config: `EpisodicPivotConfig`

Key defaults table:
| Parameter | Default | Description |
|-----------|---------|-------------|
| gap_min_pct | 10.0 | Min gap-up % |
| volume_mult_min | 2.0 | Min volume multiple |
| prior_flat_bars | 60 | Lookback for flatness |
| prior_flat_max_range_pct | 30.0 | Max range % in base |
| adr_min_pct | 3.5 | Min ADR % |
| stop_at_lod | True | Stop at low of day |

## 4. Parabolic Short Strategy
Shorting exhaustion after a 100%+ surge in under 20 bars.

**Entry**: Close of first red candle or VWAP failure.
**Stop**: High of the exhaustion day.
**Target**: 10/20 SMA.
**Conviction**: 55-90 based on surge magnitude, consecutive up days, red candle, VWAP.

Source: `src/qullamaggie/parabolic_short_strategy.py`
Config: `ParabolicShortConfig`

Key defaults table:
| Parameter | Default | Description |
|-----------|---------|-------------|
| surge_min_pct | 100.0 | Min surge % |
| surge_max_bars | 20 | Max bars for surge |
| consecutive_up_days | 3 | Min green candles |
| vwap_entry | True | Use VWAP failure |
| stop_at_hod | True | Stop at high of day |
| target_sma_period | 20 | Target SMA period |

## 5. Scanner Presets
Five presets in `src/qullamaggie/scanner.py`, also registered in `src/scanner/presets.py`:

| Preset Key | Name | Key Criteria |
|------------|------|-------------|
| qullamaggie_ep | Episodic Pivot | gap >= 10%, rel_vol >= 2x, price >= $5 |
| qullamaggie_breakout | Flag Breakout | ADX >= 25, rel_vol >= 1.5x, change > 2% |
| qullamaggie_htf | High Tight Flag | change > 3%, rel_vol >= 1x, vol > 300K |
| qullamaggie_momentum_leaders | Momentum Leaders | above 200 SMA, vol > 500K |
| qullamaggie_parabolic | Parabolic Short | RSI >= 80, change > 5%, rel_vol >= 1.5x |

## 6. Position Sizing & Risk Management
- **Risk per trade**: 0.3-0.5% of equity (configurable via `risk_per_trade`)
- **Max position**: 20% of equity for breakouts
- **Max overnight exposure**: 30% of equity
- **Stop placement**: Always defined (LOD for longs, HOD for shorts)
- **Trailing**: SMA-based (10 or 20 period) — managed by exit_monitor

## 7. Indicators
Shared helpers in `src/qullamaggie/indicators.py`:
- `compute_adr(highs, lows, period=20)` — Average Daily Range %
- `compute_atr(highs, lows, closes, period=14)` — Average True Range
- `compute_sma(values, period)` — Simple Moving Average series
- `compute_ema(values, period)` — Exponential Moving Average series
- `compute_rsi(closes, period=14)` — Relative Strength Index
- `compute_adx(highs, lows, closes, period=14)` — Average Directional Index
- `compute_vwap(highs, lows, closes, volumes)` — Volume-Weighted Average Price
- `detect_consolidation(highs, lows, closes, config)` — Flag/consolidation detection
- `detect_higher_lows(lows, lookback)` — Higher-lows pattern detection
- `volume_contraction(volumes, lookback=20)` — Volume contraction ratio

## 8. Platform Integration
- **StrategyRegistry**: All 3 strategies registered in `src/api/routes/strategies.py`
- **StrategySelector**: Qullamaggie routing added in `src/strategy_selector/selector.py` — when ADX > 25 and prior move + consolidation detected
- **StrategyBridge**: Strategy names added to `src/bot_pipeline/strategy_bridge.py`
- **Scanner**: Presets merged into `src/scanner/presets.py` PRESET_SCANNERS dict
- **Dashboard**: 4 pages in `app/pages/qullamaggie_*.py`

## 9. Key File Locations
| Component | Path |
|-----------|------|
| Module | `src/qullamaggie/` |
| Config | `src/qullamaggie/config.py` |
| Indicators | `src/qullamaggie/indicators.py` |
| Breakout | `src/qullamaggie/breakout_strategy.py` |
| Episodic Pivot | `src/qullamaggie/episodic_pivot_strategy.py` |
| Parabolic Short | `src/qullamaggie/parabolic_short_strategy.py` |
| Scanner Presets | `src/qullamaggie/scanner.py` |
| Tests | `tests/test_qullamaggie.py` |
| Dashboards | `app/pages/qullamaggie_*.py` |

## 10. See Also
- `ripster-ema-trading` — Ripster EMA Cloud strategies (complementary trend setups)
- `bot-management` — Bot lifecycle, kill switch, and pipeline control
- `trading-signal-generation` — Signal types, fusion, and persistence
- `market-scanning` — Scanner infrastructure and preset system
