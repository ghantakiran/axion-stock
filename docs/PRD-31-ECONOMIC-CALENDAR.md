# PRD-31: Economic Calendar

**Priority**: P1 | **Phase**: 20 | **Status**: Draft

---

## Problem Statement

Economic data releases and central bank decisions have significant impacts on financial markets. Traders need to track upcoming economic events, understand their historical market impact, and prepare trading strategies around high-impact releases. A comprehensive economic calendar helps traders stay informed and manage risk around volatile events.

---

## Goals

1. **Event Tracking** - Comprehensive calendar of economic events worldwide
2. **Impact Analysis** - Historical market reaction to economic releases
3. **Forecasts & Actuals** - Track consensus forecasts vs actual results
4. **Fed Watch** - Monitor Fed meetings, rate decisions, and dot plots
5. **Custom Alerts** - Notifications for important upcoming events
6. **Market Impact** - Real-time analysis of how releases affect markets

---

## Detailed Requirements

### R1: Economic Event Model

#### R1.1: Event Structure
```python
@dataclass
class EconomicEvent:
    event_id: str
    name: str
    country: str  # US, EU, UK, JP, CN, etc.
    category: EventCategory
    
    # Timing
    release_date: date
    release_time: Optional[time]
    timezone: str = "America/New_York"
    
    # Importance
    impact: ImpactLevel  # low, medium, high
    
    # Data
    previous: Optional[float] = None
    forecast: Optional[float] = None
    actual: Optional[float] = None
    unit: str = ""  # %, K, M, B, index
    
    # Status
    is_released: bool = False
    release_timestamp: Optional[datetime] = None
```

#### R1.2: Event Categories
| Category | Examples |
|----------|----------|
| **Employment** | Non-Farm Payrolls, Unemployment Rate, Jobless Claims |
| **Inflation** | CPI, PPI, PCE, Core Inflation |
| **GDP** | GDP Growth, GDP Price Index |
| **Central Bank** | Fed Rate Decision, ECB Rate, BOJ Decision |
| **Manufacturing** | ISM Manufacturing, PMI, Industrial Production |
| **Consumer** | Retail Sales, Consumer Confidence, Michigan Sentiment |
| **Housing** | Housing Starts, Existing Home Sales, Building Permits |
| **Trade** | Trade Balance, Import/Export Prices |
| **Treasury** | Treasury Auctions, Yield Curve |

### R2: Calendar Management

#### R2.1: Calendar Views
| View | Description |
|------|-------------|
| **Daily** | Events for a specific day |
| **Weekly** | Week at a glance |
| **Monthly** | Full month calendar |
| **Upcoming** | Next N events |
| **By Impact** | Filtered by importance |

#### R2.2: Filtering
- By country (US, EU, UK, Global)
- By category (Employment, Inflation, etc.)
- By impact level (High, Medium, Low)
- By date range

### R3: Historical Analysis

#### R3.1: Historical Data Model
```python
@dataclass
class HistoricalRelease:
    event_name: str
    release_date: datetime
    
    # Values
    actual: float
    forecast: float
    previous: float
    surprise: float  # actual - forecast
    surprise_pct: float
    
    # Market reaction
    spx_1h_change: float  # S&P 500 1-hour change
    spx_1d_change: float  # 1-day change
    dxy_1h_change: float  # Dollar index
    vix_change: float
    bond_yield_change: float
```

#### R3.2: Analysis Features
| Feature | Description |
|---------|-------------|
| **Surprise History** | Track beat/miss patterns |
| **Market Reaction** | How markets typically react |
| **Volatility Impact** | VIX changes around releases |
| **Sector Impact** | Which sectors most affected |
| **Correlation** | Relationship between indicators |

### R4: Fed Watch

#### R4.1: Fed Meeting Tracker
```python
@dataclass
class FedMeeting:
    meeting_date: date
    meeting_type: str  # FOMC, Minutes, Speech
    
    # Rate decision
    current_rate: float
    rate_decision: Optional[str]  # hike, cut, hold
    rate_change: Optional[float]
    
    # Market expectations
    prob_hike: float
    prob_cut: float
    prob_hold: float
    
    # Dot plot
    median_projection: Optional[float]
    long_run_rate: Optional[float]
```

#### R4.2: Fed Features
| Feature | Description |
|---------|-------------|
| **Rate Probabilities** | Fed funds futures implied probabilities |
| **Dot Plot** | FOMC members' rate projections |
| **Statement Analysis** | Hawkish/dovish language tracking |
| **Historical Decisions** | Past rate decisions and impacts |

### R5: Alerts & Notifications

#### R5.1: Alert Types
| Alert | Trigger |
|-------|---------|
| **Upcoming Event** | X minutes before release |
| **Event Released** | When data is published |
| **Big Surprise** | Significant beat/miss |
| **Fed Alert** | Rate decisions, speeches |
| **Custom** | User-defined conditions |

#### R5.2: Alert Configuration
```python
@dataclass
class EventAlert:
    alert_id: str
    event_pattern: str  # Event name pattern
    
    # Triggers
    minutes_before: int = 30
    on_release: bool = True
    surprise_threshold: Optional[float] = None
    
    # Filters
    min_impact: ImpactLevel = ImpactLevel.MEDIUM
    countries: list[str] = field(default_factory=list)
```

### R6: Market Impact Analysis

#### R6.1: Real-Time Impact
- Track market moves immediately after release
- Compare to historical average reaction
- Identify if reaction is muted or amplified

#### R6.2: Trading Implications
| Analysis | Description |
|----------|-------------|
| **Pre-Event** | Positioning recommendations |
| **Post-Event** | Interpret the release |
| **Volatility** | Expected vs realized vol |
| **Sector Impact** | Which sectors to watch |

---

## Key Economic Events

### US High-Impact Events
| Event | Frequency | Typical Impact |
|-------|-----------|----------------|
| Non-Farm Payrolls | Monthly | Very High |
| CPI | Monthly | Very High |
| Fed Rate Decision | 8x/year | Very High |
| GDP | Quarterly | High |
| PCE | Monthly | High |
| Retail Sales | Monthly | Medium-High |
| ISM Manufacturing | Monthly | Medium |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Event coverage | 95%+ major events |
| Data accuracy | 99%+ |
| Alert timeliness | < 1 min delay |
| User engagement | 70%+ check calendar weekly |

---

## Dependencies

- Data providers (economic data feeds)
- Alerting system (PRD-13)
- Market data (PRD-01)

---

*Owner: Product Engineering Lead*
*Last Updated: January 2026*
