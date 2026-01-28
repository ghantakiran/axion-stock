# PRD-07: Social & Sentiment Intelligence

**Priority**: P1 | **Phase**: 4 | **Status**: Draft

---

## Problem Statement

Axion relies entirely on quantitative price/fundamental data. Markets are increasingly driven by narrative, social momentum, and news flow. Retail trading (meme stocks, Reddit communities) can move prices 50%+ in a day. Institutional investors track sentiment as alpha signals. Axion needs a sentiment intelligence layer.

---

## Goals

1. **News sentiment analysis** with real-time NLP scoring
2. **Social media monitoring** (Reddit, Twitter/X, StockTwits)
3. **Insider trading signals** from SEC Form 4 filings
4. **Analyst consensus tracking** with revision momentum
5. **Earnings call NLP** for management tone analysis
6. **Composite sentiment score** integrated into factor model

---

## Detailed Requirements

### R1: News Sentiment Engine

#### R1.1: News Ingestion
| Source | Method | Coverage |
|--------|--------|----------|
| Benzinga | API | Real-time financial news |
| NewsAPI | API | General news, 80K+ sources |
| SEC EDGAR | RSS/API | Filings, 8-K, press releases |
| PR Newswire | API | Corporate press releases |
| Seeking Alpha | RSS | Analysis articles |

#### R1.2: NLP Sentiment Pipeline
```python
class NewsSentimentEngine:
    def __init__(self):
        self.model = pipeline(
            'sentiment-analysis',
            model='ProsusAI/finbert'  # Finance-specific BERT
        )

    async def score_article(self, article: Article) -> SentimentScore:
        # 1. Extract relevant text
        text = article.title + ". " + article.summary

        # 2. FinBERT sentiment classification
        result = self.model(text[:512])
        label = result[0]['label']    # positive/negative/neutral
        confidence = result[0]['score']

        # 3. Entity extraction (which stocks mentioned)
        entities = self._extract_tickers(text)

        # 4. Topic classification
        topic = self._classify_topic(text)  # earnings, M&A, macro, etc.

        return SentimentScore(
            sentiment=label,
            score=self._to_numeric(label, confidence),  # -1 to +1
            confidence=confidence,
            symbols=entities,
            topic=topic,
            source=article.source,
            timestamp=article.published_at,
        )
```

#### R1.3: Aggregate News Sentiment
```python
class NewsAggregator:
    def get_sentiment(self, symbol: str, window: str = '24h') -> float:
        """Aggregate sentiment score for a symbol."""
        articles = self.db.get_articles(symbol, window)

        if not articles:
            return 0.0  # neutral

        # Time-decay weighted average (recent articles weight more)
        weights = np.exp(-self.decay * np.arange(len(articles)))
        scores = [a.score for a in articles]

        # Source credibility weighting
        source_weights = [self.source_credibility[a.source] for a in articles]

        final_weights = weights * source_weights
        return np.average(scores, weights=final_weights)
```

### R2: Social Media Monitoring

#### R2.1: Reddit Integration
- **Subreddits**: r/wallstreetbets, r/stocks, r/investing, r/options, r/stockmarket
- **Metrics**: Mention count, sentiment, upvote velocity, comment engagement
- **Detection**: Emerging tickers trending before mainstream awareness

```python
class RedditMonitor:
    async def scan_subreddit(self, subreddit: str) -> list[TickerMention]:
        """Scan recent posts for ticker mentions and sentiment."""
        posts = await self.reddit.get_hot(subreddit, limit=100)

        mentions = {}
        for post in posts:
            tickers = self._extract_tickers(post.title + post.selftext)
            sentiment = self._analyze_sentiment(post.title + post.selftext)

            for ticker in tickers:
                if ticker not in mentions:
                    mentions[ticker] = TickerMention(symbol=ticker)
                mentions[ticker].count += 1
                mentions[ticker].scores.append(sentiment)
                mentions[ticker].total_upvotes += post.score
                mentions[ticker].total_comments += post.num_comments

        return sorted(mentions.values(),
                       key=lambda x: x.count, reverse=True)
```

#### R2.2: Twitter/X Integration
- Track cashtag mentions ($AAPL, $TSLA)
- Volume of mentions (hourly, daily)
- Sentiment of tweets mentioning each ticker
- Influencer tracking (accounts with >100K followers)
- Breaking news detection (sudden spike in mentions)

#### R2.3: StockTwits Integration
- Bull/Bear sentiment ratio per ticker
- Message volume trends
- Trending tickers list
- Sentiment momentum (improving/declining)

### R3: Insider Trading Signals

#### R3.1: SEC Form 4 Analysis
```python
class InsiderTracker:
    async def get_insider_activity(self, symbol: str) -> InsiderReport:
        """Analyze insider buying/selling patterns."""
        filings = await self.sec.get_form4(symbol, months=6)

        buys = [f for f in filings if f.transaction_type == 'P']
        sells = [f for f in filings if f.transaction_type == 'S']

        return InsiderReport(
            buy_count=len(buys),
            sell_count=len(sells),
            net_shares=sum(f.shares for f in buys) - sum(f.shares for f in sells),
            net_value=sum(f.value for f in buys) - sum(f.value for f in sells),
            cluster_buy=self._detect_cluster(buys),  # 3+ insiders buying in 30 days
            ceo_activity=self._get_ceo_trades(filings),
            insider_score=self._compute_score(filings),  # -1 to +1
        )
```

#### R3.2: Insider Signal Scoring
| Signal | Score | Description |
|--------|-------|-------------|
| Cluster Buying (3+ insiders) | +0.8 | Strong conviction |
| CEO/CFO Purchase | +0.6 | C-suite skin in the game |
| Director Purchase | +0.4 | Board confidence |
| 10b5-1 Plan Sale | -0.1 | Routine, low signal |
| Open Market Sale | -0.3 | Voluntary selling |
| Cluster Selling (3+) | -0.7 | Bearish signal |

### R4: Analyst Consensus

#### R4.1: Consensus Tracking
```python
class AnalystConsensus:
    def get_consensus(self, symbol: str) -> ConsensusReport:
        return ConsensusReport(
            rating=self._aggregate_rating(),  # Strong Buy to Strong Sell
            target_price_mean=mean_target,
            target_price_median=median_target,
            target_price_high=max_target,
            target_price_low=min_target,
            upside_pct=(mean_target - current_price) / current_price,
            num_analysts=count,
            buy_count=buys, hold_count=holds, sell_count=sells,
            revision_momentum=self._revision_trend(),  # upgrades - downgrades
        )
```

#### R4.2: Estimate Revision Momentum
- Track EPS estimate changes over 30/60/90 days
- Up-revisions vs down-revisions ratio
- Magnitude of revisions (% change)
- Revision breadth (% of analysts revising up)
- Post-revision price reaction patterns

### R5: Earnings Call NLP

#### R5.1: Transcript Analysis
```python
class EarningsCallAnalyzer:
    def analyze_transcript(self, symbol: str, quarter: str) -> CallAnalysis:
        transcript = self.data.get_transcript(symbol, quarter)

        return CallAnalysis(
            management_tone=self._analyze_tone(transcript.prepared_remarks),
            qa_sentiment=self._analyze_tone(transcript.qa_section),
            key_topics=self._extract_topics(transcript),
            forward_guidance=self._extract_guidance(transcript),
            uncertainty_words=self._count_uncertainty(transcript),
            confidence_score=self._compute_confidence(transcript),
            compared_to_previous=self._compare_quarters(symbol, quarter),
        )
```

#### R5.2: Tone Metrics
| Metric | Measurement | Signal |
|--------|-------------|--------|
| Positivity Ratio | Positive words / Total words | Higher = bullish |
| Uncertainty Count | "uncertain", "challenging", "risk" | Higher = bearish |
| Forward-Looking | Future tense statements count | More = confident |
| Guidance Direction | Raised / Maintained / Lowered | Direct signal |
| Q&A Defensiveness | Evasive or defensive responses | Higher = concerning |
| Complexity (Fog Index) | Readability of responses | Higher = obfuscating |

### R6: Composite Sentiment Score

#### R6.1: Score Aggregation
```python
class SentimentComposite:
    WEIGHTS = {
        'news_sentiment': 0.25,
        'social_sentiment': 0.15,
        'insider_signal': 0.20,
        'analyst_revision': 0.20,
        'earnings_tone': 0.10,
        'options_flow': 0.10,  # From PRD-06
    }

    def compute(self, symbol: str) -> float:
        scores = {
            'news_sentiment': self.news.get_sentiment(symbol),
            'social_sentiment': self.social.get_sentiment(symbol),
            'insider_signal': self.insider.get_score(symbol),
            'analyst_revision': self.analyst.get_revision_score(symbol),
            'earnings_tone': self.earnings.get_tone_score(symbol),
            'options_flow': self.options.get_flow_score(symbol),
        }

        composite = sum(
            self.WEIGHTS[k] * v
            for k, v in scores.items()
            if v is not None
        )

        # Normalize to 0-1 range
        return (composite + 1) / 2
```

#### R6.2: Integration with Factor Model
The sentiment composite becomes a new factor category in PRD-02's factor engine:
```python
REGIME_WEIGHTS_WITH_SENTIMENT = {
    'bull': {
        'value': 0.10, 'momentum': 0.30, 'quality': 0.10,
        'growth': 0.20, 'volatility': 0.05, 'technical': 0.10,
        'sentiment': 0.15  # NEW
    },
    # ... other regimes
}
```

### R7: Sentiment Dashboard

```
SENTIMENT INTELLIGENCE - AAPL
═══════════════════════════════════════════════════
Overall Sentiment:  ████████░░  0.72 (Bullish)

News (24h):         ████████░░  0.68  (14 articles, 71% positive)
Social Media:       █████████░  0.85  (Reddit trending, WSB buzz)
Insider Activity:   ██████░░░░  0.55  (1 director buy, no sells)
Analyst Revisions:  ████████░░  0.74  (3 upgrades this month)
Earnings Tone:      ███████░░░  0.65  (Confident guidance)
Options Flow:       █████████░  0.82  (Unusual call buying)

TRENDING NEWS
├── "Apple Reports Record Services Revenue" (+0.8) - 2h ago
├── "iPhone Sales Beat Estimates in China" (+0.6) - 5h ago
└── "Apple Expands AI Features Globally" (+0.4) - 8h ago

SOCIAL BUZZ
├── Reddit: 342 mentions (24h), +180% vs avg
├── Twitter: 12,400 cashtag mentions, 68% positive
└── StockTwits: 72% bullish (vs 58% 7-day avg)

INSIDER ACTIVITY (90 days)
├── Tim Cook: No trades
├── Luca Maestri: Sold 40,000 shares (10b5-1 plan)
└── Board Member: Bought 5,000 shares ($890K)
```

---

## Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| NLP Model | FinBERT | Finance-domain fine-tuned BERT |
| Reddit API | PRAW | Official Python Reddit API |
| Twitter API | tweepy | Standard Twitter/X access |
| SEC Filings | sec-edgar-downloader | Form 4, 8-K, 10-Q |
| Transcripts | Financial Modeling Prep | Earnings call transcripts |
| Message Queue | Kafka | Real-time event processing |
| Sentiment DB | PostgreSQL + JSONB | Flexible schema for varied sources |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| News sentiment accuracy | >75% vs human labeling |
| Social signal lead time | >2 hours before price move |
| Insider signal predictiveness | >60% accuracy (6-month forward) |
| Meme stock early detection | Detect within 4 hours of emergence |
| Sentiment factor IC | >0.03 (incremental to existing factors) |

---

## Dependencies

- PRD-01 (Data Infrastructure) for data storage and streaming
- PRD-02 (Factor Engine) for sentiment factor integration
- PRD-05 (ML Prediction) for NLP model serving
- Reddit API access (free tier)
- Twitter/X API access (Basic: $100/mo)
- News API subscription ($449/mo for business tier)

---

*Owner: Alternative Data Lead*
*Last Updated: January 2026*
