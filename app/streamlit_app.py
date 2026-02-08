"""Axion — AI Stock Research Platform (entrypoint).

Slim navigation router using st.navigation() + st.Page().
All chat logic lives in pages/home.py; CSS in styles.py; page defs in nav_config.py.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from app.styles import inject_global_styles
from app.nav_config import build_navigation_pages
from app.chat import get_api_key

# ── Page config (must be first Streamlit call) ──────────────────────
st.set_page_config(
    page_title="Axion - AI Stock Research",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ──────────────────────────────────────────────────────
inject_global_styles()


# ── Session state defaults ──────────────────────────────────────────
def init_session_state():
    defaults = {
        "messages": [],
        "api_messages": [],
        "show_ai_picks": False,
        "ai_picks_category": "balanced_picks",
        "active_agent": None,
        "selected_provider": "anthropic",
        "selected_model": "claude-sonnet-4-20250514",
        "provider_registry": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()

# ── Navigation ──────────────────────────────────────────────────────
pg = st.navigation(build_navigation_pages(), position="sidebar")

# ── Shared sidebar (visible on all pages) ───────────────────────────
with st.sidebar:
    # Logo
    st.markdown("""
    <div class="logo-area">
        <h1>Axion</h1>
        <div class="subtitle">AI Stock Research</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ── Provider & Model Selection ──────────────────────────────────
    st.markdown('<div class="sidebar-section">LLM Provider</div>', unsafe_allow_html=True)

    try:
        from src.model_providers.config import (
            ProviderType, list_models_for_provider, get_model_info,
        )
        from src.model_providers.registry import ProviderRegistry
        from src.model_providers.config import ProviderConfig

        _PROVIDER_DISPLAY = {
            "anthropic": "Anthropic (Claude)",
            "openai": "OpenAI (GPT)",
            "gemini": "Google (Gemini)",
            "deepseek": "DeepSeek",
            "ollama": "Ollama (Local)",
        }
        _PROVIDER_PLACEHOLDERS = {
            "anthropic": "sk-ant-...",
            "openai": "sk-...",
            "gemini": "AI...",
            "deepseek": "sk-...",
            "ollama": "",
        }
        _PROVIDER_HELP = {
            "anthropic": "console.anthropic.com",
            "openai": "platform.openai.com/api-keys",
            "gemini": "aistudio.google.com/app/apikey",
            "deepseek": "platform.deepseek.com/api_keys",
            "ollama": "No key needed — runs locally",
        }

        provider_names = list(_PROVIDER_DISPLAY.keys())
        current_prov_idx = provider_names.index(st.session_state.selected_provider) \
            if st.session_state.selected_provider in provider_names else 0

        selected_prov = st.selectbox(
            "Provider",
            options=provider_names,
            index=current_prov_idx,
            format_func=lambda x: _PROVIDER_DISPLAY.get(x, x),
            key="provider_selector",
            label_visibility="collapsed",
        )
        st.session_state.selected_provider = selected_prov

        # Model selector for chosen provider
        prov_type = ProviderType(selected_prov)
        prov_models = list_models_for_provider(prov_type)
        model_ids = [m.model_id for m in prov_models]
        model_labels = {m.model_id: m.display_name for m in prov_models}

        if model_ids:
            default_model_idx = 0
            if st.session_state.selected_model in model_ids:
                default_model_idx = model_ids.index(st.session_state.selected_model)
            selected_model = st.selectbox(
                "Model",
                options=model_ids,
                index=default_model_idx,
                format_func=lambda x: model_labels.get(x, x),
                key="model_selector",
                label_visibility="collapsed",
            )
            st.session_state.selected_model = selected_model
            model_info = get_model_info(selected_model)
            if model_info:
                tier_icon = {
                    "flagship": "🏆", "fast": "⚡",
                }.get(model_info.tier.value, "⭐")
                tool_icon = "🔧 Tools" if model_info.supports_tool_use else "💬 Chat"
                st.caption(
                    f"{tier_icon} {model_info.tier.value.title()} · "
                    f"{tool_icon} · {model_info.context_window:,} ctx"
                )

        # API key input
        if selected_prov == "ollama":
            ollama_url = st.text_input(
                "Ollama URL",
                value="http://localhost:11434/v1",
                key="ollama_url_input",
                label_visibility="collapsed",
                placeholder="http://localhost:11434/v1",
            )
            api_key = "ollama"
            st.caption("Ollama runs locally — no API key needed")
        else:
            default_key = get_api_key() or "" if selected_prov == "anthropic" else ""
            api_key = st.text_input(
                "API Key",
                value=default_key,
                type="password",
                placeholder=_PROVIDER_PLACEHOLDERS.get(selected_prov, ""),
                help=_PROVIDER_HELP.get(selected_prov, ""),
                key="api_key",
                label_visibility="collapsed",
            )
            if not api_key:
                st.caption(f"Enter {_PROVIDER_DISPLAY.get(selected_prov, '')} API key")

        # Configure provider registry
        if api_key:
            registry = ProviderRegistry()
            if selected_prov == "ollama":
                registry.configure(ProviderConfig(
                    provider=prov_type,
                    base_url=ollama_url if selected_prov == "ollama" else None,
                ))
            else:
                registry.configure(ProviderConfig(
                    provider=prov_type,
                    api_key=api_key,
                ))
            st.session_state.provider_registry = registry
        else:
            st.session_state.provider_registry = None

    except Exception:
        # Fallback: basic Anthropic-only key input
        default_key = get_api_key() or ""
        api_key = st.text_input(
            "API Key",
            value=default_key,
            type="password",
            placeholder="sk-ant-...",
            help="Anthropic API key from console.anthropic.com",
            key="api_key",
            label_visibility="collapsed",
        )
        if not api_key:
            st.caption("Enter Anthropic API key above")
        st.session_state.provider_registry = None

    # Store API key for pages to read
    st.session_state["_api_key"] = api_key

    st.divider()

    # ── Agent selector ──────────────────────────────────────────────
    st.markdown('<div class="sidebar-section">AI Agent</div>', unsafe_allow_html=True)
    try:
        from src.agents.registry import list_agents
        agents = list_agents()
        agent_options = ["Default (no agent)"] + [f"{a.avatar} {a.name}" for a in agents]
        current_idx = 0
        if st.session_state.get("active_agent"):
            for i, a in enumerate(agents):
                if a.agent_type == st.session_state.active_agent:
                    current_idx = i + 1
                    break
        agent_choice = st.selectbox(
            "Agent",
            options=agent_options,
            index=current_idx,
            key="agent_selector",
            label_visibility="collapsed",
        )
        if agent_choice == "Default (no agent)":
            st.session_state.active_agent = None
        else:
            for a in agents:
                if f"{a.avatar} {a.name}" == agent_choice:
                    st.session_state.active_agent = a.agent_type
                    st.caption(a.description)
                    break
    except Exception:
        pass

# ── Run selected page ───────────────────────────────────────────────
pg.run()
