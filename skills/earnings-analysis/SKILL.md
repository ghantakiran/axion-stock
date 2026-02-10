---
name: earnings-analysis
description: Earnings calendar management, estimate tracking, quality assessment (Beneish M-Score, accruals, cash conversion), post-earnings reaction analysis, surprise classification, PEAD drift screening, and M&A probability estimation. Use when analyzing upcoming earnings, tracking analyst revisions, assessing earnings quality, studying price reactions to earnings, or evaluating merger arbitrage opportunities.
metadata:
  author: axion-platform
  version: "1.0"
---

# Earnings Analysis

## When to use this skill

Use this skill when you need to:
- Track upcoming earnings dates and filter by portfolio/watchlist
- Monitor analyst EPS and revenue estimate revisions
- Assess earnings quality using Beneish M-Score and accruals analysis
- Analyze price reactions (gap, drift, fade) around earnings announcements
- Classify earnings as beat/meet/miss and compute surprise statistics
- Screen for post-earnings announcement drift (PEAD) opportunities
- Estimate deal completion probability for M&A risk arbitrage
- Generate earnings-related alerts

## Step-by-step instructions

### 1. Manage the earnings calendar

```python
from datetime import date, timedelta
from src.earnings import (
    EarningsCalendar, EarningsEvent, EarningsTime,
    generate_sample_calendar,
)

# Create calendar and populate
calendar = EarningsCalendar()

calendar.add_event(EarningsEvent(
    symbol="AAPL",
    company_name="Apple Inc.",
    report_date=date(2025, 1, 30),
    report_time=EarningsTime.AFTER_MARKET,
    fiscal_quarter="Q1 2025",
    fiscal_year=2025,
    eps_estimate=2.10,
    revenue_estimate=94.5e9,
    is_confirmed=True,
))

# Or use sample data for testing
calendar = generate_sample_calendar()

# Get upcoming earnings (next 7 days)
upcoming = calendar.get_upcoming(days=7)
for event in upcoming:
    print(f"{event.symbol}: {event.report_date} {event.report_time.value} "
          f"(EPS est: ${event.eps_estimate:.2f})")

# Get earnings for a specific day
today_earnings = calendar.get_day(date.today())
before_market = calendar.get_before_market(date.today())
after_market = calendar.get_after_market(date.today())

# Get weekly view
week = calendar.get_week(date.today())
for day, events in week.items():
    if events:
        print(f"{day}: {[e.symbol for e in events]}")

# Get monthly view
month = calendar.get_month(2025, 1)

# Filter by portfolio holdings
portfolio_events = calendar.filter_by_portfolio(upcoming, ["AAPL", "MSFT", "GOOGL"])

# Count by time of day
counts = calendar.count_by_day(date.today())
print(f"Before: {counts['before_market']}, After: {counts['after_market']}")

# Get next event for a symbol
next_event = calendar.get_next_event("AAPL")
```

### 2. Track analyst estimates

```python
from src.earnings import (
    EstimateTracker, EarningsEstimate, generate_sample_estimates,
)

tracker = generate_sample_estimates()  # Pre-populated with sample data

# Get current consensus
estimate = tracker.get_estimate("AAPL", "Q4 2025")
print(f"EPS consensus: ${estimate.eps_consensus:.2f}")
print(f"EPS range: ${estimate.eps_low:.2f} - ${estimate.eps_high:.2f}")
print(f"Revenue consensus: ${estimate.revenue_consensus / 1e9:.1f}B")
print(f"Analysts covering: {estimate.eps_num_analysts}")
print(f"Revisions up: {estimate.eps_revisions_up}, down: {estimate.eps_revisions_down}")

# Calculate revision momentum
momentum = tracker.calculate_revision_momentum("AAPL", "Q4 2025", days=30)
print(f"EPS change: ${momentum['eps_change']:.2f} ({momentum['direction']})")
print(f"Change %: {momentum['eps_change_pct']:.1%}")

# Get estimate spread (analyst disagreement)
spread = tracker.get_estimate_spread("AAPL", "Q4 2025")
print(f"EPS spread: ${spread['eps_spread']:.2f}")
print(f"Dispersion: {spread['dispersion']}")  # low, moderate, high

# Compare to year-ago actuals
yoy = tracker.compare_to_year_ago("AAPL", "Q4 2025")
print(f"EPS growth: {yoy['eps_growth']:.1%}")
print(f"Revenue growth: {yoy['revenue_growth']:.1%}")

# Screen for revision trends
positive = tracker.get_symbols_with_positive_revisions()
negative = tracker.get_symbols_with_negative_revisions()
print(f"Positive revisions: {positive}")
print(f"Negative revisions: {negative}")

# Track revisions over time
history = tracker.get_estimate_history("AAPL", "Q4 2025")
for est in history:
    print(f"  {est.as_of_date}: EPS={est.eps_consensus:.2f}")
```

### 3. Assess earnings quality (Beneish M-Score)

```python
from src.earnings import QualityAnalyzer, FinancialData, EarningsQuality

analyzer = QualityAnalyzer()

data = FinancialData(
    # Current period
    revenue=94.5e9,
    cost_of_revenue=52.0e9,
    gross_profit=42.5e9,
    operating_income=30.0e9,
    net_income=25.0e9,
    operating_cash_flow=30.0e9,
    receivables=25.0e9,
    current_assets=120.0e9,
    total_assets=350.0e9,
    ppe=40.0e9,
    total_liabilities=280.0e9,
    long_term_debt=100.0e9,
    depreciation=10.0e9,
    sga_expense=18.0e9,
    # Prior period (for M-Score component calculations)
    revenue_prior=89.5e9,
    gross_profit_prior=40.0e9,
    receivables_prior=23.0e9,
    current_assets_prior=115.0e9,
    total_assets_prior=340.0e9,
    ppe_prior=38.0e9,
    depreciation_prior=9.5e9,
    sga_expense_prior=17.0e9,
    long_term_debt_prior=95.0e9,
)

quality: EarningsQuality = analyzer.analyze("AAPL", data)

print(f"Beneish M-Score: {quality.beneish_m_score:.2f}")
print(f"Manipulation risk: {quality.is_manipulation_risk}")  # True if M-Score > -1.78
print(f"Accruals ratio: {quality.accruals_ratio:.3f}")
print(f"Cash conversion: {quality.cash_conversion:.2f}")
print(f"Quality rating: {quality.quality_rating.value}")  # HIGH, MEDIUM, LOW, WARNING
print(f"Overall score: {quality.overall_quality_score:.0f}/100")
print(f"Red flags: {quality.red_flags}")

# M-Score components
print(f"DSRI (Days Sales Receivable Index): {quality.dsri:.3f}")
print(f"GMI (Gross Margin Index): {quality.gmi:.3f}")
print(f"AQI (Asset Quality Index): {quality.aqi:.3f}")
print(f"SGI (Sales Growth Index): {quality.sgi:.3f}")
print(f"TATA (Total Accruals / Total Assets): {quality.tata:.3f}")

# Screen for high-quality earnings
high_quality = analyzer.screen_by_quality(min_score=70, exclude_manipulation_risk=True)
```

### 4. Analyze price reactions to earnings

```python
from src.earnings import ReactionAnalyzer, EarningsReaction

reaction_analyzer = ReactionAnalyzer()

# Record a price reaction
reaction: EarningsReaction = reaction_analyzer.record_reaction(
    symbol="AAPL",
    fiscal_quarter="Q1 2025",
    report_date=date(2025, 1, 30),
    price_5d_before=182.0,
    price_1d_before=185.0,
    volume_avg=65e6,
    iv_percentile=0.82,
    open_price=192.0,        # Gap up
    close_price=190.5,
    high_price=194.0,
    low_price=189.0,
    volume=120e6,
    price_1d_after=191.0,
    price_5d_after=195.0,
    price_20d_after=198.0,
)

print(f"Gap: {reaction.gap_open_pct:.1%}")
print(f"Close change: {reaction.close_change_pct:.1%}")
print(f"Volume ratio: {reaction.volume_ratio:.1f}x")
print(f"1-day change: {reaction.price_change_1d:.1%}")
print(f"5-day change: {reaction.price_change_5d:.1%}")
print(f"20-day change: {reaction.price_change_20d:.1%}")
print(f"Pre-earnings drift: {reaction.pre_earnings_drift:.1%}")
print(f"Post-earnings drift: {reaction.post_earnings_drift:.1%}")

# Historical reaction statistics
stats = reaction_analyzer.calculate_historical_stats("AAPL")
print(f"Avg gap: {stats['avg_gap']:.1%}")
print(f"Max gap up: {stats['max_gap_up']:.1%}")
print(f"Fade rate: {stats['fade_rate']:.0%}")
print(f"Avg 5d change: {stats['avg_5d_change']:.1%}")

# Analyze by surprise direction
from src.earnings import QuarterlyEarnings
by_surprise = reaction_analyzer.analyze_reaction_by_surprise("AAPL", quarters)
print(f"Beat avg gap: {by_surprise['beat']['avg_gap']:.1%}")
print(f"Miss avg gap: {by_surprise['miss']['avg_gap']:.1%}")

# Screen for post-earnings drift opportunities
drift = reaction_analyzer.screen_for_drift(min_drift=0.03)
print(f"Continuation drifts: {len(drift['continuation'])}")
print(f"Reversal drifts: {len(drift['reversal'])}")

# Get extreme reactions (large gaps)
extreme = reaction_analyzer.get_extreme_reactions(threshold=0.10)
```

### 5. Event-level earnings analysis (beat/miss classification)

```python
from src.events.earnings import EarningsAnalyzer
from src.events.models import EarningsEvent as EventEarnings, EarningsSummary

analyzer = EarningsAnalyzer()

# Add earnings events
event = EventEarnings(
    symbol="AAPL",
    report_date=date(2025, 1, 30),
    eps_actual=2.18,
    eps_estimate=2.10,
    revenue_actual=95.4e9,
    revenue_estimate=94.5e9,
    post_drift=0.035,  # 3.5% post-earnings drift
)

classified = analyzer.add_event(event)
print(f"Result: {classified.result.value}")  # beat, meet, miss
print(f"EPS surprise: {classified.eps_surprise:.2f}")

# Summarize earnings history
summary: EarningsSummary = analyzer.summarize("AAPL")
print(f"Total reports: {summary.total_reports}")
print(f"Beats: {summary.beats}, Meets: {summary.meets}, Misses: {summary.misses}")
print(f"Avg EPS surprise: {summary.avg_eps_surprise:.2f}")
print(f"Avg post drift: {summary.avg_post_drift:.1%}")
print(f"Current streak: {summary.streak}")  # Positive = beat streak, negative = miss streak

# Estimate PEAD drift for a given surprise
estimated_drift = analyzer.estimate_drift("AAPL", surprise_pct=0.05)
print(f"Estimated drift for 5% surprise: {estimated_drift:.1%}")
```

### 6. M&A probability and risk arbitrage

```python
from src.events.mergers import MergerAnalyzer
from src.events.models import MergerEvent
from src.events.config import DealStatus

merger_analyzer = MergerAnalyzer()

deal = MergerEvent(
    target="ATVI",
    acquirer="MSFT",
    announce_date=date(2024, 1, 18),
    offer_price=95.0,
    current_price=92.0,
    status=DealStatus.PENDING,
    is_cash=True,
    expected_close=date(2025, 6, 30),
    premium=0.30,
)

merger_analyzer.add_deal(deal)

# Estimate deal completion probability
prob = merger_analyzer.estimate_probability(deal)
print(f"Completion probability: {prob:.0%}")

# Get annualized spread
ann_spread = merger_analyzer.annualized_spread(deal)
print(f"Annualized spread: {ann_spread:.1%}")

# Generate risk arbitrage signal
signal = merger_analyzer.risk_arb_signal(deal)
print(f"Signal: {signal['signal']}")             # strong_buy, buy, neutral, avoid
print(f"Spread: {signal['spread']:.1%}")
print(f"Expected return: {signal['expected_return']:.1%}")

# Get all active deals
active = merger_analyzer.get_active_deals()
```

## Key classes and methods

### Earnings Calendar (`src/earnings/calendar.py`)
- `EarningsCalendar.add_event(event)`, `update_event(event)`, `get_event(id)`
- `get_upcoming(days, symbols)` -> `list[EarningsEvent]`
- `get_day(date)`, `get_week(date)`, `get_month(year, month)`
- `get_before_market(date)`, `get_after_market(date)`
- `get_next_event(symbol)` -> `Optional[EarningsEvent]`
- `filter_by_portfolio(events, symbols)`, `filter_by_watchlist(events, symbols)`

### Estimate Tracker (`src/earnings/estimates.py`)
- `EstimateTracker.add_estimate(estimate)`, `get_estimate(symbol, quarter)`
- `get_estimate_history(symbol, quarter)` -> `list[EarningsEstimate]`
- `calculate_revision_momentum(symbol, quarter, days)` -> `dict`
- `get_estimate_spread(symbol, quarter)` -> `dict`
- `get_symbols_with_positive_revisions()` -> `list[str]`

### Quality Analyzer (`src/earnings/quality.py`)
- `QualityAnalyzer.analyze(symbol, data)` -> `EarningsQuality`
- `screen_by_quality(min_score, exclude_manipulation_risk)` -> `list[str]`
- M-Score formula: -4.84 + 0.920*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI + 0.115*DEPI - 0.172*SGAI + 4.679*TATA - 0.327*LVGI
- Manipulation risk threshold: M-Score > -1.78

### Reaction Analyzer (`src/earnings/reactions.py`)
- `ReactionAnalyzer.record_reaction(symbol, quarter, ...)` -> `EarningsReaction`
- `calculate_historical_stats(symbol)` -> `dict`
- `analyze_reaction_by_surprise(symbol, quarters)` -> `dict`
- `screen_for_drift(min_drift)` -> `dict` with "continuation" and "reversal"
- `get_extreme_reactions(threshold)` -> `list[EarningsReaction]`

### Earnings Analyzer (`src/events/earnings.py`)
- `EarningsAnalyzer.add_event(event)` -> auto-classifies beat/meet/miss
- `summarize(symbol)` -> `EarningsSummary` with beat rate, streak, drift stats
- `estimate_drift(symbol, surprise_pct)` -> `float` (regression-based PEAD estimate)

### Merger Analyzer (`src/events/mergers.py`)
- `MergerAnalyzer.add_deal(deal)`, `get_active_deals()`, `get_deals(target)`
- `estimate_probability(deal)` -> `float` (0-1)
- `annualized_spread(deal)` -> `float`
- `risk_arb_signal(deal)` -> `dict` with signal, spread, probability, expected_return

## Common patterns

### Beneish M-Score red flags
- M-Score > -1.78: manipulation risk (BENEISH_THRESHOLD)
- Accruals ratio > 0.05: high accruals warning
- Cash conversion < 0.5: low cash conversion
- DSRI > 1.5: receivables growing faster than sales
- GMI > 1.3: declining gross margins
- AQI > 1.5: declining asset quality

### Earnings quality ratings
- **HIGH**: overall score >= 80, no manipulation risk
- **MEDIUM**: overall score >= 60
- **LOW**: overall score < 60
- **WARNING**: manipulation risk OR 3+ red flags

### PEAD drift estimation
The `EarningsAnalyzer.estimate_drift()` method uses OLS regression on historical
surprise vs drift data. With fewer than `min_history` observations, it falls
back to a simple linear estimate: `drift = surprise * 0.5`.

### Deal completion probability factors
- Base probability by status: Announced 60%, Pending 70%, Approved 92%
- Cash deals: +5% probability boost
- Narrow spread (<2%): +5% (market confident)
- Wide spread (>10%): -10% (market skeptical)
- Regulatory risk factor applied multiplicatively
