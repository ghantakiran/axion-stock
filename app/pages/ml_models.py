"""ML Models Dashboard - Prediction Engine Interface.

Provides:
- Model status and health overview
- Stock ranking predictions
- Regime classification
- Feature importance visualization
- Model performance monitoring
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# Page config
try:
    st.set_page_config(
        page_title="Axion ML Models",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()


# Import ML module
try:
    from src.ml import (
        MLConfig,
        StockRankingModel,
        RegimeClassifier,
        FactorTimingModel,
        HybridScorer,
        ModelPerformanceTracker,
        ModelExplainer,
        FeatureEngineer,
    )
    ML_AVAILABLE = True
except ImportError as e:
    ML_AVAILABLE = False
    st.error(f"ML module not available: {e}")


# =============================================================================
# Demo Data
# =============================================================================

def get_demo_predictions():
    """Generate demo ML predictions."""
    np.random.seed(42)
    symbols = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "JPM",
               "JNJ", "XOM", "PG", "UNH", "V", "HD", "MA", "CRM"]

    predictions = pd.DataFrame({
        "symbol": symbols,
        "ml_score": np.random.uniform(0.2, 0.95, len(symbols)),
        "rule_score": np.random.uniform(0.3, 0.9, len(symbols)),
        "predicted_quintile": np.random.choice([1, 2, 3, 4, 5], len(symbols), p=[0.1, 0.15, 0.3, 0.25, 0.2]),
        "prob_q5": np.random.uniform(0.05, 0.45, len(symbols)),
        "sector": np.random.choice(["Technology", "Financials", "Healthcare", "Energy", "Consumer"], len(symbols)),
    })
    predictions = predictions.sort_values("ml_score", ascending=False).reset_index(drop=True)
    predictions["hybrid_score"] = 0.7 * predictions["rule_score"] + 0.3 * predictions["ml_score"]

    return predictions


def get_demo_regime():
    """Generate demo regime classification."""
    return {
        "regime": "bull",
        "confidence": 0.68,
        "probabilities": {"bull": 0.68, "sideways": 0.20, "bear": 0.08, "crisis": 0.04},
        "duration_days": 42,
    }


def get_demo_feature_importance():
    """Generate demo feature importance."""
    features = [
        "momentum_12m", "roe", "pe_ratio_rank", "earnings_surprise",
        "sector_momentum", "beta", "value_score", "growth_score",
        "rsi_14", "quality_score", "fcf_yield", "debt_equity",
        "realized_vol", "price_to_sma200", "market_breadth",
    ]
    np.random.seed(42)
    importance = np.random.exponential(0.5, len(features))
    importance = importance / importance.sum()
    return pd.Series(importance, index=features).sort_values(ascending=False)


def get_demo_ic_history():
    """Generate demo IC history."""
    np.random.seed(42)
    months = pd.date_range(end=datetime.now(), periods=12, freq="ME")
    ics = np.random.normal(0.045, 0.015, 12).clip(0.01, 0.08)
    return pd.Series(ics, index=months)


# =============================================================================
# Dashboard Components
# =============================================================================

def render_model_status():
    """Render model status overview."""
    st.markdown("### Model Status")

    models = [
        {"name": "Stock Ranking", "type": "LightGBM", "status": "Active",
         "ic": 0.052, "last_trained": "2026-01-15", "age": 14},
        {"name": "Regime Classifier", "type": "GMM + RF", "status": "Active",
         "ic": None, "accuracy": 0.73, "last_trained": "2026-01-01", "age": 28},
        {"name": "Earnings Predictor", "type": "XGBoost", "status": "Active",
         "ic": None, "accuracy": 0.64, "last_trained": "2026-01-10", "age": 19},
        {"name": "Factor Timing", "type": "LightGBM", "status": "Active",
         "ic": 0.038, "last_trained": "2026-01-05", "age": 24},
    ]

    cols = st.columns(4)
    for i, model in enumerate(models):
        with cols[i]:
            status_color = "green" if model["status"] == "Active" else "orange"
            metric_label = f"IC: {model['ic']:.3f}" if model.get("ic") else f"Acc: {model.get('accuracy', 0):.0%}"

            st.markdown(f"""
            <div style="padding: 1rem; background: {status_color}11;
                        border-left: 3px solid {status_color}; border-radius: 8px;">
                <strong>{model['name']}</strong><br>
                <small style="color: #666;">{model['type']}</small><br>
                <span style="color: {status_color};">{metric_label}</span><br>
                <small>Trained: {model['last_trained']} ({model['age']}d ago)</small>
            </div>
            """, unsafe_allow_html=True)


def render_rankings(predictions):
    """Render stock ranking predictions."""
    st.markdown("### Stock Rankings")

    col1, col2 = st.columns([2, 1])

    with col1:
        # Rankings table
        display_df = predictions[["symbol", "hybrid_score", "ml_score", "rule_score", "predicted_quintile", "sector"]].copy()
        display_df.columns = ["Symbol", "Hybrid Score", "ML Score", "Rule Score", "Quintile", "Sector"]

        def color_quintile(val):
            colors = {5: "background-color: #c6efce", 4: "background-color: #e2efda",
                      3: "background-color: #ffffff", 2: "background-color: #fce4d6",
                      1: "background-color: #ffc7ce"}
            return colors.get(val, "")

        st.dataframe(
            display_df.style.format({
                "Hybrid Score": "{:.2f}",
                "ML Score": "{:.2f}",
                "Rule Score": "{:.2f}",
            }).map(color_quintile, subset=["Quintile"]),
            use_container_width=True,
            hide_index=True,
            height=400,
        )

    with col2:
        # Quintile distribution
        quintile_counts = predictions["predicted_quintile"].value_counts().sort_index()
        fig = px.bar(
            x=quintile_counts.index,
            y=quintile_counts.values,
            labels={"x": "Quintile", "y": "Count"},
            title="Quintile Distribution",
            color=quintile_counts.index,
            color_continuous_scale="RdYlGn",
        )
        fig.update_layout(height=200, margin=dict(l=0, r=0, t=40, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        # Score comparison
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=predictions["rule_score"],
            y=predictions["ml_score"],
            mode="markers+text",
            text=predictions["symbol"],
            textposition="top center",
            marker=dict(size=8, color=predictions["hybrid_score"], colorscale="Viridis"),
        ))
        fig.add_shape(type="line", x0=0, y0=0, x1=1, y1=1, line=dict(dash="dash", color="gray"))
        fig.update_layout(
            title="ML vs Rule Scores",
            xaxis_title="Rule Score",
            yaxis_title="ML Score",
            height=200,
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)


def render_regime(regime_data):
    """Render regime classification."""
    st.markdown("### Market Regime")

    col1, col2 = st.columns([1, 2])

    with col1:
        regime = regime_data["regime"]
        confidence = regime_data["confidence"]
        duration = regime_data["duration_days"]

        regime_colors = {"bull": "green", "bear": "red", "sideways": "orange", "crisis": "darkred"}
        regime_icons = {"bull": "📈", "bear": "📉", "sideways": "➡️", "crisis": "🚨"}

        color = regime_colors.get(regime, "gray")
        icon = regime_icons.get(regime, "⚪")

        st.markdown(f"""
        <div style="padding: 1.5rem; background: {color}11;
                    border: 2px solid {color}; border-radius: 12px; text-align: center;">
            <h1 style="margin: 0; color: {color};">{icon} {regime.upper()}</h1>
            <p style="margin: 0.5rem 0 0 0;">Confidence: {confidence:.0%}</p>
            <small>Duration: {duration} days</small>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        # Regime probabilities
        probs = regime_data["probabilities"]
        fig = go.Figure(go.Bar(
            x=list(probs.values()),
            y=[k.title() for k in probs.keys()],
            orientation="h",
            marker_color=["green", "orange", "red", "darkred"],
        ))
        fig.update_layout(
            title="Regime Probabilities",
            xaxis_title="Probability",
            height=200,
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)


def render_feature_importance(importance):
    """Render feature importance chart."""
    st.markdown("### Feature Importance (Stock Ranking Model)")

    top_n = 15
    top_features = importance.head(top_n)

    fig = go.Figure(go.Bar(
        x=top_features.values,
        y=top_features.index,
        orientation="h",
        marker_color="rgba(99, 110, 250, 0.7)",
    ))
    fig.update_layout(
        title=f"Top {top_n} Features",
        xaxis_title="Importance",
        height=400,
        margin=dict(l=0, r=0, t=40, b=0),
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_ic_history(ic_series):
    """Render IC history chart."""
    st.markdown("### Information Coefficient (Rolling)")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=ic_series.index,
        y=ic_series.values,
        mode="lines+markers",
        name="Monthly IC",
        line=dict(color="rgb(99, 110, 250)"),
    ))

    # Threshold lines
    fig.add_hline(y=0.05, line_dash="dash", line_color="green",
                  annotation_text="Good (0.05)")
    fig.add_hline(y=0.03, line_dash="dash", line_color="orange",
                  annotation_text="Acceptable (0.03)")
    fig.add_hline(y=0.02, line_dash="dash", line_color="red",
                  annotation_text="Degraded (0.02)")

    fig.update_layout(
        title="Monthly Information Coefficient",
        xaxis_title="Month",
        yaxis_title="IC",
        height=300,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_hybrid_config():
    """Render hybrid scoring configuration."""
    st.markdown("### Score Blending Configuration")

    col1, col2 = st.columns(2)

    with col1:
        ml_weight = st.slider(
            "ML Weight",
            min_value=0.0,
            max_value=1.0,
            value=0.30,
            step=0.05,
            help="0 = rules only, 1 = ML only. Recommended: 0.30"
        )
        st.info(f"Rule Weight: {1-ml_weight:.0%} | ML Weight: {ml_weight:.0%}")

    with col2:
        st.markdown("**Auto-Fallback Settings**")
        fallback = st.toggle("Auto-fallback to rules on ML degradation", value=True)
        min_ic = st.number_input("Min IC for ML", value=0.02, step=0.01, format="%.2f")
        st.markdown(f"ML deactivates when IC < {min_ic:.2f} for 3+ months")


# =============================================================================
# Main Page
# =============================================================================

def main():
    st.title("🤖 ML Prediction Engine")

    if not ML_AVAILABLE:
        st.error("ML module not available. Please check installation.")
        return

    # Sidebar
    with st.sidebar:
        st.markdown("## ML Models")
        st.markdown("---")
        st.toggle("Demo Mode", value=True, key="ml_demo_mode")
        st.markdown("---")
        st.markdown("### Quick Info")
        st.metric("Active Models", "4/4")
        st.metric("Avg IC", "0.045")
        st.metric("Regime", "BULL (68%)")

    # Status overview
    render_model_status()
    st.markdown("---")

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Rankings", "🌡️ Regime", "🔬 Features", "📈 Performance", "⚙️ Config"
    ])

    with tab1:
        predictions = get_demo_predictions()
        render_rankings(predictions)

    with tab2:
        regime = get_demo_regime()
        render_regime(regime)

    with tab3:
        importance = get_demo_feature_importance()
        render_feature_importance(importance)

    with tab4:
        ic_history = get_demo_ic_history()
        render_ic_history(ic_history)

    with tab5:
        render_hybrid_config()



main()
