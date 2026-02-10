"""Fidelity Broker Dashboard (PRD-156).

Four-tab Streamlit dashboard for Fidelity account management,
trading, market data, and mutual fund research.
"""

import streamlit as st
from app.styles import inject_global_styles

inject_global_styles()

from src.fidelity_broker import FidelityClient, FidelityConfig

st.header("Fidelity Broker")
st.caption("PRD-156 · Full-featured Fidelity integration with OAuth2, stocks, options, ETFs, mutual funds & bonds")

tab1, tab2, tab3, tab4 = st.tabs([
    "Account", "Trading", "Market Data", "Research",
])

# ── Tab 1: Account ──────────────────────────────────────────────────

with tab1:
    st.subheader("Account Overview")

    if st.button("Connect (Demo)", key="fid_connect"):
        client = FidelityClient(FidelityConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect()) if hasattr(asyncio, 'get_event_loop') else None

        st.success(f"Connected in **{client.mode}** mode")

        accounts = asyncio.get_event_loop().run_until_complete(client.get_accounts())
        for acct in accounts:
            st.markdown(f"### Account: {acct.account_number}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Equity", f"${acct.equity:,.2f}")
            c2.metric("Cash", f"${acct.cash:,.2f}")
            c3.metric("Buying Power", f"${acct.buying_power:,.2f}")
            c4.metric("Positions", acct.position_count)

        st.divider()
        st.subheader("Positions")
        positions = asyncio.get_event_loop().run_until_complete(
            client.get_positions(accounts[0].account_number)
        )
        for pos in positions:
            pnl_icon = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
            st.write(
                f"{pnl_icon} **{pos.symbol}** ({pos.asset_type}) — "
                f"{pos.quantity} shares @ ${pos.average_price:.2f} | "
                f"MV=${pos.market_value:,.2f} | "
                f"P&L=${pos.unrealized_pnl:,.2f} ({pos.unrealized_pnl_pct:+.2f}%)"
            )

# ── Tab 2: Trading ──────────────────────────────────────────────────

with tab2:
    st.subheader("Order Entry")

    col1, col2 = st.columns(2)
    with col1:
        symbol = st.text_input("Symbol", "AAPL", key="fid_sym")
        side = st.selectbox("Side", ["BUY", "SELL", "SELL_SHORT", "BUY_TO_COVER"], key="fid_side")
        quantity = st.number_input("Quantity", min_value=1, value=10, key="fid_qty")
    with col2:
        order_type = st.selectbox("Type", ["MARKET", "LIMIT", "STOP", "STOP_LIMIT"], key="fid_otype")
        limit_price = st.number_input("Limit Price", value=0.0, key="fid_limit")
        duration = st.selectbox("Duration", ["DAY", "GTC", "IOC"], key="fid_dur")

    if st.button("Submit Order (Demo)", key="fid_submit"):
        st.info(f"Demo: {side} {quantity} {symbol} @ {order_type}")

    st.divider()
    st.subheader("Recent Orders")
    if st.button("Load Orders", key="fid_orders"):
        client = FidelityClient(FidelityConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect())
        orders = asyncio.get_event_loop().run_until_complete(
            client.get_orders("DEMO-FID-001")
        )
        for o in orders:
            status_icon = {"FILLED": "✅", "QUEUED": "⏳", "CANCELED": "❌"}.get(o.status, "⚪")
            st.write(
                f"{status_icon} **{o.order_id}** — {o.side} {o.quantity} {o.symbol} "
                f"@ ${o.price:.2f} ({o.order_type}) — {o.status}"
            )

# ── Tab 3: Market Data ──────────────────────────────────────────────

with tab3:
    st.subheader("Real-Time Quotes")

    symbols_input = st.text_input("Symbols (comma-separated)", "AAPL,MSFT,GOOGL,SPY", key="fid_quotes")

    if st.button("Get Quotes", key="fid_get_quotes"):
        client = FidelityClient(FidelityConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect())
        symbols = [s.strip().upper() for s in symbols_input.split(",")]
        quotes = asyncio.get_event_loop().run_until_complete(client.get_quote(symbols))

        for q in quotes:
            change_icon = "🟢" if q.net_change >= 0 else "🔴"
            st.write(
                f"{change_icon} **{q.symbol}** — ${q.last_price:.2f} "
                f"({q.net_change:+.2f}, {q.net_percent_change:+.2f}%) | "
                f"Vol: {q.total_volume:,} | P/E: {q.pe_ratio:.1f} | "
                f"52w: ${q.week_52_low:.2f}–${q.week_52_high:.2f}"
            )

    st.divider()
    st.subheader("Price History")
    hist_sym = st.text_input("Symbol", "AAPL", key="fid_hist_sym")
    if st.button("Load History", key="fid_hist"):
        client = FidelityClient(FidelityConfig())
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.connect())
        candles = asyncio.get_event_loop().run_until_complete(
            client.get_price_history(hist_sym)
        )
        st.write(f"**{len(candles)}** candles loaded for {hist_sym}")
        if candles:
            st.write(f"Latest: O={candles[-1].open:.2f} H={candles[-1].high:.2f} "
                     f"L={candles[-1].low:.2f} C={candles[-1].close:.2f}")

# ── Tab 4: Research ─────────────────────────────────────────────────

with tab4:
    st.subheader("Fidelity Research")

    st.markdown("""
    Fidelity's research tools include fundamentals analysis,
    mutual fund screening (Fidelity manages $4.5T+ AUM), and
    analyst ratings from multiple firms.
    """)

    from src.fidelity_broker import FidelityResearch
    research = FidelityResearch()

    if st.button("Get Fundamentals (AAPL)", key="fid_fund"):
        data = research.get_fundamentals("AAPL")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("P/E Ratio", f"{data.pe_ratio:.1f}")
        c2.metric("EPS", f"${data.eps:.2f}")
        c3.metric("Div Yield", f"{data.dividend_yield:.2f}%")
        c4.metric("Market Cap", f"${data.market_cap/1e9:.0f}B")

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Revenue", f"${data.revenue/1e9:.0f}B")
        c6.metric("Profit Margin", f"{data.profit_margin:.1f}%")
        c7.metric("ROE", f"{data.roe:.1f}%")
        c8.metric("Beta", f"{data.beta:.2f}")

    st.divider()
    st.subheader("Mutual Fund Screener")
    if st.button("Screen Top Funds", key="fid_screen"):
        funds = research.screen_funds()
        for f in funds:
            stars = "⭐" * f.morningstar_rating
            st.write(
                f"{stars} **{f.symbol}** — {f.name} | "
                f"Expense: {f.expense_ratio:.2f}% | "
                f"YTD: {f.ytd_return:+.1f}% | "
                f"AUM: ${f.aum/1e9:.0f}B"
            )
