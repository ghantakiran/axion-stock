"""Trading Dashboard - Paper & Live Trading Interface.

Provides:
- Real-time positions and P&L
- Order execution interface
- Rebalance preview and execution
- Trade history
- Portfolio performance
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Axion Trading",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Import after path setup
try:
    from src.execution import (
        TradingService,
        TradingConfig,
        OrderSide,
        OrderType,
        OrderStatus,
    )
    EXECUTION_AVAILABLE = True
except ImportError:
    EXECUTION_AVAILABLE = False


def run_async(coro):
    """Run async function in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def init_session_state():
    """Initialize session state for trading."""
    if "trading_service" not in st.session_state:
        st.session_state.trading_service = None
    if "trading_connected" not in st.session_state:
        st.session_state.trading_connected = False
    if "paper_initial_cash" not in st.session_state:
        st.session_state.paper_initial_cash = 100000
    if "rebalance_proposal" not in st.session_state:
        st.session_state.rebalance_proposal = None


def render_connection_panel():
    """Render connection panel for broker setup."""
    st.markdown("### 🔌 Connection")

    mode = st.radio(
        "Trading Mode",
        ["Paper Trading (Local)", "Alpaca Paper", "Alpaca Live"],
        help="Select your trading mode. Paper trading is simulated.",
    )

    if mode == "Paper Trading (Local)":
        initial_cash = st.number_input(
            "Initial Cash ($)",
            min_value=1000,
            max_value=10_000_000,
            value=st.session_state.paper_initial_cash,
            step=10000,
        )
        st.session_state.paper_initial_cash = initial_cash

        if st.button("Connect Paper Trading", type="primary"):
            try:
                config = TradingConfig(
                    paper_trading=True,
                    initial_cash=initial_cash,
                )
                service = TradingService(config)
                success = run_async(service.connect())

                if success:
                    st.session_state.trading_service = service
                    st.session_state.trading_connected = True
                    st.success("Connected to paper trading!")
                    st.rerun()
                else:
                    st.error("Failed to connect")
            except Exception as e:
                st.error(f"Connection error: {e}")

    elif mode == "Alpaca Paper":
        api_key = st.text_input("Alpaca API Key", type="password")
        secret_key = st.text_input("Alpaca Secret Key", type="password")

        if st.button("Connect to Alpaca Paper", type="primary"):
            if not api_key or not secret_key:
                st.error("Please enter API credentials")
            else:
                try:
                    config = TradingConfig(
                        paper_trading=False,
                        alpaca_api_key=api_key,
                        alpaca_secret_key=secret_key,
                        alpaca_paper=True,
                    )
                    service = TradingService(config)
                    success = run_async(service.connect())

                    if success:
                        st.session_state.trading_service = service
                        st.session_state.trading_connected = True
                        st.success("Connected to Alpaca Paper!")
                        st.rerun()
                    else:
                        st.error("Failed to connect")
                except Exception as e:
                    st.error(f"Connection error: {e}")

    else:  # Alpaca Live
        st.warning("⚠️ LIVE TRADING - Real money will be used!")
        api_key = st.text_input("Alpaca Live API Key", type="password")
        secret_key = st.text_input("Alpaca Live Secret Key", type="password")

        confirm = st.checkbox("I understand this uses real money")

        if st.button("Connect to Alpaca Live", type="primary", disabled=not confirm):
            if not api_key or not secret_key:
                st.error("Please enter API credentials")
            else:
                try:
                    config = TradingConfig(
                        paper_trading=False,
                        alpaca_api_key=api_key,
                        alpaca_secret_key=secret_key,
                        alpaca_paper=False,
                    )
                    service = TradingService(config)
                    success = run_async(service.connect())

                    if success:
                        st.session_state.trading_service = service
                        st.session_state.trading_connected = True
                        st.success("Connected to Alpaca Live!")
                        st.rerun()
                    else:
                        st.error("Failed to connect")
                except Exception as e:
                    st.error(f"Connection error: {e}")


def render_account_summary():
    """Render account summary metrics."""
    service = st.session_state.trading_service

    try:
        summary = run_async(service.get_portfolio_summary())

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Equity",
                f"${summary['equity']:,.2f}",
            )
        with col2:
            st.metric(
                "Cash",
                f"${summary['cash']:,.2f}",
            )
        with col3:
            pnl = summary['total_unrealized_pnl']
            pnl_pct = summary['total_unrealized_pnl_pct']
            st.metric(
                "Unrealized P&L",
                f"${pnl:+,.2f}",
                delta=f"{pnl_pct:+.2%}",
            )
        with col4:
            st.metric(
                "Positions",
                summary['num_positions'],
            )

    except Exception as e:
        st.error(f"Failed to get account summary: {e}")


def render_positions():
    """Render positions table."""
    service = st.session_state.trading_service

    st.markdown("### 📊 Positions")

    try:
        positions = run_async(service.get_positions())

        if not positions:
            st.info("No open positions")
            return

        # Build DataFrame
        data = []
        for p in positions:
            data.append({
                "Symbol": p.symbol,
                "Shares": p.qty,
                "Avg Cost": f"${p.avg_entry_price:.2f}",
                "Current": f"${p.current_price:.2f}",
                "Market Value": f"${p.market_value:,.2f}",
                "P&L": f"${p.unrealized_pnl:+,.2f}",
                "P&L %": f"{p.unrealized_pnl_pct:+.2%}",
            })

        df = pd.DataFrame(data)

        # Style the dataframe
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

        # Quick close buttons
        st.markdown("#### Quick Actions")
        cols = st.columns(min(len(positions), 5))
        for i, pos in enumerate(positions[:5]):
            with cols[i]:
                if st.button(f"Close {pos.symbol}", key=f"close_{pos.symbol}"):
                    try:
                        result = run_async(service.close_position(pos.symbol))
                        if result.success:
                            st.success(f"Closed {pos.symbol}")
                            st.rerun()
                        else:
                            st.error(result.error_message)
                    except Exception as e:
                        st.error(str(e))

    except Exception as e:
        st.error(f"Failed to get positions: {e}")


def render_trade_panel():
    """Render trade execution panel."""
    service = st.session_state.trading_service

    st.markdown("### 🎯 Execute Trade")

    col1, col2 = st.columns(2)

    with col1:
        symbol = st.text_input("Symbol", placeholder="AAPL").upper()
        side = st.selectbox("Side", ["BUY", "SELL"])

    with col2:
        sizing = st.selectbox("Size By", ["Dollars", "Shares"])

        if sizing == "Dollars":
            amount = st.number_input("Amount ($)", min_value=100, value=5000, step=100)
        else:
            amount = st.number_input("Shares", min_value=1, value=10, step=1)

    order_type = st.selectbox("Order Type", ["Market", "Limit"])
    limit_price = None
    if order_type == "Limit":
        limit_price = st.number_input("Limit Price ($)", min_value=0.01, step=0.01)

    if st.button("Submit Order", type="primary"):
        if not symbol:
            st.error("Enter a symbol")
            return

        try:
            if side == "BUY":
                if sizing == "Dollars":
                    result = run_async(service.buy(symbol, dollars=amount, limit_price=limit_price))
                else:
                    result = run_async(service.buy(symbol, shares=amount, limit_price=limit_price))
            else:
                if sizing == "Dollars":
                    # Need to calculate shares for sell by dollars
                    pos = run_async(service.get_position(symbol))
                    if pos:
                        shares = min(pos.qty, amount / pos.current_price)
                        result = run_async(service.sell(symbol, shares=shares, limit_price=limit_price))
                    else:
                        st.error(f"No position in {symbol}")
                        return
                else:
                    result = run_async(service.sell(symbol, shares=amount, limit_price=limit_price))

            if result.success:
                st.success(f"Order submitted: {result.order.status.value}")
                if result.order.filled_avg_price:
                    st.info(f"Filled at ${result.order.filled_avg_price:.2f}")
                st.rerun()
            else:
                st.error(f"Order failed: {result.error_message}")

        except Exception as e:
            st.error(f"Error: {e}")


def render_rebalance_panel():
    """Render rebalancing interface."""
    service = st.session_state.trading_service

    st.markdown("### ⚖️ Rebalance Portfolio")

    # Target weights input
    st.markdown("**Enter Target Weights (must sum to 100%)**")

    # Default stocks
    default_stocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]

    weights = {}
    cols = st.columns(len(default_stocks))

    for i, symbol in enumerate(default_stocks):
        with cols[i]:
            w = st.number_input(
                symbol,
                min_value=0,
                max_value=100,
                value=20,
                step=5,
                key=f"weight_{symbol}",
            )
            if w > 0:
                weights[symbol] = w / 100

    # Custom stocks
    custom_input = st.text_input(
        "Additional stocks (comma-separated, e.g., 'TSLA:10,META:15')",
        placeholder="SYMBOL:WEIGHT%",
    )

    if custom_input:
        for item in custom_input.split(","):
            if ":" in item:
                parts = item.strip().split(":")
                if len(parts) == 2:
                    sym = parts[0].strip().upper()
                    try:
                        w = float(parts[1].strip()) / 100
                        weights[sym] = w
                    except ValueError:
                        pass

    # Show total
    total = sum(weights.values()) * 100
    if abs(total - 100) < 0.01:
        st.success(f"Total: {total:.0f}%")
    else:
        st.warning(f"Total: {total:.0f}% (should be 100%)")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Preview Rebalance"):
            if not weights:
                st.error("Enter target weights")
                return

            try:
                proposal = run_async(service.preview_rebalance(weights))
                st.session_state.rebalance_proposal = proposal
            except Exception as e:
                st.error(f"Error: {e}")

    # Show proposal if exists
    if st.session_state.rebalance_proposal:
        proposal = st.session_state.rebalance_proposal

        st.markdown("---")
        st.markdown("#### Rebalance Preview")

        st.info(proposal.summary())

        if proposal.proposed_trades:
            st.markdown("**Proposed Trades:**")

            trade_data = []
            for t in proposal.proposed_trades:
                trade_data.append({
                    "Symbol": t.symbol,
                    "Side": t.side.value.upper(),
                    "Shares": f"{t.qty:.4f}",
                    "Type": t.order_type.value,
                    "Limit": f"${t.limit_price:.2f}" if t.limit_price else "Market",
                })

            st.dataframe(pd.DataFrame(trade_data), use_container_width=True, hide_index=True)

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Execute Rebalance", type="primary"):
                    try:
                        proposal.approved = True
                        results = run_async(service.execute_rebalance(proposal))
                        st.success(f"Executed {len(results)} trades")
                        st.session_state.rebalance_proposal = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Execution failed: {e}")

            with col2:
                if st.button("Cancel"):
                    st.session_state.rebalance_proposal = None
                    st.rerun()


def render_orders():
    """Render orders table."""
    service = st.session_state.trading_service

    st.markdown("### 📋 Recent Orders")

    try:
        orders = run_async(service.get_orders(limit=20))

        if not orders:
            st.info("No orders")
            return

        data = []
        for o in orders:
            data.append({
                "Time": o.created_at.strftime("%Y-%m-%d %H:%M"),
                "Symbol": o.symbol,
                "Side": o.side.value.upper(),
                "Qty": o.qty,
                "Filled": o.filled_qty,
                "Price": f"${o.filled_avg_price:.2f}" if o.filled_avg_price else "-",
                "Status": o.status.value,
            })

        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

        # Cancel pending orders
        pending = [o for o in orders if o.is_active]
        if pending:
            if st.button("Cancel All Pending Orders"):
                try:
                    count = run_async(service.cancel_all_orders())
                    st.success(f"Cancelled {count} orders")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    except Exception as e:
        st.error(f"Failed to get orders: {e}")


def render_portfolio_chart():
    """Render portfolio allocation chart."""
    service = st.session_state.trading_service

    try:
        positions = run_async(service.get_positions())
        account = run_async(service.get_account())

        if not positions:
            return

        # Pie chart
        labels = [p.symbol for p in positions] + ["Cash"]
        values = [p.market_value for p in positions] + [account.cash]

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            textinfo='label+percent',
            marker=dict(colors=[
                '#7c3aed', '#8b5cf6', '#a78bfa', '#c4b5fd',
                '#ddd6fe', '#ede9fe', '#f5f3ff', '#1e3a5f'
            ]),
        )])

        fig.update_layout(
            title="Portfolio Allocation",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#e2e8f0'),
            showlegend=True,
            height=400,
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Chart error: {e}")


def render_sidebar():
    """Render sidebar controls."""
    with st.sidebar:
        st.markdown("# 📈 Trading")

        if st.session_state.trading_connected:
            st.success("✅ Connected")

            if st.button("Disconnect"):
                try:
                    run_async(st.session_state.trading_service.disconnect())
                except Exception:
                    pass
                st.session_state.trading_service = None
                st.session_state.trading_connected = False
                st.rerun()

            st.divider()

            if st.button("Take Snapshot", use_container_width=True):
                try:
                    snapshot = run_async(st.session_state.trading_service.take_snapshot())
                    st.success(f"Snapshot saved: ${snapshot['equity']:,.2f}")
                except Exception as e:
                    st.error(str(e))

            if st.button("Refresh", use_container_width=True):
                st.rerun()

        else:
            st.warning("⚪ Not Connected")

        st.divider()

        st.markdown("### Navigation")
        if st.button("← Back to Research", use_container_width=True):
            st.switch_page("streamlit_app.py")


def main():
    """Main trading dashboard."""
    init_session_state()

    if not EXECUTION_AVAILABLE:
        st.error("Execution module not available. Please check installation.")
        return

    render_sidebar()

    st.title("📈 Trading Dashboard")

    if not st.session_state.trading_connected:
        render_connection_panel()
        return

    # Connected - show trading interface
    render_account_summary()
    st.divider()

    # Main layout
    tab1, tab2, tab3, tab4 = st.tabs(["Positions", "Trade", "Rebalance", "Orders"])

    with tab1:
        col1, col2 = st.columns([2, 1])
        with col1:
            render_positions()
        with col2:
            render_portfolio_chart()

    with tab2:
        render_trade_panel()

    with tab3:
        render_rebalance_panel()

    with tab4:
        render_orders()


if __name__ == "__main__":
    main()
