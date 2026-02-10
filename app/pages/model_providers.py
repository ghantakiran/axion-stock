"""Model Providers Dashboard — Configure and manage LLM backends."""

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Model Providers", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Model Providers")

# ── Imports ───────────────────────────────────────────────────────────

from src.model_providers.config import (
    MODEL_CATALOG,
    ModelTier,
    ProviderConfig,
    ProviderType,
    get_model_info,
    list_all_models,
    list_models_for_provider,
)
from src.model_providers.registry import ProviderRegistry
from src.model_providers.router import (
    FAST_CHAIN,
    FLAGSHIP_CHAIN,
    LOCAL_CHAIN,
    FallbackChain,
    ModelRouter,
)

# ── Session State ─────────────────────────────────────────────────────

if "provider_registry" not in st.session_state:
    st.session_state["provider_registry"] = ProviderRegistry()

registry: ProviderRegistry = st.session_state["provider_registry"]

# ── Sidebar ───────────────────────────────────────────────────────────

st.sidebar.header("Model Providers")
st.sidebar.caption("Configure API keys for different LLM providers.")

# ── Main Tabs ─────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "Provider Setup",
    "Model Catalog",
    "Fallback Chains",
    "Usage & Costs",
])

# ── Tab 1: Provider Setup ────────────────────────────────────────────

with tab1:
    st.subheader("Configure Providers")
    st.caption("Enter API keys for the LLM providers you want to use. Keys are stored in session only.")

    provider_defs = [
        (ProviderType.ANTHROPIC, "Anthropic (Claude)", "sk-ant-...", "https://console.anthropic.com/settings/keys"),
        (ProviderType.OPENAI, "OpenAI (GPT-4o)", "sk-...", "https://platform.openai.com/api-keys"),
        (ProviderType.GEMINI, "Google (Gemini)", "AI...", "https://aistudio.google.com/app/apikey"),
        (ProviderType.DEEPSEEK, "DeepSeek (V3/R1)", "sk-...", "https://platform.deepseek.com/api_keys"),
        (ProviderType.OLLAMA, "Ollama (Local)", "", "https://ollama.com"),
    ]

    for ptype, display_name, placeholder, url in provider_defs:
        with st.expander(f"{'✅' if registry.is_configured(ptype) else '⚪'} {display_name}", expanded=False):
            if ptype == ProviderType.OLLAMA:
                st.markdown(f"**Ollama** runs locally — no API key needed. [Install Ollama]({url})")
                base_url = st.text_input(
                    "Ollama URL",
                    value="http://localhost:11434/v1",
                    key=f"url_{ptype.value}",
                )
                if st.button(f"Enable {display_name}", key=f"btn_{ptype.value}"):
                    registry.configure(ProviderConfig(
                        provider=ptype,
                        base_url=base_url,
                    ))
                    st.success(f"{display_name} configured!")
                    st.rerun()
            else:
                existing = registry.get_config(ptype)
                current_key = existing.api_key if existing else ""

                api_key = st.text_input(
                    f"API Key",
                    value=current_key,
                    type="password",
                    placeholder=placeholder,
                    key=f"key_{ptype.value}",
                )
                st.caption(f"Get your key: [{url}]({url})")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"Save", key=f"save_{ptype.value}"):
                        if api_key:
                            registry.configure(ProviderConfig(
                                provider=ptype,
                                api_key=api_key,
                            ))
                            st.success(f"{display_name} configured!")
                            st.rerun()
                        else:
                            st.warning("Enter an API key first.")
                with col2:
                    if registry.is_configured(ptype):
                        if st.button(f"Remove", key=f"rm_{ptype.value}"):
                            registry.remove(ptype)
                            st.info(f"{display_name} removed.")
                            st.rerun()

    # Summary
    st.markdown("---")
    st.subheader("Status")
    configured = registry.list_configured()
    if configured:
        for ptype in configured:
            st.markdown(f"✅ **{ptype.value.title()}** — configured")
        st.success(f"{len(configured)} provider(s) active")
    else:
        st.info("No providers configured yet. Add at least one API key above.")


# ── Tab 2: Model Catalog ─────────────────────────────────────────────

with tab2:
    st.subheader("Available Models")
    st.caption("All models in the catalog, grouped by provider.")

    for ptype in ProviderType:
        models = list_models_for_provider(ptype)
        if not models:
            continue

        is_configured = registry.is_configured(ptype)
        status = "✅" if is_configured else "⚪"

        st.markdown(f"### {status} {ptype.value.title()}")

        for model in models:
            tier_badge = {
                ModelTier.FLAGSHIP: "🏆 Flagship",
                ModelTier.STANDARD: "⭐ Standard",
                ModelTier.FAST: "⚡ Fast",
                ModelTier.LOCAL: "💻 Local",
            }.get(model.tier, model.tier.value)

            tool_badge = "🔧 Tools" if model.supports_tool_use else "💬 Chat only"
            cost_str = (
                f"${model.cost_per_1k_input:.4f}/{model.cost_per_1k_output:.4f}"
                if model.cost_per_1k_input > 0
                else "Free"
            )

            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            with col1:
                st.markdown(f"**{model.display_name}** (`{model.model_id}`)")
            with col2:
                st.caption(tier_badge)
            with col3:
                st.caption(tool_badge)
            with col4:
                st.caption(f"Cost: {cost_str}")

        st.markdown("---")


# ── Tab 3: Fallback Chains ───────────────────────────────────────────

with tab3:
    st.subheader("Fallback Chains")
    st.caption(
        "When a model fails, the system tries the next model in the chain. "
        "Only configured providers are used."
    )

    chains = [
        ("Flagship Chain", "Best quality models", FLAGSHIP_CHAIN),
        ("Fast Chain", "Speed-optimized models", FAST_CHAIN),
        ("Local Chain", "Ollama local models", LOCAL_CHAIN),
    ]

    for name, desc, chain in chains:
        with st.expander(f"**{name}** — {desc}", expanded=True):
            for i, model_id in enumerate(chain.models, 1):
                info = get_model_info(model_id)
                if not info:
                    st.markdown(f"{i}. `{model_id}` — ❓ Unknown")
                    continue

                is_ready = registry.is_configured(info.provider)
                status = "✅" if is_ready else "⚪ Not configured"
                st.markdown(
                    f"{i}. **{info.display_name}** (`{model_id}`) "
                    f"— {info.provider.value.title()} {status}"
                )

    st.markdown("---")
    st.subheader("Custom Chain")
    st.caption("Build your own fallback order.")

    all_model_ids = list(MODEL_CATALOG.keys())
    selected = st.multiselect(
        "Select models in priority order",
        options=all_model_ids,
        default=["claude-sonnet-4-20250514", "gpt-4o"],
        key="custom_chain_select",
    )
    if selected:
        st.markdown("**Your chain:**")
        for i, m in enumerate(selected, 1):
            info = get_model_info(m)
            name = info.display_name if info else m
            st.markdown(f"{i}. {name}")


# ── Tab 4: Usage & Costs ─────────────────────────────────────────────

with tab4:
    st.subheader("Usage Analytics")
    st.caption("Track token usage and estimated costs across providers.")

    # Cost estimator
    st.markdown("### Cost Estimator")
    col1, col2, col3 = st.columns(3)
    with col1:
        est_model = st.selectbox("Model", list(MODEL_CATALOG.keys()), key="cost_model")
    with col2:
        est_input = st.number_input("Input tokens", min_value=0, value=1000, step=100, key="cost_input")
    with col3:
        est_output = st.number_input("Output tokens", min_value=0, value=500, step=100, key="cost_output")

    info = get_model_info(est_model)
    if info:
        cost = (est_input / 1000) * info.cost_per_1k_input + (est_output / 1000) * info.cost_per_1k_output
        st.metric("Estimated Cost", f"${cost:.6f}")
        st.caption(
            f"Rates: ${info.cost_per_1k_input:.4f}/1K input, "
            f"${info.cost_per_1k_output:.4f}/1K output"
        )

    st.markdown("---")

    # Comparison table
    st.markdown("### Model Comparison")
    comparison_data = []
    for model in list_all_models():
        comparison_data.append({
            "Model": model.display_name,
            "Provider": model.provider.value.title(),
            "Tier": model.tier.value.title(),
            "Context Window": f"{model.context_window:,}",
            "Input $/1K": f"${model.cost_per_1k_input:.4f}",
            "Output $/1K": f"${model.cost_per_1k_output:.4f}",
            "Tools": "Yes" if model.supports_tool_use else "No",
        })

    if comparison_data:
        st.dataframe(comparison_data, use_container_width=True)
