"""Strategy Optimizer Dashboard (PRD-148).

Four-tab Streamlit dashboard for parameter space visualization,
GA optimization, performance evaluation, and drift monitoring.
"""

import streamlit as st
from app.styles import inject_global_styles

inject_global_styles()

from src.strategy_optimizer.parameters import build_default_parameter_space
from src.strategy_optimizer.evaluator import PerformanceMetrics, StrategyEvaluator
from src.strategy_optimizer.optimizer import OptimizerConfig, AdaptiveOptimizer
from src.strategy_optimizer.monitor import (
    DriftStatus, DriftConfig, PerformanceDriftMonitor,
)

st.header("Strategy Optimizer")
st.caption("PRD-148 · Adaptive parameter optimization via genetic algorithm")

tab1, tab2, tab3, tab4 = st.tabs([
    "Parameter Space", "Optimizer", "Performance", "Drift Monitor",
])

# ── Tab 1: Parameter Space ──────────────────────────────────────────────

with tab1:
    st.subheader("Tunable Parameters (20)")
    space = build_default_parameter_space()
    params = space.get_all()

    modules = sorted({p.module for p in params})
    for mod in modules:
        with st.expander(f"Module: {mod}", expanded=True):
            mod_params = space.get_by_module(mod)
            for p in mod_params:
                cols = st.columns([2, 1, 1, 1, 3])
                cols[0].write(f"**{p.name}**")
                cols[1].write(p.param_type.value)
                if p.min_val is not None:
                    cols[2].write(f"{p.min_val} – {p.max_val}")
                elif p.choices:
                    cols[2].write(", ".join(str(c) for c in p.choices))
                cols[3].write(f"Default: {p.default}")
                cols[4].write(p.description)

# ── Tab 2: Optimizer ────────────────────────────────────────────────────

with tab2:
    st.subheader("Genetic Algorithm Optimizer")

    c1, c2, c3 = st.columns(3)
    pop_size = c1.number_input("Population", 6, 100, 20)
    generations = c2.number_input("Generations", 2, 50, 10)
    mutation = c3.slider("Mutation Rate", 0.01, 0.5, 0.1)

    if st.button("Run Optimization (Demo)"):
        # Generate synthetic trades for demo
        demo_trades = []
        for i in range(60):
            pnl = 80.0 if i % 3 != 0 else -50.0
            demo_trades.append({"pnl": pnl, "pnl_pct": pnl / 100000.0})

        cfg = OptimizerConfig(
            population_size=int(pop_size),
            generations=int(generations),
            mutation_rate=mutation,
            seed=42,
        )
        opt = AdaptiveOptimizer(cfg)
        evaluator = StrategyEvaluator()
        result = opt.optimize(space, evaluator, demo_trades)

        st.success(f"Best score: **{result.best_score:.2f}** / 100")
        st.json(result.best_params)

        if result.generation_history:
            scores = [h["best_score"] for h in result.generation_history]
            st.line_chart(scores)
            st.caption("Best score per generation")

# ── Tab 3: Performance ──────────────────────────────────────────────────

with tab3:
    st.subheader("Strategy Evaluation Metrics")

    demo_metrics = PerformanceMetrics(
        sharpe_ratio=1.42, total_return=0.187, max_drawdown=-0.065,
        win_rate=0.62, profit_factor=1.85, avg_trade_pnl=42.5,
        trade_count=156, calmar_ratio=2.88,
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Sharpe Ratio", f"{demo_metrics.sharpe_ratio:.2f}")
    m2.metric("Total Return", f"{demo_metrics.total_return:.1%}")
    m3.metric("Max Drawdown", f"{demo_metrics.max_drawdown:.1%}")
    m4.metric("Win Rate", f"{demo_metrics.win_rate:.1%}")

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Profit Factor", f"{demo_metrics.profit_factor:.2f}")
    m6.metric("Avg Trade P&L", f"${demo_metrics.avg_trade_pnl:.2f}")
    m7.metric("Trade Count", demo_metrics.trade_count)
    m8.metric("Calmar Ratio", f"{demo_metrics.calmar_ratio:.2f}")

    ev = StrategyEvaluator()
    score = ev.score(demo_metrics)
    st.info(f"Composite Score: **{score:.1f}** / 100")

# ── Tab 4: Drift Monitor ───────────────────────────────────────────────

with tab4:
    st.subheader("Performance Drift Monitor")

    baseline = PerformanceMetrics(
        sharpe_ratio=1.5, total_return=0.20, max_drawdown=-0.06,
        win_rate=0.60, profit_factor=1.9, trade_count=200,
    )

    status_colors = {
        DriftStatus.HEALTHY: "🟢",
        DriftStatus.WARNING: "🟡",
        DriftStatus.CRITICAL: "🔴",
        DriftStatus.STALE: "⚪",
    }

    monitor = PerformanceDriftMonitor(baseline_metrics=baseline)
    demo_trades = [
        {"pnl": 75, "pnl_pct": 0.0075} if i % 3 != 0 else {"pnl": -55, "pnl_pct": -0.0055}
        for i in range(40)
    ]
    report = monitor.check(demo_trades)

    icon = status_colors.get(report.status, "⚪")
    st.markdown(f"### Status: {icon} {report.status.value.upper()}")
    st.write(report.recommendation)

    c1, c2 = st.columns(2)
    with c1:
        st.write("**Baseline Metrics**")
        st.json(baseline.to_dict())
    with c2:
        st.write("**Current Metrics**")
        st.json(report.current_metrics.to_dict())

    st.metric("Sharpe Delta", f"{report.sharpe_ratio_delta:+.4f}")
    st.metric("Drawdown Delta", f"{report.drawdown_delta:+.4f}")
