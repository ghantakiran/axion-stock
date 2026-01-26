"""Streamlit MVP - AI Stock Research Assistant (Axion)."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from app.chat import get_chat_response, get_api_key
from app.charts import create_stock_chart, create_comparison_chart, create_factor_chart
from app.tools import _get_cached_scores
from app.ai_picks import get_ai_picks, PICK_CATEGORIES

# Page config
st.set_page_config(
    page_title="Axion - AI Stock Research",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Full custom CSS - dark theme with purple accents for Axion
st.markdown("""
<style>
    /* Global */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Main container */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 0;
        max-width: 900px;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0a1e 0%, #1a1035 100%);
        border-right: 1px solid rgba(124, 58, 237, 0.2);
    }

    [data-testid="stSidebar"] .stMarkdown p {
        color: #a0aec0;
        font-size: 13px;
    }

    /* Chat messages */
    [data-testid="stChatMessage"] {
        background: transparent;
        border: none;
        padding: 12px 0;
    }

    /* User messages */
    [data-testid="stChatMessage"][data-testid-type="user"] {
        background: rgba(124, 58, 237, 0.08);
        border-radius: 16px;
        border: 1px solid rgba(124, 58, 237, 0.15);
        padding: 12px 16px;
        margin: 8px 0;
    }

    /* Assistant messages */
    [data-testid="stChatMessage"][data-testid-type="assistant"] {
        background: rgba(30, 30, 50, 0.5);
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.06);
        padding: 12px 16px;
        margin: 8px 0;
    }

    /* Chat input */
    [data-testid="stChatInput"] {
        border-top: 1px solid rgba(124, 58, 237, 0.2);
        padding-top: 16px;
    }

    [data-testid="stChatInput"] textarea {
        background: #1a1a2e !important;
        border: 1px solid rgba(124, 58, 237, 0.3) !important;
        border-radius: 12px !important;
        color: #e2e8f0 !important;
        font-size: 15px !important;
        padding: 14px 16px !important;
    }

    [data-testid="stChatInput"] textarea:focus {
        border-color: #7c3aed !important;
        box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.15) !important;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #1a1035 0%, #2d1b69 100%);
        border: 1px solid rgba(124, 58, 237, 0.3);
        border-radius: 10px;
        color: #c4b5fd;
        font-weight: 500;
        font-size: 13px;
        padding: 8px 16px;
        transition: all 0.2s ease;
        text-align: left;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #2d1b69 0%, #4c1d95 100%);
        border-color: #7c3aed;
        color: #e9d5ff;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(124, 58, 237, 0.2);
    }

    /* Text input (API key) */
    [data-testid="stTextInput"] input {
        background: #1a1a2e !important;
        border: 1px solid rgba(124, 58, 237, 0.2) !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
    }

    /* Dividers */
    hr {
        border-color: rgba(124, 58, 237, 0.15) !important;
        margin: 16px 0 !important;
    }

    /* Headers */
    h1 {
        background: linear-gradient(135deg, #a78bfa 0%, #7c3aed 50%, #6d28d9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 700;
        letter-spacing: -0.5px;
    }

    h2, h3 {
        color: #c4b5fd !important;
        font-weight: 600;
    }

    /* Spinner */
    .stSpinner > div {
        border-top-color: #7c3aed !important;
    }

    /* Welcome cards */
    .welcome-card {
        background: linear-gradient(135deg, rgba(124, 58, 237, 0.08) 0%, rgba(30, 30, 50, 0.5) 100%);
        border: 1px solid rgba(124, 58, 237, 0.15);
        border-radius: 16px;
        padding: 24px;
        margin: 12px 0;
        transition: all 0.2s ease;
    }

    .welcome-card:hover {
        border-color: rgba(124, 58, 237, 0.4);
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(124, 58, 237, 0.1);
    }

    .welcome-card h4 {
        color: #e9d5ff;
        margin: 0 0 8px 0;
        font-size: 16px;
        font-weight: 600;
    }

    .welcome-card p {
        color: #94a3b8;
        margin: 0;
        font-size: 13px;
        line-height: 1.5;
    }

    /* Logo area */
    .logo-area {
        text-align: center;
        padding: 20px 0 10px 0;
    }

    .logo-area h1 {
        font-size: 28px;
        margin: 0;
    }

    .logo-area .subtitle {
        color: #64748b;
        font-size: 12px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin-top: 4px;
    }

    /* Sidebar section headers */
    .sidebar-section {
        color: #7c3aed;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        margin: 16px 0 8px 0;
        padding-left: 2px;
    }

    /* Factor badge styling */
    .factor-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
        margin: 2px;
    }
    .pill-value { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
    .pill-momentum { background: rgba(168, 85, 247, 0.15); color: #c084fc; }
    .pill-quality { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
    .pill-growth { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }

    /* Metric cards in welcome */
    .metric-row {
        display: flex;
        gap: 12px;
        margin: 16px 0;
    }
    .metric-card {
        flex: 1;
        background: rgba(124, 58, 237, 0.06);
        border: 1px solid rgba(124, 58, 237, 0.12);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    .metric-card .value {
        font-size: 24px;
        font-weight: 700;
        color: #a78bfa;
    }
    .metric-card .label {
        font-size: 11px;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }

    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
    }
    ::-webkit-scrollbar-track {
        background: #0f0f1a;
    }
    ::-webkit-scrollbar-thumb {
        background: #2d1b69;
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #7c3aed;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "api_messages" not in st.session_state:
        st.session_state.api_messages = []
    if "show_ai_picks" not in st.session_state:
        st.session_state.show_ai_picks = False
    if "ai_picks_category" not in st.session_state:
        st.session_state.ai_picks_category = "balanced_picks"


def render_sidebar():
    with st.sidebar:
        # Logo
        st.markdown("""
        <div class="logo-area">
            <h1>Axion</h1>
            <div class="subtitle">AI Stock Research</div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        api_key = st.text_input(
            "API Key",
            type="password",
            placeholder="sk-ant-...",
            help="Anthropic API key from console.anthropic.com",
            key="api_key",
            label_visibility="collapsed",
        )
        if not api_key:
            st.caption("Enter Anthropic API key above")

        st.divider()

        # Research section
        st.markdown('<div class="sidebar-section">Research</div>', unsafe_allow_html=True)

        if st.button("Market Overview", use_container_width=True, key="btn_market"):
            add_user_message("Give me a market overview with the top-scored stocks and current index levels")

        if st.button("Top Momentum", use_container_width=True, key="btn_mom"):
            add_user_message("Screen for the top 10 momentum stocks in the S&P 500")

        if st.button("Top Value", use_container_width=True, key="btn_val"):
            add_user_message("Screen for the top 10 value stocks in the S&P 500")

        if st.button("Top Quality", use_container_width=True, key="btn_qual"):
            add_user_message("Screen for the top 10 quality stocks in the S&P 500")

        if st.button("Top Growth", use_container_width=True, key="btn_grow"):
            add_user_message("Screen for the top 10 growth stocks in the S&P 500")

        st.divider()

        # AI Picks section
        st.markdown('<div class="sidebar-section">AI Stock Picks</div>', unsafe_allow_html=True)

        if st.button("🎯 Today's AI Picks", use_container_width=True, key="btn_ai_picks"):
            st.session_state.show_ai_picks = True
            st.session_state.ai_picks_category = "balanced_picks"
            st.rerun()

        col_ai1, col_ai2 = st.columns(2)
        with col_ai1:
            if st.button("Growth", use_container_width=True, key="btn_ai_growth"):
                st.session_state.show_ai_picks = True
                st.session_state.ai_picks_category = "growth_champions"
                st.rerun()
        with col_ai2:
            if st.button("Value", use_container_width=True, key="btn_ai_value"):
                st.session_state.show_ai_picks = True
                st.session_state.ai_picks_category = "value_gems"
                st.rerun()

        col_ai3, col_ai4 = st.columns(2)
        with col_ai3:
            if st.button("Quality", use_container_width=True, key="btn_ai_quality"):
                st.session_state.show_ai_picks = True
                st.session_state.ai_picks_category = "quality_compounders"
                st.rerun()
        with col_ai4:
            if st.button("Momentum", use_container_width=True, key="btn_ai_momentum"):
                st.session_state.show_ai_picks = True
                st.session_state.ai_picks_category = "momentum_leaders"
                st.rerun()

        st.divider()

        # Portfolio section
        st.markdown('<div class="sidebar-section">Portfolios</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("$10K", use_container_width=True, key="btn_10k"):
                add_user_message("Recommend a portfolio for $10,000 with 9 stocks")
        with col2:
            if st.button("$25K", use_container_width=True, key="btn_25k"):
                add_user_message("Recommend a portfolio for $25,000 with 9 stocks")

        col3, col4 = st.columns(2)
        with col3:
            if st.button("$50K", use_container_width=True, key="btn_50k"):
                add_user_message("Recommend a portfolio for $50,000 with 9 stocks")
        with col4:
            if st.button("$100K", use_container_width=True, key="btn_100k"):
                add_user_message("Recommend a portfolio for $100,000 with 9 stocks")

        st.divider()

        # Options section
        st.markdown('<div class="sidebar-section">Options</div>', unsafe_allow_html=True)

        if st.button("AAPL Options Chain", use_container_width=True, key="btn_opt_aapl"):
            add_user_message("Analyze the options chain for AAPL and recommend a strategy")

        if st.button("NVDA Options Strategy", use_container_width=True, key="btn_opt_nvda"):
            add_user_message("What options strategy do you recommend for NVDA?")

        if st.button("Top Picks + Options", use_container_width=True, key="btn_opt_picks"):
            add_user_message("Give me your top 5 stock picks and recommend options strategies for the top 2")

        col_o1, col_o2 = st.columns(2)
        with col_o1:
            if st.button("Bullish Plays", use_container_width=True, key="btn_opt_bull"):
                add_user_message("Recommend bullish options strategies for top momentum stocks")
        with col_o2:
            if st.button("Iron Condors", use_container_width=True, key="btn_opt_ic"):
                add_user_message("Find good iron condor candidates from the S&P 500 with high IV and neutral scores")

        st.divider()

        # Clear
        if st.button("Clear conversation", use_container_width=True, key="btn_clear"):
            st.session_state.messages = []
            st.session_state.api_messages = []
            st.rerun()

        # Footer
        st.markdown("""
        <div style="position: fixed; bottom: 16px; left: 16px; right: 16px; max-width: 250px;">
            <p style="color: #475569; font-size: 11px; text-align: center; margin: 0;">
                Multi-factor model scoring 500+ stocks<br/>
                Value + Momentum + Quality + Growth
            </p>
        </div>
        """, unsafe_allow_html=True)

        return api_key


def add_user_message(text: str):
    """Add a user message and trigger rerun."""
    st.session_state.messages.append({"role": "user", "content": text})
    st.session_state.api_messages.append({"role": "user", "content": text})
    st.session_state.pending_response = True
    st.rerun()


def render_welcome():
    """Show welcome screen when no messages."""
    st.markdown("""
    <div style="text-align: center; padding: 40px 0 20px 0;">
        <h1 style="font-size: 42px; margin-bottom: 8px;">Axion</h1>
        <p style="color: #64748b; font-size: 16px; margin: 0;">
            Your AI research assistant for the stock market
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Metrics row
    st.markdown("""
    <div class="metric-row">
        <div class="metric-card">
            <div class="value">500+</div>
            <div class="label">Stocks Scored</div>
        </div>
        <div class="metric-card">
            <div class="value">4</div>
            <div class="label">Factor Model</div>
        </div>
        <div class="metric-card">
            <div class="value">Options</div>
            <div class="label">Chains & Strategy</div>
        </div>
        <div class="metric-card">
            <div class="value">Live</div>
            <div class="label">Market Data</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Featured: AI Picks card
    st.markdown("""
    <div style="background: linear-gradient(135deg, #7c3aed 0%, #4c1d95 100%); border-radius: 16px; padding: 24px; margin-bottom: 24px; text-align: center;">
        <div style="font-size: 32px; margin-bottom: 8px;">🎯</div>
        <h3 style="color: white; margin: 0 0 8px 0; font-size: 22px;">AI Stock Picks</h3>
        <p style="color: rgba(255,255,255,0.8); margin: 0 0 16px 0; font-size: 14px;">
            Claude analyzes 500+ stocks and selects the best opportunities with detailed investment thesis
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_picks = st.columns(5)
    pick_categories = [
        ("🏆", "Balanced", "balanced_picks"),
        ("🚀", "Growth", "growth_champions"),
        ("💎", "Value", "value_gems"),
        ("⭐", "Quality", "quality_compounders"),
        ("📈", "Momentum", "momentum_leaders"),
    ]
    for i, (emoji, label, cat) in enumerate(pick_categories):
        with col_picks[i]:
            if st.button(f"{emoji} {label}", use_container_width=True, key=f"w_pick_{cat}"):
                st.session_state.show_ai_picks = True
                st.session_state.ai_picks_category = cat
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Suggestion cards
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="welcome-card">
            <h4>Analyze a Stock</h4>
            <p>Get factor scores, fundamentals, and ranking vs the S&P 500 for any ticker</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Analyze NVDA", use_container_width=True, key="w_nvda"):
            add_user_message("Analyze NVDA with full factor breakdown")

        st.markdown("""
        <div class="welcome-card">
            <h4>Build a Portfolio</h4>
            <p>Get a score-weighted portfolio with exact share counts for your investment amount</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Build $25K Portfolio", use_container_width=True, key="w_port"):
            add_user_message("Recommend a portfolio for $25,000")

    with col2:
        st.markdown("""
        <div class="welcome-card">
            <h4>Options Strategy</h4>
            <p>Get options recommendations with strikes, expiry, and risk/reward based on factor scores</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("AAPL Options Strategy", use_container_width=True, key="w_options"):
            add_user_message("Analyze AAPL options and recommend a strategy based on its factor scores")

        st.markdown("""
        <div class="welcome-card">
            <h4>Top Picks</h4>
            <p>Curated stock picks with buy thesis, risk analysis, and entry strategies</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Top 5 Stock Picks", use_container_width=True, key="w_picks"):
            add_user_message("Give me your top 5 stock picks with detailed reasoning")

    # Factor explanation
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div style="text-align: center; padding: 12px 0;">
        <span class="factor-pill pill-value">Value 25%</span>
        <span class="factor-pill pill-momentum">Momentum 30%</span>
        <span class="factor-pill pill-quality">Quality 25%</span>
        <span class="factor-pill pill-growth">Growth 20%</span>
    </div>
    <p style="text-align: center; color: #475569; font-size: 12px; margin-top: 8px;">
        Percentile-ranked factor scores across the S&P 500 universe
    </p>
    """, unsafe_allow_html=True)


def render_charts(tool_calls: list):
    """Render stock charts based on which tools were called."""
    rendered_tickers = set()

    for call in tool_calls:
        name = call["name"]
        inp = call["input"]

        if name == "analyze_stock":
            ticker = inp["ticker"].upper()
            if ticker in rendered_tickers:
                continue
            rendered_tickers.add(ticker)

            # Price chart
            fig = create_stock_chart(ticker, period="6mo", chart_type="candlestick")
            st.plotly_chart(fig, use_container_width=True, key=f"chart_{ticker}_{id(call)}")

            # Factor score chart
            try:
                scores, _, _ = _get_cached_scores()
                if ticker in scores.index:
                    row = scores.loc[ticker]
                    factor_scores = {
                        "value": float(row["value"]),
                        "momentum": float(row["momentum"]),
                        "quality": float(row["quality"]),
                        "growth": float(row["growth"]),
                    }
                    fig_factors = create_factor_chart(factor_scores, ticker)
                    st.plotly_chart(fig_factors, use_container_width=True, key=f"factors_{ticker}_{id(call)}")
            except Exception:
                pass

        elif name == "get_stock_quote":
            ticker = inp["ticker"].upper()
            if ticker in rendered_tickers:
                continue
            rendered_tickers.add(ticker)
            fig = create_stock_chart(ticker, period="3mo", chart_type="line", show_ma=False)
            st.plotly_chart(fig, use_container_width=True, key=f"quote_{ticker}_{id(call)}")

        elif name == "compare_stocks":
            tickers = [t.upper() for t in inp["tickers"]]
            fig = create_comparison_chart(tickers, period="6mo")
            st.plotly_chart(fig, use_container_width=True, key=f"compare_{id(call)}")

            # Individual mini charts
            cols = st.columns(min(len(tickers), 3))
            for i, ticker in enumerate(tickers[:3]):
                with cols[i]:
                    fig = create_stock_chart(ticker, period="6mo", chart_type="line", show_volume=False, show_ma=False)
                    fig.update_layout(height=250, title=dict(text=ticker, font=dict(size=13)))
                    st.plotly_chart(fig, use_container_width=True, key=f"mini_{ticker}_{id(call)}")

        elif name == "analyze_options":
            ticker = inp["ticker"].upper()
            # Show price chart for context
            if ticker not in rendered_tickers:
                rendered_tickers.add(ticker)
                fig = create_stock_chart(ticker, period="3mo", chart_type="candlestick")
                st.plotly_chart(fig, use_container_width=True, key=f"opt_price_{ticker}_{id(call)}")

        elif name == "recommend_options":
            ticker = inp["ticker"].upper()
            if ticker not in rendered_tickers:
                rendered_tickers.add(ticker)
                fig = create_stock_chart(ticker, period="6mo", chart_type="candlestick")
                st.plotly_chart(fig, use_container_width=True, key=f"rec_price_{ticker}_{id(call)}")

            # Factor chart for options context
            try:
                scores, _, _ = _get_cached_scores()
                if ticker in scores.index:
                    row = scores.loc[ticker]
                    factor_scores = {
                        "value": float(row["value"]),
                        "momentum": float(row["momentum"]),
                        "quality": float(row["quality"]),
                        "growth": float(row["growth"]),
                    }
                    fig_factors = create_factor_chart(factor_scores, ticker)
                    st.plotly_chart(fig_factors, use_container_width=True, key=f"rec_factors_{ticker}_{id(call)}")
            except Exception:
                pass

        elif name == "recommend_top_picks":
            # Show price charts for top picks
            try:
                picks = call.get("input", {}).get("category", "growth")
                scores_df = _get_cached_scores()
                if scores_df is not None:
                    # Get top 3 by composite score
                    top_tickers = scores_df.nlargest(3, "composite").index.tolist()
                    cols = st.columns(len(top_tickers))
                    for col, ticker in zip(cols, top_tickers):
                        with col:
                            fig = create_stock_chart(ticker, period="6mo")
                            st.plotly_chart(fig, use_container_width=True, key=f"top_pick_{ticker}_{id(call)}")
            except Exception:
                pass

        elif name == "screen_stocks":
            # Show factor chart for screened stocks
            try:
                factor = call.get("input", {}).get("factor", "composite")
                top_n = call.get("input", {}).get("top_n", 10)
                scores_df = _get_cached_scores()
                if scores_df is not None:
                    top_stocks = scores_df.nlargest(min(top_n, 5), factor)
                    for ticker in top_stocks.index[:3]:
                        factor_scores = {
                            "value": scores_df.loc[ticker, "value"],
                            "momentum": scores_df.loc[ticker, "momentum"],
                            "quality": scores_df.loc[ticker, "quality"],
                            "growth": scores_df.loc[ticker, "growth"],
                        }
                        fig = create_factor_chart(factor_scores, ticker)
                        st.plotly_chart(fig, use_container_width=True, key=f"screen_{ticker}_{id(call)}")
            except Exception:
                pass

        elif name == "recommend_portfolio":
            # Show allocation pie chart
            try:
                scores_df = _get_cached_scores()
                if scores_df is not None:
                    import plotly.graph_objects as go
                    top_stocks = scores_df.nlargest(9, "composite")
                    weights = top_stocks["composite"] / top_stocks["composite"].sum()

                    fig = go.Figure(data=[go.Pie(
                        labels=top_stocks.index.tolist(),
                        values=weights.values,
                        hole=0.4,
                        marker=dict(colors=['#7c3aed', '#8b5cf6', '#a78bfa', '#c4b5fd',
                                           '#ddd6fe', '#ede9fe', '#f5f3ff', '#faf5ff', '#fdf4ff']),
                        textinfo='label+percent',
                        textfont=dict(color='white'),
                    )])
                    fig.update_layout(
                        title="Portfolio Allocation",
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#e2e8f0'),
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True, key=f"portfolio_pie_{id(call)}")
            except Exception:
                pass


def render_chat():
    """Display chat history."""
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Render charts for assistant messages
            if msg["role"] == "assistant" and f"charts_{i}" in st.session_state:
                render_charts(st.session_state[f"charts_{i}"])


def process_response(api_key: str):
    """Process pending response if needed."""
    if not st.session_state.get("pending_response"):
        return

    if not api_key:
        st.error("Enter your Anthropic API key in the sidebar to get started.")
        st.session_state.pending_response = False
        return

    st.session_state.pending_response = False

    with st.chat_message("assistant"):
        with st.spinner("Researching..."):
            try:
                response_text, updated_messages, tool_calls = get_chat_response(
                    st.session_state.api_messages, api_key
                )
                st.session_state.api_messages = updated_messages
                st.session_state.api_messages.append(
                    {"role": "assistant", "content": response_text}
                )
                st.session_state.messages.append(
                    {"role": "assistant", "content": response_text}
                )
                # Store tool calls for chart rendering
                msg_idx = len(st.session_state.messages) - 1
                if tool_calls:
                    st.session_state[f"charts_{msg_idx}"] = tool_calls

                st.markdown(response_text)

                # Render charts
                if tool_calls:
                    render_charts(tool_calls)

            except Exception as e:
                error_msg = str(e)
                if "api_key" in error_msg.lower() or "auth" in error_msg.lower():
                    st.error("Invalid API key. Check your key at console.anthropic.com")
                else:
                    st.error(f"Something went wrong: {error_msg}")


def render_ai_picks(api_key: str):
    """Render AI Stock Picks section like Rallies.ai."""
    category = st.session_state.get("ai_picks_category", "balanced_picks")
    cat_config = PICK_CATEGORIES.get(category, PICK_CATEGORIES["balanced_picks"])

    # Header
    st.markdown(f"""
    <div style="text-align: center; padding: 20px 0;">
        <h1 style="font-size: 32px; margin-bottom: 8px;">🎯 AI Stock Picks</h1>
        <p style="color: #64748b; font-size: 16px;">{cat_config['name']}: {cat_config['description']}</p>
    </div>
    """, unsafe_allow_html=True)

    # Category tabs
    cols = st.columns(5)
    categories = list(PICK_CATEGORIES.keys())
    for i, cat in enumerate(categories):
        with cols[i]:
            is_active = cat == category
            btn_style = "primary" if is_active else "secondary"
            if st.button(PICK_CATEGORIES[cat]["name"].split()[0], key=f"cat_{cat}", type=btn_style, use_container_width=True):
                st.session_state.ai_picks_category = cat
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Get picks
    try:
        scores_df, fundamentals_df, _ = _get_cached_scores()
        if scores_df is None:
            st.warning("Loading stock data... Please wait.")
            return

        with st.spinner("AI is analyzing stocks..."):
            picks_data = get_ai_picks(scores_df, fundamentals_df, category, num_picks=5, api_key=api_key)

        # Render each pick as a card using Streamlit components
        for i, pick in enumerate(picks_data["picks"]):
            conviction_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(pick["conviction"], "⚪")

            # Format values safely
            price_str = f"${pick['price']:.2f}" if pick['price'] else "N/A"
            pe_str = f"{pick['pe_ratio']:.1f}" if pick['pe_ratio'] else "N/A"
            mcap_str = f"${pick['market_cap_B']:.0f}B" if pick['market_cap_B'] else "N/A"

            with st.container():
                # Header row
                col_ticker, col_price = st.columns([2, 1])
                with col_ticker:
                    st.markdown(f"### {pick['ticker']} {conviction_emoji} {pick['conviction'].upper()}")
                with col_price:
                    st.markdown(f"**{price_str}** · P/E: {pe_str} · MCap: {mcap_str}")

                # Thesis
                st.info(f"💡 **Investment Thesis:** {pick['thesis']}")

                # Bull/Bear cases
                col_bull, col_bear = st.columns(2)
                with col_bull:
                    st.success(f"📈 **Bull Case:** {pick['bull_case']}")
                with col_bear:
                    st.error(f"⚠️ **Bear Case:** {pick['bear_case']}")

                # Factor scores as metrics
                score_cols = st.columns(4)
                with score_cols[0]:
                    st.metric("Value", f"{pick['scores']['value']:.0%}")
                with score_cols[1]:
                    st.metric("Momentum", f"{pick['scores']['momentum']:.0%}")
                with score_cols[2]:
                    st.metric("Quality", f"{pick['scores']['quality']:.0%}")
                with score_cols[3]:
                    st.metric("Growth", f"{pick['scores']['growth']:.0%}")

                # Charts
                col1, col2 = st.columns([2, 1])
                with col1:
                    fig = create_stock_chart(pick["ticker"], period="3mo", chart_type="line", show_ma=False)
                    st.plotly_chart(fig, use_container_width=True, key=f"ai_chart_{pick['ticker']}_{i}")
                with col2:
                    fig_factors = create_factor_chart(pick["scores"], pick["ticker"])
                    st.plotly_chart(fig_factors, use_container_width=True, key=f"ai_factors_{pick['ticker']}_{i}")

                st.divider()

    except Exception as e:
        st.error(f"Error loading AI picks: {str(e)}")

    # Back button
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← Back to Chat", use_container_width=True, key="back_to_chat"):
        st.session_state.show_ai_picks = False
        st.rerun()

    st.markdown("""
    <p style="text-align: center; color: #64748b; font-size: 12px; margin-top: 24px;">
        AI-generated analysis based on multi-factor scoring. Not financial advice.
    </p>
    """, unsafe_allow_html=True)


def main():
    init_session_state()
    api_key = render_sidebar()

    # Check for AI Picks view
    if st.session_state.get("show_ai_picks"):
        render_ai_picks(api_key)
        return

    # Show welcome or chat
    if not st.session_state.messages:
        render_welcome()
    else:
        render_chat()

    # Handle pending responses from sidebar/welcome buttons
    process_response(api_key)

    # Chat input
    if prompt := st.chat_input("Ask about any stock..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.api_messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        if not api_key:
            with st.chat_message("assistant"):
                st.error("Enter your Anthropic API key in the sidebar to get started.")
            return

        with st.chat_message("assistant"):
            with st.spinner("Researching..."):
                try:
                    response_text, updated_messages, tool_calls = get_chat_response(
                        st.session_state.api_messages, api_key
                    )
                    st.session_state.api_messages = updated_messages
                    st.session_state.api_messages.append(
                        {"role": "assistant", "content": response_text}
                    )
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response_text}
                    )
                    msg_idx = len(st.session_state.messages) - 1
                    if tool_calls:
                        st.session_state[f"charts_{msg_idx}"] = tool_calls

                    st.markdown(response_text)

                    if tool_calls:
                        render_charts(tool_calls)

                except Exception as e:
                    st.error(f"Something went wrong: {str(e)}")


if __name__ == "__main__":
    main()
