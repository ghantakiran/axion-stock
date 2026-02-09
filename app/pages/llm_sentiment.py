"""LLM Sentiment Engine Dashboard (PRD-151).

Four-tab Streamlit dashboard for AI-powered sentiment analysis,
aspect extraction, entity resolution, and sentiment prediction.
"""

import streamlit as st
from datetime import datetime, timedelta, timezone

from src.llm_sentiment.analyzer import (
    AnalyzerConfig,
    LLMSentimentAnalyzer,
    LLMSentimentResult,
)
from src.llm_sentiment.aspects import AspectExtractor, AspectReport
from src.llm_sentiment.entity import EntityResolver, EntityReport
from src.llm_sentiment.predictor import (
    ForecastHorizon,
    PredictorConfig,
    SentimentPredictor,
)

st.header("LLM Sentiment Engine")
st.caption("PRD-151 · AI-powered financial sentiment with aspect & entity analysis")

tab1, tab2, tab3, tab4 = st.tabs([
    "Sentiment Analysis", "Aspect Extraction", "Entity Resolution", "Prediction",
])

# ── Tab 1: Core Sentiment Analysis ────────────────────────────────────

with tab1:
    st.subheader("AI Sentiment Analysis")

    text_input = st.text_area(
        "Enter financial text to analyze",
        value="NVDA beats Q4 earnings expectations with 40% revenue growth driven by AI demand",
        height=100,
    )
    context = st.text_input("Context (optional)", placeholder="e.g. earnings call, news headline")

    if st.button("Analyze Sentiment", key="analyze"):
        analyzer = LLMSentimentAnalyzer(
            config=AnalyzerConfig(fallback_to_keywords=True)
        )
        result = analyzer.analyze(text_input, context=context)

        sentiment_colors = {
            "bullish": "🟢", "bearish": "🔴",
            "neutral": "⚪", "mixed": "🟡",
        }
        icon = sentiment_colors.get(result.sentiment, "⚪")
        st.markdown(f"### {icon} {result.sentiment.upper()}")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Score", f"{result.score:+.2f}")
        m2.metric("Confidence", f"{result.confidence:.0%}")
        m3.metric("Urgency", result.urgency.upper())
        m4.metric("Horizon", result.time_horizon.upper())

        if result.reasoning:
            st.info(f"**Reasoning:** {result.reasoning}")

        if result.themes:
            st.write(f"**Themes:** {', '.join(result.themes)}")

        if result.tickers:
            st.write(f"**Tickers:** {', '.join(result.tickers)}")

        st.write(f"**Model:** {result.model_used}")
        st.write(f"**Actionable:** {'Yes' if result.is_actionable else 'No'}")

    st.divider()
    st.subheader("Batch Analysis")

    batch_text = st.text_area(
        "Enter multiple texts (one per line)",
        value="AAPL revenue up 15% on strong iPhone demand\nTSLA recalls 500K vehicles over safety concerns\nMSFT Azure growth slows to 28%",
        height=100,
        key="batch_input",
    )

    if st.button("Analyze Batch", key="batch"):
        lines = [l.strip() for l in batch_text.split("\n") if l.strip()]
        analyzer = LLMSentimentAnalyzer(
            config=AnalyzerConfig(fallback_to_keywords=True)
        )
        results = analyzer.analyze_batch(lines)

        for text, result in zip(lines, results):
            icon = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪", "mixed": "🟡"}.get(result.sentiment, "⚪")
            st.write(f"{icon} **{result.sentiment}** ({result.score:+.2f}) — {text[:80]}")

# ── Tab 2: Aspect Extraction ──────────────────────────────────────────

with tab2:
    st.subheader("Aspect-Level Sentiment")

    aspect_text = st.text_area(
        "Enter text for aspect extraction",
        value="Apple posted record iPhone revenue but management guidance was cautious amid regulatory headwinds in the EU",
        height=100,
        key="aspect_input",
    )

    if st.button("Extract Aspects", key="aspects"):
        extractor = AspectExtractor()
        report = extractor.extract(aspect_text)

        st.markdown(f"### Overall Score: {report.overall_score:+.2f}")
        st.write(f"**Dominant Aspect:** {report.dominant_aspect}")
        st.write(f"**Conflicting Signals:** {'Yes' if report.conflicting_aspects else 'No'}")

        if report.aspects:
            for a in report.aspects:
                icon = "🟢" if a["score"] > 0 else ("🔴" if a["score"] < 0 else "⚪")
                st.write(f"  {icon} **{a['category'].title()}**: {a['sentiment']} ({a['score']:+.2f})")
                if a.get("evidence"):
                    st.caption(f"    Evidence: {a['evidence']}")

# ── Tab 3: Entity Resolution ─────────────────────────────────────────

with tab3:
    st.subheader("Entity-Level Sentiment")

    entity_text = st.text_area(
        "Enter text for entity resolution",
        value="Apple posted record revenue while Google faces antitrust probe and Tesla's Elon Musk plans new factory",
        height=100,
        key="entity_input",
    )

    if st.button("Resolve Entities", key="entities"):
        resolver = EntityResolver()
        report = resolver.resolve(entity_text)

        st.write(f"**Entities Found:** {report.entity_count}")

        for e in report.entities:
            icon = "🟢" if e.score > 0 else ("🔴" if e.score < 0 else "⚪")
            ticker_str = f" ({e.ticker})" if e.ticker else ""
            st.write(f"  {icon} **{e.name}{ticker_str}** [{e.entity_type}]: {e.sentiment} ({e.score:+.2f})")

        if report.relationships:
            st.write("**Relationships:**")
            for r in report.relationships:
                st.write(f"  {r['entity1']} ↔ {r['entity2']}: {r['relation']}")

# ── Tab 4: Sentiment Prediction ───────────────────────────────────────

with tab4:
    st.subheader("Sentiment Momentum & Prediction")

    predictor = SentimentPredictor()

    # Demo data: trending positive for AAPL, negative for TSLA
    now = datetime.now(timezone.utc)
    for i, score in enumerate([0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6]):
        predictor.add_observation("AAPL", score, now - timedelta(hours=28 - i * 4))
    for i, score in enumerate([0.3, 0.2, 0.1, 0.0, -0.1, -0.2, -0.3]):
        predictor.add_observation("TSLA", score, now - timedelta(hours=28 - i * 4))
    for i, score in enumerate([0.4, 0.41, 0.39, 0.4, 0.41, 0.4, 0.4]):
        predictor.add_observation("MSFT", score, now - timedelta(hours=28 - i * 4))

    horizon = st.selectbox("Forecast Horizon", [h.value for h in ForecastHorizon])
    horizon_enum = {h.value: h for h in ForecastHorizon}[horizon]

    report = predictor.predict_all(horizon_enum)

    for f in report.forecasts:
        dir_icon = {"improving": "📈", "deteriorating": "📉", "stable": "➡️"}.get(f.predicted_direction, "➡️")
        st.markdown(f"### {f.ticker} {dir_icon} {f.predicted_direction.title()}")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Current", f"{f.current_score:+.2f}")
        m2.metric("Predicted", f"{f.predicted_score:+.2f}")
        m3.metric("Momentum", f"{f.momentum:+.4f}")
        m4.metric("Reversal Prob", f"{f.reversal_probability:.0%}")
