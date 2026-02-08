"""Portfolio Scenarios Dashboard."""

import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

try:
    st.set_page_config(page_title="Portfolio Scenarios", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("📊 Portfolio Scenarios")

# Try to import scenarios module
try:
    from src.scenarios import (
        Portfolio, Holding, ProposedTrade, TradeAction,
        TargetAllocation, InvestmentGoal, GoalType,
        WhatIfAnalyzer, RebalanceSimulator, ScenarioAnalyzer,
        PortfolioComparer, GoalPlanner, ScenarioType,
        PREDEFINED_SCENARIOS,
    )
    SCENARIOS_AVAILABLE = True
except ImportError as e:
    SCENARIOS_AVAILABLE = False
    st.error(f"Scenarios module not available: {e}")


def get_demo_portfolio() -> Portfolio:
    """Get demo portfolio."""
    return Portfolio(
        name="Demo Portfolio",
        holdings=[
            Holding(symbol="AAPL", shares=100, cost_basis=15000, current_price=185, sector="Technology"),
            Holding(symbol="MSFT", shares=50, cost_basis=17500, current_price=378, sector="Technology"),
            Holding(symbol="GOOGL", shares=40, cost_basis=5200, current_price=141, sector="Technology"),
            Holding(symbol="JNJ", shares=75, cost_basis=11000, current_price=155, sector="Healthcare"),
            Holding(symbol="JPM", shares=60, cost_basis=10800, current_price=195, sector="Financial"),
        ],
        cash=15000,
    )


def render_portfolio_summary(portfolio: Portfolio):
    """Render portfolio summary."""
    st.subheader("Current Portfolio")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Value", f"${portfolio.total_value:,.2f}")
    col2.metric("Holdings", len(portfolio.holdings))
    col3.metric("Cash", f"${portfolio.cash:,.2f}")
    col4.metric("Cash %", f"{portfolio.cash/portfolio.total_value*100:.1f}%")
    
    # Holdings table
    data = []
    for h in portfolio.holdings:
        weight = h.market_value / portfolio.total_value * 100
        data.append({
            "Symbol": h.symbol,
            "Shares": h.shares,
            "Price": f"${h.current_price:.2f}",
            "Value": f"${h.market_value:,.2f}",
            "Weight": f"{weight:.1f}%",
            "Gain/Loss": f"${h.unrealized_gain:,.2f}",
            "Sector": h.sector,
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_what_if_tab():
    """Render what-if analysis tab."""
    st.subheader("What-If Trade Analysis")
    st.write("Simulate trades before executing them.")
    
    portfolio = get_demo_portfolio()
    render_portfolio_summary(portfolio)
    
    st.markdown("---")
    st.subheader("Proposed Trades")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        symbol = st.text_input("Symbol", value="NVDA").upper()
    with col2:
        action = st.selectbox("Action", options=["buy", "sell", "sell_all"])
    with col3:
        if action == "sell_all":
            amount = 0
        else:
            amount = st.number_input("Dollar Amount", value=5000, min_value=0)
    with col4:
        price = st.number_input("Price", value=800.0, min_value=0.01)
    
    if st.button("Simulate Trade", type="primary"):
        analyzer = WhatIfAnalyzer()
        
        if action == "sell_all":
            trade = ProposedTrade(symbol=symbol, action=TradeAction.SELL_ALL)
        else:
            trade = ProposedTrade(
                symbol=symbol,
                action=TradeAction.BUY if action == "buy" else TradeAction.SELL,
                dollar_amount=amount,
                assumed_price=price,
            )
        
        result = analyzer.simulate(portfolio, [trade])
        
        st.success("Simulation complete!")
        
        col1, col2, col3 = st.columns(3)
        col1.metric(
            "New Portfolio Value",
            f"${result.resulting_portfolio.total_value:,.2f}",
            f"${result.value_change:,.2f}"
        )
        col2.metric("Total Cost", f"${result.total_cost:.2f}")
        col3.metric("Est. Tax Impact", f"${result.tax_impact.estimated_tax:.2f}")
        
        # Risk impact
        if result.risk_impact:
            st.markdown("**Risk Impact:**")
            st.write(f"- Beta change: {result.risk_impact.beta_change:+.3f}")
            st.write(f"- Concentration change: {result.risk_impact.concentration_change:+.3f}")


def render_rebalance_tab():
    """Render rebalancing tab."""
    st.subheader("Rebalancing Simulation")
    st.write("Simulate rebalancing to a target allocation.")
    
    portfolio = get_demo_portfolio()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Current Allocation:**")
        weights = portfolio.get_weights()
        for symbol, weight in weights.items():
            st.write(f"- {symbol}: {weight*100:.1f}%")
        st.write(f"- Cash: {portfolio.cash/portfolio.total_value*100:.1f}%")
    
    with col2:
        st.markdown("**Target Allocation:**")
        targets = {}
        for symbol in weights.keys():
            targets[symbol] = st.slider(
                f"{symbol} Target %",
                0, 50, int(25),
                key=f"target_{symbol}"
            ) / 100
        
        remaining = 1.0 - sum(targets.values())
        st.write(f"Remaining (Cash): {remaining*100:.1f}%")
    
    if st.button("Simulate Rebalance", type="primary"):
        target = TargetAllocation(name="Custom", targets=targets)
        
        simulator = RebalanceSimulator()
        result = simulator.simulate(portfolio, target)
        
        st.success("Simulation complete!")
        
        st.markdown("**Required Trades:**")
        for trade in result.required_trades:
            action = trade.action.value
            value = trade.calculated_value
            st.write(f"- {action.upper()} ${value:,.2f} of {trade.symbol}")
        
        col1, col2 = st.columns(2)
        col1.metric("Est. Trading Cost", f"${result.estimated_costs:.2f}")
        if result.tax_impact:
            col2.metric("Est. Tax Impact", f"${result.tax_impact.estimated_tax:.2f}")


def render_stress_test_tab():
    """Render stress testing tab."""
    st.subheader("Market Stress Testing")
    st.write("See how your portfolio performs under different market scenarios.")
    
    portfolio = get_demo_portfolio()
    analyzer = ScenarioAnalyzer()
    
    # Scenario selector
    scenarios = analyzer.get_all_scenarios()
    scenario_names = {s.scenario_type: s.name for s in scenarios}
    
    selected = st.selectbox(
        "Select Scenario",
        options=list(scenario_names.keys()),
        format_func=lambda x: scenario_names[x]
    )
    
    scenario = analyzer.get_scenario(selected)
    if scenario:
        st.info(scenario.description)
        st.write(f"Market Impact: {scenario.market_change_pct*100:+.0f}%")
    
    if st.button("Run Stress Test", type="primary"):
        result = analyzer.apply_scenario(portfolio, selected)
        
        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Portfolio Value",
            f"${result.ending_value:,.2f}",
            f"${result.value_change:,.2f}"
        )
        col2.metric("Change %", f"{result.pct_change:.1f}%")
        col3.metric("Positions Down", result.positions_down)
        
        # Position impacts
        st.markdown("**Position Impacts:**")
        impact_data = []
        for impact in result.position_impacts:
            impact_data.append({
                "Symbol": impact.symbol,
                "Starting": f"${impact.starting_value:,.2f}",
                "Ending": f"${impact.ending_value:,.2f}",
                "Change": f"${impact.change:,.2f}",
                "Change %": f"{impact.change_pct:.1f}%",
            })
        
        df = pd.DataFrame(impact_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Run all scenarios
    st.markdown("---")
    if st.button("Run All Scenarios"):
        results = analyzer.run_all_scenarios(portfolio)
        
        summary = []
        for r in results:
            summary.append({
                "Scenario": r.scenario.name,
                "Starting": f"${r.starting_value:,.2f}",
                "Ending": f"${r.ending_value:,.2f}",
                "Change %": f"{r.pct_change:.1f}%",
            })
        
        df = pd.DataFrame(summary)
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_goals_tab():
    """Render investment goals tab."""
    st.subheader("Investment Goals")
    st.write("Plan and track your investment goals.")
    
    planner = GoalPlanner()
    
    # Goal input
    col1, col2 = st.columns(2)
    
    with col1:
        goal_name = st.text_input("Goal Name", value="Retirement")
        target_amount = st.number_input("Target Amount ($)", value=1_000_000, step=10000)
        current_amount = st.number_input("Current Savings ($)", value=100_000, step=1000)
    
    with col2:
        years = st.slider("Years to Goal", 1, 40, 20)
        monthly_contrib = st.number_input("Monthly Contribution ($)", value=1500, step=100)
        expected_return = st.slider("Expected Return (%)", 1, 15, 7) / 100
    
    target_date = date.today() + relativedelta(years=years)
    
    if st.button("Calculate Projection", type="primary"):
        goal = InvestmentGoal(
            name=goal_name,
            target_amount=target_amount,
            target_date=target_date,
            current_amount=current_amount,
            monthly_contribution=monthly_contrib,
            expected_return=expected_return,
        )
        
        projection = planner.project_goal(goal, monte_carlo=True)
        
        # Results
        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Projected Value",
            f"${goal.projected_value:,.0f}",
            f"vs target: ${goal.shortfall:,.0f}" if goal.shortfall > 0 else "On track!"
        )
        col2.metric("Probability of Success", f"{goal.probability_of_success:.0%}")
        col3.metric("Required Monthly", f"${goal.required_monthly:,.0f}")
        
        # Chart
        st.markdown("**Projection Chart:**")
        chart_data = pd.DataFrame({
            "Month": projection.months,
            "Projected": projection.projected_values,
            "10th Percentile": projection.p10_values,
            "90th Percentile": projection.p90_values,
        })
        
        st.line_chart(chart_data.set_index("Month")[["Projected", "10th Percentile", "90th Percentile"]])
        
        # Target line
        st.write(f"Target: ${target_amount:,.0f} (shown as horizontal line at {target_amount:,.0f})")


def main():
    if not SCENARIOS_AVAILABLE:
        return
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔄 What-If Analysis",
        "⚖️ Rebalancing",
        "📉 Stress Testing",
        "🎯 Investment Goals",
    ])
    
    with tab1:
        render_what_if_tab()
    
    with tab2:
        render_rebalance_tab()
    
    with tab3:
        render_stress_test_tab()
    
    with tab4:
        render_goals_tab()



main()
