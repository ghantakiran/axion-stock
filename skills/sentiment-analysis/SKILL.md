---
name: sentiment-analysis
description: Multi-source sentiment scoring for stocks using news NLP (FinBERT), social media monitoring, insider trading signals, analyst consensus, and LLM-powered aspect extraction. Produces composite sentiment scores from 6 sources with adaptive fusion, conflict detection, and source reliability tracking. Use for sentiment-driven screening, regime detection, or factor model integration.
metadata:
  author: axion-platform
  version: "1.0"
---

# Sentiment Analysis

## When to use this skill

Use this skill when you need to:
- Score news article sentiment (FinBERT or keyword fallback)
- Monitor social media for stock mentions and trending tickers
- Compute composite sentiment from multiple sources (news, social, insider, analyst, earnings, options)
- Fuse sentiment signals with conflict detection and reliability tracking
- Use LLM providers (Claude, GPT, Gemini) for nuanced financial sentiment
- Extract aspect-level sentiment (e.g., bullish on revenue, bearish on margins)
- Detect market sentiment regime (extreme_bullish to extreme_bearish)
- Generate cross-sectional sentiment factor scores for the factor model

## Step-by-step instructions

### 1. News sentiment analysis

```python
from src.sentiment.news import NewsSentimentEngine, Article, SentimentScore

engine = NewsSentimentEngine()

article = Article(
    title="Apple beats Q4 estimates with record iPhone revenue",
    summary="Apple reported EPS of $2.18 vs $2.10 expected, driven by strong iPhone demand.",
    source="reuters",
    published_at="2025-01-25T16:30:00",
    symbols=["AAPL"],
)

score: SentimentScore = engine.score_article(article)
print(f"Sentiment: {score.sentiment}")    # positive, negative, neutral
print(f"Score: {score.score:.2f}")        # -1 to +1
print(f"Confidence: {score.confidence:.2f}")
print(f"Topic: {score.topic}")            # earnings, merger_acquisition, regulatory, etc.
print(f"Symbols: {score.symbols}")

# Score raw text directly
result = engine.score_text("NVIDIA stock surges on AI demand outlook")
# Returns: {"label": "positive", "score": 0.85, "confidence": 0.92}

# Aggregate multiple scores with time-decay weighting
aggregate = engine.aggregate_sentiment(scores_list, window_hours=24)
# Returns: float between -1 and +1

# Extract tickers from text
tickers = engine.extract_tickers("$AAPL and MSFT are leading the rally")
# Returns: ["AAPL", "MSFT"]

# Classify topic
topic = engine.classify_topic("Fed raises interest rates by 25 basis points")
# Returns: "macro"
```

### 2. Social media sentiment monitoring

```python
from src.sentiment.social import (
    SocialMediaMonitor, SocialPost, TickerMention,
    TrendingAlert, SocialSentimentSummary,
)

monitor = SocialMediaMonitor()

# Create posts (from crawlers or manual)
posts = [
    SocialPost(
        text="NVDA to the moon! AI is unstoppable",
        source="reddit", author="user123",
        upvotes=500, comments=120,
        sentiment=0.8, tickers=["NVDA"],
    ),
    SocialPost(
        text="$AAPL looking weak after earnings miss",
        source="twitter", author="analyst_x",
        upvotes=200, comments=45,
        sentiment=-0.6, tickers=["AAPL"],
    ),
]

# Process posts into ticker mentions
mentions: dict[str, TickerMention] = monitor.process_posts(posts)
for symbol, m in mentions.items():
    print(f"{symbol}: {m.count} mentions, sentiment={m.avg_sentiment:.2f}, "
          f"engagement={m.engagement}")

# Detect trending tickers
trending: list[TrendingAlert] = monitor.detect_trending(
    current_mentions={"NVDA": 500, "AAPL": 100},
    historical_avg={"NVDA": 50, "AAPL": 80},
)
# Spike ratio = current / historical_avg; triggers at 3x default

# Get symbol-level summary
summary: SocialSentimentSummary = monitor.get_symbol_summary("NVDA", posts)
print(f"Reddit: {summary.reddit_sentiment:.2f} ({summary.reddit_mentions} mentions)")
print(f"Composite: {summary.composite_sentiment:.2f}")
print(f"Bullish %: {summary.bullish_pct:.0%}")
print(f"Trending: {summary.is_trending}")

# Rank tickers by buzz score (mentions * log(engagement))
ranked: list[TickerMention] = monitor.rank_by_buzz(mentions, top_n=20)
```

### 3. Composite sentiment scoring

```python
from src.sentiment.composite import SentimentComposite, SentimentBreakdown

composite = SentimentComposite()

# Compute composite from available sources (-1 to +1 each, None = unavailable)
breakdown: SentimentBreakdown = composite.compute("AAPL", {
    "news_sentiment": 0.6,
    "social_sentiment": 0.3,
    "insider_signal": 0.2,
    "analyst_revision": 0.5,
    "earnings_tone": None,      # Unavailable sources are skipped
    "options_flow": None,
})

print(f"Composite: {breakdown.composite_score:.2f}")
print(f"Normalized (0-1): {breakdown.composite_normalized:.2f}")
print(f"Confidence: {breakdown.confidence}")  # low, medium, high
print(f"Sources used: {breakdown.sources_available}")

# Batch compute for multiple symbols
all_breakdowns = composite.compute_batch({
    "AAPL": {"news_sentiment": 0.6, "social_sentiment": 0.3},
    "MSFT": {"news_sentiment": 0.4, "analyst_revision": 0.7},
    "TSLA": {"news_sentiment": -0.3, "social_sentiment": 0.8},
})

# Rank symbols by composite sentiment
df = composite.rank_symbols(all_breakdowns)

# Convert to factor model score (cross-sectional rank, 0-1)
factor_scores = composite.compute_factor_score(all_breakdowns)

# Detect market sentiment regime
regime = composite.get_sentiment_regime(all_breakdowns)
print(f"Regime: {regime['regime']}")  # extreme_bullish, bullish, neutral, bearish, extreme_bearish
print(f"Avg score: {regime['avg_score']:.2f}, Breadth: {regime['breadth']:.0%}")
```

### 4. Multi-source sentiment fusion

```python
from src.sentiment.fusion import (
    SentimentFusionEngine, SourceSignal, FusionResult,
)

fusion = SentimentFusionEngine(
    min_sources=2,
    conflict_penalty=0.3,
)

signals = [
    SourceSignal(source="news", score=0.6, confidence=0.9, symbol="AAPL"),
    SourceSignal(source="social", score=0.3, confidence=0.6, symbol="AAPL"),
    SourceSignal(source="insider", score=-0.2, confidence=0.8, symbol="AAPL"),
    SourceSignal(source="analyst", score=0.5, confidence=0.85, symbol="AAPL"),
]

result: FusionResult = fusion.fuse(signals, symbol="AAPL")

print(f"Fused score: {result.fused_score:.3f}")
print(f"Confidence: {result.fused_confidence:.3f}")
print(f"Label: {result.sentiment_label}")        # bullish, mildly_bullish, neutral, etc.
print(f"Agreement: {result.agreement_ratio:.2f}")
print(f"Conflict: {result.conflict_level:.2f}")
print(f"High conviction: {result.is_high_conviction}")
print(f"Dominant source: {result.dominant_source}")
print(f"Contributions: {result.source_contributions}")

# Update source reliability over time
fusion.update_reliability("news", predicted_direction=0.6, actual_direction=0.3)
reliability = fusion.get_reliability("news")
print(f"News hit rate: {reliability.hit_rate:.2f}")

# Compare fusion results across symbols
comparison = fusion.compare_fusions([result_aapl, result_msft, result_tsla])
print(f"Most bullish: {comparison.most_bullish}")
print(f"Highest conviction: {comparison.highest_conviction}")
```

### 5. LLM-powered sentiment analysis

```python
from src.llm_sentiment import LLMSentimentAnalyzer, LLMSentimentResult

analyzer = LLMSentimentAnalyzer()

result: LLMSentimentResult = await analyzer.analyze(
    "Apple reported record Q4 revenue but warned about China weakness. "
    "iPhone demand exceeded expectations while Mac sales declined 5%."
)

print(f"Sentiment: {result.sentiment}")    # bullish, bearish, neutral, mixed
print(f"Score: {result.score:.2f}")
print(f"Confidence: {result.confidence:.2f}")
print(f"Reasoning: {result.reasoning}")
print(f"Themes: {result.themes}")
print(f"Tickers: {result.tickers}")
print(f"Urgency: {result.urgency}")        # low, medium, high

# Aspect-level extraction
from src.llm_sentiment import AspectExtractor, AspectReport

extractor = AspectExtractor()
report: AspectReport = await extractor.extract(text)
for aspect in report.aspects:
    print(f"  {aspect.category}: {aspect.sentiment} ({aspect.score:.2f})")
```

## Key classes and methods

### `NewsSentimentEngine` (`src/sentiment/news.py`)
- `score_article(article)` -> `SentimentScore`
- `score_text(text)` -> `dict` with label, score, confidence
- `aggregate_sentiment(scores, window_hours)` -> `float`
- `extract_tickers(text)` -> `list[str]`
- `classify_topic(text)` -> `str`
- Uses FinBERT (`ProsusAI/finbert`) when transformers is installed; keyword fallback otherwise

### `SocialMediaMonitor` (`src/sentiment/social.py`)
- `process_posts(posts)` -> `dict[str, TickerMention]`
- `detect_trending(current_mentions, historical_avg)` -> `list[TrendingAlert]`
- `detect_mention_spike(mention_timeseries)` -> `bool`
- `get_symbol_summary(symbol, posts, historical_avg_mentions)` -> `SocialSentimentSummary`
- `rank_by_buzz(mentions, top_n)` -> `list[TickerMention]`

### `SentimentComposite` (`src/sentiment/composite.py`)
- `compute(symbol, scores)` -> `SentimentBreakdown`
- `compute_batch(scores_by_symbol)` -> `dict[str, SentimentBreakdown]`
- `rank_symbols(breakdowns)` -> `pd.DataFrame`
- `compute_factor_score(breakdowns)` -> `pd.Series`
- `get_sentiment_regime(breakdowns)` -> `dict`

### `SentimentFusionEngine` (`src/sentiment/fusion.py`)
- `fuse(signals, symbol)` -> `FusionResult`
- `update_reliability(source, predicted, actual)` -> `SourceReliability`
- `compare_fusions(results)` -> `FusionComparison`

### `LLMSentimentAnalyzer` (`src/llm_sentiment/analyzer.py`)
- `analyze(text)` -> `LLMSentimentResult`
- `analyze_batch(texts)` -> `list[LLMSentimentResult]`
- Uses multi-model providers via `src/model_providers/`

### Additional modules in `src/sentiment/`
- `InsiderTracker` (`insider.py`) -- insider filing sentiment signals
- `AnalystConsensusTracker` (`analyst.py`) -- analyst rating and revision tracking
- `EarningsCallAnalyzer` (`earnings.py`) -- NLP on earnings call transcripts
- `DecayWeightingEngine` (`decay_weighting.py`) -- time-decay sentiment weighting
- `ConsensusScorer` (`consensus.py`) -- cross-source consensus voting
- `SentimentMomentumTracker` (`momentum.py`) -- sentiment trend and reversal detection

## Common patterns

### Default source weights for composite scoring
```python
# From src/sentiment/fusion.py
DEFAULT_SOURCE_WEIGHTS = {
    "news": 0.25,
    "social": 0.15,
    "insider": 0.20,
    "analyst": 0.20,
    "earnings": 0.10,
    "options": 0.10,
}
```

### Confidence levels
- **Low**: fewer than 3 sources available
- **Medium**: 3-4 sources available
- **High**: 5+ sources available

### Fusion conflict handling
When sources disagree (e.g., news bullish but insider bearish), the fusion
engine measures `conflict_level` (0-1) based on score standard deviation.
High conflict (>0.5) reduces confidence by the `conflict_penalty` factor.
The `has_conflict` property on `FusionResult` flags disagreement.

### High conviction signals
A signal is `is_high_conviction` when `fused_confidence >= 0.7` AND
`agreement_ratio >= 0.6`. These are the strongest composite signals.

### Sentiment regime detection
The `get_sentiment_regime()` method classifies overall market mood:
- `extreme_bullish`: avg > 0.3 and >60% of stocks bullish
- `bullish`: avg > 0.1
- `neutral`: avg between -0.1 and 0.1
- `bearish`: avg < -0.1
- `extreme_bearish`: avg < -0.3

## See Also
- **ml-model-development** — Use sentiment scores as features in ML factor models
- **social-intelligence** — Social media signals as a sentiment source (crawling, scoring)
- **trading-signal-generation** — Sentiment as one of 7 fusion sources in SignalFusion
- **economic-data-analysis** — News and macro sentiment overlap with economic analysis
