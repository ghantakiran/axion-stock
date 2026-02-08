"""API Management Dashboard."""

import streamlit as st
import pandas as pd

try:
    st.set_page_config(page_title="API Dashboard", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("API & Developer Tools")

# --- Sidebar ---
st.sidebar.header("API Settings")
tier = st.sidebar.selectbox("Subscription Tier", ["Free", "Pro", "Enterprise"])
st.sidebar.markdown("---")
st.sidebar.markdown("**API Docs:** `/docs`")
st.sidebar.markdown("**OpenAPI Spec:** `/openapi.json`")

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "API Keys", "Webhooks", "Rate Limits", "SDK",
])

# --- Tab 1: API Keys ---
with tab1:
    st.subheader("API Key Management")

    col1, col2 = st.columns([2, 1])
    with col1:
        key_name = st.text_input("Key Name", placeholder="e.g. Production Bot")
    with col2:
        scopes = st.multiselect("Scopes", ["read", "write", "admin"], default=["read"])

    if st.button("Create API Key", type="primary"):
        try:
            from src.api.auth import APIKeyManager
            from src.api.config import APITier

            tier_map = {"Free": APITier.FREE, "Pro": APITier.PRO, "Enterprise": APITier.ENTERPRISE}
            manager = APIKeyManager()
            result = manager.create_key(
                user_id="demo_user",
                name=key_name or "Unnamed Key",
                scopes=scopes,
                tier=tier_map[tier],
            )

            st.success("API key created successfully!")
            st.code(result["key"], language=None)
            st.warning("Copy this key now. It won't be shown again.")

            st.markdown(f"**Key ID:** `{result['key_id']}`")
            st.markdown(f"**Scopes:** {', '.join(result['scopes'])}")

        except Exception as e:
            st.error(f"Failed to create key: {e}")

    st.markdown("#### Active Keys (Demo)")
    keys_data = pd.DataFrame([
        {"Name": "Production Bot", "Preview": "ax_...8f2a", "Scopes": "read, write",
         "Created": "2026-01-15", "Last Used": "2026-01-30"},
        {"Name": "Research Script", "Preview": "ax_...c4b1", "Scopes": "read",
         "Created": "2026-01-20", "Last Used": "2026-01-29"},
    ])
    st.dataframe(keys_data, use_container_width=True, hide_index=True)

# --- Tab 2: Webhooks ---
with tab2:
    st.subheader("Webhook Management")

    col1, col2 = st.columns(2)
    with col1:
        wh_url = st.text_input("Webhook URL", placeholder="https://yourapp.com/webhook")
    with col2:
        events = st.multiselect(
            "Events",
            ["order.filled", "alert.risk", "signal.new", "rebalance.due",
             "factor.change", "drawdown.warning"],
            default=["order.filled"],
        )

    if st.button("Register Webhook"):
        if wh_url:
            try:
                from src.api.webhooks import WebhookManager
                manager = WebhookManager()
                wh, err = manager.register(
                    user_id="demo_user",
                    url=wh_url,
                    events=events,
                )
                if wh:
                    st.success(f"Webhook registered: {wh.webhook_id}")
                    st.markdown(f"**Secret:** `{wh.secret}`")
                else:
                    st.error(err)
            except Exception as e:
                st.error(f"Failed: {e}")
        else:
            st.warning("Enter a webhook URL.")

    st.markdown("#### Registered Webhooks (Demo)")
    wh_data = pd.DataFrame([
        {"URL": "https://myapp.com/webhook", "Events": "order.filled, alert.risk",
         "Status": "Active", "Success Rate": "99.8%", "Last Delivery": "2 min ago"},
        {"URL": "https://slack.com/api/hook", "Events": "signal.new",
         "Status": "Active", "Success Rate": "100%", "Last Delivery": "1 hour ago"},
    ])
    st.dataframe(wh_data, use_container_width=True, hide_index=True)

# --- Tab 3: Rate Limits ---
with tab3:
    st.subheader("Rate Limit Status")

    from src.api.config import RATE_LIMITS, APITier
    tier_map = {"Free": APITier.FREE, "Pro": APITier.PRO, "Enterprise": APITier.ENTERPRISE}
    limits = RATE_LIMITS[tier_map[tier]]

    col1, col2, col3 = st.columns(3)
    col1.metric("Per Minute Limit", str(limits["per_minute"]))
    daily = limits["daily_limit"] if limits["daily_limit"] > 0 else "Unlimited"
    col2.metric("Daily Limit", str(daily))
    col3.metric("Burst Limit", str(limits["burst"]))

    st.markdown("#### Usage (Demo)")
    col4, col5, col6, col7 = st.columns(4)
    col4.metric("Requests Today", "247", delta="12 this hour")
    col5.metric("Avg Response", "42ms")
    col6.metric("Error Rate", "0.4%")
    col7.metric("Rate Limited", "0")

    st.markdown("#### Rate Limits by Tier")
    tier_table = pd.DataFrame([
        {"Tier": "Free", "Daily": "100", "Per Minute": "10", "Burst": "10"},
        {"Tier": "Pro", "Daily": "1,000", "Per Minute": "60", "Burst": "60"},
        {"Tier": "Enterprise", "Daily": "Unlimited", "Per Minute": "600", "Burst": "600"},
    ])
    st.dataframe(tier_table, use_container_width=True, hide_index=True)

# --- Tab 4: SDK ---
with tab4:
    st.subheader("Python SDK")

    st.markdown("#### Installation")
    st.code("pip install axion-sdk", language="bash")

    st.markdown("#### Quick Start")
    st.code('''import axion

# Initialize client
client = axion.Client(api_key="ax_...")

# Get factor scores
scores = client.factors.get("AAPL")
print(f"AAPL composite: {scores.composite}")

# Screen stocks
top = client.factors.screen(factor="momentum", top=20)

# Submit order
order = client.orders.create(
    symbol="AAPL", qty=10, side="buy",
    order_type="limit", limit_price=175.0,
)

# Run backtest
result = client.backtest.run(
    strategy="balanced_factor",
    start="2020-01-01",
    end="2025-12-31",
)
print(f"Sharpe: {result.sharpe_ratio}")
''', language="python")

    st.markdown("#### Available Endpoints")
    endpoints = pd.DataFrame([
        {"Category": "Market Data", "Endpoints": "GET /quotes, /ohlcv, /fundamentals, /universe"},
        {"Category": "Factors", "Endpoints": "GET /factors, /factors/history, /screen, /regime"},
        {"Category": "Portfolio", "Endpoints": "GET /portfolio, /risk | POST /optimize, /rebalance"},
        {"Category": "Trading", "Endpoints": "POST /orders | GET /orders | DELETE /orders/{id}"},
        {"Category": "AI", "Endpoints": "POST /chat | GET /predictions, /sentiment, /picks"},
        {"Category": "Options", "Endpoints": "GET /chain, /greeks, /iv-surface | POST /analyze"},
        {"Category": "Backtesting", "Endpoints": "POST /backtest | GET /backtest/{id}, /tearsheet"},
    ])
    st.dataframe(endpoints, use_container_width=True, hide_index=True)
