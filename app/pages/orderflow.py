"""Order Flow Analysis Dashboard (PRD-42).

4-tab layout: Imbalance | Blocks | Pressure | Smart Money.
Uses ImbalanceAnalyzer, BlockDetector, PressureAnalyzer; loads/saves via repository when DB available.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta

from src.orderflow import (
    ImbalanceAnalyzer,
    BlockDetector,
    PressureAnalyzer,
    BlockSize,
    OrderBookSnapshot,
    BlockTrade,
    FlowPressure,
    SmartMoneySignal,
)

# Optional DB: load/save via repository
try:
    from src.orderflow.repository import (
        get_session,
        save_orderbook_snapshot,
        save_block_trades,
        save_flow_pressure,
        save_smart_money_signal,
        get_orderbook_history,
        get_block_trades as repo_get_block_trades,
        get_flow_pressure_history,
        get_smart_money_history,
    )
    _repo_available = True
except Exception:
    _repo_available = False


def _demo_bid_ask_series(n: int = 5):
    """Generate demo bid/ask volumes for current symbol (deterministic from n)."""
    import numpy as np
    np.random.seed(42)
    base_bid = 45000 + np.random.randint(-5000, 15000, n).cumsum()
    base_ask = 40000 + np.random.randint(-8000, 12000, n).cumsum()
    base_bid = np.clip(base_bid, 10000, 100000)
    base_ask = np.clip(base_ask, 10000, 100000)
    return pd.Series(base_bid.astype(float)), pd.Series(base_ask.astype(float))


def _demo_trade_series(n: int = 8):
    """Generate demo trade sizes, prices, sides for block detection."""
    import numpy as np
    np.random.seed(43)
    sizes = np.array([500, 15000, 75000, 200000, 8000, 120000, 5000, 55000])
    prices = np.full(n, 450.0)
    sides = np.array(["buy", "buy", "sell", "buy", "sell", "buy", "buy", "sell"])
    return pd.Series(sizes), pd.Series(prices), pd.Series(sides)


def _demo_buy_sell_series(n: int = 5):
    """Generate demo buy/sell volumes for pressure."""
    import numpy as np
    np.random.seed(44)
    buys = np.array([60000, 30000, 70000, 50000, 80000])[:n]
    sells = np.array([40000, 50000, 30000, 50000, 20000])[:n]
    return pd.Series(buys.astype(float)), pd.Series(sells.astype(float))


st.set_page_config(page_title="Order Flow Analysis", layout="wide")
st.title("Order Flow Analysis")

# --- Sidebar ---
st.sidebar.header("Order Flow Settings")
symbol = st.sidebar.text_input("Symbol", "AAPL").strip().upper() or "AAPL"
window = st.sidebar.selectbox("Window", ["5 min", "15 min", "1 hour", "1 day"], index=2)
use_sample = st.sidebar.checkbox("Compute with sample data", value=True, help="Run analyzers on demo series to populate metrics and history")
save_to_db = st.sidebar.button("Save current snapshot to DB") if _repo_available else False

# --- Compute live metrics from analyzers (sample or placeholder) ---
imb_analyzer = ImbalanceAnalyzer()
block_detector = BlockDetector()
pressure_analyzer = PressureAnalyzer()

if use_sample:
    bid_s, ask_s = _demo_bid_ask_series(5)
    imb_results = imb_analyzer.rolling_imbalance(bid_s, ask_s, symbol=symbol)
    current_book = imb_results[-1] if imb_results else imb_analyzer.compute_imbalance(52300, 38100, symbol=symbol)
else:
    current_book = imb_analyzer.compute_imbalance(52300, 38100, symbol=symbol)

if use_sample:
    sizes_s, prices_s, sides_s = _demo_trade_series(8)
    blocks_list = block_detector.detect_blocks(sizes_s, prices_s, sides_s, symbol=symbol)
    total_vol = float(sizes_s.sum())
    smart_money = block_detector.compute_smart_money(blocks_list, total_volume=total_vol, symbol=symbol)
else:
    blocks_list = []
    total_vol = 0.0
    smart_money = block_detector.compute_smart_money([], symbol=symbol)

if use_sample:
    buy_s, sell_s = _demo_buy_sell_series(5)
    pressure_results = pressure_analyzer.compute_series(buy_s, sell_s, symbol=symbol)
    current_pressure = pressure_results[-1] if pressure_results else pressure_analyzer.compute_pressure(3200000, 2100000, symbol=symbol)
else:
    current_pressure = pressure_analyzer.compute_pressure(3200000, 2100000, symbol=symbol)

# Optional: persist to DB
if save_to_db and _repo_available:
    try:
        session = get_session()
        try:
            save_orderbook_snapshot(session, current_book)
            save_block_trades(session, blocks_list, symbol)
            save_flow_pressure(session, current_pressure)
            save_smart_money_signal(session, smart_money)
            session.commit()
            st.sidebar.success("Snapshot saved to database.")
        finally:
            session.close()
    except Exception as e:
        st.sidebar.error(f"Save failed: {e}")

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Imbalance", "Blocks", "Pressure", "Smart Money",
])

# --- Tab 1: Imbalance ---
with tab1:
    st.subheader("Order Book Imbalance")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Bid Volume", f"{current_book.bid_volume:,.0f}")
    col2.metric("Ask Volume", f"{current_book.ask_volume:,.0f}")
    col3.metric("Imbalance Ratio", f"{current_book.imbalance_ratio:.2f}")
    col4.metric("Type", current_book.imbalance_type.value.replace("_", " ").title())

    st.markdown("#### Recent Imbalance History")
    imb_history = []
    if _repo_available:
        try:
            session = get_session()
            try:
                imb_history = get_orderbook_history(session, symbol, limit=20)
            finally:
                session.close()
        except Exception:
            pass
    if not imb_history and imb_analyzer.get_history():
        for s in list(imb_analyzer.get_history())[-20:]:
            imb_history.append({
                "timestamp": s.timestamp.strftime("%H:%M") if s.timestamp else "",
                "bid_volume": s.bid_volume,
                "ask_volume": s.ask_volume,
                "imbalance_ratio": s.imbalance_ratio,
                "imbalance_type": s.imbalance_type.value.replace("_", " ").title(),
                "signal": s.signal.value.replace("_", " ").title(),
            })
    if imb_history:
        df = pd.DataFrame(imb_history)
        if "computed_at" in df.columns:
            df["Time"] = pd.to_datetime(df["computed_at"], errors="coerce").dt.strftime("%H:%M")
        elif "timestamp" in df.columns:
            df["Time"] = df["timestamp"].apply(lambda x: x.strftime("%H:%M") if hasattr(x, "strftime") else str(x)[:5] if pd.notna(x) else "")
        else:
            df["Time"] = ""
        display_cols = ["Time", "bid_volume", "ask_volume", "imbalance_ratio", "imbalance_type", "signal"]
        display_cols = [c for c in display_cols if c in df.columns]
        renames = {"bid_volume": "Bid Vol", "ask_volume": "Ask Vol", "imbalance_ratio": "Ratio", "imbalance_type": "Type", "signal": "Signal"}
        st.dataframe(df[display_cols].rename(columns=renames), use_container_width=True, hide_index=True)
    else:
        st.info("No imbalance history. Enable \"Compute with sample data\" or load from DB.")

# --- Tab 2: Blocks ---
with tab2:
    st.subheader("Block Trades")

    n_inst = sum(1 for b in blocks_list if b.block_size == BlockSize.INSTITUTIONAL)
    block_vol = sum(b.size for b in blocks_list)
    block_ratio_pct = (block_vol / total_vol * 100) if total_vol else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Blocks Detected", len(blocks_list))
    col2.metric("Institutional", n_inst)
    col3.metric("Block Volume", f"{block_vol:,.0f} shares")
    col4.metric("Block Ratio", f"{block_ratio_pct:.1f}%")

    st.markdown("#### Recent Block Trades")
    block_history = []
    if _repo_available:
        try:
            session = get_session()
            try:
                block_history = repo_get_block_trades(session, symbol, limit=20)
            finally:
                session.close()
        except Exception:
            pass
    if not block_history and blocks_list:
        for b in blocks_list[:20]:
            block_history.append({
                "timestamp": b.timestamp.strftime("%H:%M") if b.timestamp else "",
                "size": b.size,
                "price": b.price,
                "side": b.side,
                "dollar_value": b.dollar_value,
                "block_size": b.block_size.value,
            })
    if block_history:
        df = pd.DataFrame(block_history)
        if "computed_at" in df.columns:
            df["Time"] = pd.to_datetime(df["computed_at"], errors="coerce").dt.strftime("%H:%M")
        elif "timestamp" in df.columns:
            df["Time"] = df["timestamp"].apply(lambda x: x.strftime("%H:%M") if hasattr(x, "strftime") else str(x)[:5] if pd.notna(x) else "")
        else:
            df["Time"] = ""
        if "dollar_value" in df.columns:
            df["Value"] = df["dollar_value"].apply(lambda x: f"${float(x):,.0f}" if pd.notna(x) and x else "")
        display_cols = [c for c in ["Time", "size", "price", "side", "Value", "block_size"] if c in df.columns]
        st.dataframe(df[display_cols].rename(columns={"size": "Size", "price": "Price", "side": "Side", "block_size": "Class"}), use_container_width=True, hide_index=True)
    else:
        st.info("No block trades. Enable \"Compute with sample data\" or load from DB.")

# --- Tab 3: Pressure ---
with tab3:
    st.subheader("Buy/Sell Pressure")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Buy Volume", f"{current_pressure.buy_volume:,.0f}")
    col2.metric("Sell Volume", f"{current_pressure.sell_volume:,.0f}")
    col3.metric("Net Flow", f"{current_pressure.net_flow:+,.0f}")
    col4.metric("Direction", current_pressure.direction.value.title())

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Pressure Ratio", f"{current_pressure.pressure_ratio:.2f}")
    col6.metric("Buy %", f"{current_pressure.buy_pct:.1f}%")
    col7.metric("Cumulative Delta", f"{current_pressure.cumulative_delta:+,.0f}")
    smoothed = pressure_analyzer.smoothed_ratio(
        pd.Series([current_pressure.buy_volume]),
        pd.Series([current_pressure.sell_volume]),
    )
    col8.metric("Smoothed Ratio", f"{smoothed.iloc[-1]:.2f}" if len(smoothed) else "—")

    st.markdown("#### Pressure History")
    pressure_history = []
    if _repo_available:
        try:
            session = get_session()
            try:
                pressure_history = get_flow_pressure_history(session, symbol, limit=20)
            finally:
                session.close()
        except Exception:
            pass
    if not pressure_history and pressure_analyzer.get_history():
        for p in list(pressure_analyzer.get_history())[-20:]:
            pressure_history.append({
                "date": p.date or date.today(),
                "buy_volume": p.buy_volume,
                "sell_volume": p.sell_volume,
                "net_flow": p.net_flow,
                "pressure_ratio": p.pressure_ratio,
                "direction": p.direction.value,
                "cumulative_delta": p.cumulative_delta,
            })
    if pressure_history:
        df = pd.DataFrame(pressure_history)
        if "date" in df.columns:
            df["Date"] = df["date"].apply(lambda x: x.strftime("%Y-%m-%d") if hasattr(x, "strftime") else str(x))
        elif "computed_at" in df.columns:
            df["Date"] = pd.to_datetime(df["computed_at"], errors="coerce").dt.strftime("%Y-%m-%d")
        else:
            df["Date"] = ""
        if "net_flow" in df.columns:
            df["Net"] = df["net_flow"].apply(lambda x: f"{float(x):+,.0f}" if pd.notna(x) else "")
        if "cumulative_delta" in df.columns:
            df["Cum Delta"] = df["cumulative_delta"].apply(lambda x: f"{float(x):+,.0f}" if pd.notna(x) else "")
        display_cols = [c for c in ["Date", "buy_volume", "sell_volume", "Net", "pressure_ratio", "direction", "Cum Delta"] if c in df.columns]
        st.dataframe(df[display_cols].rename(columns={"buy_volume": "Buy Vol", "sell_volume": "Sell Vol", "pressure_ratio": "Ratio", "direction": "Direction"}), use_container_width=True, hide_index=True)
    else:
        st.info("No pressure history. Enable \"Compute with sample data\" or load from DB.")

# --- Tab 4: Smart Money ---
with tab4:
    st.subheader("Smart Money Signals")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Signal", smart_money.signal.value.replace("_", " ").title())
    col2.metric("Confidence", f"{smart_money.confidence * 100:.0f}%")
    col3.metric("Block Ratio", f"{smart_money.block_ratio * 100:.1f}%")
    col4.metric("Inst. Buy %", f"{smart_money.institutional_buy_pct:.1f}%")

    st.markdown("#### Smart Money History")
    smart_history = []
    if _repo_available:
        try:
            session = get_session()
            try:
                smart_history = get_smart_money_history(session, symbol, limit=20)
            finally:
                session.close()
        except Exception:
            pass
    if smart_history:
        df = pd.DataFrame(smart_history)
        if "date" in df.columns:
            df["Date"] = df["date"].apply(lambda x: x.strftime("%Y-%m-%d") if hasattr(x, "strftime") else str(x))
        elif "computed_at" in df.columns:
            df["Date"] = pd.to_datetime(df["computed_at"], errors="coerce").dt.strftime("%Y-%m-%d")
        else:
            df["Date"] = ""
        if "confidence" in df.columns:
            df["Confidence"] = df["confidence"].apply(lambda x: f"{float(x)*100:.0f}%" if pd.notna(x) else "")
        if "institutional_buy_pct" in df.columns:
            df["Inst Buy %"] = df["institutional_buy_pct"].apply(lambda x: f"{float(x):.1f}%" if pd.notna(x) else "")
        if "block_ratio" in df.columns:
            df["Block Ratio"] = df["block_ratio"].apply(lambda x: f"{float(x)*100:.1f}%" if pd.notna(x) else "")
        display_cols = [c for c in ["Date", "signal", "Confidence", "Inst Buy %", "Block Ratio"] if c in df.columns]
        st.dataframe(df[display_cols].rename(columns={"signal": "Signal"}), use_container_width=True, hide_index=True)
    else:
        st.info("No smart money history. Enable \"Compute with sample data\" and run block detection, or load from DB.")
