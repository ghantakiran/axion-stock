"""Broker Integrations Dashboard."""

import streamlit as st
import pandas as pd
import asyncio

st.set_page_config(page_title="Broker Integrations", layout="wide")
st.title("🏦 Broker Integrations")

# Try to import brokers module
try:
    from src.brokers import (
        BrokerManager, BrokerType, BROKER_CAPABILITIES,
        OrderRequest, OrderSide, OrderType, TimeInForce,
        ConnectionStatus,
    )
    BROKERS_AVAILABLE = True
except ImportError as e:
    BROKERS_AVAILABLE = False
    st.error(f"Brokers module not available: {e}")


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def get_or_create_manager():
    """Get or create broker manager from session state."""
    if "broker_manager" not in st.session_state:
        st.session_state.broker_manager = BrokerManager()
    return st.session_state.broker_manager


def render_broker_capabilities():
    """Render broker capabilities comparison."""
    st.subheader("Supported Brokers")
    
    data = []
    for broker_type, caps in BROKER_CAPABILITIES.items():
        data.append({
            "Broker": broker_type.value.title(),
            "Stocks": "✓" if caps.stocks else "✗",
            "Options": "✓" if caps.options else "✗",
            "ETFs": "✓" if caps.etfs else "✗",
            "Crypto": "✓" if caps.crypto else "✗",
            "Futures": "✓" if caps.futures else "✗",
            "Margin": "✓" if caps.margin else "✗",
            "Fractional": "✓" if caps.fractional_shares else "✗",
            "Extended Hours": "✓" if caps.extended_hours else "✗",
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_connection_form():
    """Render broker connection form."""
    st.subheader("Connect Broker")
    
    col1, col2 = st.columns(2)
    
    with col1:
        broker_type = st.selectbox(
            "Broker",
            options=[b for b in BrokerType],
            format_func=lambda x: x.value.title().replace("_", " ")
        )
        
        sandbox = st.checkbox("Paper Trading / Sandbox", value=True)
    
    with col2:
        caps = BROKER_CAPABILITIES.get(broker_type)
        if caps:
            st.markdown("**Authentication:**")
            st.write(f"Method: {caps.auth_method.value.replace('_', ' ').title()}")
    
    st.markdown("---")
    
    # Credentials based on broker
    if broker_type == BrokerType.ALPACA:
        api_key = st.text_input("API Key", type="password")
        api_secret = st.text_input("API Secret", type="password")
        credentials = {"api_key": api_key, "api_secret": api_secret}
    else:
        st.info(f"OAuth connection required for {broker_type.value.title()}. Click Connect to start authorization.")
        credentials = {}
    
    if st.button("Connect", type="primary"):
        if broker_type == BrokerType.ALPACA and (not api_key or not api_secret):
            st.error("Please provide API credentials")
            return
        
        manager = get_or_create_manager()
        
        with st.spinner(f"Connecting to {broker_type.value.title()}..."):
            try:
                connection_id = run_async(
                    manager.add_broker(
                        broker_type,
                        credentials=credentials,
                        sandbox=sandbox,
                    )
                )
                st.success(f"Connected! ID: {connection_id}")
                st.rerun()
            except Exception as e:
                st.error(f"Connection failed: {e}")


def render_connections():
    """Render active connections."""
    manager = get_or_create_manager()
    connections = manager.get_connections()
    
    if not connections:
        st.info("No broker connections. Add one above.")
        return
    
    st.subheader(f"Active Connections ({len(connections)})")
    
    for conn in connections:
        status_emoji = {
            ConnectionStatus.CONNECTED: "🟢",
            ConnectionStatus.DISCONNECTED: "🔴",
            ConnectionStatus.CONNECTING: "🟡",
            ConnectionStatus.ERROR: "🔴",
            ConnectionStatus.TOKEN_EXPIRED: "🟠",
        }.get(conn.status, "⚪")
        
        with st.expander(f"{status_emoji} {conn.broker.value.title()} - {conn.connection_id[:8]}..."):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**Status:** {conn.status.value}")
                st.markdown(f"**Accounts:** {', '.join(conn.accounts) or 'Default'}")
                if conn.connected_at:
                    st.markdown(f"**Connected:** {conn.connected_at.strftime('%Y-%m-%d %H:%M')}")
            
            with col2:
                if st.button("Refresh", key=f"refresh_{conn.connection_id}"):
                    run_async(manager.refresh_connection(conn.connection_id))
                    st.rerun()
                
                if st.button("Disconnect", key=f"disconnect_{conn.connection_id}"):
                    run_async(manager.remove_broker(conn.connection_id))
                    st.rerun()


def render_portfolio_overview():
    """Render portfolio overview across all brokers."""
    manager = get_or_create_manager()
    connections = manager.get_connections()
    
    if not connections:
        return
    
    st.subheader("Portfolio Overview")
    
    # Get aggregated data
    try:
        total_value = run_async(manager.get_total_portfolio_value())
        balances = run_async(manager.get_all_balances())
        positions = run_async(manager.get_all_positions())
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Value", f"${total_value:,.2f}")
        
        total_cash = sum(b.cash for b in balances)
        col2.metric("Cash", f"${total_cash:,.2f}")
        
        total_pnl = sum(b.day_pnl for b in balances)
        col3.metric("Day P&L", f"${total_pnl:,.2f}", f"{total_pnl/total_value*100:.2f}%" if total_value else "0%")
        
        col4.metric("Positions", len(positions))
        
        # Positions table
        if positions:
            st.markdown("**Positions:**")
            pos_data = []
            for pos in positions:
                pos_data.append({
                    "Symbol": pos.symbol,
                    "Qty": pos.quantity,
                    "Avg Cost": f"${pos.average_cost:.2f}",
                    "Price": f"${pos.current_price:.2f}",
                    "Value": f"${pos.market_value:,.2f}",
                    "P&L": f"${pos.unrealized_pnl:,.2f}",
                    "P&L %": f"{pos.unrealized_pnl_pct:.2f}%",
                })
            
            df = pd.DataFrame(pos_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"Error loading portfolio: {e}")


def render_order_form():
    """Render order placement form."""
    manager = get_or_create_manager()
    connections = manager.get_connections()
    
    if not connections:
        return
    
    st.subheader("Place Order")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        symbol = st.text_input("Symbol", value="AAPL").upper()
        side = st.selectbox("Side", options=[OrderSide.BUY, OrderSide.SELL],
                           format_func=lambda x: x.value.title())
    
    with col2:
        quantity = st.number_input("Quantity", min_value=1, value=1)
        order_type = st.selectbox("Order Type", 
                                  options=[OrderType.MARKET, OrderType.LIMIT, OrderType.STOP],
                                  format_func=lambda x: x.value.title())
    
    with col3:
        limit_price = None
        if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
            limit_price = st.number_input("Limit Price", min_value=0.01, value=100.0)
        
        time_in_force = st.selectbox("Time in Force",
                                     options=[TimeInForce.DAY, TimeInForce.GTC],
                                     format_func=lambda x: x.value.upper())
    
    # Connection selection
    connection_options = [(c.connection_id, f"{c.broker.value.title()}") for c in connections]
    selected_conn = st.selectbox(
        "Execute via",
        options=[c[0] for c in connection_options],
        format_func=lambda x: next(c[1] for c in connection_options if c[0] == x)
    )
    
    if st.button("Place Order", type="primary"):
        order = OrderRequest(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            time_in_force=time_in_force,
        )
        
        with st.spinner("Placing order..."):
            try:
                result = run_async(manager.place_order(order, selected_conn))
                if result.success:
                    st.success(f"Order placed! ID: {result.order_id}")
                else:
                    st.error(f"Order failed: {result.message}")
            except Exception as e:
                st.error(f"Error: {e}")


def main():
    if not BROKERS_AVAILABLE:
        return
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Portfolio", "🔗 Connections", "📝 Trade", "ℹ️ Brokers"
    ])
    
    with tab1:
        render_portfolio_overview()
    
    with tab2:
        render_connections()
        st.markdown("---")
        render_connection_form()
    
    with tab3:
        render_order_form()
        
        # Recent orders
        manager = get_or_create_manager()
        if manager.get_connections():
            st.markdown("---")
            st.subheader("Recent Orders")
            try:
                orders = run_async(manager.get_all_orders())
                if orders:
                    order_data = []
                    for o in orders[:10]:
                        order_data.append({
                            "ID": o.order_id[:8],
                            "Symbol": o.symbol,
                            "Side": o.side.value.title(),
                            "Qty": o.quantity,
                            "Type": o.order_type.value.title(),
                            "Status": o.status.value.title(),
                        })
                    st.dataframe(pd.DataFrame(order_data), use_container_width=True, hide_index=True)
                else:
                    st.info("No recent orders")
            except Exception as e:
                st.error(f"Error loading orders: {e}")
    
    with tab4:
        render_broker_capabilities()
        
        st.markdown("---")
        st.markdown("""
        ### Authentication Methods
        
        **API Key (Alpaca):**
        - Generate keys in your Alpaca dashboard
        - Supports paper and live trading
        
        **OAuth 2.0 (Schwab, Fidelity, IBKR, etc.):**
        - Click Connect to start OAuth flow
        - Authorize app in broker portal
        - Tokens auto-refresh
        
        ### Security
        - Credentials encrypted at rest
        - OAuth tokens auto-rotate
        - Never stores passwords
        """)


if __name__ == "__main__":
    main()
