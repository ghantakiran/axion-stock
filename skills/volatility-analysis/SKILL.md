---
name: volatility-analysis
description: Multi-method volatility estimation (historical, EWMA, Parkinson, Garman-Klass), SVI surface calibration, skew analytics (risk reversal, butterfly, skew regime), Nelson-Siegel term structure modeling with carry/roll-down analysis, and vol regime detection with trading signals. Use when pricing vol, analyzing surfaces, or building vol-based strategies.
metadata:
  author: axion-platform
  version: "1.0"
---

# Volatility Analysis

## When to use this skill

Use this skill when you need to:
- Estimate realized volatility using multiple methods (close-to-close, EWMA, Parkinson, Garman-Klass)
- Build volatility cones and compute vol percentiles
- Calibrate SVI (Stochastic Volatility Inspired) surfaces to market IV data
- Analyze vol skew dynamics, risk reversals, and butterfly spreads
- Fit Nelson-Siegel term structure models with carry/roll-down analysis
- Detect volatility regimes (LOW, NORMAL, HIGH, EXTREME) and generate trading signals
- Compute vol-of-vol, mean-reversion signals, and regime transition signals

## Step-by-step instructions

### 1. Multi-method volatility estimation

`VolatilityEngine` in `src/volatility/engine.py` computes annualized vol using 4 estimators.

```python
import pandas as pd
from src.volatility.engine import VolatilityEngine
from src.volatility.config import VolMethod

engine = VolatilityEngine()

# Close-to-close historical vol
hist = engine.compute_historical(returns=log_returns, window=21, symbol="SPY")
print(f"Historical vol: {hist.value:.4f}")  # Annualized

# EWMA vol (exponentially weighted, default lambda=0.94)
ewma = engine.compute_ewma(returns=log_returns, lambda_=0.94, symbol="SPY")

# Parkinson high-low estimator (more efficient than close-to-close)
park = engine.compute_parkinson(high=high_series, low=low_series, window=21, symbol="SPY")

# Garman-Klass OHLC estimator (most efficient single-day estimator)
gk = engine.compute_garman_klass(
    open_=open_series, high=high_series, low=low_series, close=close_series,
    window=21, symbol="SPY",
)

# Compute all available estimators at once
all_vols = engine.compute_all(
    returns=log_returns, high=high_series, low=low_series,
    open_=open_series, close=close_series, symbol="SPY",
)
for method, estimate in all_vols.items():
    print(f"  {method.value}: {estimate.value:.4f}")
```

### 2. Volatility cones and percentiles

```python
# Vol cone: percentile bands across multiple windows
cone = engine.compute_vol_cone(returns=log_returns, symbol="SPY")
for point in cone:
    print(f"  {point.window}d: current={point.current:.4f}, "
          f"percentiles={point.percentiles}")

# Where does current vol sit historically?
percentile = engine.compute_percentile(
    current_vol=0.18, returns=log_returns, window=21,
)
print(f"Vol percentile: {percentile:.1f}th")  # 0-100

# Implied vs realized comparison
ivr = engine.implied_vs_realized(implied_vol=0.22, realized_vol=0.18)
print(f"Spread: {ivr['spread']:.4f}, Ratio: {ivr['ratio']:.3f}, "
      f"Premium: {ivr['premium_pct']:.1f}%")

# Term structure from realized vol
ts = engine.compute_term_structure(
    returns=log_returns,
    tenor_days=(5, 10, 21, 63, 126, 252),
    iv_by_tenor={21: 0.20, 63: 0.22, 126: 0.23},
    symbol="SPY",
)
for pt in ts.points:
    print(f"  {pt.tenor_days}d: RV={pt.realized_vol}, IV={pt.implied_vol}")
```

### 3. Vol surface construction and analysis

`VolSurfaceAnalyzer` in `src/volatility/surface.py` builds surfaces from strike x tenor IV data.

```python
from src.volatility.surface import VolSurfaceAnalyzer

analyzer = VolSurfaceAnalyzer()

# Build surface from IV data: {tenor_days -> [(strike, iv), ...]}
surface = analyzer.build_surface(
    iv_data={
        30: [(90, 0.28), (95, 0.24), (100, 0.20), (105, 0.19), (110, 0.21)],
        60: [(90, 0.26), (95, 0.23), (100, 0.21), (105, 0.20), (110, 0.22)],
    },
    spot=100.0,
    symbol="SPY",
)

# Compute skew (OTM put vol - OTM call vol)
skew = analyzer.compute_skew(surface, tenor_days=30)

# Butterfly (avg wing vol - ATM vol)
butterfly = analyzer.compute_butterfly(surface, tenor_days=30)

# ATM term structure extraction
atm_ts = analyzer.atm_term_structure(surface)
for tenor, atm_vol in atm_ts:
    print(f"  {tenor}d ATM: {atm_vol:.4f}")

# Full smile metrics for a tenor
metrics = analyzer.smile_metrics(surface, tenor_days=30)
print(f"ATM: {metrics['atm_vol']}, Skew: {metrics['skew']}, "
      f"Butterfly: {metrics['butterfly']}")
```

### 4. SVI surface calibration

`SVICalibrator` in `src/volatility/svi_model.py` fits the SVI parametrization (a, b, rho, m, sigma) to market IV with arbitrage-free constraints.

```python
import numpy as np
from src.volatility.svi_model import SVICalibrator

calibrator = SVICalibrator(
    max_iterations=500,
    tolerance=1e-6,
    enforce_arbitrage_free=True,
)

# Calibrate a single slice
params = calibrator.calibrate_slice(
    log_moneyness=np.array([-0.10, -0.05, 0.0, 0.05, 0.10]),
    market_iv=np.array([0.28, 0.24, 0.20, 0.19, 0.21]),
    tenor_days=30,
)
print(f"SVI params: a={params.a}, b={params.b}, rho={params.rho}")
print(f"ATM vol: {params.atm_vol:.4f}, RMSE: {params.rmse:.6f}")
print(f"Arbitrage-free: {params.is_arbitrage_free}")

# Calibrate full surface across tenors
result = calibrator.calibrate_surface(
    iv_data={
        30: (np.array([-0.1, -0.05, 0, 0.05, 0.1]),
             np.array([0.28, 0.24, 0.20, 0.19, 0.21])),
        60: (np.array([-0.1, -0.05, 0, 0.05, 0.1]),
             np.array([0.26, 0.23, 0.21, 0.20, 0.22])),
    },
    spot=100.0,
    symbol="SPY",
)
print(f"Converged: {result.converged}, RMSE: {result.final_rmse:.6f}")
print(f"Quality: {result.quality_label}")  # excellent/good/fair/poor

# Interpolate IV from calibrated surface
iv = result.surface.get_iv(log_moneyness=-0.07, tenor_days=45)

# Compare two surfaces (e.g., today vs yesterday)
diff = calibrator.compare_surfaces(surface_today, surface_yesterday)
print(f"Avg ATM change: {diff['avg_atm_change']:.4f}")
```

### 5. Skew analytics

`SkewAnalyzer` in `src/volatility/skew_analytics.py` computes risk reversals, tracks skew dynamics, and classifies skew regimes.

```python
from src.volatility.skew_analytics import SkewAnalyzer

skew_analyzer = SkewAnalyzer(put_moneyness=0.90, call_moneyness=1.10)

# Risk reversal from vol quotes
rr = skew_analyzer.compute_risk_reversal(
    put_vol=0.28, call_vol=0.19, atm_vol=0.20,
    tenor_days=30, symbol="SPY",
)
print(f"Risk reversal: {rr.risk_reversal:.4f}")  # put - call
print(f"Butterfly: {rr.butterfly:.4f}")
print(f"Direction: {rr.skew_direction}")   # put_skew / call_skew / symmetric
print(f"Magnitude: {rr.skew_magnitude}")   # extreme / elevated / moderate / low

# From a vol smile
rr_from_smile = skew_analyzer.compute_from_smile(
    moneyness_iv=[(0.85, 0.32), (0.90, 0.28), (1.0, 0.20), (1.10, 0.19)],
    tenor_days=30,
)

# Skew dynamics over time
dynamics = skew_analyzer.skew_dynamics(
    rr_history=[0.06, 0.07, 0.08, 0.09, 0.085, 0.09, 0.10],
    symbol="SPY",
)
print(f"Z-score: {dynamics.z_score:.2f}, Trend: {dynamics.trend}")
print(f"Cheap downside: {dynamics.is_cheap}")  # z < -1
print(f"Expensive downside: {dynamics.is_expensive}")  # z > 1

# Skew term structure
skew_ts = skew_analyzer.skew_term_structure(
    tenor_rr=[(7, 0.12), (30, 0.09), (90, 0.06), (180, 0.05)],
    symbol="SPY",
)
print(f"Shape: {skew_ts.shape}")   # normal / inverted / humped / flat
print(f"Slope: {skew_ts.slope:.6f}")

# Skew regime classification
regime = skew_analyzer.classify_regime(rr=0.09, butterfly=0.03, symbol="SPY")
print(f"Regime: {regime.regime}")  # panic / normal / complacent / speculative
```

### 6. Term structure modeling (Nelson-Siegel)

`TermStructureModeler` in `src/volatility/term_model.py` fits parametric curves and computes carry/roll-down.

```python
from src.volatility.term_model import TermStructureModeler

modeler = TermStructureModeler(default_tau=90.0, min_points=3)

# Fit Nelson-Siegel model
fit = modeler.fit(
    tenor_vol=[(7, 0.25), (30, 0.22), (60, 0.21), (90, 0.20), (180, 0.19)],
    symbol="SPY",
)
print(f"Long-term vol: {fit.long_term_vol:.4f}")
print(f"Short-term vol: {fit.short_term_vol:.4f}")
print(f"Slope: {fit.slope:.4f}")  # Positive = contango
predicted_vol = fit.predict(tenor_days=45)

# Carry and roll-down analysis
carry = modeler.carry_roll_down(
    fit=fit,
    realized_vol=0.18,
    tenor_days=30,
    horizon_days=1,
)
print(f"Vol carry: {carry.vol_carry:.4f} (IV - RV)")
print(f"Roll-down: {carry.roll_down:.4f}")
print(f"Total PnL: {carry.total_pnl_bps:.1f} bps")
print(f"Signal: {carry.carry_signal}")  # strong_sell_vol / mild_sell_vol / ...

# Classify term structure shape
shape = modeler.classify_shape(tenor_vol)
print(f"Shape: {shape}")  # contango / backwardation / humped / flat

# Track dynamics between periods
dynamics = modeler.track_dynamics(
    current_vols=[(30, 0.22), (60, 0.21), (90, 0.20)],
    prior_vols=[(30, 0.20), (60, 0.20), (90, 0.20)],
    symbol="SPY",
)
print(f"Shape change: {dynamics.shape_change}")  # steepening / flattening / ...
```

### 7. Vol regime detection

`VolRegimeDetector` in `src/volatility/regime.py` classifies vol environment from z-score relative to history.

```python
import pandas as pd
from src.volatility.regime import VolRegimeDetector

detector = VolRegimeDetector()

state = detector.detect(returns=returns_series, window=21)
print(f"Regime: {state.regime.value}")     # LOW / NORMAL / HIGH / EXTREME
print(f"Current vol: {state.current_vol:.4f}")
print(f"Z-score: {state.z_score:.2f}")
print(f"Percentile: {state.percentile:.1f}th")
print(f"Days in regime: {state.days_in_regime}")
print(f"Regime changed: {state.regime_changed}")

# Historical distribution
dist = detector.regime_distribution(returns_series, window=21)
for regime, frac in dist.items():
    print(f"  {regime.value}: {frac:.1%} of time")
```

### 8. Vol regime trading signals

`VolRegimeSignalGenerator` in `src/volatility/vol_regime_signals.py` combines vol-of-vol, mean-reversion, and transition signals.

```python
from src.volatility.vol_regime_signals import VolRegimeSignalGenerator

gen = VolRegimeSignalGenerator(mean_reversion_hl=21.0, vov_window=63)

# Vol-of-vol measurement
vov = gen.compute_vol_of_vol(vol_series=historical_vols, symbol="SPY")
print(f"Vol-of-vol: {vov.vol_of_vol:.6f}, Percentile: {vov.vol_of_vol_percentile:.1f}")
print(f"Stability: {vov.stability_score:.2f}")

# Mean-reversion signal
mr = gen.mean_reversion_signal(vol_series=historical_vols, symbol="SPY")
print(f"Signal: {mr.signal}")       # sell_vol / buy_vol / neutral
print(f"Z-score: {mr.z_score:.2f}")
print(f"Half-life: {mr.half_life_days:.1f} days")
print(f"Expected change: {mr.expected_change:.4f}")

# Regime transition signal
trans = gen.regime_transition_signal(
    from_regime="normal", to_regime="high",
    days_in_new=3, symbol="SPY",
)
print(f"Transition: {trans.transition_type}")  # escalation / spike / ...
print(f"Signal: {trans.signal}")               # risk_off / risk_on / ...
print(f"Confirmed: {trans.is_confirmed}")      # True if days >= 3

# Comprehensive summary
summary = gen.generate_summary(
    vol_series=historical_vols,
    current_regime="high",
    prev_regime="normal",
    days_in_regime=5,
    symbol="SPY",
)
print(f"Composite: {summary.composite_signal}")      # strong_risk_off / risk_off / ...
print(f"Strength: {summary.composite_strength:.2f}")
print(f"Action: {summary.recommended_action}")        # reduce_exposure / add_hedges / ...
```

## Key classes and methods

| Class | File | Key Methods |
|-------|------|-------------|
| `VolatilityEngine` | `src/volatility/engine.py` | `compute_historical()`, `compute_ewma()`, `compute_parkinson()`, `compute_garman_klass()`, `compute_all()`, `compute_vol_cone()`, `compute_term_structure()`, `implied_vs_realized()`, `compute_percentile()` |
| `VolSurfaceAnalyzer` | `src/volatility/surface.py` | `build_surface()`, `compute_skew()`, `compute_butterfly()`, `atm_term_structure()`, `smile_metrics()` |
| `SVICalibrator` | `src/volatility/svi_model.py` | `calibrate_slice()`, `calibrate_surface()`, `compare_surfaces()` |
| `SkewAnalyzer` | `src/volatility/skew_analytics.py` | `compute_risk_reversal()`, `compute_from_smile()`, `skew_dynamics()`, `skew_term_structure()`, `classify_regime()` |
| `TermStructureModeler` | `src/volatility/term_model.py` | `fit()`, `carry_roll_down()`, `classify_shape()`, `track_dynamics()`, `compare_term_structures()` |
| `VolRegimeDetector` | `src/volatility/regime.py` | `detect()`, `regime_distribution()`, `reset()` |
| `VolRegimeSignalGenerator` | `src/volatility/vol_regime_signals.py` | `compute_vol_of_vol()`, `mean_reversion_signal()`, `regime_transition_signal()`, `generate_summary()` |

## Common patterns

### Full vol analysis pipeline

```python
# 1. Estimate realized vol
vols = engine.compute_all(returns, high, low, open_, close, symbol="SPY")

# 2. Detect vol regime
state = regime_detector.detect(returns)

# 3. Build surface from market IVs
surface = surface_analyzer.build_surface(iv_data, spot)

# 4. Analyze skew
rr = skew_analyzer.compute_risk_reversal(put_vol, call_vol, atm_vol)
skew_regime = skew_analyzer.classify_regime(rr.risk_reversal, rr.butterfly)

# 5. Fit term structure, compute carry
fit = modeler.fit(tenor_vol)
carry = modeler.carry_roll_down(fit, realized_vol=vols[VolMethod.HISTORICAL].value)

# 6. Generate composite signal
summary = signal_gen.generate_summary(
    vol_series=vol_history, current_regime=state.regime.value,
    prev_regime=state.prev_regime.value if state.prev_regime else None,
)
print(f"Action: {summary.recommended_action}")
```

### Key data models

- `VolEstimate`: value, method, window, annualized
- `SVIParams`: a, b, rho, m, sigma, tenor_days, rmse (properties: atm_vol, is_arbitrage_free)
- `CalibrationResult`: surface, converged, final_rmse, quality_label
- `RiskReversal`: risk_reversal, butterfly, skew_direction, skew_magnitude
- `SkewDynamics`: z_score, percentile, trend, is_cheap, is_expensive
- `TermStructureFit`: beta0 (long-term), beta1 (slope), beta2 (curvature), tau, predict(tenor)
- `CarryRollDown`: vol_carry, roll_down, total_pnl_bps, carry_signal
- `VolRegimeState`: regime (LOW/NORMAL/HIGH/EXTREME), z_score, percentile, days_in_regime
- `VolSignalSummary`: composite_signal, composite_strength, recommended_action
