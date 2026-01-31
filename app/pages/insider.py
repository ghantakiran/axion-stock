"""Insider Trading Tracker Dashboard."""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="Insider Trading", layout="wide")
st.title("🕵️ Insider Trading Tracker")

# Try to import insider module
try:
    from src.insider import (
        TransactionTracker, InsiderTransaction, InsiderType, TransactionType,
        ClusterDetector, SignalStrength,
        InstitutionalTracker, InstitutionType,
        ProfileManager,
        SignalGenerator, AlertManager, create_default_alerts,
        generate_sample_transactions, generate_sample_institutional,
    )
    INSIDER_AVAILABLE = True
except ImportError as e:
    INSIDER_AVAILABLE = False
    st.error(f"Insider module not available: {e}")


def render_transactions_tab():
    """Render transactions tab."""
    st.subheader("Recent Insider Transactions")
    
    tracker = generate_sample_transactions()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        days = st.selectbox("Time Period", [7, 14, 30, 90], index=2)
    
    with col2:
        txn_type = st.selectbox(
            "Transaction Type",
            ["All", "Buys Only", "Sells Only"],
        )
    
    with col3:
        min_value = st.selectbox(
            "Min Value",
            [0, 100_000, 500_000, 1_000_000],
            format_func=lambda x: f"${x:,}" if x > 0 else "All",
        )
    
    # Get transactions
    if txn_type == "Buys Only":
        transactions = tracker.get_recent_buys(days=days, min_value=min_value)
    elif txn_type == "Sells Only":
        transactions = tracker.get_recent_sells(days=days, min_value=min_value)
    else:
        transactions = [
            t for t in tracker.get_all_transactions()
            if t.transaction_date and t.transaction_date >= date.today() - timedelta(days=days)
            and t.value >= min_value
        ]
        transactions.sort(key=lambda t: t.value, reverse=True)
    
    st.markdown(f"### {len(transactions)} Transactions")
    
    if not transactions:
        st.info("No transactions found")
        return
    
    # Display table
    data = []
    for t in transactions[:50]:
        type_icon = "🟢" if t.is_buy else "🔴"
        data.append({
            "Date": t.transaction_date.strftime("%Y-%m-%d") if t.transaction_date else "-",
            "Type": f"{type_icon} {t.transaction_type.value.title()}",
            "Symbol": t.symbol,
            "Insider": t.insider_name,
            "Title": t.insider_title,
            "Shares": f"{t.shares:,}",
            "Price": f"${t.price:.2f}",
            "Value": f"${t.value:,.0f}",
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Market summary
    st.markdown("---")
    st.markdown("### Market Summary")
    
    summary = tracker.get_market_summary(days=days)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Buys", f"${summary['total_buy_value']:,.0f}")
    
    with col2:
        st.metric("Total Sells", f"${summary['total_sell_value']:,.0f}")
    
    with col3:
        net = summary['net_value']
        st.metric("Net Value", f"${net:+,.0f}")
    
    with col4:
        ratio = summary['buy_sell_ratio']
        ratio_str = f"{ratio:.2f}" if ratio != float('inf') else "∞"
        st.metric("Buy/Sell Ratio", ratio_str)


def render_clusters_tab():
    """Render cluster buying tab."""
    st.subheader("Cluster Buying Detection")
    
    tracker = generate_sample_transactions()
    detector = ClusterDetector(tracker)
    
    # Detect clusters
    clusters = detector.detect_clusters(days=90)
    
    if not clusters:
        st.info("No cluster buying patterns detected")
        return
    
    st.markdown(f"### {len(clusters)} Clusters Detected")
    
    for cluster in clusters:
        strength_color = {
            SignalStrength.VERY_STRONG: "🔴",
            SignalStrength.STRONG: "🟠",
            SignalStrength.MODERATE: "🟡",
            SignalStrength.WEAK: "🟢",
        }.get(cluster.signal_strength, "⚪")
        
        with st.expander(f"{strength_color} **{cluster.symbol}** - {cluster.company_name} (Score: {cluster.cluster_score:.0f})"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Insiders", cluster.insider_count)
            
            with col2:
                st.metric("Total Value", f"${cluster.total_value:,.0f}")
            
            with col3:
                st.metric("Avg Price", f"${cluster.avg_price:.2f}")
            
            st.markdown("**Insiders:**")
            for insider in cluster.insiders:
                st.write(f"• {insider}")
            
            st.markdown(f"**Period:** {cluster.start_date} to {cluster.end_date} ({cluster.days_span} days)")


def render_signals_tab():
    """Render signals tab."""
    st.subheader("Insider Trading Signals")
    
    tracker = generate_sample_transactions()
    detector = ClusterDetector(tracker)
    generator = SignalGenerator(tracker, detector)
    
    # Generate signals
    signals = generator.generate_signals(days=90)
    
    if not signals:
        st.info("No signals generated")
        return
    
    st.markdown(f"### {len(signals)} Active Signals")
    
    # Filter
    signal_types = list(set(s.signal_type for s in signals))
    selected_type = st.selectbox(
        "Signal Type",
        ["All"] + signal_types,
    )
    
    if selected_type != "All":
        signals = [s for s in signals if s.signal_type == selected_type]
    
    for signal in signals:
        strength_icon = {
            SignalStrength.VERY_STRONG: "🔴",
            SignalStrength.STRONG: "🟠",
            SignalStrength.MODERATE: "🟡",
            SignalStrength.WEAK: "🟢",
        }.get(signal.signal_strength, "⚪")
        
        type_label = signal.signal_type.replace("_", " ").title()
        
        st.markdown(f"""
        {strength_icon} **{signal.symbol}** - {type_label}
        
        {signal.description}
        
        **Value:** ${signal.total_value:,.0f} | **Strength:** {signal.signal_strength.value.title()}
        
        ---
        """)


def render_institutions_tab():
    """Render institutional holdings tab."""
    st.subheader("Institutional Holdings")
    
    tracker = generate_sample_institutional()
    
    # Symbol selector
    symbol = st.selectbox("Select Symbol", ["AAPL", "NVDA", "META"])
    
    # Get data
    holders = tracker.get_top_holders(symbol, limit=10)
    summary = tracker.get_summary(symbol)
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Institutions", summary.total_institutions)
    
    with col2:
        st.metric("Total Value", f"${summary.total_value/1e9:.1f}B")
    
    with col3:
        st.metric("New Positions", summary.new_positions)
    
    with col4:
        st.metric("Sold Out", summary.sold_out)
    
    # Holdings table
    st.markdown("### Top Holders")
    
    if holders:
        data = []
        for h in holders:
            change_icon = "🟢" if h.shares_change > 0 else "🔴" if h.shares_change < 0 else "➡️"
            
            data.append({
                "Institution": h.institution_name,
                "Type": h.institution_type.value.replace("_", " ").title(),
                "Shares": f"{h.shares/1e6:.1f}M",
                "Value": f"${h.value/1e9:.1f}B",
                "Change": f"{change_icon} {h.shares_change_pct:+.1f}%",
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Activity
    st.markdown("---")
    st.markdown("### Recent Activity")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**New Positions:**")
        new_positions = tracker.get_new_positions()
        for h in new_positions[:5]:
            st.write(f"• {h.institution_name} → {h.symbol}")
    
    with col2:
        st.markdown("**Sold Out:**")
        sold_out = tracker.get_sold_out()
        for h in sold_out[:5]:
            st.write(f"• {h.institution_name} ✕ {h.symbol}")


def render_profiles_tab():
    """Render insider profiles tab."""
    st.subheader("Insider Profiles")
    
    tracker = generate_sample_transactions()
    manager = ProfileManager(tracker)
    manager.build_profiles()
    
    # Profile list
    profiles = manager.get_all_profiles()
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("### Insiders")
        
        profile_names = [p.name for p in profiles]
        selected_name = st.radio("Select Insider", profile_names)
    
    with col2:
        profile = manager.get_profile(selected_name)
        
        if profile:
            st.markdown(f"### {profile.name}")
            
            # Companies
            st.markdown("**Companies:**")
            for symbol in profile.companies:
                title = profile.titles.get(symbol, "")
                st.write(f"• {symbol} - {title}")
            
            # Stats
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Transactions", profile.total_transactions)
            
            with col2:
                st.metric("Total Buys", f"${profile.total_buy_value:,.0f}")
            
            with col3:
                st.metric("Total Sells", f"${profile.total_sell_value:,.0f}")
            
            # Recent activity
            st.markdown("---")
            st.markdown("**Recent Transactions:**")
            
            for txn in profile.recent_transactions[:5]:
                type_icon = "🟢" if txn.is_buy else "🔴"
                st.write(f"• {type_icon} {txn.transaction_date} - {txn.symbol} - ${txn.value:,.0f}")


def render_sidebar():
    """Render sidebar with summary."""
    st.sidebar.header("Quick Stats")
    
    tracker = generate_sample_transactions()
    summary = tracker.get_market_summary(days=7)
    
    st.sidebar.metric("Weekly Buy Volume", f"${summary['total_buy_value']/1e6:.1f}M")
    st.sidebar.metric("Weekly Sell Volume", f"${summary['total_sell_value']/1e6:.1f}M")
    
    ratio = summary['buy_sell_ratio']
    ratio_str = f"{ratio:.2f}" if ratio != float('inf') else "∞"
    st.sidebar.metric("Buy/Sell Ratio", ratio_str)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Top Bought (7d)")
    
    top_bought = tracker.get_top_bought(days=7, limit=5)
    for symbol, value in top_bought:
        st.sidebar.write(f"• {symbol}: ${value/1e6:.1f}M")


def main():
    if not INSIDER_AVAILABLE:
        return
    
    # Sidebar
    render_sidebar()
    
    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Transactions",
        "🎯 Clusters",
        "📡 Signals",
        "🏛️ Institutions",
        "👤 Profiles",
    ])
    
    with tab1:
        render_transactions_tab()
    
    with tab2:
        render_clusters_tab()
    
    with tab3:
        render_signals_tab()
    
    with tab4:
        render_institutions_tab()
    
    with tab5:
        render_profiles_tab()


if __name__ == "__main__":
    main()
