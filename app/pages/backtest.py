"""Backtest Dashboard Streamlit Page.

Professional backtesting interface with:
- Strategy configuration
- Backtest execution
- Tear sheet visualization
- Walk-forward analysis
- Monte Carlo simulation
- Strategy comparison
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, datetime, timedelta

# Page config
st.set_page_config(
    page_title="Axion Backtesting Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Import backtesting module
try:
    from src.backtesting import (
        BacktestEngine, BacktestConfig, BacktestResult,
        CostModelConfig, ExecutionConfig, RiskConfig,
        RebalanceFrequency, FillModel, BarType,
        TearSheetGenerator, StrategyComparator,
        MonteCarloAnalyzer, MonteCarloConfig,
        Signal, OrderSide, MarketEvent,
    )
    BACKTEST_AVAILABLE = True
except ImportError as e:
    BACKTEST_AVAILABLE = False
    st.error(f"Backtesting module not available: {e}")


def init_session_state():
    """Initialize session state variables."""
    if "backtest_results" not in st.session_state:
        st.session_state.backtest_results = {}
    if "selected_result" not in st.session_state:
        st.session_state.selected_result = None


def render_configuration():
    """Render backtest configuration section."""
    st.subheader("📋 Backtest Configuration")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Time Range**")
        start_date = st.date_input(
            "Start Date",
            value=date(2020, 1, 1),
            min_value=date(2010, 1, 1),
            max_value=date.today(),
        )
        end_date = st.date_input(
            "End Date",
            value=date(2024, 12, 31),
            min_value=date(2010, 1, 1),
            max_value=date.today(),
        )
        
        bar_type = st.selectbox(
            "Bar Frequency",
            options=["1d", "1h", "15m", "5m", "1m"],
            index=0,
        )
    
    with col2:
        st.markdown("**Capital & Rebalancing**")
        initial_capital = st.number_input(
            "Initial Capital ($)",
            min_value=1000,
            max_value=10_000_000,
            value=100_000,
            step=10000,
        )
        
        rebalance_freq = st.selectbox(
            "Rebalance Frequency",
            options=["daily", "weekly", "monthly", "quarterly"],
            index=2,
        )
        
        benchmark = st.text_input("Benchmark", value="SPY")
    
    with col3:
        st.markdown("**Risk Limits**")
        max_position = st.slider(
            "Max Position Size (%)",
            min_value=1,
            max_value=50,
            value=15,
        )
        
        max_drawdown_halt = st.slider(
            "Max Drawdown Halt (%)",
            min_value=-50,
            max_value=-5,
            value=-15,
        )
        
        stop_loss = st.slider(
            "Position Stop-Loss (%)",
            min_value=-50,
            max_value=-5,
            value=-15,
        )
    
    # Cost model
    with st.expander("💰 Cost Model Settings"):
        cost_col1, cost_col2 = st.columns(2)
        
        with cost_col1:
            commission = st.number_input(
                "Commission per Share ($)",
                min_value=0.0,
                max_value=0.1,
                value=0.0,
                step=0.001,
                format="%.3f",
            )
            spread_bps = st.number_input(
                "Min Spread (bps)",
                min_value=0.0,
                max_value=20.0,
                value=1.0,
                step=0.5,
            )
        
        with cost_col2:
            market_impact = st.number_input(
                "Market Impact (bps per 1% ADV)",
                min_value=0.0,
                max_value=50.0,
                value=10.0,
                step=1.0,
            )
            fill_model = st.selectbox(
                "Fill Model",
                options=["slippage", "immediate", "vwap", "volume_participation"],
                index=0,
            )
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "bar_type": bar_type,
        "initial_capital": initial_capital,
        "rebalance_freq": rebalance_freq,
        "benchmark": benchmark,
        "max_position": max_position / 100,
        "max_drawdown_halt": max_drawdown_halt / 100,
        "stop_loss": stop_loss / 100,
        "commission": commission,
        "spread_bps": spread_bps,
        "market_impact": market_impact,
        "fill_model": fill_model,
    }


def render_strategy_selector():
    """Render strategy selection section."""
    st.subheader("🎯 Strategy Selection")
    
    strategy_type = st.selectbox(
        "Strategy Type",
        options=[
            "Equal Weight",
            "Momentum",
            "Value",
            "Quality",
            "Multi-Factor",
            "Mean Reversion",
        ],
        index=0,
    )
    
    # Strategy-specific parameters
    params = {}
    
    if strategy_type == "Momentum":
        col1, col2 = st.columns(2)
        with col1:
            params["lookback"] = st.slider("Lookback Period (days)", 20, 252, 126)
        with col2:
            params["top_n"] = st.slider("Top N Stocks", 5, 50, 20)
    
    elif strategy_type == "Value":
        col1, col2 = st.columns(2)
        with col1:
            params["pe_threshold"] = st.slider("Max P/E Ratio", 5, 50, 20)
        with col2:
            params["pb_threshold"] = st.slider("Max P/B Ratio", 0.5, 5.0, 3.0)
    
    elif strategy_type == "Multi-Factor":
        st.markdown("**Factor Weights**")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            params["momentum_weight"] = st.slider("Momentum", 0.0, 1.0, 0.25)
        with col2:
            params["value_weight"] = st.slider("Value", 0.0, 1.0, 0.25)
        with col3:
            params["quality_weight"] = st.slider("Quality", 0.0, 1.0, 0.25)
        with col4:
            params["volatility_weight"] = st.slider("Low Vol", 0.0, 1.0, 0.25)
    
    # Universe selection
    universe = st.multiselect(
        "Universe",
        options=["S&P 500", "NASDAQ 100", "Russell 2000", "Custom"],
        default=["S&P 500"],
    )
    
    return strategy_type, params, universe


def render_results(result: "BacktestResult"):
    """Render backtest results."""
    st.subheader("📈 Backtest Results")
    
    m = result.metrics
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Return",
            f"{m.total_return*100:.1f}%",
            delta=f"vs Benchmark: {m.alpha*100:+.1f}%",
        )
    with col2:
        st.metric(
            "Sharpe Ratio",
            f"{m.sharpe_ratio:.2f}",
            delta=f"Sortino: {m.sortino_ratio:.2f}",
        )
    with col3:
        st.metric(
            "Max Drawdown",
            f"{m.max_drawdown*100:.1f}%",
        )
    with col4:
        st.metric(
            "Win Rate",
            f"{m.win_rate*100:.1f}%",
            delta=f"PF: {m.profit_factor:.2f}",
        )
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Performance",
        "📉 Drawdown",
        "💹 Trades",
        "📋 Tear Sheet",
    ])
    
    with tab1:
        render_performance_charts(result)
    
    with tab2:
        render_drawdown_analysis(result)
    
    with tab3:
        render_trade_analysis(result)
    
    with tab4:
        render_tearsheet(result)


def render_performance_charts(result: "BacktestResult"):
    """Render performance charts."""
    if result.equity_curve.empty:
        st.warning("No equity curve data available")
        return
    
    # Equity curve
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=result.equity_curve.index,
        y=result.equity_curve.values,
        name="Strategy",
        line=dict(color="blue", width=2),
    ))
    
    if not result.benchmark_curve.empty:
        # Normalize benchmark to same start
        normalized_bench = result.benchmark_curve / result.benchmark_curve.iloc[0] * result.equity_curve.iloc[0]
        fig.add_trace(go.Scatter(
            x=normalized_bench.index,
            y=normalized_bench.values,
            name="Benchmark",
            line=dict(color="gray", width=1, dash="dash"),
        ))
    
    fig.update_layout(
        title="Equity Curve",
        xaxis_title="Date",
        yaxis_title="Portfolio Value ($)",
        height=400,
        hovermode="x unified",
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Monthly returns heatmap
    if not result.monthly_returns.empty:
        st.markdown("**Monthly Returns Heatmap**")
        
        monthly = result.monthly_returns.copy()
        monthly_df = pd.DataFrame({
            "year": monthly.index.year,
            "month": monthly.index.month,
            "return": monthly.values * 100,
        })
        
        pivot = monthly_df.pivot(index="year", columns="month", values="return")
        pivot.columns = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][:len(pivot.columns)]
        
        fig = px.imshow(
            pivot,
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0,
            aspect="auto",
            text_auto=".1f",
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)


def render_drawdown_analysis(result: "BacktestResult"):
    """Render drawdown analysis."""
    if result.drawdown_curve.empty:
        st.warning("No drawdown data available")
        return
    
    # Drawdown chart
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=result.drawdown_curve.index,
        y=result.drawdown_curve.values * 100,
        fill="tozeroy",
        name="Drawdown",
        line=dict(color="red"),
        fillcolor="rgba(255, 0, 0, 0.3)",
    ))
    
    fig.update_layout(
        title="Drawdown Chart",
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        height=300,
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Drawdown statistics
    col1, col2, col3 = st.columns(3)
    
    m = result.metrics
    with col1:
        st.metric("Max Drawdown", f"{m.max_drawdown*100:.1f}%")
    with col2:
        st.metric("Avg Drawdown", f"{m.avg_drawdown*100:.1f}%")
    with col3:
        st.metric("Calmar Ratio", f"{m.calmar_ratio:.2f}")


def render_trade_analysis(result: "BacktestResult"):
    """Render trade analysis."""
    if not result.trades:
        st.warning("No trades recorded")
        return
    
    trades_df = result.get_trades_df()
    
    # Trade statistics
    col1, col2, col3, col4 = st.columns(4)
    
    m = result.metrics
    with col1:
        st.metric("Total Trades", m.total_trades)
    with col2:
        st.metric("Winning", f"{m.winning_trades} ({m.win_rate*100:.0f}%)")
    with col3:
        st.metric("Avg Win", f"${m.avg_win:,.0f}")
    with col4:
        st.metric("Avg Loss", f"${m.avg_loss:,.0f}")
    
    # P&L distribution
    fig = px.histogram(
        trades_df,
        x="pnl",
        nbins=50,
        title="Trade P&L Distribution",
        color_discrete_sequence=["steelblue"],
    )
    fig.add_vline(x=0, line_dash="dash", line_color="red")
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)
    
    # Recent trades table
    st.markdown("**Recent Trades**")
    display_df = trades_df.tail(20).copy()
    display_df["pnl"] = display_df["pnl"].apply(lambda x: f"${x:,.0f}")
    display_df["pnl_pct"] = (display_df["pnl_pct"] * 100).apply(lambda x: f"{x:.1f}%")
    st.dataframe(display_df, use_container_width=True)


def render_tearsheet(result: "BacktestResult"):
    """Render full tear sheet."""
    generator = TearSheetGenerator()
    tearsheet = generator.generate(result, "Strategy")
    
    st.code(tearsheet, language=None)
    
    # Download button
    st.download_button(
        label="📥 Download Tear Sheet",
        data=tearsheet,
        file_name="tearsheet.txt",
        mime="text/plain",
    )


def render_monte_carlo():
    """Render Monte Carlo analysis section."""
    st.subheader("🎲 Monte Carlo Analysis")
    
    if "selected_result" not in st.session_state or st.session_state.selected_result is None:
        st.info("Run a backtest first to perform Monte Carlo analysis")
        return
    
    result = st.session_state.selected_result
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        n_simulations = st.slider(
            "Number of Simulations",
            min_value=100,
            max_value=10000,
            value=1000,
            step=100,
        )
        
        run_mc = st.button("🚀 Run Monte Carlo", type="primary")
    
    if run_mc and result.trades:
        with st.spinner(f"Running {n_simulations} simulations..."):
            analyzer = MonteCarloAnalyzer(MonteCarloConfig(n_simulations=n_simulations))
            mc_result = analyzer.bootstrap_analysis(result.trades)
        
        with col2:
            # Results
            st.markdown("**Results**")
            
            metrics_col1, metrics_col2 = st.columns(2)
            
            with metrics_col1:
                st.metric(
                    "Sharpe 95% CI",
                    f"[{mc_result.sharpe_95ci[0]:.2f}, {mc_result.sharpe_95ci[1]:.2f}]",
                )
                st.metric(
                    "CAGR 95% CI",
                    f"[{mc_result.cagr_95ci[0]*100:.1f}%, {mc_result.cagr_95ci[1]*100:.1f}%]",
                )
            
            with metrics_col2:
                st.metric("% Profitable", f"{mc_result.pct_profitable*100:.1f}%")
                st.metric("% Beats Benchmark", f"{mc_result.pct_beats_benchmark*100:.1f}%")
        
        # Distribution plot
        fig = go.Figure()
        
        fig.add_trace(go.Histogram(
            x=mc_result.sharpe_distribution,
            name="Sharpe Distribution",
            nbinsx=50,
            opacity=0.7,
        ))
        
        fig.add_vline(
            x=result.metrics.sharpe_ratio,
            line_dash="dash",
            line_color="red",
            annotation_text="Actual",
        )
        
        fig.update_layout(
            title="Monte Carlo Sharpe Distribution",
            xaxis_title="Sharpe Ratio",
            yaxis_title="Frequency",
            height=300,
        )
        
        st.plotly_chart(fig, use_container_width=True)


def render_comparison():
    """Render strategy comparison section."""
    st.subheader("⚖️ Strategy Comparison")
    
    if len(st.session_state.backtest_results) < 2:
        st.info("Run at least 2 backtests to compare strategies")
        return
    
    # Select strategies to compare
    selected = st.multiselect(
        "Select Strategies to Compare",
        options=list(st.session_state.backtest_results.keys()),
        default=list(st.session_state.backtest_results.keys())[:3],
    )
    
    if len(selected) < 2:
        return
    
    results = {name: st.session_state.backtest_results[name] for name in selected}
    
    comparator = StrategyComparator()
    comparison = comparator.compare(results)
    
    # Returns comparison table
    st.markdown("**Returns Comparison**")
    returns_df = comparison["returns_table"].copy()
    for col in returns_df.columns:
        if "Return" in col or "CAGR" in col or "Alpha" in col or "Rate" in col:
            returns_df[col] = returns_df[col].apply(lambda x: f"{x*100:.1f}%")
    st.dataframe(returns_df, use_container_width=True)
    
    # Risk comparison table
    st.markdown("**Risk Comparison**")
    risk_df = comparison["risk_table"].copy()
    for col in ["Volatility", "Downside Vol", "Max Drawdown"]:
        if col in risk_df.columns:
            risk_df[col] = risk_df[col].apply(lambda x: f"{x*100:.1f}%")
    for col in ["Sharpe", "Sortino", "Calmar"]:
        if col in risk_df.columns:
            risk_df[col] = risk_df[col].apply(lambda x: f"{x:.2f}")
    st.dataframe(risk_df, use_container_width=True)
    
    # Winner badges
    st.markdown("**Best by Metric**")
    winners = comparison["winner_by_metric"]
    badges = " | ".join([f"**{m.title()}**: {w}" for m, w in winners.items()])
    st.markdown(badges)
    
    # Equity curves comparison
    fig = go.Figure()
    for name, result in results.items():
        if not result.equity_curve.empty:
            # Normalize to 100
            normalized = result.equity_curve / result.equity_curve.iloc[0] * 100
            fig.add_trace(go.Scatter(
                x=normalized.index,
                y=normalized.values,
                name=name,
                mode="lines",
            ))
    
    fig.update_layout(
        title="Normalized Equity Curves",
        xaxis_title="Date",
        yaxis_title="Value (Base = 100)",
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def create_demo_result():
    """Create demo backtest result for display."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", "2024-12-31", freq="B")
    
    # Generate realistic equity curve
    returns = np.random.normal(0.0004, 0.012, len(dates))
    equity = 100_000 * np.cumprod(1 + returns)
    
    equity_curve = pd.Series(equity, index=dates)
    
    # Drawdown
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    drawdown_curve = pd.Series(drawdown, index=dates)
    
    # Monthly returns
    monthly = (1 + pd.Series(returns, index=dates)).resample("ME").prod() - 1
    
    # Create trades
    trades = []
    from src.backtesting.models import Trade
    base_date = datetime(2020, 1, 1)
    for i in range(150):
        is_win = np.random.random() > 0.42
        pnl = np.random.uniform(200, 800) if is_win else np.random.uniform(-500, -100)
        trades.append(Trade(
            symbol=f"STOCK{i % 20}",
            entry_date=base_date + timedelta(days=i * 7),
            exit_date=base_date + timedelta(days=i * 7 + np.random.randint(5, 30)),
            side=OrderSide.BUY,
            entry_price=100.0,
            exit_price=100.0 + pnl / 100,
            qty=100,
            pnl=pnl,
            pnl_pct=pnl / 10000,
            hold_days=np.random.randint(5, 30),
        ))
    
    from src.backtesting.models import BacktestMetrics, BacktestResult
    
    metrics = BacktestMetrics(
        total_return=(equity[-1] / equity[0]) - 1,
        cagr=0.112,
        benchmark_return=0.095,
        benchmark_cagr=0.085,
        alpha=0.027,
        volatility=0.182,
        downside_volatility=0.128,
        max_drawdown=drawdown.min(),
        avg_drawdown=-0.042,
        sharpe_ratio=0.88,
        sortino_ratio=1.25,
        calmar_ratio=0.72,
        information_ratio=0.58,
        total_trades=len(trades),
        winning_trades=sum(1 for t in trades if t.pnl > 0),
        losing_trades=sum(1 for t in trades if t.pnl <= 0),
        win_rate=sum(1 for t in trades if t.pnl > 0) / len(trades),
        avg_win=np.mean([t.pnl for t in trades if t.pnl > 0]),
        avg_loss=np.mean([t.pnl for t in trades if t.pnl <= 0]),
        profit_factor=1.58,
        avg_trade_pnl=np.mean([t.pnl for t in trades]),
        avg_hold_days=18,
        total_commission=0,
        total_slippage=3200,
        turnover=2.8,
        best_month=monthly.max(),
        worst_month=monthly.min(),
    )
    
    return BacktestResult(
        metrics=metrics,
        equity_curve=equity_curve,
        benchmark_curve=equity_curve * 0.9,  # Simplified benchmark
        drawdown_curve=drawdown_curve,
        trades=trades,
        monthly_returns=monthly,
        daily_returns=pd.Series(returns, index=dates),
    )


def main():
    """Main application."""
    st.title("📊 Professional Backtesting Engine")
    
    if not BACKTEST_AVAILABLE:
        st.error("Backtesting module not available. Please check your installation.")
        return
    
    init_session_state()
    
    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Select Page",
            options=[
                "🔧 Configure & Run",
                "📈 Results",
                "🎲 Monte Carlo",
                "⚖️ Compare",
            ],
        )
        
        st.divider()
        
        # Saved backtests
        if st.session_state.backtest_results:
            st.markdown("**Saved Results**")
            for name in st.session_state.backtest_results:
                if st.button(f"📁 {name}", key=f"load_{name}"):
                    st.session_state.selected_result = st.session_state.backtest_results[name]
        
        # Demo mode
        st.divider()
        if st.button("🎭 Load Demo Data"):
            demo_result = create_demo_result()
            st.session_state.backtest_results["Demo Strategy"] = demo_result
            st.session_state.selected_result = demo_result
            st.rerun()
    
    # Main content
    if page == "🔧 Configure & Run":
        config = render_configuration()
        strategy_type, params, universe = render_strategy_selector()
        
        st.divider()
        
        col1, col2 = st.columns([1, 3])
        with col1:
            run_name = st.text_input("Run Name", value=f"{strategy_type}_{datetime.now().strftime('%H%M')}")
        with col2:
            if st.button("🚀 Run Backtest", type="primary", use_container_width=True):
                st.info("Backtest would run here with real data. Using demo data for display.")
                demo_result = create_demo_result()
                st.session_state.backtest_results[run_name] = demo_result
                st.session_state.selected_result = demo_result
                st.rerun()
    
    elif page == "📈 Results":
        if st.session_state.selected_result:
            render_results(st.session_state.selected_result)
        else:
            st.info("No results to display. Run a backtest or load demo data.")
    
    elif page == "🎲 Monte Carlo":
        render_monte_carlo()
    
    elif page == "⚖️ Compare":
        render_comparison()


if __name__ == "__main__":
    main()
