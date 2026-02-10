"""Push Notifications Settings Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
from datetime import datetime, timezone

try:
    st.set_page_config(page_title="Notification Settings", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Push Notification Settings")

# --- Sidebar ---
st.sidebar.header("Quick Actions")

if st.sidebar.button("Enable All"):
    st.sidebar.success("All notifications enabled")

if st.sidebar.button("Mute All"):
    st.sidebar.warning("All notifications muted")

if st.sidebar.button("Send Test"):
    st.sidebar.info("Test notification sent")

st.sidebar.markdown("---")
st.sidebar.markdown("**Registered Devices:** 2")
st.sidebar.markdown("**Notifications Today:** 12")

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Preferences", "Devices", "History", "Analytics"
])

# --- Tab 1: Preferences ---
with tab1:
    st.subheader("Notification Preferences")

    # Category settings
    categories = [
        {
            "name": "Price Alerts",
            "key": "price_alerts",
            "description": "Price target and threshold alerts",
            "icon": "trending_up",
            "default": True,
        },
        {
            "name": "Trade Executions",
            "key": "trade_executions",
            "description": "Order fills, cancellations, rejections",
            "icon": "swap_horiz",
            "default": True,
        },
        {
            "name": "Portfolio Updates",
            "key": "portfolio",
            "description": "Daily P&L summaries, significant changes",
            "icon": "account_balance_wallet",
            "default": True,
        },
        {
            "name": "Risk Alerts",
            "key": "risk_alerts",
            "description": "Stop-loss triggers, margin warnings",
            "icon": "warning",
            "default": True,
        },
        {
            "name": "News",
            "key": "news",
            "description": "Breaking news for watched symbols",
            "icon": "article",
            "default": False,
        },
        {
            "name": "Earnings",
            "key": "earnings",
            "description": "Earnings announcements and surprises",
            "icon": "event",
            "default": False,
        },
        {
            "name": "Dividends",
            "key": "dividends",
            "description": "Dividend declarations and ex-dates",
            "icon": "payments",
            "default": False,
        },
        {
            "name": "System",
            "key": "system",
            "description": "Maintenance, updates, announcements",
            "icon": "info",
            "default": True,
        },
    ]

    for cat in categories:
        with st.expander(f"{cat['name']}", expanded=False):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"_{cat['description']}_")

            with col2:
                enabled = st.toggle("Enabled", value=cat["default"], key=f"enable_{cat['key']}")

            if enabled:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.selectbox(
                        "Priority",
                        ["Urgent", "High", "Normal", "Low"],
                        index=2,
                        key=f"priority_{cat['key']}",
                    )
                with col2:
                    st.multiselect(
                        "Channels",
                        ["Push", "Email", "SMS"],
                        default=["Push"],
                        key=f"channels_{cat['key']}",
                    )
                with col3:
                    st.number_input(
                        "Max per hour",
                        min_value=1,
                        max_value=100,
                        value=10,
                        key=f"max_{cat['key']}",
                    )

    st.markdown("---")

    # Quiet Hours
    st.subheader("Quiet Hours")
    col1, col2, col3 = st.columns(3)

    with col1:
        quiet_enabled = st.toggle("Enable Quiet Hours", value=False)

    if quiet_enabled:
        with col2:
            quiet_start = st.time_input("Start Time", value=None)
        with col3:
            quiet_end = st.time_input("End Time", value=None)

        st.selectbox(
            "Timezone",
            ["UTC", "America/New_York", "America/Chicago", "America/Los_Angeles", "Europe/London"],
            index=1,
        )

        st.multiselect(
            "Apply to categories",
            [cat["name"] for cat in categories],
            default=[cat["name"] for cat in categories],
        )

    if st.button("Save Preferences", type="primary"):
        st.success("Preferences saved successfully")

# --- Tab 2: Devices ---
with tab2:
    st.subheader("Registered Devices")

    devices = [
        {
            "id": "dev_abc123",
            "name": "iPhone 15 Pro",
            "platform": "iOS",
            "model": "iPhone15,2",
            "app_version": "2.1.0",
            "registered": "2024-12-15",
            "last_used": "2025-01-15 14:30",
            "active": True,
        },
        {
            "id": "dev_xyz789",
            "name": "Samsung Galaxy S24",
            "platform": "Android",
            "model": "SM-S921B",
            "app_version": "2.1.0",
            "registered": "2024-11-20",
            "last_used": "2025-01-14 09:15",
            "active": True,
        },
    ]

    for device in devices:
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

            with col1:
                status = "Active" if device["active"] else "Inactive"
                st.markdown(f"**{device['name']}** ({status})")
                st.caption(f"Platform: {device['platform']} | Model: {device['model']}")

            with col2:
                st.markdown(f"**App Version**")
                st.caption(device["app_version"])

            with col3:
                st.markdown(f"**Last Used**")
                st.caption(device["last_used"])

            with col4:
                if st.button("Remove", key=f"remove_{device['id']}"):
                    st.warning(f"Device {device['name']} removed")

            st.markdown("---")

    st.info("To register a new device, open the mobile app and enable push notifications.")

# --- Tab 3: History ---
with tab3:
    st.subheader("Notification History")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_category = st.selectbox(
            "Category",
            ["All"] + [cat["name"] for cat in categories],
        )
    with col2:
        filter_status = st.selectbox(
            "Status",
            ["All", "Sent", "Delivered", "Opened", "Failed"],
        )
    with col3:
        filter_period = st.selectbox(
            "Period",
            ["Last 24 hours", "Last 7 days", "Last 30 days"],
        )

    # Notification history
    history = [
        {
            "id": "notif_001",
            "title": "AAPL Price Alert",
            "body": "AAPL reached $190.00 (target: $189.50)",
            "category": "Price Alerts",
            "status": "Opened",
            "sent_at": "2025-01-15 14:30:15",
            "device": "iPhone 15 Pro",
        },
        {
            "id": "notif_002",
            "title": "Order Filled",
            "body": "BUY 100 MSFT @ $420.50",
            "category": "Trade Executions",
            "status": "Delivered",
            "sent_at": "2025-01-15 13:45:00",
            "device": "iPhone 15 Pro",
        },
        {
            "id": "notif_003",
            "title": "Daily Portfolio Summary",
            "body": "P&L: +$1,234.50 (+0.99%)",
            "category": "Portfolio Updates",
            "status": "Delivered",
            "sent_at": "2025-01-15 16:00:00",
            "device": "Samsung Galaxy S24",
        },
        {
            "id": "notif_004",
            "title": "Stop-Loss Triggered",
            "body": "NVDA position closed at $845.00",
            "category": "Risk Alerts",
            "status": "Opened",
            "sent_at": "2025-01-14 10:15:30",
            "device": "iPhone 15 Pro",
        },
    ]

    import pandas as pd
    df = pd.DataFrame(history)
    df = df[["sent_at", "title", "category", "status", "device"]]
    df.columns = ["Sent At", "Title", "Category", "Status", "Device"]

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Detail view
    st.markdown("---")
    st.markdown("### Notification Details")
    selected = st.selectbox(
        "Select notification",
        [f"{h['title']} ({h['sent_at']})" for h in history],
    )

    if selected:
        notif = history[0]  # Would lookup by selection
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**Title:** {notif['title']}")
            st.markdown(f"**Body:** {notif['body']}")
            st.markdown(f"**Category:** {notif['category']}")

        with col2:
            st.markdown(f"**Status:** {notif['status']}")
            st.markdown(f"**Sent At:** {notif['sent_at']}")
            st.markdown(f"**Device:** {notif['device']}")

# --- Tab 4: Analytics ---
with tab4:
    st.subheader("Notification Analytics")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Sent", "1,234", "+45 today")
    col2.metric("Delivery Rate", "99.2%", "+0.1%")
    col3.metric("Open Rate", "68.5%", "-2.3%")
    col4.metric("Avg Latency", "1.2s", "-0.3s")

    st.markdown("---")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### By Category")
        import pandas as pd

        category_data = pd.DataFrame({
            "Category": ["Price Alerts", "Trades", "Portfolio", "Risk", "News"],
            "Sent": [456, 312, 234, 89, 143],
            "Opened": [345, 256, 189, 78, 67],
        })
        st.bar_chart(category_data.set_index("Category"))

    with col2:
        st.markdown("### By Platform")
        platform_data = pd.DataFrame({
            "Platform": ["iOS", "Android", "Web"],
            "Devices": [1234, 876, 234],
        })
        st.bar_chart(platform_data.set_index("Platform"))

    st.markdown("---")

    # Daily trend
    st.markdown("### Daily Notifications (Last 7 Days)")
    import pandas as pd
    import numpy as np

    dates = pd.date_range(end=datetime.now(), periods=7, freq="D")
    daily_data = pd.DataFrame({
        "Date": dates,
        "Sent": np.random.randint(150, 250, 7),
        "Delivered": np.random.randint(145, 245, 7),
        "Opened": np.random.randint(100, 180, 7),
    })
    st.line_chart(daily_data.set_index("Date"))

    # Error breakdown
    st.markdown("---")
    st.markdown("### Failed Notifications")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Failed (24h)", "8", "0.6%")
    with col2:
        st.metric("Invalid Tokens", "3", "cleaned up")

    errors = pd.DataFrame({
        "Error": ["Invalid Token", "Rate Limited", "Network Timeout", "Unknown"],
        "Count": [3, 2, 2, 1],
    })
    st.dataframe(errors, use_container_width=True, hide_index=True)
