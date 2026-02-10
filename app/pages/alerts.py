"""Alerts & Notifications Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd

try:
    st.set_page_config(page_title="Alerts", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Alerts & Notifications")

# --- Sidebar ---
st.sidebar.header("Alert Management")
alert_action = st.sidebar.selectbox(
    "Action",
    ["View Alerts", "Create Alert", "Templates", "Preferences"],
)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Active Alerts", "History", "Notifications", "Settings",
])

# --- Tab 1: Active Alerts ---
with tab1:
    st.subheader("Active Alerts")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active", "12")
    col2.metric("Triggered Today", "5")
    col3.metric("Snoozed", "2")
    col4.metric("Expired", "1")

    st.markdown("#### Your Alerts")
    alerts_data = pd.DataFrame([
        {"Name": "AAPL > $200", "Type": "Price", "Symbol": "AAPL",
         "Condition": "price > 200.0", "Priority": "Medium",
         "Status": "Active", "Triggers": "3"},
        {"Name": "RSI Overbought", "Type": "Technical", "Symbol": "MSFT",
         "Condition": "rsi_14 > 70", "Priority": "Medium",
         "Status": "Active", "Triggers": "1"},
        {"Name": "VaR Breach", "Type": "Risk", "Symbol": "Portfolio",
         "Condition": "var_95 > 2%", "Priority": "Critical",
         "Status": "Active", "Triggers": "0"},
        {"Name": "Unusual Volume", "Type": "Volume", "Symbol": "TSLA",
         "Condition": "vol_ratio > 2x", "Priority": "Medium",
         "Status": "Snoozed", "Triggers": "8"},
        {"Name": "Drawdown Warning", "Type": "Portfolio", "Symbol": "Portfolio",
         "Condition": "drawdown < -5%", "Priority": "High",
         "Status": "Active", "Triggers": "1"},
    ])
    st.dataframe(alerts_data, use_container_width=True, hide_index=True)

# --- Tab 2: Alert History ---
with tab2:
    st.subheader("Alert History")

    history_data = pd.DataFrame([
        {"Time": "2026-01-30 14:32", "Alert": "AAPL > $200",
         "Symbol": "AAPL", "Value": "205.30", "Priority": "Medium",
         "Channels": "In-App, Email"},
        {"Time": "2026-01-30 13:15", "Alert": "RSI Overbought",
         "Symbol": "MSFT", "Value": "72.4", "Priority": "Medium",
         "Channels": "In-App"},
        {"Time": "2026-01-30 10:45", "Alert": "Unusual Volume",
         "Symbol": "TSLA", "Value": "3.2x", "Priority": "Medium",
         "Channels": "In-App, Slack"},
        {"Time": "2026-01-29 16:00", "Alert": "Drawdown Warning",
         "Symbol": "Portfolio", "Value": "-5.2%", "Priority": "High",
         "Channels": "In-App, Email, SMS"},
        {"Time": "2026-01-29 11:20", "Alert": "AAPL > $200",
         "Symbol": "AAPL", "Value": "201.15", "Priority": "Medium",
         "Channels": "In-App"},
    ])
    st.dataframe(history_data, use_container_width=True, hide_index=True)

# --- Tab 3: Notifications ---
with tab3:
    st.subheader("Recent Notifications")

    col1, col2, col3 = st.columns(3)
    col1.metric("Unread", "3")
    col2.metric("Delivered Today", "8")
    col3.metric("Failed", "0")

    st.markdown("#### Notification Feed")
    notif_data = pd.DataFrame([
        {"Time": "14:32", "Message": "AAPL price crossed above $200 (now $205.30)",
         "Channel": "In-App", "Status": "Delivered", "Read": "No"},
        {"Time": "14:32", "Message": "AAPL price crossed above $200 (now $205.30)",
         "Channel": "Email", "Status": "Delivered", "Read": "—"},
        {"Time": "13:15", "Message": "MSFT RSI(14) = 72.4 (overbought)",
         "Channel": "In-App", "Status": "Delivered", "Read": "No"},
        {"Time": "10:45", "Message": "TSLA volume 3.2x above 20-day average",
         "Channel": "Slack", "Status": "Delivered", "Read": "—"},
        {"Time": "10:45", "Message": "TSLA volume 3.2x above 20-day average",
         "Channel": "In-App", "Status": "Delivered", "Read": "Yes"},
    ])
    st.dataframe(notif_data, use_container_width=True, hide_index=True)

    st.markdown("#### Delivery Stats")
    delivery_stats = pd.DataFrame([
        {"Channel": "In-App", "Sent": "45", "Delivered": "45", "Failed": "0", "Rate": "100%"},
        {"Channel": "Email", "Sent": "12", "Delivered": "12", "Failed": "0", "Rate": "100%"},
        {"Channel": "SMS", "Sent": "3", "Delivered": "3", "Failed": "0", "Rate": "100%"},
        {"Channel": "Webhook", "Sent": "8", "Delivered": "7", "Failed": "1", "Rate": "87.5%"},
        {"Channel": "Slack", "Sent": "15", "Delivered": "15", "Failed": "0", "Rate": "100%"},
    ])
    st.dataframe(delivery_stats, use_container_width=True, hide_index=True)

# --- Tab 4: Settings ---
with tab4:
    st.subheader("Notification Preferences")

    st.markdown("#### Delivery Channels")
    channels_data = pd.DataFrame([
        {"Channel": "In-App", "Enabled": "Yes", "Recipient": "—", "Status": "Active"},
        {"Channel": "Email", "Enabled": "Yes", "Recipient": "trader@example.com", "Status": "Verified"},
        {"Channel": "SMS", "Enabled": "No", "Recipient": "—", "Status": "Not configured"},
        {"Channel": "Webhook", "Enabled": "No", "Recipient": "—", "Status": "Not configured"},
        {"Channel": "Slack", "Enabled": "Yes", "Recipient": "hooks.slack.com/...", "Status": "Active"},
    ])
    st.dataframe(channels_data, use_container_width=True, hide_index=True)

    st.markdown("#### Quiet Hours")
    quiet_data = pd.DataFrame([
        {"Setting": "Enabled", "Value": "Yes"},
        {"Setting": "Start", "Value": "10:00 PM ET"},
        {"Setting": "End", "Value": "7:00 AM ET"},
        {"Setting": "Critical Override", "Value": "Yes"},
    ])
    st.dataframe(quiet_data, use_container_width=True, hide_index=True)

    st.markdown("#### Alert Templates")
    from src.alerts.config import ALERT_TEMPLATES
    templates_data = pd.DataFrame([
        {"Template": v["name"], "Type": v["alert_type"].value,
         "Description": v["description"],
         "Priority": v.get("priority", "medium").value
            if hasattr(v.get("priority", ""), "value") else "medium"}
        for v in ALERT_TEMPLATES.values()
    ])
    st.dataframe(templates_data, use_container_width=True, hide_index=True)
