"""PRD-173: Strategy Integration Dashboard.

4 tabs: Regime, Strategy Selection, Signal Fusion, Pipeline Flow.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Strategy Integration", page_icon="\U0001f9e9", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("\U0001f9e9 Strategy Integration")
st.caption("Regime detection, ADX-gated strategy routing, signal fusion, and full pipeline visualization")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

try:
    from src.regime_adaptive.strategy import RegimeAdaptiveStrategy
    REGIME_AVAILABLE = True
except ImportError:
    REGIME_AVAILABLE = False

try:
    from src.strategy_selector.selector import StrategySelector
    SELECTOR_AVAILABLE = True
except ImportError:
    SELECTOR_AVAILABLE = False

try:
    from src.signal_fusion.fusion_engine import FusionEngine
    FUSION_AVAILABLE = True
except ImportError:
    FUSION_AVAILABLE = False

np.random.seed(173)
NOW = datetime.now()
TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AMD", "JPM", "V"]

# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------

# Regime data
REGIMES = ["bull", "bear", "sideways", "crisis"]
current_regime = "bull"
regime_confidence = 0.78
regime_duration_hours = int(np.random.randint(4, 72))
regime_adx = round(float(np.random.uniform(22, 45)), 1)
regime_vix = round(float(np.random.uniform(12, 28)), 1)

regime_history = []
for i in range(20):
    regime_history.append({
        "Timestamp": (NOW - timedelta(hours=i * 6)).strftime("%Y-%m-%d %H:%M"),
        "Regime": np.random.choice(REGIMES, p=[0.45, 0.20, 0.30, 0.05]),
        "Confidence": round(float(np.random.uniform(0.55, 0.95)), 2),
        "ADX": round(float(np.random.uniform(10, 50)), 1),
        "VIX": round(float(np.random.uniform(12, 35)), 1),
    })

# Strategy selection data
adx_values = np.random.uniform(8, 50, len(TICKERS))
strategies_selected = ["ema_cloud" if a >= 25 else "mean_reversion" for a in adx_values]
selection_confidences = [min(95, int(abs(a - 25) * 2 + 50)) for a in adx_values]

# Fusion weights
SOURCES = ["ema_cloud", "social", "momentum", "volume", "breakout", "mean_reversion"]
fusion_weights = {
    "ema_cloud": 0.28,
    "social": 0.12,
    "momentum": 0.22,
    "volume": 0.14,
    "breakout": 0.14,
    "mean_reversion": 0.10,
}
fusion_scores = {s: round(float(np.random.uniform(30, 90)), 1) for s in SOURCES}

# Pipeline stages
PIPELINE_STAGES = [
    {"Stage": "1. Signal Generation", "Module": "ema_signals / strategy_selector", "Status": "Active", "Latency (ms)": round(float(np.random.uniform(5, 25)), 1)},
    {"Stage": "2. Signal Fusion", "Module": "signal_fusion", "Status": "Active", "Latency (ms)": round(float(np.random.uniform(2, 10)), 1)},
    {"Stage": "3. Signal Persistence", "Module": "signal_persistence", "Status": "Active", "Latency (ms)": round(float(np.random.uniform(3, 15)), 1)},
    {"Stage": "4. Unified Risk Check", "Module": "unified_risk", "Status": "Active", "Latency (ms)": round(float(np.random.uniform(5, 20)), 1)},
    {"Stage": "5. Signal Guard", "Module": "bot_pipeline.signal_guard", "Status": "Active", "Latency (ms)": round(float(np.random.uniform(1, 5)), 1)},
    {"Stage": "6. Order Validation", "Module": "bot_pipeline.order_validator", "Status": "Active", "Latency (ms)": round(float(np.random.uniform(2, 8)), 1)},
    {"Stage": "7. Trade Execution", "Module": "trade_executor", "Status": "Active", "Latency (ms)": round(float(np.random.uniform(15, 80)), 1)},
    {"Stage": "8. Fill Validation", "Module": "bot_pipeline.order_validator", "Status": "Active", "Latency (ms)": round(float(np.random.uniform(5, 30)), 1)},
    {"Stage": "9. Position Reconciliation", "Module": "bot_pipeline.position_reconciler", "Status": "Active", "Latency (ms)": round(float(np.random.uniform(10, 40)), 1)},
    {"Stage": "10. Feedback Loop", "Module": "signal_feedback", "Status": "Active", "Latency (ms)": round(float(np.random.uniform(3, 12)), 1)},
]

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "Regime",
    "Strategy Selection",
    "Signal Fusion",
    "Pipeline Flow",
])

# =====================================================================
# Tab 1 - Regime
# =====================================================================
with tab1:
    st.subheader("Current Market Regime")

    if not REGIME_AVAILABLE:
        st.info("RegimeBridge module not installed. Showing demo regime data.")

    regime_colors = {"bull": "green", "bear": "red", "sideways": "orange", "crisis": "red"}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Regime", current_regime.upper())
    c2.metric("Confidence", f"{regime_confidence:.0%}")
    c3.metric("Duration", f"{regime_duration_hours}h")
    c4.metric("ADX (Market)", regime_adx)

    if current_regime == "bull":
        st.success(f"Market regime: **{current_regime.upper()}** -- Trend-following strategies preferred")
    elif current_regime == "bear":
        st.error(f"Market regime: **{current_regime.upper()}** -- Defensive positioning recommended")
    elif current_regime == "crisis":
        st.error(f"Market regime: **{current_regime.upper()}** -- Risk reduction active, tighten stops")
    else:
        st.warning(f"Market regime: **{current_regime.upper()}** -- Range-bound, mean-reversion active")

    st.markdown("---")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Regime Indicators")
        indicator_data = {
            "ADX (14)": regime_adx,
            "VIX": regime_vix,
            "Put/Call Ratio": round(float(np.random.uniform(0.7, 1.3)), 2),
            "Breadth (A/D)": round(float(np.random.uniform(0.4, 0.8)), 2),
            "Correlation (SPY-QQQ)": round(float(np.random.uniform(0.6, 0.95)), 2),
            "Momentum Score": round(float(np.random.uniform(30, 80)), 0),
        }
        st.json(indicator_data)

    with col_right:
        st.markdown("#### Regime-Adaptive Parameters")
        params = {
            "bull": {"max_position_pct": 8, "stop_loss_pct": 3, "take_profit_pct": 8, "max_positions": 10},
            "bear": {"max_position_pct": 4, "stop_loss_pct": 2, "take_profit_pct": 5, "max_positions": 5},
            "sideways": {"max_position_pct": 5, "stop_loss_pct": 2, "take_profit_pct": 4, "max_positions": 7},
            "crisis": {"max_position_pct": 2, "stop_loss_pct": 1, "take_profit_pct": 3, "max_positions": 3},
        }
        params_df = pd.DataFrame(params).T
        params_df.index.name = "Regime"
        st.dataframe(params_df, use_container_width=True)

    st.markdown("---")
    st.subheader("Regime History (Last 5 Days)")
    st.dataframe(pd.DataFrame(regime_history), use_container_width=True, hide_index=True)

    # Regime distribution
    regime_counts = pd.Series([r["Regime"] for r in regime_history]).value_counts()
    st.bar_chart(regime_counts)

# =====================================================================
# Tab 2 - Strategy Selection
# =====================================================================
with tab2:
    st.subheader("ADX-Gated Strategy Routing")

    if not SELECTOR_AVAILABLE:
        st.info("Strategy selector module not installed. Showing demo selection data.")

    ema_count = sum(1 for s in strategies_selected if s == "ema_cloud")
    mr_count = sum(1 for s in strategies_selected if s == "mean_reversion")

    c1, c2, c3 = st.columns(3)
    c1.metric("EMA Cloud Routed", ema_count)
    c2.metric("Mean Reversion Routed", mr_count)
    c3.metric("ADX Threshold", "25.0")

    st.markdown("---")

    routing_df = pd.DataFrame({
        "Ticker": TICKERS,
        "ADX": [f"{a:.1f}" for a in adx_values],
        "Trend": ["Strong" if a >= 35 else "Moderate" if a >= 20 else "Weak" for a in adx_values],
        "Strategy": strategies_selected,
        "Confidence": [f"{c}%" for c in selection_confidences],
        "RSI": [f"{r:.1f}" for r in np.random.uniform(25, 75, len(TICKERS))],
        "Conviction": np.random.randint(35, 90, len(TICKERS)).tolist(),
    })
    st.dataframe(routing_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### ADX Distribution")
        adx_chart = pd.DataFrame({"ADX": adx_values}, index=TICKERS)
        st.bar_chart(adx_chart)

    with col_right:
        st.markdown("#### Strategy Selection Logic")
        st.markdown("""
        - **ADX >= 25**: Route to **EMA Cloud** (trend-following)
        - **ADX < 25**: Route to **Mean Reversion** (RSI/Z-score/Bollinger)
        - **Override**: Regime can force strategy selection
        - **A/B Tracking**: Both strategies scored for comparison
        """)

        routing_stats = {
            "total_routings_today": int(np.random.randint(200, 500)),
            "ema_cloud_pct": round(ema_count / len(TICKERS) * 100, 1),
            "mean_reversion_pct": round(mr_count / len(TICKERS) * 100, 1),
            "avg_adx": round(float(np.mean(adx_values)), 1),
            "adx_threshold": 25.0,
        }
        st.json(routing_stats)

# =====================================================================
# Tab 3 - Signal Fusion
# =====================================================================
with tab3:
    st.subheader("Signal Fusion Weights")

    if not FUSION_AVAILABLE:
        st.info("Signal fusion module not installed. Showing demo fusion data.")

    c1, c2, c3 = st.columns(3)
    active_sources = sum(1 for w in fusion_weights.values() if w > 0)
    total_weight = sum(fusion_weights.values())
    avg_score = round(np.mean(list(fusion_scores.values())), 1)
    c1.metric("Active Sources", active_sources)
    c2.metric("Total Weight", f"{total_weight:.2f}")
    c3.metric("Avg Fusion Score", avg_score)

    st.markdown("---")
    st.markdown("#### Current Weight Distribution")

    weight_df = pd.DataFrame({
        "Weight": list(fusion_weights.values()),
    }, index=list(fusion_weights.keys()))
    st.bar_chart(weight_df)

    st.markdown("---")
    st.markdown("#### Source Contribution Detail")

    contribution_rows = []
    for src in SOURCES:
        w = fusion_weights[src]
        score = fusion_scores[src]
        contribution_rows.append({
            "Source": src,
            "Weight": f"{w:.1%}",
            "Raw Score": score,
            "Weighted Score": round(w * score, 2),
            "Signals (24h)": int(np.random.randint(10, 120)),
            "Win Rate": f"{np.random.uniform(0.45, 0.72):.1%}",
            "Sharpe": round(float(np.random.uniform(0.3, 2.5)), 2),
        })
    st.dataframe(pd.DataFrame(contribution_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Fused Signal Output (Latest)")

    fused_signals = []
    for t in TICKERS[:5]:
        raw_scores = {s: round(float(np.random.uniform(20, 95)), 1) for s in SOURCES}
        fused_score = round(sum(raw_scores[s] * fusion_weights[s] for s in SOURCES), 1)
        direction = "long" if fused_score > 50 else "short" if fused_score < 35 else "neutral"
        fused_signals.append({
            "Ticker": t,
            "Fused Score": fused_score,
            "Direction": direction,
            "Top Source": max(raw_scores, key=raw_scores.get),
            "Conviction": int(min(100, fused_score * 1.2)),
        })
    st.dataframe(pd.DataFrame(fused_signals), use_container_width=True, hide_index=True)

# =====================================================================
# Tab 4 - Pipeline Flow
# =====================================================================
with tab4:
    st.subheader("End-to-End Pipeline Flow")

    total_latency = sum(s["Latency (ms)"] for s in PIPELINE_STAGES)
    active_stages = sum(1 for s in PIPELINE_STAGES if s["Status"] == "Active")

    c1, c2, c3 = st.columns(3)
    c1.metric("Pipeline Stages", len(PIPELINE_STAGES))
    c2.metric("All Active", f"{active_stages}/{len(PIPELINE_STAGES)}")
    c3.metric("Total Latency", f"{total_latency:.1f} ms")

    st.markdown("---")
    st.markdown("#### Pipeline Stage Details")
    st.dataframe(pd.DataFrame(PIPELINE_STAGES), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### Pipeline Flow Diagram")

    flow_text = """
    ```
    Signal Source (EMA Cloud / Mean Reversion / Social / Momentum)
         |
         v
    [1] Signal Generation  -->  Strategy Selector (ADX gate)
         |
         v
    [2] Signal Fusion  -->  Weighted combination of all sources
         |
         v
    [3] Signal Persistence  -->  Audit trail (SignalRecord)
         |
         v
    [4] Unified Risk Check  -->  7 risk checks (correlation, VaR, regime limits)
         |
         v
    [5] Signal Guard  -->  Freshness + deduplication filter
         |
         v
    [6] Order Validation  -->  Pre-trade checks
         |
         v
    [7] Trade Execution  -->  Broker routing (Alpaca / IBKR / Schwab / ...)
         |
         v
    [8] Fill Validation  -->  Partial fill detection, slippage check
         |
         v
    [9] Position Reconciliation  -->  Ghost / orphan / mismatch detection
         |
         v
    [10] Feedback Loop  -->  Rolling Sharpe, weight adjustment
    ```
    """
    st.markdown(flow_text)

    st.markdown("---")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Stage Latency Breakdown")
        latency_df = pd.DataFrame({
            "Latency (ms)": [s["Latency (ms)"] for s in PIPELINE_STAGES],
        }, index=[s["Stage"].split(". ")[1] for s in PIPELINE_STAGES])
        st.bar_chart(latency_df)

    with col_right:
        st.markdown("#### Pipeline Throughput (Last 24h)")
        hours = pd.date_range(end=NOW, periods=24, freq="h")
        throughput = np.random.poisson(lam=35, size=24).tolist()
        tp_df = pd.DataFrame({"Signals Processed": throughput}, index=hours)
        st.line_chart(tp_df)

    st.markdown("---")
    st.subheader("Pipeline Health Summary")
    health = {
        "pipeline_status": "healthy",
        "stages_active": active_stages,
        "stages_total": len(PIPELINE_STAGES),
        "avg_e2e_latency_ms": round(total_latency, 1),
        "signals_processed_24h": int(np.random.randint(600, 1200)),
        "errors_24h": int(np.random.randint(0, 15)),
        "last_signal_time": (NOW - timedelta(seconds=int(np.random.randint(10, 300)))).isoformat(),
        "kill_switch_active": False,
        "circuit_breaker_state": "closed",
    }
    st.json(health)
