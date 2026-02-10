"""AI Trading Copilot Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
from datetime import datetime, timezone

try:
    st.set_page_config(page_title="AI Trading Copilot", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("AI Trading Copilot")

# --- Sidebar ---
st.sidebar.header("Copilot Settings")

risk_tolerance = st.sidebar.selectbox(
    "Risk Tolerance",
    ["Conservative", "Moderate", "Aggressive"],
    index=1,
)

investment_style = st.sidebar.selectbox(
    "Investment Style",
    ["Value", "Growth", "Momentum", "Income", "Balanced"],
    index=4,
)

response_style = st.sidebar.selectbox(
    "Response Detail",
    ["Concise", "Balanced", "Detailed"],
    index=1,
)

st.sidebar.markdown("---")
st.sidebar.subheader("Quick Actions")
if st.sidebar.button("Generate Trade Idea", use_container_width=True):
    st.session_state["quick_action"] = "trade_idea"
if st.sidebar.button("Market Outlook", use_container_width=True):
    st.session_state["quick_action"] = "market_outlook"
if st.sidebar.button("Portfolio Review", use_container_width=True):
    st.session_state["quick_action"] = "portfolio_review"

# --- Initialize Session State ---
if "copilot_messages" not in st.session_state:
    st.session_state["copilot_messages"] = [
        {
            "role": "assistant",
            "content": """Welcome to the AI Trading Copilot! I'm here to help with your investment decisions.

You can ask me about:
- **Stock Research**: "What do you think about AAPL?"
- **Trade Ideas**: "Give me a trade idea in healthcare"
- **Portfolio Analysis**: "Review my portfolio risks"
- **Market Outlook**: "What's your view on the market?"

How can I help you today?""",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ]

if "saved_ideas" not in st.session_state:
    st.session_state["saved_ideas"] = []

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Chat", "Trade Ideas", "Portfolio Insights", "Settings"
])

# --- Tab 1: Chat Interface ---
with tab1:
    # Chat container
    chat_container = st.container()

    with chat_container:
        for msg in st.session_state["copilot_messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Quick action handler
    if st.session_state.get("quick_action"):
        action = st.session_state.pop("quick_action")
        if action == "trade_idea":
            user_input = "Generate a trade idea for me based on my preferences"
        elif action == "market_outlook":
            user_input = "What's the current market outlook?"
        elif action == "portfolio_review":
            user_input = "Review my portfolio for potential risks and improvements"
        else:
            user_input = None

        if user_input:
            st.session_state["copilot_messages"].append({
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            st.rerun()

    # Chat input
    user_input = st.chat_input("Ask the copilot anything...")

    if user_input:
        # Add user message
        st.session_state["copilot_messages"].append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Generate response (mock for demo)
        response = _generate_mock_response(user_input, risk_tolerance, investment_style)

        st.session_state["copilot_messages"].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        st.rerun()

# --- Tab 2: Trade Ideas ---
with tab2:
    st.subheader("AI-Generated Trade Ideas")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Generate New Ideas", type="primary"):
            st.session_state["trade_ideas_generated"] = True

    with col2:
        sector_filter = st.selectbox(
            "Sector",
            ["All Sectors", "Technology", "Healthcare", "Financials", "Energy", "Consumer"],
        )

    with col3:
        time_horizon = st.selectbox(
            "Time Horizon",
            ["Any", "Short-term", "Medium-term", "Long-term"],
        )

    st.markdown("---")

    # Display trade ideas
    ideas = [
        {
            "symbol": "GOOGL",
            "action": "BUY",
            "confidence": 85,
            "entry": 175.00,
            "target": 200.00,
            "stop_loss": 165.00,
            "time_horizon": "Medium",
            "rationale": "Strong AI momentum, cloud growth accelerating, attractive valuation vs peers.",
            "risk_reward": "2.5:1",
        },
        {
            "symbol": "UNH",
            "action": "BUY",
            "confidence": 80,
            "entry": 520.00,
            "target": 580.00,
            "stop_loss": 495.00,
            "time_horizon": "Medium",
            "rationale": "Defensive healthcare leader, consistent earnings growth, strong moat.",
            "risk_reward": "2.4:1",
        },
        {
            "symbol": "XOM",
            "action": "HOLD",
            "confidence": 65,
            "entry": None,
            "target": 115.00,
            "stop_loss": 98.00,
            "time_horizon": "Long",
            "rationale": "Strong dividend yield, but oil price volatility creates uncertainty.",
            "risk_reward": "1.8:1",
        },
    ]

    for i, idea in enumerate(ideas):
        with st.expander(f"{idea['symbol']} - {idea['action']} (Confidence: {idea['confidence']}%)", expanded=(i == 0)):
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Entry Price", f"${idea['entry']:.2f}" if idea['entry'] else "N/A")
            with col2:
                st.metric("Target Price", f"${idea['target']:.2f}")
            with col3:
                st.metric("Stop Loss", f"${idea['stop_loss']:.2f}")
            with col4:
                st.metric("Risk/Reward", idea['risk_reward'])

            st.markdown(f"**Rationale:** {idea['rationale']}")
            st.markdown(f"**Time Horizon:** {idea['time_horizon']}")

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Save Idea", key=f"save_{i}"):
                    st.session_state["saved_ideas"].append(idea)
                    st.success("Idea saved!")
            with col2:
                if st.button("Add to Watchlist", key=f"watch_{i}"):
                    st.info(f"Added {idea['symbol']} to watchlist")
            with col3:
                if st.button("View Chart", key=f"chart_{i}"):
                    st.info(f"Opening chart for {idea['symbol']}")

# --- Tab 3: Portfolio Insights ---
with tab3:
    st.subheader("Portfolio Analysis")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### Portfolio Health Score")

        # Mock portfolio health metrics
        health_score = 78

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Overall Score", f"{health_score}/100", "+3 vs last week")
        col_b.metric("Diversification", "Good", "Well balanced")
        col_c.metric("Risk Level", "Moderate", "Within tolerance")

        st.markdown("---")

        st.markdown("### AI Recommendations")

        recommendations = [
            ("Reduce", "NVDA", "Position size (15%) exceeds recommended max (10%)"),
            ("Add", "VEA", "Portfolio lacks international exposure"),
            ("Hold", "AAPL", "Position well-sized, strong fundamentals"),
            ("Trim", "TSLA", "High volatility increasing portfolio risk"),
        ]

        for action, symbol, reason in recommendations:
            if action == "Reduce":
                st.warning(f"**{action} {symbol}**: {reason}")
            elif action == "Add":
                st.info(f"**{action} {symbol}**: {reason}")
            elif action == "Trim":
                st.warning(f"**{action} {symbol}**: {reason}")
            else:
                st.success(f"**{action} {symbol}**: {reason}")

    with col2:
        st.markdown("### Risk Breakdown")

        risk_factors = {
            "Concentration": 7,
            "Sector": 5,
            "Correlation": 4,
            "Volatility": 6,
            "Liquidity": 2,
        }

        for factor, score in risk_factors.items():
            color = "green" if score <= 3 else "orange" if score <= 6 else "red"
            st.markdown(f"**{factor}**: {'🔴' if score > 6 else '🟡' if score > 3 else '🟢'} {score}/10")

        st.markdown("---")

        st.markdown("### Sector Allocation")
        sectors = {
            "Technology": 35,
            "Healthcare": 20,
            "Financials": 18,
            "Consumer": 15,
            "Energy": 12,
        }
        for sector, weight in sectors.items():
            st.progress(weight / 100, text=f"{sector}: {weight}%")

# --- Tab 4: Settings ---
with tab4:
    st.subheader("Copilot Preferences")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Investment Profile")

        st.selectbox("Risk Tolerance", ["Conservative", "Moderate", "Aggressive"], index=1, key="pref_risk")
        st.selectbox("Investment Style", ["Value", "Growth", "Momentum", "Income", "Balanced"], index=4, key="pref_style")
        st.selectbox("Time Horizon", ["Short-term (< 1 month)", "Medium-term (1-6 months)", "Long-term (> 6 months)"], index=1, key="pref_horizon")

        st.markdown("### Analysis Preferences")
        st.checkbox("Include Technical Analysis", value=True, key="pref_technicals")
        st.checkbox("Include Fundamental Analysis", value=True, key="pref_fundamentals")
        st.checkbox("Include Sentiment Data", value=True, key="pref_sentiment")

    with col2:
        st.markdown("### Sector Preferences")

        sectors = ["Technology", "Healthcare", "Financials", "Consumer", "Energy", "Industrials", "Materials", "Utilities", "Real Estate"]

        st.multiselect("Preferred Sectors", sectors, default=["Technology", "Healthcare"], key="pref_sectors")
        st.multiselect("Excluded Sectors", sectors, default=[], key="pref_excluded")

        st.markdown("### Constraints")
        st.slider("Max Position Size (%)", 5, 25, 10, key="pref_max_position")
        st.number_input("Min Market Cap ($B)", min_value=0, value=1, key="pref_min_cap")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Preferences", type="primary"):
            st.success("Preferences saved successfully!")
    with col2:
        if st.button("Reset to Defaults"):
            st.info("Preferences reset to defaults")


def _generate_mock_response(user_input: str, risk: str, style: str) -> str:
    """Generate mock copilot response."""
    user_lower = user_input.lower()

    if any(word in user_lower for word in ['trade', 'idea', 'buy', 'sell']):
        return f"""Based on your {risk.lower()} risk tolerance and {style.lower()} investment style, here's a trade idea:

**SYMBOL: AMZN**
**ACTION: BUY**
**CONFIDENCE: 8/10**

**Entry:** $185.00
**Target:** $210.00 (+13.5%)
**Stop Loss:** $175.00 (-5.4%)

**Rationale:**
1. AWS growth reaccelerating with AI workloads
2. Retail margins improving significantly
3. Technical breakout above $180 resistance

**Risk/Reward:** 2.5:1

This aligns with your preferences for {style.lower()} opportunities with measured risk."""

    elif any(word in user_lower for word in ['market', 'outlook']):
        return """**Market Outlook - February 2026**

**Overall: Cautiously Bullish** 📈

The market continues to show strength with the S&P 500 near all-time highs.

**Key Themes:**
1. **AI Investment Cycle** - Capex spending remains robust
2. **Rate Cuts Delayed** - Fed likely on hold until Q2
3. **Earnings Growth** - Q4 season better than expected

**Sector Views:**
- 🟢 **Overweight:** Technology, Healthcare
- 🟡 **Neutral:** Financials, Consumer
- 🔴 **Underweight:** Utilities, Real Estate

**Trading Stance:**
Stay invested but be selective. Quality over quantity. Keep 10% cash for opportunities.

**Key Levels:**
- S&P 500 Support: 5,800
- S&P 500 Resistance: 6,200"""

    elif any(word in user_lower for word in ['portfolio', 'review', 'risk']):
        return """**Portfolio Review Summary**

**Overall Health: Good** (78/100)

**Strengths:**
✅ Diversified across 15 positions
✅ Quality holdings with strong fundamentals
✅ Reasonable sector balance

**Areas for Improvement:**
⚠️ Top position (NVDA) at 15% - consider trimming
⚠️ No international exposure
⚠️ Below-average dividend yield

**Recommended Actions:**
1. **Trim NVDA by 5%** - Reduce concentration risk
2. **Add VEA or IEFA** - International diversification
3. **Consider JNJ or PG** - Add defensive dividend payers

Would you like me to elaborate on any of these recommendations?"""

    elif any(word in user_lower for word in ['aapl', 'apple']):
        return """**AAPL Analysis**

**Apple Inc. (AAPL)** - $185.50

**Quick Take: HOLD** 🟡

**Fundamentals:**
- P/E: 28.5x (vs 5Y avg 26x)
- Revenue Growth: +5% YoY
- Gross Margin: 45.9%
- FCF Yield: 3.2%

**Technical Setup:**
- Trend: Neutral (range-bound)
- Support: $175 / $165
- Resistance: $195 / $200
- RSI: 52 (neutral)

**Bull Case:** iPhone 16 cycle, services growth, AI features
**Bear Case:** China weakness, premium valuation, market saturation

**Recommendation:**
Hold existing positions. Not adding at current levels - wait for pullback to $175 or breakout above $195."""

    else:
        return f"""I'd be happy to help with that! Based on your question, here are some thoughts:

Your {risk.lower()} risk profile and {style.lower()} investment approach suggest focusing on quality companies with strong fundamentals and reasonable valuations.

**I can help you with:**
- 📊 Stock research and analysis
- 💡 Trade ideas tailored to your preferences
- 📈 Market outlook and sector views
- 🛡️ Portfolio risk assessment

What specific area would you like to explore? You can ask me about:
- A specific stock (e.g., "What about MSFT?")
- Generate trade ideas
- Review market conditions
- Analyze your portfolio"""
