"""PRD-65: Portfolio Stress Testing Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd
import numpy as np

from src.risk.shock_propagation import (
    FactorShock,
    ShockPropagationEngine,
    DEFAULT_FACTOR_CORRELATIONS,
)
from src.risk.drawdown_analysis import DrawdownAnalyzer, DrawdownMetrics
from src.risk.recovery_estimation import RecoveryEstimator
from src.risk.scenario_builder import (
    MacroShock,
    ScenarioBuilder,
    SCENARIO_TEMPLATES,
)

try:
    st.set_page_config(page_title="Portfolio Stress Testing", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Portfolio Stress Testing")

# Initialize engines
if "shock_engine" not in st.session_state:
    st.session_state.shock_engine = ShockPropagationEngine()
if "dd_analyzer" not in st.session_state:
    st.session_state.dd_analyzer = DrawdownAnalyzer()
if "recovery_est" not in st.session_state:
    st.session_state.recovery_est = RecoveryEstimator(n_simulations=500, max_days=300)
if "scenario_builder" not in st.session_state:
    st.session_state.scenario_builder = ScenarioBuilder()

shock_engine = st.session_state.shock_engine
dd_analyzer = st.session_state.dd_analyzer
recovery_est = st.session_state.recovery_est
scenario_builder = st.session_state.scenario_builder

# --- Sidebar: Portfolio Definition ---
st.sidebar.header("Portfolio")

default_portfolio = {
    "AAPL": {"value": 50000, "market": 1.2, "growth": 0.8, "quality": 0.5},
    "MSFT": {"value": 40000, "market": 1.1, "growth": 0.7, "quality": 0.6},
    "XOM": {"value": 30000, "market": 0.8, "value": 0.9, "oil": 0.7},
    "JPM": {"value": 25000, "market": 1.3, "value": 0.5, "interest_rate": 0.6},
    "JNJ": {"value": 20000, "market": 0.6, "quality": 0.8, "volatility": -0.3},
}

portfolio_value = sum(h["value"] for h in default_portfolio.values())
st.sidebar.metric("Portfolio Value", f"${portfolio_value:,.0f}")
st.sidebar.markdown(f"**{len(default_portfolio)} positions**")

for sym, data in default_portfolio.items():
    weight = data["value"] / portfolio_value * 100
    st.sidebar.write(f"**{sym}** — ${data['value']:,} ({weight:.1f}%)")

# Build exposure and value dicts
position_exposures = {sym: {k: v for k, v in data.items() if k != "value"} for sym, data in default_portfolio.items()}
position_values = {sym: data["value"] for sym, data in default_portfolio.items()}

# --- Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Shock Propagation", "Drawdown Analysis", "Recovery Estimation",
    "Scenario Builder", "Sensitivity",
])

# --- Tab 1: Shock Propagation ---
with tab1:
    st.subheader("Factor Shock Propagation")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("#### Define Shock")
        shock_factor = st.selectbox(
            "Factor",
            ["market", "growth", "value", "momentum", "quality", "size",
             "volatility", "interest_rate", "credit_spread", "oil", "dollar"],
        )
        shock_magnitude = st.slider("Shock Magnitude", -0.30, 0.10, -0.10, 0.01)
        max_hops = st.slider("Propagation Hops", 1, 3, 2)

        if st.button("Propagate Shock"):
            shocks = [FactorShock(factor=shock_factor, shock_magnitude=shock_magnitude)]

            result = shock_engine.propagate_shock(
                shocks, position_exposures, position_values, portfolio_value, max_hops=max_hops,
            )

            st.session_state.shock_result = result

    with col2:
        if "shock_result" in st.session_state:
            result = st.session_state.shock_result

            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("Total Impact", f"{result.total_impact_pct:.2%}")
            col_b.metric("Impact ($)", f"${result.total_impact_usd:,.0f}")
            col_c.metric("Amplification", f"{result.amplification_factor:.2f}x")
            col_d.metric("Systemic?", "Yes" if result.is_systemic else "No")

            st.markdown("#### Position Impacts")
            impact_data = []
            for pi in result.position_impacts:
                impact_data.append({
                    "Symbol": pi.symbol,
                    "Direct": f"{pi.direct_impact:.4f}",
                    "Indirect": f"{pi.indirect_impact:.4f}",
                    "Total": f"{pi.total_impact:.4f}",
                    "Amplification": f"{pi.amplification_ratio:.2f}x",
                })
            st.dataframe(pd.DataFrame(impact_data), use_container_width=True, hide_index=True)

            if result.factor_contributions:
                st.markdown("#### Factor Contributions")
                fc_df = pd.DataFrame([
                    {"Factor": f, "Contribution": c}
                    for f, c in result.factor_contributions.items()
                ])
                st.bar_chart(fc_df.set_index("Factor")["Contribution"])

    # Contagion tracing
    st.markdown("---")
    st.markdown("#### Contagion Tracing")
    trace_factor = st.selectbox("Trace from factor", ["market", "growth", "oil", "credit_spread", "dollar"], key="trace")
    if st.button("Trace Contagion"):
        paths = shock_engine.trace_contagion(trace_factor, -0.10, max_hops=3)
        if paths:
            path_data = []
            for p in paths:
                path_data.append({
                    "Source": p.source_factor,
                    "Target": p.target_factor,
                    "Correlation": f"{p.correlation:.2f}",
                    "Transmitted Shock": f"{p.transmitted_shock:.4f}",
                })
            st.dataframe(pd.DataFrame(path_data), use_container_width=True, hide_index=True)
        else:
            st.info("No contagion paths found.")

# --- Tab 2: Drawdown Analysis ---
with tab2:
    st.subheader("Drawdown Analysis")

    # Generate sample portfolio values
    np.random.seed(42)
    n_days = 252
    daily_returns = np.random.normal(0.0004, 0.012, n_days)
    portfolio_values = [portfolio_value]
    for r in daily_returns:
        portfolio_values.append(portfolio_values[-1] * (1 + r))

    # Underwater curve
    curve = dd_analyzer.compute_underwater_curve(portfolio_values, symbol="Portfolio")
    st.markdown("#### Underwater Curve")

    dd_df = pd.DataFrame({
        "Day": range(len(curve.drawdowns)),
        "Drawdown": curve.drawdowns,
    })
    st.line_chart(dd_df.set_index("Day")["Drawdown"])

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Drawdown Events")
        events = dd_analyzer.identify_drawdown_events(portfolio_values, symbol="Portfolio")
        if events:
            event_data = []
            for i, e in enumerate(events):
                event_data.append({
                    "Event": i + 1,
                    "Drawdown": f"{e.drawdown_pct:.2%}",
                    "Severity": e.severity,
                    "Duration to Trough": e.duration_to_trough,
                    "Recovery": e.recovery_duration if e.recovery_duration else "Ongoing",
                    "Status": "Ongoing" if e.is_ongoing else "Recovered",
                })
            st.dataframe(pd.DataFrame(event_data), use_container_width=True, hide_index=True)

    with col2:
        st.markdown("#### Drawdown Metrics")
        returns = list(daily_returns)
        metrics = dd_analyzer.compute_metrics(portfolio_values, returns=returns, symbol="Portfolio")

        met_col1, met_col2 = st.columns(2)
        met_col1.metric("Max Drawdown", f"{metrics.max_drawdown:.2%}")
        met_col1.metric("Avg Drawdown", f"{metrics.avg_drawdown:.2%}")
        met_col1.metric("Current DD", f"{metrics.current_drawdown:.2%}")
        met_col2.metric("# Drawdowns", metrics.n_drawdowns)
        met_col2.metric("Ulcer Index", f"{metrics.ulcer_index:.4f}")
        met_col2.metric("% Underwater", f"{metrics.pct_time_underwater:.1%}")

        if metrics.calmar_ratio is not None:
            st.metric("Calmar Ratio", f"{metrics.calmar_ratio:.2f}")

        st.metric("Risk Score", f"{metrics.drawdown_risk_score:.0f}/100")

    # Conditional drawdown
    st.markdown("---")
    st.markdown("#### Tail Risk (Conditional Drawdown)")
    cdd = dd_analyzer.conditional_drawdown(portfolio_values, symbol="Portfolio")
    if cdd.cvar_5 != 0:
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("CVaR 5%", f"{cdd.cvar_5:.2%}")
        col_b.metric("CVaR 1%", f"{cdd.cvar_1:.2%}")
        col_c.metric("Tail Risk Ratio", f"{cdd.tail_risk_ratio:.2f}")
        st.write(f"**Worst 5 drawdowns:** {', '.join(f'{d:.2%}' for d in cdd.worst_5_drawdowns)}")

# --- Tab 3: Recovery Estimation ---
with tab3:
    st.subheader("Recovery Estimation")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Parameters")
        current_dd = st.slider("Current Drawdown", -0.50, -0.01, -0.15, 0.01)
        drift = st.number_input("Daily Drift", value=0.0003, step=0.0001, format="%.4f")
        vol = st.number_input("Daily Volatility", value=0.015, step=0.001, format="%.3f")

        st.markdown("#### Analytical Estimate")
        analytical = recovery_est.analytical_estimate(current_dd, drift=drift, volatility=vol, symbol="Portfolio")
        st.write(f"**Expected Days:** {analytical.expected_days:.0f}")
        st.write(f"**P(30d):** {analytical.probability_30d:.1%}")
        st.write(f"**P(90d):** {analytical.probability_90d:.1%}")
        st.write(f"**P(180d):** {analytical.probability_180d:.1%}")
        st.write(f"**Confidence:** {analytical.recovery_confidence}")

    with col2:
        st.markdown("#### Monte Carlo Estimate")
        if st.button("Run Monte Carlo"):
            mc = recovery_est.monte_carlo_estimate(current_dd, drift=drift, volatility=vol, symbol="Portfolio")
            st.session_state.mc_result = mc

        if "mc_result" in st.session_state:
            mc = st.session_state.mc_result
            col_a, col_b = st.columns(2)
            col_a.metric("Expected Days", f"{mc.expected_days:.0f}")
            col_a.metric("Median Days", f"{mc.median_days:.0f}")
            col_b.metric("90th Percentile", f"{mc.days_90th_pctile:.0f}")
            col_b.metric("P(90d)", f"{mc.probability_90d:.1%}")

        st.markdown("#### Breakeven Analysis")
        current_value = st.number_input("Current Value ($)", value=85000, step=1000)
        peak_value = st.number_input("Peak Value ($)", value=100000, step=1000)

        be = recovery_est.breakeven_analysis(current_value, peak_value)
        if be.required_gain_pct > 0:
            st.write(f"**Required Gain:** {be.required_gain_pct:.2%}")
            st.write(f"**Days to Breakeven:** {be.days_to_breakeven:.0f}")
            st.write(f"**Compounding Effect:** {be.compound_effect:.1f} extra days")
            st.write(f"**Deep Hole?** {'Yes' if be.is_deep_hole else 'No'}")
        else:
            st.success("No drawdown — already at or above peak!")

# --- Tab 4: Scenario Builder ---
with tab4:
    st.subheader("Scenario Builder")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Template Scenarios")
        template_name = st.selectbox(
            "Template",
            list(SCENARIO_TEMPLATES.keys()),
            format_func=lambda x: x.replace("_", " ").title(),
        )
        severity_mult = st.slider("Severity Multiplier", 0.5, 3.0, 1.0, 0.1)

        if st.button("Build from Template"):
            scn = scenario_builder.from_template(template_name, severity_multiplier=severity_mult)
            st.session_state.built_scenario = scn

        # List templates
        st.markdown("#### Available Templates")
        templates = scenario_builder.list_templates()
        tmpl_data = []
        for t in templates:
            tmpl_data.append({
                "Name": t["name"],
                "Category": t["category"],
                "Base Shock": f"{t['base_shock']:.0%}",
                "Duration": f"{t['duration_days']}d",
            })
        st.dataframe(pd.DataFrame(tmpl_data), use_container_width=True, hide_index=True)

    with col2:
        st.markdown("#### Built Scenario")
        if "built_scenario" in st.session_state:
            scn = st.session_state.built_scenario
            st.write(f"**Name:** {scn.name}")
            st.write(f"**Type:** {scn.scenario_type}")
            st.write(f"**Market Shock:** {scn.market_shock:.1%}")
            st.write(f"**Vol Multiplier:** {scn.volatility_multiplier:.2f}x")
            st.write(f"**Severity Score:** {scn.severity_score:.0f}/100")
            st.write(f"**Components:** {scn.n_components}")

            if scn.macro_shocks:
                st.markdown("##### Macro Shocks")
                macro_data = [{
                    "Variable": ms.variable,
                    "Magnitude": f"{ms.magnitude:.2%}",
                    "Direction": ms.direction,
                } for ms in scn.macro_shocks]
                st.dataframe(pd.DataFrame(macro_data), use_container_width=True, hide_index=True)

            if scn.sector_rotations:
                st.markdown("##### Sector Impacts")
                sector_data = [{
                    "Sector": sr.sector,
                    "Impact": f"{sr.impact_pct:.1%}",
                } for sr in scn.sector_rotations]
                st.dataframe(pd.DataFrame(sector_data), use_container_width=True, hide_index=True)

            # Validate
            validation = scenario_builder.validate_scenario(scn)
            if validation["valid"]:
                st.success("Scenario is consistent")
            else:
                for issue in validation["issues"]:
                    st.warning(issue)

    # Custom macro scenario
    st.markdown("---")
    st.markdown("#### Custom Macro Scenario")
    col_a, col_b = st.columns(2)
    with col_a:
        macro_var = st.selectbox("Macro Variable", ["interest_rates", "inflation", "growth", "dollar", "oil"])
        macro_dir = st.selectbox("Direction", ["up", "down"])
        macro_mag = st.slider("Magnitude", 0.01, 0.10, 0.02, 0.01, key="macro_mag")

        if st.button("Build Custom"):
            shock = MacroShock(variable=macro_var, magnitude=macro_mag, direction=macro_dir)
            custom_scn = scenario_builder.from_macro_shocks([shock], name="Custom Macro Scenario")
            st.session_state.custom_scenario = custom_scn

    with col_b:
        if "custom_scenario" in st.session_state:
            cs = st.session_state.custom_scenario
            st.write(f"**Market Shock:** {cs.market_shock:.2%}")
            if cs.sector_rotations:
                for sr in cs.sector_rotations:
                    st.write(f"- {sr.sector}: {sr.impact_pct:.1%}")

# --- Tab 5: Sensitivity Analysis ---
with tab5:
    st.subheader("Factor Sensitivity Analysis")

    shock_min = st.slider("Shock Range Min", -0.30, 0.0, -0.15, 0.01)
    shock_max = st.slider("Shock Range Max", 0.0, 0.30, 0.15, 0.01)
    n_points = st.slider("Points", 3, 11, 5, 2)

    if st.button("Run Sensitivity"):
        result = shock_engine.sensitivity_analysis(
            position_exposures, position_values, portfolio_value,
            shock_range=(shock_min, shock_max), n_points=n_points,
        )

        st.session_state.sensitivity_result = result

    if "sensitivity_result" in st.session_state:
        result = st.session_state.sensitivity_result

        col1, col2 = st.columns(2)
        col1.metric("Most Sensitive Factor", result["most_sensitive"])
        col2.metric("Least Sensitive Factor", result["least_sensitive"])

        st.markdown("#### Factor Betas")
        beta_data = [{"Factor": f, "Beta": b} for f, b in sorted(
            result["factor_betas"].items(), key=lambda x: abs(x[1]), reverse=True
        )]
        st.dataframe(pd.DataFrame(beta_data), use_container_width=True, hide_index=True)

        st.markdown("#### Sensitivity Curves")
        sens_df = pd.DataFrame()
        for factor, points in result["sensitivities"].items():
            for shock_val, impact_val in points:
                sens_df = pd.concat([sens_df, pd.DataFrame([{
                    "Shock": shock_val, "Factor": factor, "Impact": impact_val,
                }])], ignore_index=True)

        if not sens_df.empty:
            pivot = sens_df.pivot(index="Shock", columns="Factor", values="Impact")
            st.line_chart(pivot)
