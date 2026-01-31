# PRD-27: Earnings Calendar & Analysis

**Priority**: P1 | **Phase**: 16 | **Status**: Draft

---

## Problem Statement

Earnings announcements are among the most impactful events for stock prices, often causing significant volatility. Investors need tools to track upcoming earnings, analyze historical patterns, compare estimates vs actuals, and make informed decisions around earnings season. A comprehensive earnings calendar and analysis tool helps investors prepare for and capitalize on earnings events.

---

## Goals

1. **Earnings Calendar** - Track upcoming earnings dates across portfolio and watchlist
2. **Estimate Tracking** - Monitor analyst estimates, revisions, and consensus
3. **Historical Analysis** - Analyze past earnings surprises and price reactions
4. **Earnings Quality** - Assess earnings quality metrics (accruals, revenue recognition)
5. **Pre/Post Earnings** - Track pre-earnings drift and post-earnings announcement drift (PEAD)
6. **Whisper Numbers** - Track unofficial estimates and sentiment indicators

---

## Detailed Requirements

### R1: Earnings Calendar

#### R1.1: Calendar Model
```python
@dataclass
class EarningsEvent:
    event_id: str
    symbol: str
    company_name: str
    
    # Timing
    report_date: date
    report_time: EarningsTime  # before_market, after_market, during_market
    fiscal_quarter: str  # "Q1 2024"
    fiscal_year: int
    
    # Estimates
    eps_estimate: Optional[float] = None
    revenue_estimate: Optional[float] = None
    num_estimates: int = 0
    
    # Actuals (filled after report)
    eps_actual: Optional[float] = None
    revenue_actual: Optional[float] = None
    
    # Conference call
    conference_call_time: Optional[datetime] = None
    conference_call_url: Optional[str] = None
    
    # Status
    is_confirmed: bool = False
    last_updated: datetime
```

#### R1.2: Calendar Views
| View | Description |
|------|-------------|
| **Daily** | Today's earnings reports |
| **Weekly** | This week's calendar |
| **Monthly** | Full month view |
| **Portfolio** | Only portfolio holdings |
| **Watchlist** | Only watchlist stocks |

### R2: Estimate Tracking

#### R2.1: Estimate Model
```python
@dataclass
class EarningsEstimate:
    symbol: str
    fiscal_quarter: str
    
    # EPS Estimates
    eps_consensus: float
    eps_high: float
    eps_low: float
    eps_num_analysts: int
    
    # Revenue Estimates
    revenue_consensus: float
    revenue_high: float
    revenue_low: float
    revenue_num_analysts: int
    
    # Revisions (last 30 days)
    eps_revisions_up: int = 0
    eps_revisions_down: int = 0
    revenue_revisions_up: int = 0
    revenue_revisions_down: int = 0
    
    # Historical comparison
    eps_year_ago: Optional[float] = None
    revenue_year_ago: Optional[float] = None
```

#### R2.2: Revision Tracking
- Track estimate changes over time
- Calculate revision momentum
- Alert on significant revisions

### R3: Historical Analysis

#### R3.1: Earnings History
```python
@dataclass
class EarningsHistory:
    symbol: str
    quarters: list[QuarterlyEarnings]
    
    # Summary stats
    beat_rate_eps: float  # % of quarters beating EPS
    beat_rate_revenue: float
    avg_surprise_eps: float
    avg_surprise_revenue: float
    
    # Consistency
    consecutive_beats: int
    consecutive_misses: int
    
    # Guidance accuracy
    guidance_accuracy: float
```

#### R3.2: Quarterly Earnings
```python
@dataclass
class QuarterlyEarnings:
    fiscal_quarter: str
    report_date: date
    
    # EPS
    eps_estimate: float
    eps_actual: float
    eps_surprise: float
    eps_surprise_pct: float
    
    # Revenue
    revenue_estimate: float
    revenue_actual: float
    revenue_surprise: float
    revenue_surprise_pct: float
    
    # Price reaction
    price_before: float
    price_after: float
    price_change_1d: float
    price_change_5d: float
    
    # Guidance
    guidance_eps: Optional[float] = None
    guidance_revenue: Optional[float] = None
```

### R4: Earnings Quality

#### R4.1: Quality Metrics
| Metric | Description |
|--------|-------------|
| **Accruals Ratio** | Non-cash earnings component |
| **Cash Conversion** | CFO / Net Income |
| **Revenue Quality** | Recurring vs one-time |
| **Earnings Persistence** | Stability over time |
| **Manipulation Score** | Beneish M-Score |

#### R4.2: Quality Model
```python
@dataclass
class EarningsQuality:
    symbol: str
    
    # Core metrics
    accruals_ratio: float
    cash_conversion: float
    earnings_persistence: float
    
    # Quality indicators
    revenue_quality_score: float  # 0-100
    earnings_quality_score: float  # 0-100
    
    # Red flags
    beneish_m_score: float
    is_manipulation_risk: bool
    
    # Components
    dsri: float  # Days Sales Receivable Index
    gmi: float   # Gross Margin Index
    aqi: float   # Asset Quality Index
    sgi: float   # Sales Growth Index
    depi: float  # Depreciation Index
    sgai: float  # SGA Index
    lvgi: float  # Leverage Index
    tata: float  # Total Accruals to Total Assets
```

### R5: Price Reaction Analysis

#### R5.1: Reaction Patterns
```python
@dataclass
class EarningsReaction:
    symbol: str
    fiscal_quarter: str
    
    # Pre-earnings
    price_5d_before: float
    price_1d_before: float
    volume_avg_before: float
    iv_percentile_before: float
    
    # Post-earnings
    gap_open_pct: float
    close_change_pct: float
    high_low_range_pct: float
    volume_ratio: float  # vs average
    
    # Extended reaction
    price_change_1d: float
    price_change_5d: float
    price_change_20d: float
    
    # Drift analysis
    pre_earnings_drift: float
    post_earnings_drift: float
```

#### R5.2: Historical Reaction Stats
- Average gap on beat/miss
- Win rate when gap up/down
- Typical fade patterns
- Sector comparison

### R6: Earnings Alerts

#### R6.1: Alert Types
| Alert | Trigger |
|-------|---------|
| **Upcoming Earnings** | X days before report |
| **Estimate Revision** | Significant revision |
| **Earnings Released** | Report published |
| **Surprise Alert** | Beat/miss threshold |
| **Guidance Alert** | Guidance raised/lowered |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Calendar accuracy | 99%+ correct dates |
| Estimate coverage | 95%+ of S&P 500 |
| Historical data | 5+ years history |
| Alert delivery | < 1 min after release |

---

## Dependencies

- Market data (PRD-01)
- Alerting system (PRD-13)
- Research reports (PRD-23)
- Screener (PRD-24)

---

*Owner: Product Engineering Lead*
*Last Updated: January 2026*
