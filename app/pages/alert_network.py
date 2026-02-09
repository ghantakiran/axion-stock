"""Alert & Notification Network Dashboard (PRD-142).

4 tabs: Alert Rules, Notification Channels, Delivery History, Preferences.
"""

try:
    import streamlit as st
    st.set_page_config(page_title="Alert Network", layout="wide")
except Exception:
    import streamlit as st

import asyncio

import pandas as pd

st.title("Alert & Notification Network")
st.caption("Configure alert rules and multi-channel notification delivery")

tab1, tab2, tab3, tab4 = st.tabs([
    "Alert Rules",
    "Notification Channels",
    "Delivery History",
    "Preferences",
])


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Tab 1: Alert Rules ────────────────────────────────────────────────

with tab1:
    st.subheader("Manage Alert Rules")

    from src.alert_network import TriggerType, ChannelKind

    with st.form("new_rule"):
        col1, col2 = st.columns(2)
        with col1:
            rule_name = st.text_input("Rule Name", value="Price Alert")
            trigger = st.selectbox("Trigger Type", [t.value for t in TriggerType])
        with col2:
            symbol = st.text_input("Symbol (optional)", value="AAPL")
            threshold = st.number_input("Threshold", value=200.0, step=1.0)

        channels = st.multiselect(
            "Notification Channels",
            [c.value for c in ChannelKind],
            default=["email", "push"],
        )
        cooldown = st.slider("Cooldown (minutes)", 1, 120, 30)

        submitted = st.form_submit_button("Add Rule", type="primary")
        if submitted:
            from src.alert_network import AlertRule, NotificationManager

            if "alert_mgr" not in st.session_state:
                st.session_state["alert_mgr"] = NotificationManager()

            mgr = st.session_state["alert_mgr"]
            mgr.add_rule(AlertRule(
                name=rule_name,
                trigger_type=TriggerType(trigger),
                symbol=symbol if symbol else None,
                threshold=threshold,
                channels=[ChannelKind(c) for c in channels],
                cooldown_minutes=cooldown,
            ))
            st.success(f"Rule '{rule_name}' added!")

    # Show existing rules
    mgr = st.session_state.get("alert_mgr")
    if mgr:
        rules = mgr.get_rules()
        if rules:
            rows = [r.to_dict() for r in rules]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # Test evaluation
    st.divider()
    st.subheader("Test Rule Evaluation")
    test_price = st.number_input("Test Price for Symbol", value=210.0, step=1.0)
    if st.button("Evaluate Rules"):
        if mgr:
            from src.alert_network import NotificationManager
            result = _run_async(mgr.evaluate_and_notify({
                "prices": {"AAPL": test_price, "MSFT": 400.0, "NVDA": 900.0},
            }))
            st.metric("Alerts Triggered", result.alerts_triggered)
            st.metric("Notifications Sent", result.notifications_sent)
            for alert in result.triggered_alerts:
                st.info(f"**{alert.symbol}**: {alert.message}")
        else:
            st.warning("Add rules first.")


# ── Tab 2: Notification Channels ──────────────────────────────────────

with tab2:
    st.subheader("Available Channels")

    from src.alert_network import ChannelRegistry
    registry = ChannelRegistry()

    rows = []
    for kind in registry.available_channels:
        ch = registry.get(kind)
        rows.append({
            "Channel": kind.value,
            "Configured": ch.is_configured() if ch else False,
            "Status": "Demo Mode" if not (ch and ch.is_configured()) else "Live",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.divider()
    st.markdown("### Configure Channels")

    with st.expander("Email (SMTP)"):
        st.text_input("SMTP Host", key="email_host")
        st.text_input("From Address", key="email_from")
        st.text_input("Password", type="password", key="email_pass")

    with st.expander("Slack"):
        st.text_input("Webhook URL", key="slack_url")

    with st.expander("Discord"):
        st.text_input("Webhook URL", key="discord_url")

    with st.expander("Telegram"):
        st.text_input("Bot Token", type="password", key="tg_token")
        st.text_input("Chat ID", key="tg_chat")

    with st.expander("SMS (Twilio)"):
        st.text_input("Account SID", type="password", key="twilio_sid")
        st.text_input("From Number", key="twilio_from")


# ── Tab 3: Delivery History ───────────────────────────────────────────

with tab3:
    st.subheader("Delivery Log")

    mgr = st.session_state.get("alert_mgr")
    if mgr:
        stats = mgr.get_delivery_stats()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Deliveries", stats["total_deliveries"])
        c2.metric("Sent", stats["sent"])
        c3.metric("Failed", stats["failed"])
        c4.metric("Success Rate", f"{stats['success_rate']:.0%}")

        history = mgr.get_delivery_history(limit=50)
        if history:
            rows = [r.to_dict() for r in history]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.info("No delivery history yet.")
    else:
        st.info("No notification manager initialized.")


# ── Tab 4: Preferences ───────────────────────────────────────────────

with tab4:
    st.subheader("Notification Preferences")

    st.markdown("### Quiet Hours")
    quiet_enabled = st.checkbox("Enable Quiet Hours", key="quiet_on")
    col1, col2 = st.columns(2)
    with col1:
        quiet_start = st.slider("Start Hour (UTC)", 0, 23, 22, key="quiet_s")
    with col2:
        quiet_end = st.slider("End Hour (UTC)", 0, 23, 7, key="quiet_e")

    st.markdown("### Throttling")
    max_hour = st.number_input("Max Per Hour", 1, 100, 20, key="max_h")
    max_day = st.number_input("Max Per Day", 1, 1000, 100, key="max_d")

    st.markdown("### Batch Digest")
    batch = st.checkbox("Enable Batch Digest", key="batch_on")
    batch_interval = st.slider("Digest Interval (minutes)", 15, 240, 60, key="batch_int")

    st.markdown("### Channel Priority")
    for ck in ["in_app", "push", "email", "slack", "discord", "telegram", "sms"]:
        st.checkbox(f"Enable {ck.replace('_', ' ').title()}", value=ck in ("in_app", "push", "email"), key=f"ch_{ck}")

    if st.button("Save Preferences", type="primary"):
        st.success("Preferences saved!")
