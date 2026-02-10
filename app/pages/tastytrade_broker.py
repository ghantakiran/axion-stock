"""tastytrade Broker Dashboard (PRD-158).

Four-tab Streamlit dashboard for tastytrade account management,
options-focused trading, options chain analysis, and streaming.
"""

import streamlit as st
from app.styles import inject_global_styles

inject_global_styles()

from src.tastytrade_broker import TastytradeClient, TastytradeConfig

st.header("tastytrade")
st.caption("PRD-158 · Options-specialist broker with futures, crypto, and deep chain analytics")

tab1, tab2, tab3, tab4 = st.tabs([
    "Account", "Trading", "Options Chain", "Streaming",
])

# ── Tab 1: Account ──────────────────────────────────────────────────

with tab1:
    st.subheader("Account Overview")

    if st.button("Connect (Demo)", key="tt_connect"):
        client = TastytradeClient(TastytradeConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect())

        st.success(f"Connected in **{client.mode}** mode")

        accounts = asyncio.get_event_loop().run_until_complete(client.get_accounts())
        for acct in accounts:
            st.markdown(f"### {acct.nickname} ({acct.account_number})")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Net Liq", f"${acct.net_liquidating_value:,.2f}")
            c2.metric("Cash", f"${acct.cash_balance:,.2f}")
            c3.metric("Option BP", f"${acct.derivative_buying_power:,.2f}")
            c4.metric("Option Level", acct.option_level)

            c5, c6, c7 = st.columns(3)
            c5.metric("Equity BP", f"${acct.equity_buying_power:,.2f}")
            c6.metric("Futures", "✅ Enabled" if acct.futures_enabled else "❌ Disabled")
            c7.metric("Day Trader", "Yes" if acct.day_trader_status else "No")

        st.divider()
        st.subheader("Positions")
        positions = asyncio.get_event_loop().run_until_complete(
            client.get_positions(accounts[0].account_number)
        )
        for pos in positions:
            type_icons = {"Equity": "📊", "Equity Option": "📋", "Future": "📈", "Cryptocurrency": "₿"}
            icon = type_icons.get(pos.instrument_type, "📄")
            pnl_icon = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
            mult = f" (x{pos.multiplier})" if pos.multiplier > 1 else ""
            st.write(
                f"{icon} {pnl_icon} **{pos.symbol}** [{pos.instrument_type}]{mult} — "
                f"{pos.quantity} {pos.direction} @ ${pos.average_open_price:.2f} | "
                f"Mark=${pos.mark_price:.2f} | "
                f"P&L=${pos.unrealized_pnl:,.2f}"
            )

# ── Tab 2: Trading ──────────────────────────────────────────────────

with tab2:
    st.subheader("Order Entry")

    order_class = st.selectbox("Order Class", ["Single", "Spread", "Combo"], key="tt_class")

    col1, col2 = st.columns(2)
    with col1:
        symbol = st.text_input("Symbol", "SPY", key="tt_sym")
        instrument = st.selectbox("Instrument", ["Equity", "Equity Option", "Future", "Cryptocurrency"], key="tt_inst")
        quantity = st.number_input("Size", min_value=1, value=1, key="tt_qty")
    with col2:
        order_type = st.selectbox("Type", ["Limit", "Market", "Stop", "Stop Limit"], key="tt_otype")
        price = st.number_input("Price", value=0.0, key="tt_price")
        tif = st.selectbox("Time in Force", ["Day", "GTC", "IOC"], key="tt_tif")

    if order_class == "Spread":
        st.markdown("**Spread Legs:**")
        lc1, lc2 = st.columns(2)
        with lc1:
            leg1_action = st.selectbox("Leg 1", ["Buy to Open", "Sell to Open"], key="tt_l1")
            leg1_strike = st.number_input("Strike 1", value=580.0, key="tt_s1")
        with lc2:
            leg2_action = st.selectbox("Leg 2", ["Sell to Open", "Buy to Open"], key="tt_l2")
            leg2_strike = st.number_input("Strike 2", value=590.0, key="tt_s2")

    if st.button("Submit Order (Demo)", key="tt_submit"):
        st.info(f"Demo: {order_class} order — {quantity}x {symbol} [{instrument}] @ {order_type}")

    st.divider()
    st.subheader("Recent Orders")
    if st.button("Load Orders", key="tt_orders"):
        client = TastytradeClient(TastytradeConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect())
        orders = asyncio.get_event_loop().run_until_complete(
            client.get_orders("DEMO-TT-001")
        )
        for o in orders:
            status_icon = {"Filled": "✅", "Live": "⏳", "Cancelled": "❌"}.get(o.status, "⚪")
            legs_info = f" ({len(o.legs)} legs)" if len(o.legs) > 1 else ""
            st.write(
                f"{status_icon} **{o.order_id}** — {o.size}x {o.symbol}{legs_info} "
                f"@ {o.order_type} — {o.status}"
            )

# ── Tab 3: Options Chain ────────────────────────────────────────────

with tab3:
    st.subheader("Options Chain Analysis")

    st.markdown("""
    tastytrade excels at options analysis with deep chain data,
    real-time Greeks, IV rank/percentile, and strategy optimization.
    """)

    from src.tastytrade_broker import OptionsChainAnalyzer
    analyzer = OptionsChainAnalyzer()

    chain_sym = st.text_input("Symbol", "SPY", key="tt_chain_sym")

    if st.button("Load Expirations", key="tt_exp"):
        expirations = analyzer.get_expirations(chain_sym)
        for exp in expirations:
            st.write(f"📅 **{exp.expiration_date}** — {exp.days_to_expiration} DTE | {len(exp.strikes)} strikes")

    if st.button("Load Chain (Nearest)", key="tt_chain"):
        expirations = analyzer.get_expirations(chain_sym)
        if expirations:
            chain = analyzer.get_chain(chain_sym, expirations[0].expiration_date)
            st.write(f"**{len(chain)} strikes** for {chain_sym} {expirations[0].expiration_date}")

            for strike in chain[:5]:
                st.write(
                    f"**${strike.strike_price:.0f}** — "
                    f"Call: ${strike.call_bid:.2f}/{strike.call_ask:.2f} "
                    f"(Δ={strike.call_greeks.delta:.3f}, IV={strike.call_greeks.iv:.1%}) | "
                    f"Put: ${strike.put_bid:.2f}/{strike.put_ask:.2f} "
                    f"(Δ={strike.put_greeks.delta:.3f}, IV={strike.put_greeks.iv:.1%})"
                )

    st.divider()
    st.subheader("IV Surface")
    if st.button("Load IV Surface", key="tt_iv"):
        surface = analyzer.get_iv_surface(chain_sym)
        st.write(f"**{len(surface)} expirations** in IV surface for {chain_sym}")
        for exp, strikes in list(surface.items())[:3]:
            avg_iv = sum(strikes.values()) / len(strikes) if strikes else 0
            st.write(f"  📊 {exp}: avg IV = {avg_iv:.1%} ({len(strikes)} strikes)")

# ── Tab 4: Streaming ────────────────────────────────────────────────

with tab4:
    st.subheader("Live Streaming")

    from src.tastytrade_broker import TastytradeStreaming, StreamChannel
    streaming = TastytradeStreaming(TastytradeConfig())

    st.markdown("""
    tastytrade provides real-time streaming for quotes, Greeks,
    trades, and order updates via WebSocket.
    """)

    stream_syms = st.text_input("Symbols", "SPY,AAPL,/ES", key="tt_stream_syms")
    channels = st.multiselect("Channels", ["QUOTE", "GREEKS", "TRADES", "ORDERS"], default=["QUOTE"], key="tt_channels")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Start Stream", key="tt_start"):
            st.success("Demo streaming started")
            st.write(f"Symbols: {stream_syms}")
            st.write(f"Channels: {', '.join(channels)}")
    with c2:
        if st.button("Stop Stream", key="tt_stop"):
            st.info("Streaming stopped")

    st.metric("Stream Status", "🟢 Active" if streaming.is_running else "⚪ Idle")
