"""Crypto Options Platform Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
from datetime import date, timedelta

from src.crypto_options import (
    CryptoOptionPricer,
    CryptoDerivativesAnalyzer,
    CryptoOptionContract,
    CryptoPerpetual,
    CryptoOptionType,
    CryptoExchange,
)

try:
    st.set_page_config(page_title="Crypto Options", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Crypto Options Platform")

pricer = CryptoOptionPricer()
analyzer = CryptoDerivativesAnalyzer()

tab1, tab2, tab3, tab4 = st.tabs([
    "Option Pricer", "Perpetuals & Funding", "Basis Analysis", "Vol Surface",
])

with tab1:
    st.subheader("Crypto Option Pricer (Black-76)")
    col1, col2, col3 = st.columns(3)
    underlying = col1.selectbox("Underlying", ["BTC", "ETH", "SOL"])
    spot = col2.number_input("Spot Price", value=50000.0, step=100.0)
    vol = col3.number_input("Volatility (%)", value=80.0, step=5.0) / 100

    col4, col5, col6 = st.columns(3)
    strike = col4.number_input("Strike", value=50000.0, step=1000.0)
    days = col5.number_input("Days to Expiry", value=30, step=1)
    opt_type = col6.selectbox("Type", ["CALL", "PUT"])

    expiry = date.today() + timedelta(days=days)
    contract = CryptoOptionContract(
        underlying=underlying,
        option_type=CryptoOptionType.CALL if opt_type == "CALL" else CryptoOptionType.PUT,
        strike=strike,
        expiry=expiry,
    )

    quote = pricer.price(contract, spot=spot, vol=vol)
    st.metric("Option Price", f"${quote.mark:,.2f}")

    gc1, gc2, gc3, gc4 = st.columns(4)
    gc1.metric("Delta", f"{quote.greeks.delta:.4f}")
    gc2.metric("Gamma", f"{quote.greeks.gamma:.6f}")
    gc3.metric("Theta", f"{quote.greeks.theta:.2f}")
    gc4.metric("Vega", f"{quote.greeks.vega:.2f}")

with tab2:
    st.subheader("Perpetual Futures & Funding Rates")
    for sym, mark, idx, fr in [
        ("BTC", 50100, 50000, 0.0001),
        ("ETH", 3510, 3500, 0.00015),
        ("SOL", 102, 101.5, 0.00008),
    ]:
        perp = CryptoPerpetual(
            underlying=sym, mark_price=mark, index_price=idx,
            funding_rate=fr, exchange=CryptoExchange.BINANCE,
        )
        analyzer.update_perpetual(perp)
        analyzer.record_funding_rate(sym, CryptoExchange.BINANCE, fr)

        with st.expander(f"{sym} Perpetual"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Mark", f"${mark:,.2f}")
            c2.metric("Index", f"${idx:,.2f}")
            c3.metric("Basis", f"${perp.basis:.2f}")
            c4.metric("Funding (Ann.)", f"{perp.annualized_funding:.2f}%")

with tab3:
    st.subheader("Spot-Futures Basis Analysis")
    basis = analyzer.compute_basis("BTC", 50000, 50500, 50100, 90)
    col1, col2, col3 = st.columns(3)
    col1.metric("Futures Basis", f"${basis.futures_basis:.2f}")
    col2.metric("Basis %", f"{basis.futures_basis_pct:.4f}%")
    col3.metric("Annualized", f"{basis.annualized_basis:.2f}%")

    st.metric("Perp Premium", f"${basis.perp_premium:.2f} ({basis.perp_premium_pct:.4f}%)")

with tab4:
    st.subheader("Implied Volatility Surface")
    st.info("Generate vol surface by pricing options across strikes and expiries")
    strikes = [40000, 45000, 50000, 55000, 60000]
    expiry_30 = date.today() + timedelta(days=30)

    quotes = []
    for s in strikes:
        c = CryptoOptionContract(
            underlying="BTC", option_type=CryptoOptionType.CALL,
            strike=s, expiry=expiry_30,
        )
        q = pricer.price(c, spot=50000, vol=0.80)
        quotes.append(q)

    surface = pricer.build_vol_surface("BTC", 50000, quotes)
    for (strike_val, tte), iv in sorted(surface.items()):
        st.write(f"Strike: ${strike_val:,.0f} | TTE: {tte:.3f}y | IV: {iv:.1%}")
