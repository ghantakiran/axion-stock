"""PRD-80: Custom Factor Builder Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd
import numpy as np

from src.factors.builder import (
    TransformType,
    AggregationMethod,
    FactorComponent,
    CustomFactorBuilder,
)


def get_builder() -> CustomFactorBuilder:
    if "factor_builder" not in st.session_state:
        st.session_state.factor_builder = CustomFactorBuilder()
    return st.session_state.factor_builder


def render():
inject_global_styles()
    st.title("Custom Factor Builder")

    tabs = st.tabs(["Build Factor", "Factor Library", "Compute & Rank", "Factor Analysis"])

    # ── Tab 1: Build Factor ──
    with tabs[0]:
        st.subheader("Create Custom Factor")

        name = st.text_input("Factor Name", placeholder="e.g. Quality Value Blend")
        description = st.text_area("Description", placeholder="Describe your factor...")
        created_by = st.text_input("Created By", value="analyst")
        aggregation = st.selectbox(
            "Aggregation Method",
            [m.value for m in AggregationMethod],
            index=0,
        )

        st.markdown("### Components")
        n_components = st.number_input("Number of Components", 1, 10, 2)

        components = []
        for i in range(int(n_components)):
            with st.expander(f"Component {i + 1}", expanded=i == 0):
                metric = st.text_input(f"Metric Name", key=f"metric_{i}", placeholder="e.g. pe_ratio")
                weight = st.slider(f"Weight", 0.1, 5.0, 1.0, 0.1, key=f"weight_{i}")
                transform = st.selectbox(
                    f"Transform",
                    [t.value for t in TransformType],
                    index=1,
                    key=f"transform_{i}",
                )
                direction = st.selectbox(
                    f"Direction",
                    ["positive", "negative"],
                    key=f"direction_{i}",
                )
                if metric:
                    components.append(FactorComponent(
                        metric_name=metric,
                        weight=weight,
                        transform=TransformType(transform),
                        direction=direction,
                    ))

        if st.button("Create Factor") and name and components:
            builder = get_builder()
            factor = builder.create_factor(
                name=name,
                components=components,
                description=description,
                created_by=created_by,
                aggregation=AggregationMethod(aggregation),
            )
            st.success(f"Factor '{factor.name}' created (ID: {factor.id[:8]}...)")
            st.json(factor.to_dict())

    # ── Tab 2: Factor Library ──
    with tabs[1]:
        st.subheader("Saved Factors")
        builder = get_builder()
        factors = builder.list_factors()

        if not factors:
            st.info("No factors created yet. Use the Build tab to create one.")
        else:
            for f in factors:
                with st.expander(f"{f.name} ({f.n_components} components)"):
                    st.json(f.to_dict())
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Delete", key=f"del_{f.id}"):
                            builder.delete_factor(f.id)
                            st.rerun()

    # ── Tab 3: Compute & Rank ──
    with tabs[2]:
        st.subheader("Compute Factor Scores")
        builder = get_builder()
        factors = builder.list_factors()

        if not factors:
            st.info("Create a factor first.")
        else:
            factor_names = {f.name: f.id for f in factors}
            selected = st.selectbox("Select Factor", list(factor_names.keys()))

            st.markdown("### Upload Data")
            uploaded = st.file_uploader("CSV with metrics (index=symbol)", type="csv")

            if uploaded:
                data = pd.read_csv(uploaded, index_col=0)
                st.dataframe(data.head())

                if st.button("Compute Scores"):
                    factor_id = factor_names[selected]
                    result = builder.compute(factor_id, data)
                    scores_df = pd.DataFrame(
                        list(result.scores.items()),
                        columns=["Symbol", "Score"],
                    ).sort_values("Score", ascending=False)
                    st.dataframe(scores_df, use_container_width=True)

                    st.markdown("#### Top 10")
                    for sym, score in result.top_n(10):
                        st.write(f"**{sym}**: {score:.2f}")

            # Demo with sample data
            if st.checkbox("Use sample data"):
                sample = pd.DataFrame({
                    "pe_ratio": [15, 20, 25, 10, 30],
                    "roe": [0.15, 0.20, 0.10, 0.25, 0.05],
                    "momentum": [0.10, 0.05, -0.02, 0.15, -0.05],
                    "volatility": [0.20, 0.30, 0.15, 0.25, 0.40],
                }, index=["AAPL", "MSFT", "GOOG", "AMZN", "META"])
                st.dataframe(sample)

                if st.button("Compute with Sample"):
                    factor_id = factor_names[selected]
                    result = builder.compute(factor_id, sample)
                    scores_df = pd.DataFrame(
                        list(result.scores.items()),
                        columns=["Symbol", "Score"],
                    ).sort_values("Score", ascending=False)
                    st.bar_chart(scores_df.set_index("Symbol"))

    # ── Tab 4: Factor Analysis ──
    with tabs[3]:
        st.subheader("Factor Analysis")
        builder = get_builder()
        factors = builder.list_factors()

        if len(factors) < 1:
            st.info("Create factors to analyze.")
        else:
            st.markdown("### Factor Summary")
            summary_data = []
            for f in factors:
                summary_data.append({
                    "Name": f.name,
                    "Components": f.n_components,
                    "Total Weight": f.total_weight,
                    "Aggregation": f.aggregation.value,
                    "Metrics": ", ".join(f.component_names),
                })
            st.dataframe(pd.DataFrame(summary_data), use_container_width=True)

            st.markdown("### Component Weights")
            selected_factor = st.selectbox(
                "Select Factor for Weight Analysis",
                [f.name for f in factors],
                key="analysis_factor",
            )
            factor = next(f for f in factors if f.name == selected_factor)
            if factor.components:
                weight_df = pd.DataFrame([
                    {"Metric": c.metric_name, "Weight": c.weight, "Transform": c.transform.value, "Direction": c.direction}
                    for c in factor.components
                ])
                st.dataframe(weight_df, use_container_width=True)
                st.bar_chart(weight_df.set_index("Metric")["Weight"])



render()
