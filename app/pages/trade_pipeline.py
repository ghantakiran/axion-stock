"""Trade Pipeline Dashboard (PRD-149).

Four-tab Streamlit dashboard for signal bridge demo, pipeline
execution, reconciliation quality, and position tracking.
"""

import streamlit as st
from app.styles import inject_global_styles

inject_global_styles()

from src.trade_pipeline.bridge import (
    SignalType, OrderSide, OrderType, PipelineOrder, SignalBridge,
)
from src.trade_pipeline.executor import (
    PipelineStatus, PipelineConfig, PipelineExecutor,
)
from src.trade_pipeline.reconciler import ExecutionReconciler
from src.trade_pipeline.position_store import PositionStore

st.header("Trade Pipeline")
st.caption("PRD-149 · Signal-to-trade execution pipeline with validation, risk checks, and reconciliation")

tab1, tab2, tab3, tab4 = st.tabs([
    "Signal Bridge", "Pipeline Executor", "Reconciliation", "Position Tracker",
])

# ── Tab 1: Signal Bridge ────────────────────────────────────────────

with tab1:
    st.subheader("Signal → Order Conversion")
    st.info("The Signal Bridge normalizes 3 different signal types into a unified PipelineOrder format.")

    bridge = SignalBridge(account_equity=100_000)

    col1, col2 = st.columns(2)
    with col1:
        signal_source = st.selectbox("Signal Source", ["Fusion Recommendation", "Social Signal", "EMA Cloud", "Manual"])
        symbol = st.text_input("Symbol", "AAPL")

    with col2:
        confidence = st.slider("Confidence", 0.0, 1.0, 0.7)
        position_pct = st.slider("Position Size %", 1.0, 15.0, 5.0)

    if st.button("Convert to Pipeline Order"):
        order = PipelineOrder(
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET if confidence >= 0.7 else OrderType.LIMIT,
            qty=bridge._pct_to_shares(position_pct, 150.0),
            confidence=confidence,
            position_size_pct=position_pct,
            signal_type=SignalType.FUSION if signal_source == "Fusion Recommendation"
                else SignalType.SOCIAL if signal_source == "Social Signal"
                else SignalType.EMA_CLOUD if signal_source == "EMA Cloud"
                else SignalType.MANUAL,
        )
        st.success(f"Created PipelineOrder: **{order.order_id}**")
        st.json(order.to_dict())
        st.write("**Broker Order Format:**")
        st.json(order.to_broker_order())

# ── Tab 2: Pipeline Executor ────────────────────────────────────────

with tab2:
    st.subheader("Pipeline Execution Demo")

    c1, c2, c3 = st.columns(3)
    paper_mode = c1.checkbox("Paper Mode", value=True)
    min_confidence = c2.slider("Min Confidence", 0.0, 1.0, 0.3, key="exec_conf")
    max_positions = c3.number_input("Max Positions", 1, 50, 20)

    if st.button("Run Demo Pipeline"):
        cfg = PipelineConfig(
            paper_mode=paper_mode,
            min_confidence=min_confidence,
            max_positions=int(max_positions),
        )
        executor = PipelineExecutor(cfg, account_equity=100_000)
        bridge = SignalBridge(account_equity=100_000)

        # Demo orders
        demo_data = [
            {"symbol": "AAPL", "side": "buy", "qty": 50, "confidence": 0.8, "position_size_pct": 5.0},
            {"symbol": "GOOG", "side": "buy", "qty": 30, "confidence": 0.6, "position_size_pct": 4.0},
            {"symbol": "TSLA", "side": "buy", "qty": 20, "confidence": 0.15, "position_size_pct": 3.0},  # Low confidence
            {"symbol": "META", "side": "buy", "qty": 25, "confidence": 0.75, "position_size_pct": 5.0},
        ]

        results = []
        for d in demo_data:
            order = bridge.from_dict(d)
            result = executor.process(order)
            results.append(result)

        # Summary metrics
        stats = executor.get_execution_stats()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Processed", stats["total_processed"])
        m2.metric("Executed", stats["executed"])
        m3.metric("Rejected", stats["rejected"])
        m4.metric("Execution Rate", f"{stats['execution_rate']:.0%}")

        # Results table
        for r in results:
            icon = {"executed": "✅", "rejected": "❌", "routed": "🔄"}.get(r.status.value, "⚪")
            st.write(f"{icon} **{r.order.symbol}** — {r.status.value.upper()} "
                     f"{'(' + r.rejection_reason + ')' if r.rejection_reason else ''}")

# ── Tab 3: Reconciliation ──────────────────────────────────────────

with tab3:
    st.subheader("Execution Quality")

    reconciler = ExecutionReconciler()
    # Demo reconciliation data
    demo_reconciliations = [
        ("o1", "AAPL", 185.50, 185.68, 100, 100, "alpaca", 35),
        ("o2", "GOOG", 142.00, 141.85, 50, 50, "schwab", 48),
        ("o3", "TSLA", 240.00, 240.90, 30, 25, "alpaca", 62),
        ("o4", "META", 320.00, 320.15, 40, 40, "robinhood", 28),
        ("o5", "NVDA", 500.00, 501.20, 20, 20, "alpaca", 45),
    ]

    for args in demo_reconciliations:
        reconciler.reconcile(*args)

    stats = reconciler.get_stats()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Avg Slippage", f"{stats.avg_slippage_pct:.3f}%")
    m2.metric("Full Fill Rate", f"{stats.full_fill_rate:.0%}")
    m3.metric("Avg Latency", f"{stats.avg_latency_ms:.0f}ms")
    m4.metric("Records", stats.total_records)

    if stats.by_broker:
        st.write("**Per-Broker Slippage:**")
        for broker, slip in stats.by_broker.items():
            color = "🟢" if abs(slip) < 0.1 else ("🟡" if abs(slip) < 0.3 else "🔴")
            st.write(f"  {color} **{broker}**: {slip:.4f}%")

# ── Tab 4: Position Tracker ─────────────────────────────────────────

with tab4:
    st.subheader("Open Positions")

    store = PositionStore()
    # Demo positions
    store.open_position("AAPL", 100, 185.0, "long", "fusion", "ord1",
                        stop_loss_price=178.0, target_price=200.0)
    store.open_position("GOOG", 50, 142.0, "long", "social", "ord2",
                        stop_loss_price=135.0, target_price=160.0)
    store.open_position("NVDA", 20, 500.0, "long", "ema_cloud", "ord3",
                        stop_loss_price=480.0, target_price=550.0)

    # Simulate price movement
    store.update_prices({"AAPL": 190.0, "GOOG": 140.0, "NVDA": 515.0})

    summary = store.get_portfolio_summary()
    s1, s2, s3 = st.columns(3)
    s1.metric("Positions", summary["position_count"])
    s2.metric("Unrealized P&L", f"${summary['unrealized_pnl']:+,.2f}")
    s3.metric("Market Value", f"${summary['total_market_value']:,.2f}")

    for pos in store.get_all():
        pnl_color = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
        with st.expander(f"{pnl_color} {pos.symbol} — {pos.qty} shares @ ${pos.avg_entry_price:.2f}"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Current Price", f"${pos.current_price:.2f}")
            c2.metric("Unrealized P&L", f"${pos.unrealized_pnl:+,.2f}")
            c3.metric("P&L %", f"{pos.unrealized_pnl_pct:+.2f}%")
            st.write(f"Stop Loss: ${pos.stop_loss_price:.2f} | Target: ${pos.target_price:.2f}")
            st.write(f"Signal: {pos.signal_type} | Hit Stop: {pos.hit_stop_loss} | Hit Target: {pos.hit_target}")

    triggered = store.check_exits()
    if triggered:
        st.warning(f"Exit triggers for: {', '.join(triggered)}")
