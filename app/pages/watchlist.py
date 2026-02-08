"""Watchlist Management Dashboard."""

import streamlit as st
import pandas as pd
from datetime import date

try:
    st.set_page_config(page_title="Watchlist", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("📋 Watchlist Management")

# Try to import watchlist module
try:
    from src.watchlist import (
        WatchlistManager, AlertManager, NotesManager, SharingManager,
        Watchlist, WatchlistItem, AlertType, NoteType, Permission,
        ConvictionLevel, WATCHLIST_COLORS, WATCHLIST_ICONS,
    )
    WATCHLIST_AVAILABLE = True
except ImportError as e:
    WATCHLIST_AVAILABLE = False
    st.error(f"Watchlist module not available: {e}")


def create_demo_watchlist(manager):
    """Create demo watchlist with sample data."""
    wl = manager.create_watchlist(
        "Tech Favorites",
        description="Top technology stocks I'm watching",
        icon="🚀",
    )
    
    # Add sample items
    items = [
        ("AAPL", "Apple Inc.", 185.0, 170.0, 200.0, 4, ["mega-cap", "growth"]),
        ("MSFT", "Microsoft Corp.", 378.0, 350.0, 420.0, 5, ["mega-cap", "cloud"]),
        ("GOOGL", "Alphabet Inc.", 141.0, 130.0, 160.0, 4, ["mega-cap", "ai"]),
        ("NVDA", "NVIDIA Corp.", 800.0, 700.0, 900.0, 5, ["ai", "semiconductor"]),
        ("AMZN", "Amazon.com Inc.", 178.0, 160.0, 200.0, 3, ["mega-cap", "cloud"]),
    ]
    
    for symbol, name, price, buy, sell, conviction, tags in items:
        manager.add_item(
            wl.watchlist_id, symbol, name,
            current_price=price,
            buy_target=buy,
            sell_target=sell,
            conviction=conviction,
            tags=tags,
        )
    
    # Create a second watchlist
    wl2 = manager.create_watchlist(
        "Dividend Plays",
        description="Income-focused stocks",
        icon="💰",
    )
    
    div_items = [
        ("JNJ", "Johnson & Johnson", 155.0, 145.0, 170.0, 4, ["dividend", "healthcare"]),
        ("KO", "Coca-Cola Co.", 60.0, 55.0, 65.0, 3, ["dividend", "consumer"]),
        ("PG", "Procter & Gamble", 165.0, 155.0, 180.0, 4, ["dividend", "consumer"]),
    ]
    
    for symbol, name, price, buy, sell, conviction, tags in div_items:
        manager.add_item(
            wl2.watchlist_id, symbol, name,
            current_price=price,
            buy_target=buy,
            sell_target=sell,
            conviction=conviction,
            tags=tags,
        )


# Initialize session state
if "watchlist_manager" not in st.session_state:
    st.session_state.watchlist_manager = WatchlistManager() if WATCHLIST_AVAILABLE else None
    st.session_state.alert_manager = AlertManager() if WATCHLIST_AVAILABLE else None
    st.session_state.notes_manager = NotesManager() if WATCHLIST_AVAILABLE else None

    # Create demo watchlist
    if st.session_state.watchlist_manager:
        create_demo_watchlist(st.session_state.watchlist_manager)


def render_watchlist_sidebar():
    """Render watchlist selection sidebar."""
    manager = st.session_state.watchlist_manager
    
    st.sidebar.header("Watchlists")
    
    watchlists = manager.get_all_watchlists()
    
    if not watchlists:
        st.sidebar.info("No watchlists yet")
        return None
    
    # Watchlist selector
    wl_options = {f"{wl.icon} {wl.name}": wl.watchlist_id for wl in watchlists}
    selected = st.sidebar.selectbox(
        "Select Watchlist",
        options=list(wl_options.keys()),
    )
    
    selected_id = wl_options[selected]
    
    # Watchlist info
    wl = manager.get_watchlist(selected_id)
    if wl:
        st.sidebar.caption(f"{wl.item_count} items")
        if wl.description:
            st.sidebar.caption(wl.description)
    
    # Create new watchlist
    st.sidebar.markdown("---")
    with st.sidebar.expander("➕ New Watchlist"):
        new_name = st.text_input("Name", key="new_wl_name")
        new_desc = st.text_input("Description", key="new_wl_desc")
        new_icon = st.selectbox("Icon", WATCHLIST_ICONS[:8], key="new_wl_icon")
        
        if st.button("Create", key="create_wl"):
            if new_name:
                manager.create_watchlist(new_name, new_desc, icon=new_icon)
                st.rerun()
    
    return selected_id


def render_watchlist_view(watchlist_id: str):
    """Render main watchlist view."""
    manager = st.session_state.watchlist_manager
    wl = manager.get_watchlist(watchlist_id)
    
    if not wl:
        st.warning("Watchlist not found")
        return
    
    # Header
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.subheader(f"{wl.icon} {wl.name}")
    with col2:
        if st.button("📊 Performance"):
            show_performance(watchlist_id)
    with col3:
        if st.button("➕ Add Stock"):
            st.session_state.show_add_form = True
    
    # Add stock form
    if st.session_state.get("show_add_form"):
        with st.expander("Add Stock", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                new_symbol = st.text_input("Symbol").upper()
            with col2:
                new_price = st.number_input("Current Price", value=100.0, min_value=0.01)
            with col3:
                new_conviction = st.slider("Conviction", 1, 5, 3)
            
            col1, col2 = st.columns(2)
            with col1:
                buy_target = st.number_input("Buy Target", value=0.0)
            with col2:
                sell_target = st.number_input("Sell Target", value=0.0)
            
            if st.button("Add to Watchlist"):
                if new_symbol:
                    manager.add_item(
                        watchlist_id, new_symbol,
                        current_price=new_price,
                        buy_target=buy_target if buy_target > 0 else None,
                        sell_target=sell_target if sell_target > 0 else None,
                        conviction=new_conviction,
                    )
                    st.session_state.show_add_form = False
                    st.rerun()
    
    # Items table
    if not wl.items:
        st.info("No items in this watchlist. Add some stocks!")
        return
    
    data = []
    for item in wl.items:
        # Calculate distances
        to_buy = ""
        if item.buy_target:
            dist = item.distance_to_buy_target
            to_buy = f"{dist:.1%}" if dist else ""
        
        to_sell = ""
        if item.sell_target:
            dist = item.distance_to_sell_target
            to_sell = f"{dist:.1%}" if dist else ""
        
        # Conviction stars
        stars = "⭐" * (item.conviction or 0)
        
        data.append({
            "Symbol": item.symbol,
            "Company": item.company_name,
            "Price": f"${item.current_price:.2f}",
            "Change": f"{item.change_pct:.1%}" if item.change_pct else "-",
            "Buy Target": f"${item.buy_target:.2f}" if item.buy_target else "-",
            "To Buy": to_buy,
            "Sell Target": f"${item.sell_target:.2f}" if item.sell_target else "-",
            "To Sell": to_sell,
            "Since Added": f"{item.gain_since_added:.1%}",
            "Conviction": stars,
            "Tags": ", ".join(item.tags[:3]),
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Quick actions
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        remove_symbol = st.selectbox(
            "Remove Stock",
            options=[""] + [item.symbol for item in wl.items],
            key="remove_select"
        )
        if remove_symbol and st.button("Remove", key="remove_btn"):
            manager.remove_item(watchlist_id, remove_symbol)
            st.rerun()
    
    with col2:
        edit_symbol = st.selectbox(
            "Edit Stock",
            options=[""] + [item.symbol for item in wl.items],
            key="edit_select"
        )
        if edit_symbol:
            item = manager.get_item(watchlist_id, edit_symbol)
            if item and st.button("Edit Targets", key="edit_btn"):
                st.session_state.editing_symbol = edit_symbol
    
    # Edit form
    if st.session_state.get("editing_symbol"):
        edit_symbol = st.session_state.editing_symbol
        item = manager.get_item(watchlist_id, edit_symbol)
        if item:
            with st.expander(f"Edit {edit_symbol}", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    new_buy = st.number_input(
                        "Buy Target",
                        value=item.buy_target or 0.0,
                        key="edit_buy"
                    )
                with col2:
                    new_sell = st.number_input(
                        "Sell Target",
                        value=item.sell_target or 0.0,
                        key="edit_sell"
                    )
                with col3:
                    new_stop = st.number_input(
                        "Stop Loss",
                        value=item.stop_loss or 0.0,
                        key="edit_stop"
                    )
                
                new_notes = st.text_area("Notes", value=item.notes, key="edit_notes")
                
                if st.button("Save Changes"):
                    manager.update_item(
                        watchlist_id, edit_symbol,
                        buy_target=new_buy if new_buy > 0 else None,
                        sell_target=new_sell if new_sell > 0 else None,
                        stop_loss=new_stop if new_stop > 0 else None,
                        notes=new_notes,
                    )
                    st.session_state.editing_symbol = None
                    st.rerun()


def show_performance(watchlist_id: str):
    """Show watchlist performance."""
    manager = st.session_state.watchlist_manager
    perf = manager.calculate_performance(watchlist_id)
    
    if not perf:
        st.warning("No performance data")
        return
    
    st.markdown("### Performance Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Items", perf.total_items)
    col2.metric("Winners", perf.winners)
    col3.metric("Win Rate", f"{perf.win_rate:.0%}")
    col4.metric("Hypothetical Return", f"{perf.hypothetical_return_pct:.1%}")
    
    st.markdown("**Top Performers:**")
    for symbol, ret in perf.top_performers[:3]:
        st.write(f"• {symbol}: {ret:.1%}")
    
    st.markdown("**Worst Performers:**")
    for symbol, ret in perf.worst_performers[:3]:
        st.write(f"• {symbol}: {ret:.1%}")


def render_alerts_tab(watchlist_id: str):
    """Render alerts management tab."""
    alert_manager = st.session_state.alert_manager
    watchlist_manager = st.session_state.watchlist_manager
    wl = watchlist_manager.get_watchlist(watchlist_id)
    
    if not wl:
        return
    
    st.subheader("Price Alerts")
    
    # Create new alert
    with st.expander("➕ Create Alert"):
        col1, col2 = st.columns(2)
        with col1:
            alert_symbol = st.selectbox(
                "Symbol",
                options=[item.symbol for item in wl.items],
                key="alert_symbol"
            )
        with col2:
            alert_type = st.selectbox(
                "Type",
                options=[
                    ("Price Below", AlertType.PRICE_BELOW),
                    ("Price Above", AlertType.PRICE_ABOVE),
                    ("% Change Up", AlertType.PCT_CHANGE_UP),
                    ("% Change Down", AlertType.PCT_CHANGE_DOWN),
                    ("Volume Spike", AlertType.VOLUME_SPIKE),
                ],
                format_func=lambda x: x[0],
                key="alert_type"
            )
        
        threshold = st.number_input("Threshold", value=0.0, key="alert_threshold")
        
        if st.button("Create Alert"):
            if alert_symbol and threshold > 0:
                alert_manager.create_alert(
                    watchlist_id=watchlist_id,
                    symbol=alert_symbol,
                    alert_type=alert_type[1],
                    threshold=threshold,
                )
                st.success(f"Alert created for {alert_symbol}")
    
    # Active alerts
    st.markdown("---")
    st.markdown("**Active Alerts**")
    
    alerts = alert_manager.get_alerts_for_watchlist(watchlist_id)
    active_alerts = [a for a in alerts if a.is_active]
    
    if not active_alerts:
        st.info("No active alerts")
    else:
        for alert in active_alerts:
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.write(f"**{alert.symbol}**")
            with col2:
                st.write(f"{alert.alert_type.value}: {alert.threshold}")
            with col3:
                if st.button("Delete", key=f"del_{alert.alert_id}"):
                    alert_manager.delete_alert(alert.alert_id)
                    st.rerun()


def render_notes_tab(watchlist_id: str):
    """Render notes tab."""
    notes_manager = st.session_state.notes_manager
    watchlist_manager = st.session_state.watchlist_manager
    wl = watchlist_manager.get_watchlist(watchlist_id)
    
    if not wl:
        return
    
    st.subheader("Research Notes")
    
    # Add new note
    with st.expander("➕ Add Note"):
        note_symbol = st.selectbox(
            "Symbol",
            options=[item.symbol for item in wl.items],
            key="note_symbol"
        )
        note_title = st.text_input("Title", key="note_title")
        note_content = st.text_area("Content", key="note_content")
        note_type = st.selectbox(
            "Type",
            options=[nt for nt in NoteType],
            format_func=lambda x: x.value.title(),
            key="note_type"
        )
        
        if st.button("Save Note"):
            if note_symbol and note_title:
                notes_manager.add_note(
                    watchlist_id=watchlist_id,
                    symbol=note_symbol,
                    title=note_title,
                    content=note_content,
                    note_type=note_type,
                )
                st.success("Note saved!")
    
    # Display notes
    st.markdown("---")
    notes = notes_manager.get_notes_for_watchlist(watchlist_id)
    
    if not notes:
        st.info("No notes yet")
    else:
        for note in notes:
            with st.container():
                st.markdown(f"**{note.symbol} - {note.title}**")
                st.caption(f"{note.note_type.value.title()} | {note.created_at.strftime('%Y-%m-%d')}")
                st.write(note.content)
                st.markdown("---")


def main():
    if not WATCHLIST_AVAILABLE:
        return
    
    # Sidebar - watchlist selection
    selected_id = render_watchlist_sidebar()
    
    if not selected_id:
        st.info("Create a watchlist to get started")
        return
    
    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["📋 Watchlist", "🔔 Alerts", "📝 Notes"])
    
    with tab1:
        render_watchlist_view(selected_id)
    
    with tab2:
        render_alerts_tab(selected_id)
    
    with tab3:
        render_notes_tab(selected_id)



main()
