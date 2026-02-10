"""Webull Broker Dashboard (PRD-159).

Four-tab Streamlit dashboard for Webull account management,
extended-hours trading, market data, and stock screening.
"""

import streamlit as st
from app.styles import inject_global_styles

inject_global_styles()

from src.webull_broker import WebullClient, WebullConfig

st.header("Webull")
st.caption("PRD-159 · Retail-friendly broker with extended hours (4am-8pm ET), zero commission, and built-in screener")

tab1, tab2, tab3, tab4 = st.tabs([
    "Account", "Trading", "Market Data", "Screener",
])

# ── Tab 1: Account ──────────────────────────────────────────────────

with tab1:
    st.subheader("Account Overview")

    if st.button("Connect (Demo)", key="wb_connect"):
        client = WebullClient(WebullConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect())

        st.success(f"Connected in **{client.mode}** mode")

        account = asyncio.get_event_loop().run_until_complete(client.get_account())
        st.markdown(f"### Account: {account.account_id}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Net Liquidation", f"${account.net_liquidation:,.2f}")
        c2.metric("Cash", f"${account.cash_balance:,.2f}")
        c3.metric("Buying Power", f"${account.buying_power:,.2f}")
        c4.metric("Day Trades Left", account.day_trades_remaining)

        c5, c6, c7 = st.columns(3)
        c5.metric("Day BP", f"${account.day_buying_power:,.2f}")
        c6.metric("Overnight BP", f"${account.overnight_buying_power:,.2f}")
        c7.metric("Unsettled", f"${account.unsettled_funds:,.2f}")

        st.divider()
        st.subheader("Positions")
        positions = asyncio.get_event_loop().run_until_complete(client.get_positions())
        for pos in positions:
            pnl_icon = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
            st.write(
                f"{pnl_icon} **{pos.symbol}** ({pos.asset_type}) — "
                f"{pos.quantity} {pos.position_side} @ ${pos.cost_price:.2f} | "
                f"Last=${pos.last_price:.2f} | "
                f"P&L=${pos.unrealized_pnl:,.2f} ({pos.unrealized_pnl_pct:+.2f}%)"
            )

# ── Tab 2: Trading ──────────────────────────────────────────────────

with tab2:
    st.subheader("Order Entry")

    col1, col2 = st.columns(2)
    with col1:
        symbol = st.text_input("Symbol", "TSLA", key="wb_sym")
        action = st.selectbox("Action", ["BUY", "SELL"], key="wb_action")
        quantity = st.number_input("Quantity", min_value=1, value=10, key="wb_qty")
    with col2:
        order_type = st.selectbox("Type", ["MKT", "LMT", "STP", "STP_LMT"], key="wb_otype")
        limit_price = st.number_input("Limit Price", value=0.0, key="wb_limit")
        ext_hours = st.checkbox("Extended Hours (4am-8pm ET)", value=False, key="wb_ext")

    tif = st.selectbox("Time in Force", ["DAY", "GTC", "IOC"], key="wb_tif")

    if ext_hours:
        st.info("Extended hours trading: Pre-market (4:00am-9:30am ET) and After-hours (4:00pm-8:00pm ET)")

    if st.button("Submit Order (Demo)", key="wb_submit"):
        ext_label = " [EXT HOURS]" if ext_hours else ""
        st.info(f"Demo: {action} {quantity} {symbol} @ {order_type}{ext_label}")

    st.divider()
    st.subheader("Recent Orders")
    if st.button("Load Orders", key="wb_orders"):
        client = WebullClient(WebullConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect())
        orders = asyncio.get_event_loop().run_until_complete(client.get_orders())

        for o in orders:
            status_icon = {"Filled": "✅", "Working": "⏳", "Cancelled": "❌"}.get(o.status, "⚪")
            ext = " 🌙" if o.outside_regular_hours else ""
            st.write(
                f"{status_icon} **{o.order_id}** — {o.action} {o.quantity} {o.symbol}{ext} "
                f"@ ${o.avg_filled_price:.2f} ({o.order_type}) — {o.status}"
            )

# ── Tab 3: Market Data ──────────────────────────────────────────────

with tab3:
    st.subheader("Real-Time Quotes")

    st.markdown("Webull provides quotes with **pre-market** and **after-hours** pricing.")

    symbols_input = st.text_input("Symbols (comma-separated)", "TSLA,AMD,AAPL,NVDA", key="wb_quotes")
    if st.button("Get Quotes", key="wb_get_quotes"):
        client = WebullClient(WebullConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect())
        symbols = [s.strip().upper() for s in symbols_input.split(",")]
        quotes = asyncio.get_event_loop().run_until_complete(client.get_quotes(symbols))

        for q in quotes:
            change_icon = "🟢" if q.change >= 0 else "🔴"
            pre = f" | Pre: ${q.pre_market_price:.2f}" if q.pre_market_price > 0 else ""
            after = f" | AH: ${q.after_hours_price:.2f}" if q.after_hours_price > 0 else ""
            st.write(
                f"{change_icon} **{q.symbol}** — ${q.last:.2f} "
                f"({q.change:+.2f}, {q.change_pct:+.2f}%){pre}{after} | "
                f"Vol: {q.volume:,} | Avg10d: {q.avg_volume_10d:,}"
            )

    st.divider()
    st.subheader("Crypto")
    if st.button("Crypto Quotes", key="wb_crypto"):
        client = WebullClient(WebullConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect())
        crypto = asyncio.get_event_loop().run_until_complete(client.get_crypto_quote("BTC"))
        st.write(f"₿ **BTC** — ${crypto.last:,.2f} ({crypto.change_pct:+.2f}%) | Vol: {crypto.volume:,}")

# ── Tab 4: Screener ─────────────────────────────────────────────────

with tab4:
    st.subheader("Stock Screener")

    st.markdown("""
    Webull's built-in screener helps find stocks matching your criteria.
    Zero-commission trading means you can act on screener results instantly.
    """)

    col1, col2 = st.columns(2)
    with col1:
        min_price = st.number_input("Min Price", value=10.0, key="wb_min_p")
        min_vol = st.number_input("Min Volume", value=1000000, key="wb_min_v")
        min_cap = st.selectbox("Min Market Cap", ["Any", "$1B+", "$10B+", "$100B+"], key="wb_min_cap")
    with col2:
        max_price = st.number_input("Max Price", value=500.0, key="wb_max_p")
        sector = st.selectbox("Sector", ["Any", "Technology", "Healthcare", "Finance", "Energy", "Consumer"], key="wb_sector")
        sort_by = st.selectbox("Sort By", ["volume", "change_pct", "market_cap"], key="wb_sort")

    if st.button("Run Screen", key="wb_screen"):
        client = WebullClient(WebullConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect())
        results = asyncio.get_event_loop().run_until_complete(client.screen_stocks({}))

        st.write(f"**{len(results)} results** found")
        for r in results:
            change_icon = "🟢" if r.change_pct >= 0 else "🔴"
            cap_str = f"${r.market_cap/1e9:.0f}B" if r.market_cap >= 1e9 else f"${r.market_cap/1e6:.0f}M"
            st.write(
                f"{change_icon} **{r.symbol}** — {r.name} | "
                f"${r.last_price:.2f} ({r.change_pct:+.1f}%) | "
                f"Vol: {r.volume:,} | Cap: {cap_str} | {r.sector}"
            )
