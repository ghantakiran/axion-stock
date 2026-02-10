"""Real-time Streaming Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
from datetime import datetime, timezone
import time

try:
    st.set_page_config(page_title="Real-time Streaming", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Real-time Market Data")

# --- Sidebar ---
st.sidebar.header("Streaming Settings")

# Connection status
connection_status = st.sidebar.empty()
connection_status.success("Connected")

# Watchlist
st.sidebar.subheader("Watchlist")
watchlist_symbols = st.sidebar.text_input("Symbols (comma-separated)", "AAPL, MSFT, GOOGL, NVDA, AMZN")
symbols = [s.strip().upper() for s in watchlist_symbols.split(",") if s.strip()]

st.sidebar.markdown("---")

# Channel subscriptions
st.sidebar.subheader("Channels")
sub_quotes = st.sidebar.checkbox("Quotes", value=True)
sub_trades = st.sidebar.checkbox("Trades", value=False)
sub_portfolio = st.sidebar.checkbox("Portfolio", value=True)
sub_alerts = st.sidebar.checkbox("Alerts", value=True)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Live Quotes", "Order Book", "Portfolio", "Connection"
])

# --- Tab 1: Live Quotes ---
with tab1:
    st.subheader("Real-time Quotes")

    # Simulate live quotes
    quote_data = {
        "AAPL": {"bid": 185.50, "ask": 185.52, "last": 185.51, "change": 2.51, "change_pct": 1.37, "volume": "45.2M"},
        "MSFT": {"bid": 420.10, "ask": 420.15, "last": 420.12, "change": -1.23, "change_pct": -0.29, "volume": "22.1M"},
        "GOOGL": {"bid": 175.80, "ask": 175.85, "last": 175.82, "change": 3.45, "change_pct": 2.00, "volume": "18.5M"},
        "NVDA": {"bid": 850.00, "ask": 850.50, "last": 850.25, "change": 15.75, "change_pct": 1.88, "volume": "35.8M"},
        "AMZN": {"bid": 185.20, "ask": 185.25, "last": 185.22, "change": 0.82, "change_pct": 0.44, "volume": "28.3M"},
    }

    # Display quotes in columns
    cols = st.columns(len(symbols))
    for i, symbol in enumerate(symbols):
        if symbol in quote_data:
            data = quote_data[symbol]
            with cols[i]:
                change_color = "green" if data["change"] >= 0 else "red"
                st.markdown(f"### {symbol}")
                st.metric(
                    "Last",
                    f"${data['last']:.2f}",
                    f"{data['change']:+.2f} ({data['change_pct']:+.2f}%)",
                )
                st.caption(f"Bid: ${data['bid']:.2f} | Ask: ${data['ask']:.2f}")
                st.caption(f"Volume: {data['volume']}")

    st.markdown("---")

    # Quote table
    st.markdown("### Quote Details")

    import pandas as pd
    df = pd.DataFrame([
        {
            "Symbol": symbol,
            "Bid": f"${data['bid']:.2f}",
            "Ask": f"${data['ask']:.2f}",
            "Last": f"${data['last']:.2f}",
            "Change": f"{data['change']:+.2f}",
            "Change %": f"{data['change_pct']:+.2f}%",
            "Volume": data["volume"],
        }
        for symbol, data in quote_data.items()
        if symbol in symbols
    ])

    st.dataframe(df, use_container_width=True, hide_index=True)

# --- Tab 2: Order Book ---
with tab2:
    st.subheader("Level 2 Order Book")

    selected_symbol = st.selectbox("Symbol", symbols)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Bids")
        bids = pd.DataFrame([
            {"Price": f"${185.50 - i*0.01:.2f}", "Size": 100 + i*50, "Orders": 3 + i}
            for i in range(10)
        ])
        st.dataframe(bids, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("### Asks")
        asks = pd.DataFrame([
            {"Price": f"${185.52 + i*0.01:.2f}", "Size": 150 + i*30, "Orders": 2 + i}
            for i in range(10)
        ])
        st.dataframe(asks, use_container_width=True, hide_index=True)

    # Recent trades
    st.markdown("### Recent Trades")
    trades = pd.DataFrame([
        {"Time": f"14:30:{59-i:02d}", "Price": f"${185.50 + (i%3)*0.01:.2f}", "Size": 100 + i*10, "Exchange": "NYSE"}
        for i in range(20)
    ])
    st.dataframe(trades.head(10), use_container_width=True, hide_index=True)

# --- Tab 3: Portfolio ---
with tab3:
    st.subheader("Live Portfolio")

    # Portfolio summary
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Value", "$125,432.50", "+$1,234.50")
    col2.metric("Day P&L", "+$1,234.50", "+0.99%")
    col3.metric("Cash", "$15,432.50", "12.3%")
    col4.metric("Buying Power", "$50,000.00", "")

    st.markdown("---")

    # Positions
    st.markdown("### Live Positions")
    positions = pd.DataFrame([
        {"Symbol": "AAPL", "Qty": 100, "Avg Cost": "$175.00", "Current": "$185.51", "P&L": "+$1,051.00", "P&L %": "+6.0%"},
        {"Symbol": "MSFT", "Qty": 50, "Avg Cost": "$400.00", "Current": "$420.12", "P&L": "+$1,006.00", "P&L %": "+5.0%"},
        {"Symbol": "GOOGL", "Qty": 75, "Avg Cost": "$170.00", "Current": "$175.82", "P&L": "+$436.50", "P&L %": "+3.4%"},
        {"Symbol": "NVDA", "Qty": 25, "Avg Cost": "$800.00", "Current": "$850.25", "P&L": "+$1,256.25", "P&L %": "+6.3%"},
    ])
    st.dataframe(positions, use_container_width=True, hide_index=True)

    # Recent orders
    st.markdown("### Recent Orders")
    orders = pd.DataFrame([
        {"Time": "14:28:15", "Symbol": "AAPL", "Side": "BUY", "Qty": 10, "Price": "$185.50", "Status": "Filled"},
        {"Time": "14:25:30", "Symbol": "MSFT", "Side": "SELL", "Qty": 5, "Price": "$420.00", "Status": "Filled"},
        {"Time": "14:20:00", "Symbol": "GOOGL", "Side": "BUY", "Qty": 25, "Price": "$175.00", "Status": "Partial"},
    ])
    st.dataframe(orders, use_container_width=True, hide_index=True)

# --- Tab 4: Connection ---
with tab4:
    st.subheader("WebSocket Connection")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Connection Status")
        st.success("Connected")
        st.markdown(f"**Connection ID:** ws-abc123def456")
        st.markdown(f"**Connected At:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        st.markdown(f"**Last Heartbeat:** {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")

        if st.button("Reconnect"):
            st.info("Reconnecting...")

    with col2:
        st.markdown("### Message Stats")
        st.metric("Messages Received", "12,456")
        st.metric("Messages Sent", "234")
        st.metric("Avg Latency", "23ms")

    st.markdown("---")

    st.markdown("### Active Subscriptions")
    subscriptions = pd.DataFrame([
        {"Channel": "quotes", "Symbols": ", ".join(symbols), "Throttle": "100ms", "Messages": 8542},
        {"Channel": "portfolio", "Symbols": "All", "Throttle": "1000ms", "Messages": 156},
        {"Channel": "alerts", "Symbols": "All", "Throttle": "0ms", "Messages": 12},
    ])
    st.dataframe(subscriptions, use_container_width=True, hide_index=True)

    st.markdown("### Recent Messages")
    messages = [
        {"Time": "14:30:01.123", "Channel": "quotes", "Type": "update", "Data": "AAPL: $185.51"},
        {"Time": "14:30:01.100", "Channel": "quotes", "Type": "update", "Data": "MSFT: $420.12"},
        {"Time": "14:30:00.950", "Channel": "quotes", "Type": "update", "Data": "NVDA: $850.25"},
        {"Time": "14:30:00.500", "Channel": "portfolio", "Type": "update", "Data": "Total: $125,432.50"},
    ]
    for msg in messages:
        st.text(f"[{msg['Time']}] {msg['Channel']}.{msg['Type']}: {msg['Data']}")
