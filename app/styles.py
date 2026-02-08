"""Shared CSS styles for Axion platform."""

import streamlit as st


def inject_global_styles():
    """Inject the global Axion CSS into the current page."""
    st.markdown("""
<style>
    /* ============================================
       AXION - Modern Finance UI
       Trends: Glassmorphism, Bento Grid, Aurora Gradients
       Color Palette: Deep Navy + Cyan/Teal accents
       ============================================ */

    /* Import Modern Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    /* ===== ROOT VARIABLES ===== */
    :root {
        --bg-primary: #0a0e17;
        --bg-secondary: #111827;
        --bg-card: rgba(17, 24, 39, 0.7);
        --bg-glass: rgba(15, 23, 42, 0.8);
        --border-subtle: rgba(56, 189, 248, 0.1);
        --border-glow: rgba(56, 189, 248, 0.3);
        --accent-primary: #06b6d4;
        --accent-secondary: #22d3ee;
        --accent-tertiary: #67e8f9;
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --success: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --radius-xl: 24px;
    }

    /* ===== GLOBAL STYLES ===== */
    .stApp {
        font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif;
        background: linear-gradient(135deg, var(--bg-primary) 0%, #0f172a 50%, #1e1b4b 100%);
        background-attachment: fixed;
    }

    /* Animated gradient background */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background:
            radial-gradient(ellipse at 20% 20%, rgba(6, 182, 212, 0.15) 0%, transparent 50%),
            radial-gradient(ellipse at 80% 80%, rgba(139, 92, 246, 0.1) 0%, transparent 50%),
            radial-gradient(ellipse at 50% 50%, rgba(16, 185, 129, 0.05) 0%, transparent 70%);
        pointer-events: none;
        z-index: 0;
    }

    /* Hide Streamlit branding */
    #MainMenu, footer, header {visibility: hidden;}

    /* Main container */
    .block-container {
        padding: 2rem 1rem 0 1rem;
        max-width: 1000px;
        position: relative;
        z-index: 1;
    }

    /* ===== SIDEBAR - Glassmorphism ===== */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(10, 14, 23, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-right: 1px solid var(--border-subtle);
    }

    [data-testid="stSidebar"]::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 200px;
        background: linear-gradient(180deg, rgba(6, 182, 212, 0.1) 0%, transparent 100%);
        pointer-events: none;
    }

    [data-testid="stSidebar"] .stMarkdown p {
        color: var(--text-secondary);
        font-size: 13px;
    }

    /* ===== TYPOGRAPHY ===== */
    h1 {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        letter-spacing: -1px;
        background: linear-gradient(135deg, #67e8f9 0%, #06b6d4 40%, #8b5cf6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    h2, h3 {
        font-family: 'Space Grotesk', sans-serif;
        color: var(--text-primary) !important;
        font-weight: 600;
        letter-spacing: -0.5px;
    }

    /* ===== BUTTONS - Glass Effect ===== */
    .stButton > button {
        background: linear-gradient(135deg, rgba(6, 182, 212, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-md);
        color: var(--accent-tertiary);
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 500;
        font-size: 13px;
        padding: 10px 18px;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        text-align: left;
        position: relative;
        overflow: hidden;
    }

    .stButton > button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(6, 182, 212, 0.2), transparent);
        transition: left 0.5s ease;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, rgba(6, 182, 212, 0.2) 0%, rgba(139, 92, 246, 0.2) 100%);
        border-color: var(--accent-primary);
        color: var(--text-primary);
        transform: translateY(-2px);
        box-shadow: 0 8px 32px rgba(6, 182, 212, 0.2), 0 0 0 1px rgba(6, 182, 212, 0.1);
    }

    .stButton > button:hover::before {
        left: 100%;
    }

    /* Primary button style */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--accent-primary) 0%, #0891b2 100%);
        color: var(--bg-primary);
        border: none;
        font-weight: 600;
    }

    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, var(--accent-secondary) 0%, var(--accent-primary) 100%);
        box-shadow: 0 8px 32px rgba(6, 182, 212, 0.4);
    }

    /* ===== CHAT MESSAGES ===== */
    [data-testid="stChatMessage"] {
        background: transparent;
        padding: 16px 0;
    }

    /* User message bubble */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) > div:last-child {
        background: linear-gradient(135deg, rgba(6, 182, 212, 0.1) 0%, rgba(139, 92, 246, 0.05) 100%);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-lg);
        padding: 16px 20px;
    }

    /* Assistant message */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) > div:last-child {
        background: var(--bg-glass);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: var(--radius-lg);
        padding: 16px 20px;
    }

    /* Chat input */
    [data-testid="stChatInput"] {
        border-top: 1px solid var(--border-subtle);
        padding-top: 20px;
    }

    [data-testid="stChatInput"] textarea {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-lg) !important;
        color: var(--text-primary) !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: 15px !important;
        padding: 16px 20px !important;
        transition: all 0.3s ease !important;
    }

    [data-testid="stChatInput"] textarea:focus {
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.15), 0 8px 32px rgba(6, 182, 212, 0.1) !important;
    }

    /* ===== TEXT INPUT ===== */
    [data-testid="stTextInput"] input {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-md) !important;
        color: var(--text-primary) !important;
        font-family: 'JetBrains Mono', monospace !important;
        transition: all 0.3s ease !important;
    }

    [data-testid="stTextInput"] input:focus {
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.15) !important;
    }

    /* ===== DIVIDERS ===== */
    hr {
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent, var(--border-subtle), transparent) !important;
        margin: 20px 0 !important;
    }

    /* ===== METRICS ===== */
    [data-testid="stMetricValue"] {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        color: var(--accent-secondary) !important;
    }

    [data-testid="stMetricLabel"] {
        color: var(--text-muted) !important;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-size: 11px !important;
    }

    /* ===== ALERTS / INFO BOXES ===== */
    .stAlert {
        background: var(--bg-glass) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-md) !important;
        backdrop-filter: blur(10px);
    }

    [data-testid="stAlert"][data-baseweb="notification"] {
        background: var(--bg-glass) !important;
        border-left: 4px solid var(--accent-primary) !important;
    }

    /* Success alert */
    .stSuccess {
        border-left-color: var(--success) !important;
    }

    /* Error alert */
    .stError {
        border-left-color: var(--danger) !important;
    }

    /* ===== WELCOME CARDS - Bento Style ===== */
    .welcome-card {
        background: var(--bg-glass);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-xl);
        padding: 28px;
        margin: 12px 0;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }

    .welcome-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(6, 182, 212, 0.5), transparent);
    }

    .welcome-card:hover {
        border-color: var(--border-glow);
        transform: translateY(-4px);
        box-shadow:
            0 20px 40px rgba(0, 0, 0, 0.3),
            0 0 60px rgba(6, 182, 212, 0.1);
    }

    .welcome-card h4 {
        color: var(--text-primary);
        margin: 0 0 10px 0;
        font-size: 18px;
        font-weight: 600;
        font-family: 'Space Grotesk', sans-serif;
    }

    .welcome-card p {
        color: var(--text-secondary);
        margin: 0;
        font-size: 14px;
        line-height: 1.6;
    }

    /* ===== LOGO AREA ===== */
    .logo-area {
        text-align: center;
        padding: 24px 0 16px 0;
    }

    .logo-area h1 {
        font-size: 32px;
        margin: 0;
        letter-spacing: -1px;
    }

    .logo-area .subtitle {
        color: var(--text-muted);
        font-size: 11px;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin-top: 8px;
        font-weight: 500;
    }

    /* ===== SIDEBAR SECTIONS ===== */
    .sidebar-section {
        color: var(--accent-primary);
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin: 20px 0 12px 0;
        padding-left: 4px;
        position: relative;
    }

    .sidebar-section::after {
        content: '';
        position: absolute;
        bottom: -4px;
        left: 0;
        width: 24px;
        height: 2px;
        background: var(--accent-primary);
        border-radius: 1px;
    }

    /* ===== FACTOR PILLS - Modern Tags ===== */
    .factor-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        margin: 4px;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }

    .pill-value {
        background: rgba(59, 130, 246, 0.15);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.2);
    }
    .pill-momentum {
        background: rgba(168, 85, 247, 0.15);
        color: #c084fc;
        border: 1px solid rgba(168, 85, 247, 0.2);
    }
    .pill-quality {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.2);
    }
    .pill-growth {
        background: rgba(251, 191, 36, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(251, 191, 36, 0.2);
    }

    /* ===== METRIC ROW - Bento Grid ===== */
    .metric-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin: 24px 0;
    }

    .metric-card {
        background: var(--bg-glass);
        backdrop-filter: blur(20px);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-lg);
        padding: 20px;
        text-align: center;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }

    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 40px;
        height: 2px;
        background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
        border-radius: 1px;
    }

    .metric-card:hover {
        border-color: var(--border-glow);
        transform: translateY(-2px);
    }

    .metric-card .value {
        font-size: 28px;
        font-weight: 700;
        font-family: 'Space Grotesk', sans-serif;
        background: linear-gradient(135deg, var(--accent-secondary) 0%, var(--accent-primary) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }

    .metric-card .label {
        font-size: 10px;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 500;
    }

    /* ===== SCROLLBAR - Minimal ===== */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }

    ::-webkit-scrollbar-track {
        background: transparent;
    }

    ::-webkit-scrollbar-thumb {
        background: var(--border-subtle);
        border-radius: 3px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: var(--accent-primary);
    }

    /* ===== PLOTLY CHARTS - Dark Theme Override ===== */
    .js-plotly-plot .plotly .modebar {
        background: transparent !important;
    }

    .js-plotly-plot .plotly .modebar-btn path {
        fill: var(--text-muted) !important;
    }

    /* ===== SPINNER ===== */
    .stSpinner > div {
        border-top-color: var(--accent-primary) !important;
    }

    /* ===== EXPANDER ===== */
    [data-testid="stExpander"] {
        background: var(--bg-glass);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-md);
    }

    /* ===== TABS ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: transparent;
    }

    .stTabs [data-baseweb="tab"] {
        background: var(--bg-glass);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-md);
        color: var(--text-secondary);
        padding: 10px 20px;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(6, 182, 212, 0.2) 0%, rgba(139, 92, 246, 0.1) 100%);
        border-color: var(--accent-primary);
        color: var(--text-primary);
    }

    /* ===== CONTAINER STYLING ===== */
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
        background: var(--bg-glass);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-lg);
        padding: 20px;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)
