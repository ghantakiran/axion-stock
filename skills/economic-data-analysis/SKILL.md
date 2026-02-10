---
name: economic-data-analysis
description: >
  Analyze economic data across four Axion platform modules: news (sentiment, earnings, SEC filings),
  economic (calendar, Fed watcher, impact analysis), altdata (satellite, web traffic, social sentiment),
  and macro (indicators, yield curve, regime detection, factor models). Covers real-time news feeds,
  economic event calendars, alternative data scoring, macro regime classification, and yield curve analysis.
metadata:
  author: Axion Platform Team
  version: 1.0.0
---

# Economic Data Analysis Skill

## When to use this skill

Use this skill when you need to:

- Aggregate and filter financial news articles with sentiment analysis
- Track earnings calendars, EPS surprises, and beat/miss statistics
- Monitor economic event calendars (CPI, NFP, FOMC) with impact assessment
- Track Federal Reserve meetings, rate decisions, and market expectations
- Analyze alternative data signals (satellite imagery, web traffic, social sentiment)
- Build composite alternative data scores from multiple sources
- Track economic indicators and compute composite indices
- Analyze yield curves, detect inversions, and fit Nelson-Siegel models
- Detect macro economic regimes (expansion, slowdown, contraction, recovery)
- Build macro factor models with regime-conditional return decomposition

## Step-by-step instructions

### 1. News Feed and Sentiment Analysis

The `src/news/` module provides a news feed manager with built-in keyword-based sentiment scoring,
auto-categorization, and multi-index lookup by symbol and category.

```python
from src.news import (
    NewsFeedManager, NewsArticle, NewsCategory, NewsSource,
    SentimentLabel, EarningsCalendar, EarningsEvent, ReportTime,
)
from datetime import datetime, timezone

# Initialize the news feed manager
news = NewsFeedManager()

# Add articles -- sentiment is auto-computed if not provided
article = NewsArticle(
    headline="Apple beats earnings estimates by 15%",
    summary="Strong iPhone sales drive record revenue quarter",
    symbols=["AAPL"],
    source=NewsSource.REUTERS,
    published_at=datetime.now(timezone.utc),
    is_breaking=True,
)
news.add_article(article)

# Query the feed with filters
articles = news.get_feed(
    symbols=["AAPL"],
    categories=[NewsCategory.EARNINGS],
    min_sentiment=0.2,
    breaking_only=False,
    limit=20,
)

# Convenience methods
breaking = news.get_breaking_news(limit=10)
aapl_news = news.get_for_symbol("AAPL", limit=20)
results = news.search("iPhone revenue", limit=20)

# Sentiment summary for a symbol over the past 7 days
summary = news.get_sentiment_summary(symbol="AAPL", days=7)
# Returns: {"total_articles": 5, "average_sentiment": 0.45,
#           "positive_count": 3, "negative_count": 1, ...}

# Trending symbols by news volume
trending = news.get_trending_symbols(hours=24, limit=10)
```

### 2. Earnings Calendar

Track earnings events, update actuals, and analyze beat/miss patterns.

```python
from src.news import EarningsCalendar, EarningsEvent, ReportTime
from datetime import date

calendar = EarningsCalendar()

# Add an upcoming earnings event
event = EarningsEvent(
    symbol="AAPL",
    company_name="Apple Inc.",
    report_date=date(2026, 1, 30),
    report_time=ReportTime.AFTER_CLOSE,
    fiscal_quarter="Q1 2026",
    eps_estimate=2.10,
    revenue_estimate=124_000_000_000,
)
calendar.add_event(event)

# Query earnings
upcoming = calendar.get_upcoming(days=14)
today_earnings = calendar.get_today()
this_week = calendar.get_this_week()
portfolio_earnings = calendar.get_portfolio_earnings(
    symbols=["AAPL", "MSFT", "GOOGL"], days=30
)

# Update with actual results
calendar.update_actuals(
    event_id=event.event_id,
    eps_actual=2.18,
    revenue_actual=126_000_000_000,
    price_before=185.0,
    price_after=192.0,
)

# Analyze surprises
beats = calendar.get_beats(days=90, min_surprise_pct=5.0)
misses = calendar.get_misses(days=90)
stats = calendar.get_surprise_stats("AAPL")
# Returns: {"beat_rate": 87.5, "avg_surprise_pct": 8.2, ...}
```

### 3. Economic Calendar and Impact Analysis

The `src/economic/` module provides a standalone economic calendar with Fed watcher,
historical release analysis, and market impact estimation.

```python
from src.economic import (
    EconomicCalendar, EconomicEvent, ImpactLevel, EventCategory, Country,
    FedWatcher, FedMeeting, RateExpectation, RateDecision,
    HistoryAnalyzer, HistoricalRelease,
    ImpactAnalyzer, MarketImpact,
    generate_sample_calendar, generate_sample_fed_data,
)
from datetime import date, time

# Create calendar and add events
calendar = EconomicCalendar()
event = EconomicEvent(
    name="Non-Farm Payrolls",
    country=Country.US,
    category=EventCategory.EMPLOYMENT,
    release_date=date(2026, 2, 7),
    release_time=time(8, 30),
    impact=ImpactLevel.HIGH,
    previous=216.0,
    forecast=180.0,
    unit="K",
)
calendar.add_event(event)

# Query calendar views
upcoming = calendar.get_upcoming(days=7, min_impact=ImpactLevel.HIGH)
today = calendar.get_today(country=Country.US)
week_view = calendar.get_week()  # dict[date, list[EconomicEvent]]
month_view = calendar.get_month(2026, 2)
high_impact = calendar.get_high_impact(days=7)

# Record actual release
calendar.record_release(event.event_id, actual=195.0)

# Fed Watcher -- track FOMC meetings and rate expectations
fed = FedWatcher()
meeting = FedMeeting(
    meeting_date=date(2026, 3, 19),
    meeting_type="FOMC",
    rate_before=5.25,
    has_projections=True,
)
fed.add_meeting(meeting)
fed.set_expectations(date(2026, 3, 19), RateExpectation(
    prob_hike_25=5.0, prob_hold=80.0, prob_cut_25=12.0, prob_cut_50=3.0,
    implied_rate=5.22, current_rate=5.25,
))

next_meeting = fed.get_next_meeting()
rate_path = fed.get_rate_path()  # list of implied rates per future meeting

# Historical analysis
history = HistoryAnalyzer()
history.add_release(HistoricalRelease(
    event_name="Non-Farm Payrolls",
    release_date=datetime(2026, 1, 10),
    actual=216.0, forecast=170.0, previous=199.0,
    spx_1h_change=0.35, vix_change=0.8,
))
stats = history.get_stats("Non-Farm Payrolls")
# Returns EventStats with beat_rate, avg_surprise_pct, avg_spx_reaction

# Impact analysis
impact_analyzer = ImpactAnalyzer(history)
impact = impact_analyzer.analyze_event(event)
# Returns MarketImpact with expected_volatility, sector_impacts, pre_event_notes
```

### 4. Alternative Data Signals

The `src/altdata/` module provides satellite imagery analysis, web traffic tracking,
social sentiment aggregation, and composite scoring.

```python
from src.altdata import (
    SatelliteAnalyzer, SatelliteType, SatelliteSignal,
    WebTrafficAnalyzer, WebTrafficSnapshot,
    SocialSentimentAggregator, SocialSentiment,
    AltDataScorer, AltDataComposite, AltDataSignal,
)

# Satellite imagery analysis
sat = SatelliteAnalyzer()
for value in [800, 820, 850, 870, 900, 880, 910]:
    sat.add_observation("WMT", SatelliteType.PARKING_LOT, value)

signal = sat.analyze("WMT", SatelliteType.PARKING_LOT)
# SatelliteSignal with normalized_value, z_score, is_anomaly, trend

all_signals = sat.analyze_all("WMT")  # all satellite types for a symbol

# Web traffic analysis
web = WebTrafficAnalyzer()
web.add_snapshot("SHOP", "shopify.com", visits=500000, bounce_rate=0.35, avg_duration=180.0)
web.add_snapshot("SHOP", "shopify.com", visits=550000, bounce_rate=0.32, avg_duration=195.0)
traffic = web.analyze("SHOP")
# WebTrafficSnapshot with growth_rate, engagement_score, momentum

# Composite scoring from multiple alt data sources
scorer = AltDataScorer()
sat_signal = scorer.score_satellite([signal])
web_signal = scorer.score_web_traffic(traffic)

composite = scorer.composite(
    "WMT",
    satellite_signal=sat_signal,
    web_signal=web_signal,
)
# AltDataComposite with composite score, n_sources, quality, confidence
```

### 5. Macro Regime Analysis

The `src/macro/` module provides economic indicator tracking, yield curve analysis,
regime detection, and macro factor models.

```python
from src.macro import (
    IndicatorTracker, EconomicIndicator, IndicatorSummary, IndicatorType,
    YieldCurveAnalyzer, YieldCurveSnapshot, CurveShape,
    RegimeDetector, RegimeState, RegimeType,
    MacroFactorModel, MacroFactorResult,
)

# Indicator tracking
tracker = IndicatorTracker()
tracker.add_indicators([
    EconomicIndicator(name="ISM PMI", value=52.0, previous=51.0,
                      consensus=51.5, indicator_type=IndicatorType.LEADING),
    EconomicIndicator(name="Industrial Production", value=101.2, previous=100.8,
                      consensus=101.0, indicator_type=IndicatorType.COINCIDENT),
    EconomicIndicator(name="Unemployment Rate", value=3.7, previous=3.8,
                      consensus=3.7, indicator_type=IndicatorType.LAGGING),
])
summary = tracker.summarize()
# IndicatorSummary with composite_index, breadth, leading/coincident/lagging scores

surprises = tracker.get_surprises()  # [(name, surprise_value), ...]

# Yield curve analysis with Nelson-Siegel fitting
curve = YieldCurveAnalyzer()
rates = {"1M": 5.30, "3M": 5.25, "6M": 5.15, "1Y": 4.90,
         "2Y": 4.50, "5Y": 4.20, "10Y": 4.30, "30Y": 4.55}
snapshot = curve.analyze(rates, date="2026-02-09")
# YieldCurveSnapshot with shape (NORMAL/INVERTED/FLAT/HUMPED),
# term_spread, slope, curvature, level, is_inverted, inversion_depth

# Regime detection
detector = RegimeDetector()
regime = detector.detect(
    indicator_summary=summary,
    growth_score=0.3,    # positive = above-trend growth
    inflation_score=-0.2, # negative = below-trend inflation
)
# RegimeState with regime (EXPANSION/SLOWDOWN/CONTRACTION/RECOVERY),
# probability, duration, transition_probs, indicator_consensus

# Macro factor model
factor_model = MacroFactorModel()
result = factor_model.compute_factors(
    factor_series={
        "growth": [0.1, 0.2, 0.15, 0.3, 0.25],
        "inflation": [-0.1, 0.05, -0.05, 0.1, 0.0],
        "rates": [0.0, 0.1, 0.05, 0.15, 0.1],
    },
    regime=RegimeType.EXPANSION,
)
# MacroFactorResult with factor_returns, factor_exposures,
# factor_momentum, dominant_factor, regime_conditional

# Decompose asset returns into factor contributions
import numpy as np
contributions = factor_model.decompose_returns(
    asset_returns=np.array([0.01, -0.005, 0.02, 0.015, -0.01]),
    factor_matrix=np.array([[0.1, -0.1], [0.2, 0.05], [0.15, -0.05],
                            [0.3, 0.1], [0.25, 0.0]]),
)
```

## Key classes and methods

### News Module (`src/news/`)

| Class | Method | Description |
|---|---|---|
| `NewsFeedManager` | `add_article(article)` | Add article with auto-sentiment |
| `NewsFeedManager` | `get_feed(symbols, categories, min_sentiment, ...)` | Filtered news feed |
| `NewsFeedManager` | `get_for_symbol(symbol, limit)` | News for a single symbol |
| `NewsFeedManager` | `get_breaking_news(limit)` | Breaking news only |
| `NewsFeedManager` | `search(query, limit)` | Full-text search |
| `NewsFeedManager` | `get_sentiment_summary(symbol, days)` | Sentiment stats |
| `NewsFeedManager` | `get_trending_symbols(hours, limit)` | Most-mentioned symbols |
| `EarningsCalendar` | `add_event(event)` | Add earnings event |
| `EarningsCalendar` | `get_upcoming(days, symbols)` | Upcoming earnings |
| `EarningsCalendar` | `update_actuals(event_id, eps_actual, ...)` | Record actual EPS |
| `EarningsCalendar` | `get_beats(days, min_surprise_pct)` | Recent beats |
| `EarningsCalendar` | `get_surprise_stats(symbol)` | Beat rate and avg surprise |

### Economic Module (`src/economic/`)

| Class | Method | Description |
|---|---|---|
| `EconomicCalendar` | `add_event(event)` | Add economic event |
| `EconomicCalendar` | `get_upcoming(days, min_impact)` | Upcoming events |
| `EconomicCalendar` | `get_week(start_date, country, min_impact)` | Weekly view |
| `EconomicCalendar` | `get_high_impact(days)` | High-impact events only |
| `EconomicCalendar` | `record_release(event_id, actual)` | Record actual value |
| `FedWatcher` | `get_next_meeting()` | Next FOMC meeting |
| `FedWatcher` | `get_rate_path()` | Implied rate path |
| `FedWatcher` | `record_decision(meeting_id, decision, new_rate)` | Record rate decision |
| `FedWatcher` | `calculate_implied_rate(prob_hike, prob_cut)` | Implied rate |
| `HistoryAnalyzer` | `get_stats(event_name)` | EventStats (beat rate, avg reaction) |
| `HistoryAnalyzer` | `get_surprise_zscore(event_name, actual, forecast)` | Z-score of surprise |
| `HistoryAnalyzer` | `compare_to_history(event_name, actual, forecast)` | Full comparison |
| `ImpactAnalyzer` | `analyze_event(event)` | Pre-event impact analysis |
| `ImpactAnalyzer` | `analyze_release(event, market_data)` | Post-release analysis |
| `ImpactAnalyzer` | `get_sector_exposure(event)` | Sector sensitivity map |

### Alternative Data Module (`src/altdata/`)

| Class | Method | Description |
|---|---|---|
| `SatelliteAnalyzer` | `add_observation(symbol, sat_type, value)` | Record observation |
| `SatelliteAnalyzer` | `analyze(symbol, sat_type)` | Analyze single type |
| `SatelliteAnalyzer` | `analyze_all(symbol)` | Analyze all types |
| `WebTrafficAnalyzer` | `add_snapshot(symbol, domain, visits, ...)` | Record traffic |
| `WebTrafficAnalyzer` | `analyze(symbol)` | Compute growth, engagement, momentum |
| `AltDataScorer` | `score_satellite(signals)` | Score satellite signals |
| `AltDataScorer` | `score_web_traffic(snapshot)` | Score web traffic |
| `AltDataScorer` | `score_social(sentiment)` | Score social sentiment |
| `AltDataScorer` | `composite(symbol, satellite_signal, web_signal, ...)` | Composite score |

### Macro Module (`src/macro/`)

| Class | Method | Description |
|---|---|---|
| `IndicatorTracker` | `add_indicators(indicators)` | Add indicator readings |
| `IndicatorTracker` | `summarize()` | Composite IndicatorSummary |
| `IndicatorTracker` | `get_surprises()` | Sorted surprise list |
| `YieldCurveAnalyzer` | `analyze(rates, date)` | Full curve analysis with Nelson-Siegel |
| `RegimeDetector` | `detect(indicator_summary, growth_score, inflation_score)` | Detect regime |
| `MacroFactorModel` | `compute_factors(factor_series, regime)` | Factor returns and exposures |
| `MacroFactorModel` | `decompose_returns(asset_returns, factor_matrix)` | Return attribution |
| `MacroFactorModel` | `regime_factor_profile(factor_series, regime_labels)` | Per-regime factor averages |

## Common patterns

### Data model pattern

All data models are Python `dataclasses` with computed properties. They follow a consistent pattern:

```python
# Models use default factories for IDs and timestamps
from src.news.models import NewsArticle, EarningsEvent
from src.economic.models import EconomicEvent, HistoricalRelease, MarketImpact
from src.altdata.models import SatelliteSignal, AltDataComposite
from src.macro.models import EconomicIndicator, IndicatorSummary, YieldCurveSnapshot, RegimeState

# All models have to_dict() for serialization (macro, altdata)
indicator = EconomicIndicator(name="CPI", value=3.2, previous=3.4, consensus=3.3)
print(indicator.surprise)     # -0.1 (computed property)
print(indicator.change_pct)   # -5.88 (computed property)
print(indicator.to_dict())    # dict representation
```

### Configuration pattern

Each module uses dataclass-based configs with sensible defaults:

```python
from src.news import DEFAULT_NEWS_CONFIG, NewsConfig
from src.economic import DEFAULT_CALENDAR_CONFIG, CalendarConfig
from src.altdata import DEFAULT_CONFIG as ALTDATA_DEFAULT
from src.macro import DEFAULT_CONFIG as MACRO_DEFAULT

# Override specific settings
from src.economic.config import FedWatchConfig
custom_fed = FedWatchConfig(current_rate=5.25)
fed = FedWatcher(config=custom_fed)
```

### Sample data generators

Several modules provide sample data generators for testing and demos:

```python
from src.economic import generate_sample_calendar, generate_sample_fed_data, generate_sample_history

calendar = generate_sample_calendar()  # Pre-populated with US events
fed = generate_sample_fed_data()       # Pre-populated with FOMC meetings
history = generate_sample_history()     # Pre-populated with NFP and CPI history
```

### Cross-module workflow: full economic analysis pipeline

```python
from src.economic import EconomicCalendar, HistoryAnalyzer, ImpactAnalyzer, ImpactLevel
from src.macro import IndicatorTracker, YieldCurveAnalyzer, RegimeDetector

# 1. Get upcoming high-impact events
calendar = EconomicCalendar()
# ... add events ...
events = calendar.get_high_impact(days=7)

# 2. Analyze expected impact using historical data
history = HistoryAnalyzer()
# ... add historical releases ...
analyzer = ImpactAnalyzer(history)
for event in events:
    impact = analyzer.analyze_event(event)
    print(f"{event.name}: volatility={impact.expected_volatility}, "
          f"sectors={impact.sector_impacts}")

# 3. Assess current macro regime
tracker = IndicatorTracker()
# ... add indicators ...
summary = tracker.summarize()

curve_analyzer = YieldCurveAnalyzer()
curve = curve_analyzer.analyze(rates={"2Y": 4.5, "10Y": 4.3}, date="2026-02-09")

detector = RegimeDetector()
regime = detector.detect(summary, growth_score=0.2, inflation_score=-0.1)
print(f"Regime: {regime.regime.value}, Confidence: {regime.probability}")
```
