# PRD-21: News & Events Integration

**Priority**: P1 | **Phase**: 11 | **Status**: Draft

---

## Problem Statement

Traders need timely access to market-moving information including news, earnings announcements, economic events, and SEC filings. Without integrated news and events, users miss critical information that affects their positions and must manually track multiple sources. A unified news and events system enables informed decision-making and proactive portfolio management.

---

## Goals

1. **Real-Time News Feed** - Aggregated financial news with sentiment analysis
2. **Earnings Calendar** - Upcoming and historical earnings with estimates/actuals
3. **Economic Calendar** - Fed meetings, jobs reports, CPI, GDP releases
4. **SEC Filings** - 10-K, 10-Q, 8-K, insider transactions (Form 4)
5. **Corporate Events** - Dividends, splits, M&A, IPOs
6. **News Alerts** - Customizable alerts on symbols, keywords, events

---

## Detailed Requirements

### R1: News Aggregation

#### R1.1: News Sources
| Source | Type | Coverage |
|--------|------|----------|
| Financial News APIs | REST | Reuters, Bloomberg, MarketWatch |
| SEC EDGAR | REST | Official filings |
| Press Releases | RSS/API | Company announcements |
| Social/Alternative | API | Twitter/X, Reddit sentiment |

#### R1.2: News Article Model
```python
@dataclass
class NewsArticle:
    article_id: str
    headline: str
    summary: str
    content: str
    source: str
    url: str
    published_at: datetime
    symbols: list[str]  # Related tickers
    categories: list[str]  # 'earnings', 'macro', 'analyst', etc.
    sentiment_score: float  # -1 to 1
    sentiment_label: str  # 'positive', 'negative', 'neutral'
    relevance_score: float  # 0 to 1
    is_breaking: bool
    image_url: Optional[str]
```

#### R1.3: News Feed Features
- Filter by symbol, sector, category
- Sentiment-based filtering (positive/negative only)
- Breaking news priority display
- Read/unread tracking
- Bookmark/save articles
- Full-text search

### R2: Earnings Calendar

#### R2.1: Earnings Event Model
```python
@dataclass
class EarningsEvent:
    symbol: str
    company_name: str
    report_date: date
    report_time: str  # 'BMO', 'AMC', 'DMH' (before/after market, during)
    fiscal_quarter: str  # 'Q1 2024'
    fiscal_year: int
    
    # Estimates
    eps_estimate: Optional[float]
    revenue_estimate: Optional[float]
    eps_low: Optional[float]
    eps_high: Optional[float]
    num_analysts: int
    
    # Actuals (after report)
    eps_actual: Optional[float]
    revenue_actual: Optional[float]
    eps_surprise: Optional[float]
    eps_surprise_pct: Optional[float]
    
    # Guidance
    guidance_eps: Optional[float]
    guidance_revenue: Optional[float]
    
    # Market reaction
    price_before: Optional[float]
    price_after: Optional[float]
    price_change_pct: Optional[float]
```

#### R2.2: Earnings Features
- Calendar view (week/month)
- Portfolio earnings (your holdings)
- Watchlist earnings
- Historical earnings with beat/miss tracking
- Earnings surprise analysis
- Pre/post market price moves

### R3: Economic Calendar

#### R3.1: Economic Event Types
| Category | Events |
|----------|--------|
| **Central Bank** | FOMC meetings, rate decisions, Fed speeches, minutes |
| **Employment** | Non-farm payrolls, unemployment rate, jobless claims |
| **Inflation** | CPI, PPI, PCE |
| **Growth** | GDP, retail sales, industrial production |
| **Housing** | Housing starts, existing home sales, Case-Shiller |
| **Sentiment** | Consumer confidence, PMI, ISM |
| **International** | ECB, BOJ, BOE decisions |

#### R3.2: Economic Event Model
```python
@dataclass
class EconomicEvent:
    event_id: str
    name: str
    category: str
    country: str
    release_date: datetime
    importance: str  # 'high', 'medium', 'low'
    
    # Expectations
    forecast: Optional[float]
    previous: Optional[float]
    
    # Actual (after release)
    actual: Optional[float]
    surprise: Optional[float]
    
    # Impact
    market_impact: str  # 'bullish', 'bearish', 'neutral'
    affected_sectors: list[str]
```

### R4: SEC Filings

#### R4.1: Filing Types
| Form | Description | Importance |
|------|-------------|------------|
| 10-K | Annual report | High |
| 10-Q | Quarterly report | High |
| 8-K | Current report (material events) | High |
| Form 4 | Insider transactions | Medium |
| 13F | Institutional holdings | Medium |
| S-1 | IPO registration | Medium |
| DEF 14A | Proxy statement | Low |

#### R4.2: SEC Filing Model
```python
@dataclass
class SECFiling:
    filing_id: str
    symbol: str
    company_name: str
    cik: str  # SEC Central Index Key
    form_type: str
    filed_date: date
    accepted_date: datetime
    period_of_report: Optional[date]
    
    # Content
    url: str
    document_count: int
    file_size: int
    
    # Parsed data (for supported forms)
    key_items: dict[str, Any]  # Extracted highlights
    
    # For Form 4 (insider transactions)
    insider_name: Optional[str]
    insider_title: Optional[str]
    transaction_type: Optional[str]  # 'buy', 'sell', 'grant'
    shares: Optional[float]
    price: Optional[float]
    value: Optional[float]
```

### R5: Corporate Events

#### R5.1: Event Types
```python
class CorporateEventType(str, Enum):
    DIVIDEND = "dividend"
    STOCK_SPLIT = "stock_split"
    REVERSE_SPLIT = "reverse_split"
    MERGER = "merger"
    ACQUISITION = "acquisition"
    SPINOFF = "spinoff"
    IPO = "ipo"
    BUYBACK = "buyback"
    DELISTING = "delisting"
```

#### R5.2: Dividend Model
```python
@dataclass
class DividendEvent:
    symbol: str
    ex_date: date
    record_date: date
    pay_date: date
    amount: float
    frequency: str  # 'quarterly', 'monthly', 'annual', 'special'
    dividend_type: str  # 'cash', 'stock'
    yield_on_ex_date: Optional[float]
```

### R6: News & Event Alerts

#### R6.1: Alert Triggers
| Trigger | Description |
|---------|-------------|
| Symbol News | Any news for watched symbols |
| Breaking News | High-priority market news |
| Earnings Announce | When company reports |
| Earnings Surprise | Beat/miss by >5% |
| Insider Transaction | Form 4 filings |
| SEC Filing | Specific form types |
| Economic Release | High-importance events |
| Dividend Declared | New dividend announcements |

#### R6.2: Alert Configuration
```python
@dataclass
class NewsAlert:
    alert_id: str
    user_id: str
    name: str
    enabled: bool
    
    # Filters
    symbols: list[str]
    keywords: list[str]
    categories: list[str]
    sources: list[str]
    min_sentiment: Optional[float]
    max_sentiment: Optional[float]
    importance: list[str]
    
    # Delivery
    channels: list[str]  # 'in_app', 'email', 'push'
    quiet_hours: bool
```

### R7: Data Storage

#### R7.1: Database Tables
```sql
-- News articles
CREATE TABLE news_articles (
    article_id UUID PRIMARY KEY,
    headline TEXT NOT NULL,
    summary TEXT,
    content TEXT,
    source VARCHAR(100),
    url TEXT,
    published_at TIMESTAMPTZ,
    sentiment_score DECIMAL(4,3),
    sentiment_label VARCHAR(20),
    relevance_score DECIMAL(4,3),
    is_breaking BOOLEAN DEFAULT FALSE,
    categories TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Article-symbol associations
CREATE TABLE article_symbols (
    article_id UUID REFERENCES news_articles(article_id),
    symbol VARCHAR(20),
    PRIMARY KEY (article_id, symbol)
);

-- Earnings calendar
CREATE TABLE earnings_calendar (
    id UUID PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    report_date DATE NOT NULL,
    report_time VARCHAR(10),
    fiscal_quarter VARCHAR(10),
    eps_estimate DECIMAL(10,4),
    eps_actual DECIMAL(10,4),
    revenue_estimate BIGINT,
    revenue_actual BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Economic calendar
CREATE TABLE economic_calendar (
    event_id UUID PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(50),
    country VARCHAR(10),
    release_date TIMESTAMPTZ,
    importance VARCHAR(20),
    forecast DECIMAL(20,4),
    previous DECIMAL(20,4),
    actual DECIMAL(20,4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- SEC filings
CREATE TABLE sec_filings (
    filing_id UUID PRIMARY KEY,
    symbol VARCHAR(20),
    cik VARCHAR(20),
    form_type VARCHAR(20),
    filed_date DATE,
    url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| News latency | <30s from publication |
| Earnings data accuracy | >99% |
| Economic calendar coverage | 100% major events |
| SEC filing delay | <5min from EDGAR |
| Alert delivery | <10s from trigger |

---

## Dependencies

- News API provider (e.g., Polygon, Benzinga, Alpha Vantage)
- SEC EDGAR API
- Economic calendar API (e.g., Trading Economics)
- Alerting system (PRD-13)

---

*Owner: Data Engineering Lead*
*Last Updated: January 2026*
