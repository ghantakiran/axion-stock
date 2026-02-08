"""ESG Scoring & Impact Dashboard."""

import streamlit as st

from src.esg import (
    ESGScorer,
    ImpactTracker,
    ESGConfig,
    ESGPillar,
    ImpactCategory,
    PillarScore,
    CarbonMetrics,
)

try:
    st.set_page_config(page_title="ESG Scoring", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("ESG Scoring & Impact Tracking")


@st.cache_resource
def get_scorer():
    scorer = ESGScorer()
    # Sample data
    scorer.score_security("AAPL", environmental=78, social=72, governance=85, sector="Technology")
    scorer.score_security("MSFT", environmental=82, social=80, governance=88, sector="Technology")
    scorer.score_security("XOM", environmental=35, social=55, governance=60, sector="Energy",
                         controversies=["Oil spill incident"])
    scorer.score_security("JNJ", environmental=65, social=70, governance=75, sector="Healthcare")
    scorer.score_security("JPM", environmental=55, social=62, governance=70, sector="Financials")

    scorer.set_carbon_metrics("AAPL", CarbonMetrics(
        carbon_intensity=45, scope1_emissions=20, scope2_emissions=25,
        renewable_energy_pct=85, net_zero_target_year=2030,
    ))
    scorer.set_carbon_metrics("XOM", CarbonMetrics(
        carbon_intensity=850, scope1_emissions=400, scope2_emissions=200, scope3_emissions=800,
        total_emissions=1400, renewable_energy_pct=5,
    ))

    return scorer


@st.cache_resource
def get_tracker():
    tracker = ImpactTracker()
    for sym, carbon, renewable in [
        ("AAPL", 45, 85), ("MSFT", 35, 90), ("XOM", 850, 5),
        ("JNJ", 120, 40), ("JPM", 95, 30),
    ]:
        tracker.record_metric(sym, ImpactCategory.CARBON_FOOTPRINT, carbon)
        tracker.record_metric(sym, ImpactCategory.RENEWABLE_ENERGY, renewable)
        tracker.record_metric(sym, ImpactCategory.BOARD_INDEPENDENCE, 65 + hash(sym) % 20)
    return tracker


scorer = get_scorer()
tracker = get_tracker()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Portfolio ESG", "Security Scores", "Carbon Metrics",
    "Impact Tracking", "ESG Screening",
])

with tab1:
    st.subheader("Portfolio ESG Summary")
    holdings = {"AAPL": 0.30, "MSFT": 0.25, "XOM": 0.10, "JNJ": 0.20, "JPM": 0.15}
    summary = scorer.portfolio_summary(holdings)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Composite ESG", f"{summary.weighted_esg_score:.1f}")
    col2.metric("Environmental", f"{summary.weighted_e_score:.1f}")
    col3.metric("Social", f"{summary.weighted_s_score:.1f}")
    col4.metric("Governance", f"{summary.weighted_g_score:.1f}")

    st.metric("Portfolio Rating", summary.portfolio_rating.value)
    st.metric("Coverage", f"{summary.coverage_pct}%")

    if summary.best_in_class:
        st.write("**Best in Class:**", ", ".join(summary.best_in_class))
    if summary.worst_in_class:
        st.write("**Needs Improvement:**", ", ".join(summary.worst_in_class))

with tab2:
    st.subheader("Individual Security ESG Scores")
    all_scores = scorer.get_all_scores()
    for score in sorted(all_scores, key=lambda x: x.composite_score, reverse=True):
        with st.expander(f"{score.symbol} — {score.rating.value} ({score.composite_score:.1f})"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Environmental", f"{score.environmental_score:.1f}")
            c2.metric("Social", f"{score.social_score:.1f}")
            c3.metric("Governance", f"{score.governance_score:.1f}")
            if score.controversies:
                st.warning(f"Controversies: {', '.join(score.controversies)}")

with tab3:
    st.subheader("Carbon Metrics")
    for sym in ["AAPL", "MSFT", "XOM", "JNJ", "JPM"]:
        carbon = scorer.get_carbon_metrics(sym)
        if carbon:
            with st.expander(f"{sym} — {carbon.carbon_intensity:.0f} tCO2e/$M"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Scope 1", f"{carbon.scope1_emissions:.0f}")
                c2.metric("Scope 2", f"{carbon.scope2_emissions:.0f}")
                c3.metric("Renewable %", f"{carbon.renewable_energy_pct:.0f}%")

with tab4:
    st.subheader("Impact Metrics")
    portfolio_impact = tracker.portfolio_impact(holdings)
    for category, metric in portfolio_impact.items():
        st.metric(
            category.value.replace("_", " ").title(),
            f"{metric.value:.1f} {metric.unit}",
            delta=f"vs benchmark: {metric.benchmark}" if metric.benchmark else None,
        )

with tab5:
    st.subheader("ESG Screening")
    config = ESGConfig(exclude_sin_stocks=True, exclude_fossil_fuels=True, exclude_weapons=True)
    screen_scorer = ESGScorer(config)

    # Copy scores
    for sym in ["AAPL", "MSFT", "XOM", "JNJ", "JPM"]:
        s = scorer.get_score(sym)
        if s:
            screen_scorer.score_security(
                sym, s.environmental_score, s.social_score, s.governance_score,
                sector=s.sector, controversies=s.controversies,
            )

    test_cases = [
        ("AAPL", "technology"), ("XOM", "oil_gas"),
        ("PM", "tobacco"), ("JPM", "financials"),
    ]
    for sym, industry in test_cases:
        result = screen_scorer.screen_security(sym, industry=industry, min_score=40)
        if result.passed:
            st.success(f"{sym}: Passed ESG screen")
        else:
            st.error(f"{sym}: Failed — {', '.join(result.excluded_reasons)}")
