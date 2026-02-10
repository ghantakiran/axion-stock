---
name: social-intelligence
description: Social media signal extraction, influencer tracking, and social signal backtesting. Covers crawling posts from Twitter/X, Reddit, Discord, Telegram, and WhatsApp; scoring signals with multi-factor composite (sentiment, engagement, velocity, freshness, credibility); tracking influencer accuracy; and backtesting social signals against historical price data.
metadata:
  author: axion-platform
  version: "1.0"
---

# Social Intelligence

## When to use this skill

Use this skill when you need to:
- Crawl social media platforms for stock-related posts
- Score social signals with a multi-factor composite (0-100)
- Track influencer prediction accuracy and impact
- Detect volume anomalies in social mention data
- Correlate social signals with forward price returns
- Backtest social trading strategies against historical prices
- Generate actionable trading signals from social media data
- Archive social signals for later replay and validation

## Step-by-step instructions

### 1. Crawl social media posts

```python
from src.social_crawler import (
    FeedAggregator, TwitterCrawler, RedditCrawler,
    DiscordCrawler, TelegramCrawler, SocialCrawlerBridge,
    CrawlConfig, PlatformType,
)

# Create crawlers with config
twitter = TwitterCrawler(CrawlConfig(
    platform=PlatformType.TWITTER,
    keywords=["stock", "trading", "bullish", "NVDA", "AAPL"],
    poll_interval=60.0,
    max_posts_per_poll=100,
    demo_mode=True,  # Uses simulated data
))

reddit = RedditCrawler(CrawlConfig(
    platform=PlatformType.REDDIT,
    subreddits=["wallstreetbets", "stocks", "investing"],
    min_engagement=5,
))

discord = DiscordCrawler(CrawlConfig(
    platform=PlatformType.DISCORD,
    channels=["trading-signals", "stock-picks"],
))

# Aggregate all crawlers
agg = FeedAggregator()
agg.add_crawler(twitter)
agg.add_crawler(reddit)
agg.add_crawler(discord)

await agg.connect_all()
feed = await agg.crawl_all()  # Returns AggregatedFeed

print(f"Total posts: {feed.total_posts}")
print(f"Tickers found: {feed.all_tickers}")

# Bridge to sentiment pipeline (converts to SocialPost objects)
bridge = SocialCrawlerBridge()
result = bridge.process_feed(feed)
print(f"Trending: {result.trending}")
```

### 2. Score social signals

```python
from src.social_intelligence import SignalScorer, ScoredTicker, SignalStrength

scorer = SignalScorer()

# Score from raw social posts
scored: list[ScoredTicker] = scorer.score_posts(
    posts=social_posts,
    mention_baselines={"NVDA": 50.0, "AAPL": 80.0},  # Historical avg mentions
)

for ticker in scored[:10]:
    print(f"{ticker.symbol}: score={ticker.score:.1f} "
          f"({ticker.strength.value}), direction={ticker.direction}")
    print(f"  Sentiment: {ticker.sentiment_score:.2f}")
    print(f"  Engagement: {ticker.engagement_score:.2f}")
    print(f"  Velocity: {ticker.velocity_score:.2f}")
    print(f"  Freshness: {ticker.freshness_score:.2f}")
    print(f"  Credibility: {ticker.credibility_score:.2f}")
    print(f"  Platforms: {ticker.platforms}")

# Score from pre-aggregated TickerMention objects
from src.sentiment.social import SocialMediaMonitor
monitor = SocialMediaMonitor()
mentions = monitor.process_posts(posts)
scored_from_mentions = scorer.score_mentions(mentions, mention_baselines)
```

Signal strength categories (thresholds configurable):
- **very_strong**: score >= 80
- **strong**: score >= 60
- **moderate**: score >= 40
- **weak**: score >= 20
- **noise**: score < 20

### 3. Track influencers

```python
from src.social_intelligence import (
    InfluencerTracker, InfluencerProfile, InfluencerSignal,
)

tracker = InfluencerTracker()

# Build profiles from posts
updated_count = tracker.process_posts(social_posts)
print(f"Updated {updated_count} influencer profiles")

# Get top influencers by impact score
top: list[InfluencerProfile] = tracker.get_top_influencers(n=10)
for inf in top:
    print(f"{inf.author_id} ({inf.platform}): "
          f"tier={inf.tier}, impact={inf.impact_score:.2f}, "
          f"accuracy={inf.accuracy_rate:.0%}, "
          f"upvotes={inf.total_upvotes}")

# Extract signals from influencer posts
signals: list[InfluencerSignal] = tracker.get_influencer_signals(social_posts)
for sig in signals[:5]:
    print(f"{sig.author_id} -> {sig.symbol}: {sig.direction} "
          f"(confidence={sig.confidence:.2f}, tier={sig.tier})")

# Record prediction outcomes for accuracy tracking
tracker.record_prediction(platform="reddit", author="whale_trader", was_correct=True)

# Look up specific influencer
profile = tracker.get_profile("twitter", "elonmusk")
```

Influencer tiers:
- **mega**: >= 10,000 total upvotes
- **macro**: >= 5,000 total upvotes
- **micro**: >= 1,000 total upvotes
- **nano**: < 1,000 total upvotes

Impact score = 40% reach + 40% accuracy + 20% consistency.

### 4. Detect volume anomalies

```python
from src.social_intelligence import VolumeAnalyzer, VolumeAnomaly

analyzer = VolumeAnalyzer()
anomalies: list[VolumeAnomaly] = analyzer.detect_anomalies(mention_history)

for a in anomalies:
    print(f"{a.ticker}: {a.current_count} mentions "
          f"(baseline: {a.baseline_avg:.0f}, ratio: {a.spike_ratio:.1f}x)")
```

### 5. Cross-platform correlation

```python
from src.social_intelligence import CrossPlatformCorrelator, PlatformConsensus

correlator = CrossPlatformCorrelator()
consensus: PlatformConsensus = correlator.analyze(
    symbol="NVDA",
    platform_scores={"twitter": 0.7, "reddit": 0.6, "discord": 0.8},
)
print(f"Consensus: {consensus.consensus_score:.2f}")
print(f"Agreement: {consensus.agreement:.2f}")
```

### 6. Generate trading signals

```python
from src.social_intelligence import (
    SocialSignalGenerator, SocialTradingSignal, IntelligenceReport,
)

generator = SocialSignalGenerator()
signals: list[SocialTradingSignal] = generator.generate(
    scored_tickers=scored,
    anomalies=anomalies,
)

for sig in signals:
    print(f"{sig.symbol}: action={sig.action.value}, "
          f"score={sig.composite_score:.1f}, "
          f"confidence={sig.confidence:.2f}")
```

### 7. Backtest social signals

```python
from src.social_backtester import (
    SignalArchive, ArchivedSignal, OutcomeValidator,
    ValidationReport, CorrelationAnalyzer, LagAnalysis,
    SocialSignalStrategy, SocialBacktestRunner, StrategyConfig,
)

# Step 1: Archive signals
archive = SignalArchive()
archive.add(ArchivedSignal(
    ticker="NVDA", composite_score=75.0,
    direction="bullish", action="buy",
    sentiment_avg=0.7, platform_count=3,
    mention_count=500, confidence=0.85,
))
archive.add_batch(more_signals)

# Query archived signals
nvda_signals = archive.get_signals(ticker="NVDA", start=start_date, end=end_date)
stats = archive.get_stats()
print(f"Total: {stats.total}, Avg score: {stats.avg_score:.1f}")

# Step 2: Validate against prices
validator = OutcomeValidator()
report: ValidationReport = validator.validate(
    signals=list(archive.replay()),
    price_data={"NVDA": nvda_price_df, "AAPL": aapl_price_df},
)

print(f"Hit rates: {report.hit_rates}")        # {"1d": 0.55, "5d": 0.62, "30d": 0.58}
print(f"High-score hit rate: {report.high_score_hit_rate:.1%}")
print(f"Low-score hit rate: {report.low_score_hit_rate:.1%}")
print(f"Per-ticker rates: {report.per_ticker_rates}")
print(f"Return by direction: {report.avg_return_by_direction}")

# Step 3: Lag correlation analysis
corr_analyzer = CorrelationAnalyzer()
lag_analysis: LagAnalysis = corr_analyzer.analyze(
    ticker="NVDA", signals=nvda_signals, prices=nvda_price_df,
)
print(f"Optimal lag: {lag_analysis.optimal_lag} days")
print(f"Optimal correlation: {lag_analysis.optimal_correlation:.3f}")

# Step 4: Run backtest strategy
strategy = SocialSignalStrategy(StrategyConfig(
    min_score=50.0,
    direction_filter="bullish",
    stop_loss_pct=0.02,
    take_profit_pct=0.04,
    max_positions=5,
    position_weight=0.1,
))

result = strategy.run(
    signals=list(archive.replay()),
    prices={"NVDA": nvda_price_df, "AAPL": aapl_price_df},
    initial_capital=100_000.0,
)

print(f"Total return: {result.total_return:.2%}")
print(f"Win rate: {result.win_rate:.1%}")
print(f"Sharpe: {result.sharpe:.2f}")
print(f"Max drawdown: {result.max_drawdown:.2%}")
```

## Key classes and methods

### Crawling (`src/social_crawler/`)
| Class | Source file | Key methods |
|-------|-----------|-------------|
| `TwitterCrawler` | `twitter_crawler.py` | `connect()`, `crawl()`, `disconnect()` |
| `RedditCrawler` | `reddit_crawler.py` | `connect()`, `crawl()`, `disconnect()` |
| `DiscordCrawler` | `discord_crawler.py` | `connect()`, `crawl()`, `disconnect()` |
| `TelegramCrawler` | `telegram_crawler.py` | `connect()`, `crawl()`, `disconnect()` |
| `WhatsAppCrawler` | `whatsapp_crawler.py` | `connect()`, `crawl()`, `disconnect()` |
| `FeedAggregator` | `aggregator.py` | `add_crawler()`, `connect_all()`, `crawl_all()` |
| `SocialCrawlerBridge` | `bridge.py` | `process_feed(feed)` -> `BridgeResult` |

All crawlers implement `CrawlerProtocol`: `connect()`, `crawl()`, `disconnect()`, `is_connected()`.

### Scoring (`src/social_intelligence/scorer.py`)
- `SignalScorer.score_posts(posts, mention_baselines)` -> `list[ScoredTicker]`
- `SignalScorer.score_mentions(mentions, mention_baselines)` -> `list[ScoredTicker]`
- Composite = sentiment (30%) + engagement (20%) + velocity (20%) + freshness (15%) + credibility (15%)

### Influencer tracking (`src/social_intelligence/influencer.py`)
- `InfluencerTracker.process_posts(posts)` -> `int`
- `InfluencerTracker.get_influencer_signals(posts)` -> `list[InfluencerSignal]`
- `InfluencerTracker.get_top_influencers(n)` -> `list[InfluencerProfile]`
- `InfluencerTracker.record_prediction(platform, author, was_correct)` -> `None`

### Backtesting (`src/social_backtester/`)
- `SignalArchive` -- stores/replays `ArchivedSignal` objects
- `OutcomeValidator.validate(signals, price_data)` -> `ValidationReport`
- `CorrelationAnalyzer.analyze(ticker, signals, prices)` -> `LagAnalysis`
- `SocialSignalStrategy.run(signals, prices, initial_capital)` -> `SocialBacktestResult`

### Utilities (`src/social_crawler/base.py`)
- `extract_tickers(text)` -> `list[str]` -- multi-strategy ticker extraction
- `estimate_sentiment(text)` -> `float` -- lightweight keyword-based sentiment

## Common patterns

### Ticker extraction strategies
The `extract_tickers()` function uses three strategies in priority order:
1. **Cashtags** (`$AAPL`) -- highest confidence
2. **Known ticker matching** against a curated set of 100+ tickers
3. **All-caps words** (3+ chars, not in common word exclusion list) -- lowest confidence

### Signal scoring factors
| Factor | Weight | Description |
|--------|--------|-------------|
| Sentiment | 30% | Absolute value of avg sentiment, amplified |
| Engagement | 20% | Normalized upvotes (60%) + comments (40%) |
| Velocity | 20% | Log-scaled mention count vs baseline |
| Freshness | 15% | Time-decay with 6-hour half-life |
| Credibility | 15% | Platform reliability (Twitter 0.70, Reddit 0.65, etc.) |

### Backtest validation horizons
The `OutcomeValidator` measures forward returns at 1-day, 5-day, 10-day, and
30-day horizons. It reports directional hit rates (did the signal predict the
correct direction?) and separates high-score (>= 50) vs low-score (< 50)
signal performance.

### Archival and replay
`SignalArchive.replay()` yields signals in chronological order, suitable for
feeding into `SocialSignalStrategy.run()` or `OutcomeValidator.validate()`.
Use `get_signals(ticker, start, end)` for filtered queries.

## See Also
- **sentiment-analysis** — Social signals as one input to multi-source sentiment fusion
- **trading-signal-generation** — Social conviction scores feed into signal generation pipeline
- **backtesting-strategies** — Social signal backtester validates historical social signal accuracy
