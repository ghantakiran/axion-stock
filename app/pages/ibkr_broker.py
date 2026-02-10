"""IBKR Broker Dashboard (PRD-157).

Four-tab Streamlit dashboard for Interactive Brokers account management,
multi-asset trading (stocks, options, forex, futures), and gateway monitoring.
"""

import streamlit as st
from app.styles import inject_global_styles

inject_global_styles()

from src.ibkr_broker import IBKRClient, IBKRConfig

st.header("Interactive Brokers (IBKR)")
st.caption("PRD-157 · Global multi-asset broker with forex, futures, and Client Portal Gateway")

tab1, tab2, tab3, tab4 = st.tabs([
    "Account", "Trading", "Market Data", "Gateway",
])

# ── Tab 1: Account ──────────────────────────────────────────────────

with tab1:
    st.subheader("Account Overview")

    if st.button("Connect (Demo)", key="ibkr_connect"):
        client = IBKRClient(IBKRConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect())

        st.success(f"Connected in **{client.mode}** mode")

        accounts = asyncio.get_event_loop().run_until_complete(client.get_accounts())
        for acct in accounts:
            st.markdown(f"### Account: {acct.account_id} ({acct.base_currency})")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Net Liquidation", f"${acct.net_liquidation:,.2f}")
            c2.metric("Equity w/ Loan", f"${acct.equity_with_loan:,.2f}")
            c3.metric("Buying Power", f"${acct.buying_power:,.2f}")
            c4.metric("Positions", acct.position_count)

            c5, c6, c7 = st.columns(3)
            c5.metric("Available Funds", f"${acct.available_funds:,.2f}")
            c6.metric("Excess Liquidity", f"${acct.excess_liquidity:,.2f}")
            c7.metric("SMA", f"${acct.sma:,.2f}")

        st.divider()
        st.subheader("Positions (Multi-Asset)")
        positions = asyncio.get_event_loop().run_until_complete(
            client.get_positions(accounts[0].account_id)
        )
        for pos in positions:
            asset_icons = {"STK": "📊", "OPT": "📋", "FUT": "📈", "CASH": "💱", "BOND": "🏦"}
            icon = asset_icons.get(pos.asset_class, "📄")
            pnl_icon = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
            st.write(
                f"{icon} {pnl_icon} **{pos.symbol}** [{pos.asset_class}] — "
                f"{pos.quantity} @ ${pos.average_cost:.2f} | "
                f"MV=${pos.market_value:,.2f} | "
                f"P&L=${pos.unrealized_pnl:,.2f} ({pos.currency})"
            )

# ── Tab 2: Trading ──────────────────────────────────────────────────

with tab2:
    st.subheader("Order Entry")

    asset_class = st.selectbox("Asset Class", ["STK", "OPT", "FUT", "CASH"], key="ibkr_asset")
    col1, col2 = st.columns(2)
    with col1:
        symbol = st.text_input("Symbol", "AAPL" if asset_class == "STK" else "EURUSD", key="ibkr_sym")
        side = st.selectbox("Side", ["BUY", "SELL"], key="ibkr_side")
        quantity = st.number_input("Quantity", min_value=1, value=100, key="ibkr_qty")
    with col2:
        order_type = st.selectbox("Type", ["MKT", "LMT", "STP", "STP_LMT", "TRAIL"], key="ibkr_otype")
        exchange = st.selectbox("Exchange", ["SMART", "NYSE", "NASDAQ", "ARCA", "IDEALPRO", "CME"], key="ibkr_exch")
        tif = st.selectbox("Time in Force", ["DAY", "GTC", "IOC", "FOK"], key="ibkr_tif")

    if st.button("Submit Order (Demo)", key="ibkr_submit"):
        st.info(f"Demo: {side} {quantity} {symbol} [{asset_class}] @ {order_type} on {exchange}")

    st.divider()
    st.subheader("Contract Search")
    search_sym = st.text_input("Search Symbol", "ES", key="ibkr_search")
    search_type = st.selectbox("Security Type", ["STK", "FUT", "OPT", "CASH"], key="ibkr_stype")
    if st.button("Search", key="ibkr_do_search"):
        client = IBKRClient(IBKRConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect())
        contracts = asyncio.get_event_loop().run_until_complete(
            client.search_contract(search_sym, search_type)
        )
        for c in contracts:
            st.write(f"**{c.symbol}** (conid={c.conid}) [{c.sec_type}] — {c.description} | {c.exchange} ({c.currency})")

# ── Tab 3: Market Data ──────────────────────────────────────────────

with tab3:
    st.subheader("Real-Time Quotes")

    symbols_input = st.text_input("Symbols", "AAPL,MSFT,EURUSD,ES", key="ibkr_quotes")
    if st.button("Get Quotes", key="ibkr_get_quotes"):
        client = IBKRClient(IBKRConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect())
        symbols = [s.strip().upper() for s in symbols_input.split(",")]
        quotes = asyncio.get_event_loop().run_until_complete(client.get_quote(symbols))

        for q in quotes:
            change_icon = "🟢" if q.change >= 0 else "🔴"
            st.write(
                f"{change_icon} **{q.symbol}** — ${q.last:.2f} "
                f"({q.change:+.2f}, {q.change_pct:+.2f}%) | "
                f"Bid: {q.bid:.2f} Ask: {q.ask:.2f} | Vol: {q.volume:,}"
            )

    st.divider()
    st.subheader("Forex Pairs")
    if st.button("Load Forex", key="ibkr_forex"):
        client = IBKRClient(IBKRConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect())
        pairs = asyncio.get_event_loop().run_until_complete(client.get_forex_pairs())
        for p in pairs:
            st.write(f"💱 **{p['symbol']}** — {p['description']} | Rate: {p['rate']:.4f}")

# ── Tab 4: Gateway ──────────────────────────────────────────────────

with tab4:
    st.subheader("Client Portal Gateway Status")

    st.markdown("""
    IBKR uses a local **Client Portal Gateway** that runs on your machine.
    The gateway proxies API requests to IBKR's servers and handles authentication.
    """)

    from src.ibkr_broker import IBKRGateway
    gw = IBKRGateway(IBKRConfig())

    if st.button("Check Gateway", key="ibkr_gw_check"):
        import asyncio
        status = asyncio.get_event_loop().run_until_complete(gw.check_status())

        conn_icon = "🟢" if status.connected else "🔴"
        auth_icon = "🟢" if status.authenticated else "🔴"

        st.markdown(f"### {conn_icon} Gateway {'Connected' if status.connected else 'Disconnected'}")

        c1, c2, c3 = st.columns(3)
        c1.metric("Authenticated", f"{auth_icon} {'Yes' if status.authenticated else 'No'}")
        c2.metric("Server", status.server_name)
        c3.metric("Uptime", f"{status.uptime_seconds}s")

        if status.competing:
            st.warning("Competing session detected — another client may be connected")
