# PRD-24: Advanced Stock Screener

**Priority**: P1 | **Phase**: 13 | **Status**: Draft

---

## Problem Statement

Investors need powerful tools to filter the universe of stocks based on fundamental, technical, and custom criteria. Existing screeners are often limited in filter options, don't support custom formulas, and lack alerting capabilities. An advanced screener empowers users to find investment opportunities matching their specific criteria.

---

## Goals

1. **Comprehensive Filters** - 100+ built-in filters across fundamentals, technicals, and alternative data
2. **Custom Formulas** - User-defined screening criteria with expression language
3. **Saved Screens** - Persist and share screening configurations
4. **Real-time Alerts** - Notify when stocks enter/exit screen criteria
5. **Backtest Screens** - Historical performance of screening criteria
6. **Export & Integration** - Export results, integrate with portfolio tools

---

## Detailed Requirements

### R1: Filter Categories

#### R1.1: Fundamental Filters
| Category | Filters |
|----------|---------|
| **Valuation** | P/E, Forward P/E, PEG, P/S, P/B, EV/EBITDA, EV/Revenue, Dividend Yield |
| **Growth** | Revenue Growth (YoY, 3Y, 5Y), EPS Growth, FCF Growth, Dividend Growth |
| **Profitability** | Gross Margin, Operating Margin, Net Margin, ROE, ROA, ROIC |
| **Financial Health** | Debt/Equity, Current Ratio, Quick Ratio, Interest Coverage |
| **Size** | Market Cap, Enterprise Value, Revenue, Employees |
| **Dividends** | Yield, Payout Ratio, Years of Growth, Ex-Dividend Date |

#### R1.2: Technical Filters
| Category | Filters |
|----------|---------|
| **Price** | Price, 52-Week High/Low, % from High/Low, Gap % |
| **Moving Averages** | SMA (20/50/100/200), EMA, Price vs MA, MA Cross |
| **Momentum** | RSI, MACD, Stochastic, Rate of Change, Williams %R |
| **Volatility** | Beta, ATR, Standard Deviation, Bollinger Band Position |
| **Volume** | Average Volume, Relative Volume, Volume Trend |
| **Patterns** | New High/Low, Breakout, Support/Resistance |

#### R1.3: Alternative Data Filters
| Category | Filters |
|----------|---------|
| **Analyst** | Rating, Price Target Upside, Estimate Revisions |
| **Institutional** | Ownership %, Change in Ownership, # of Holders |
| **Insider** | Net Insider Buying, Insider Ownership % |
| **Short Interest** | Short Interest %, Days to Cover, Short Squeeze Score |
| **Sentiment** | News Sentiment, Social Sentiment, Earnings Surprise |

### R2: Filter Model

#### R2.1: Filter Definition
```python
@dataclass
class FilterDefinition:
    filter_id: str
    name: str
    category: FilterCategory
    data_type: DataType  # numeric, boolean, date, string
    description: str
    
    # For numeric filters
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    default_operator: str = "gte"  # gte, lte, eq, between
    
    # Metadata
    unit: Optional[str] = None  # %, $, ratio
    update_frequency: str = "daily"  # daily, realtime, quarterly
```

#### R2.2: Filter Condition
```python
@dataclass
class FilterCondition:
    filter_id: str
    operator: str  # eq, ne, gt, gte, lt, lte, between, in, not_in
    value: Any
    value2: Optional[Any] = None  # For 'between' operator
```

### R3: Custom Formulas

#### R3.1: Expression Language
```python
# Supported operations
- Arithmetic: +, -, *, /, %, ^
- Comparison: >, <, >=, <=, ==, !=
- Logical: and, or, not
- Functions: abs(), min(), max(), avg(), sqrt(), log()
- Conditionals: if(condition, true_val, false_val)

# Built-in variables (metrics)
- price, market_cap, pe_ratio, revenue, etc.
- sma_20, sma_50, rsi_14, macd, etc.

# Examples
"pe_ratio < industry_avg_pe"
"revenue_growth > 0.10 and debt_to_equity < 0.5"
"price > sma_50 and rsi_14 < 70"
"(gross_margin - industry_avg_margin) > 0.05"
```

#### R3.2: Custom Formula Model
```python
@dataclass
class CustomFormula:
    formula_id: str
    name: str
    expression: str
    description: Optional[str] = None
    created_by: str = ""
    created_at: datetime = None
```

### R4: Screen Configuration

#### R4.1: Screen Model
```python
@dataclass
class Screen:
    screen_id: str
    name: str
    description: Optional[str] = None
    
    # Filters
    filters: list[FilterCondition] = field(default_factory=list)
    custom_formulas: list[CustomFormula] = field(default_factory=list)
    
    # Universe
    universe: str = "all"  # all, sp500, nasdaq100, sector, custom
    sectors: list[str] = field(default_factory=list)
    market_cap_min: Optional[float] = None
    market_cap_max: Optional[float] = None
    
    # Display
    sort_by: str = "market_cap"
    sort_order: str = "desc"
    columns: list[str] = field(default_factory=list)
    
    # Metadata
    created_by: str = ""
    created_at: datetime = None
    is_public: bool = False
    tags: list[str] = field(default_factory=list)
```

#### R4.2: Screen Results
```python
@dataclass
class ScreenResult:
    screen_id: str
    run_at: datetime
    
    # Results
    total_universe: int
    matches: int
    stocks: list[ScreenMatch]
    
    # Performance
    execution_time_ms: float
```

### R5: Preset Screens

#### R5.1: Value Screens
| Screen | Criteria |
|--------|----------|
| **Deep Value** | P/E < 10, P/B < 1, Dividend Yield > 3% |
| **Warren Buffett** | ROE > 15%, Debt/Equity < 0.5, Consistent earnings growth |
| **Dividend Aristocrats** | 25+ years dividend growth, Payout < 60% |

#### R5.2: Growth Screens
| Screen | Criteria |
|--------|----------|
| **High Growth** | Revenue Growth > 20%, EPS Growth > 20% |
| **GARP** | PEG < 1.5, EPS Growth > 10%, ROE > 15% |
| **Momentum** | Price > SMA200, RSI > 50, New 52-week high |

#### R5.3: Quality Screens
| Screen | Criteria |
|--------|----------|
| **High Quality** | ROE > 20%, Gross Margin > 40%, FCF Positive |
| **Low Volatility** | Beta < 0.8, Standard Deviation < 20% |
| **Financially Strong** | Current Ratio > 2, Debt/Equity < 0.3 |

### R6: Screen Alerts

#### R6.1: Alert Types
| Type | Description |
|------|-------------|
| **Entry Alert** | Stock newly matches screen criteria |
| **Exit Alert** | Stock no longer matches criteria |
| **Count Alert** | # of matches crosses threshold |
| **Scheduled** | Run screen at specific times |

#### R6.2: Alert Model
```python
@dataclass
class ScreenAlert:
    alert_id: str
    screen_id: str
    alert_type: AlertType
    
    # Configuration
    enabled: bool = True
    notify_on_entry: bool = True
    notify_on_exit: bool = False
    
    # Delivery
    channels: list[str] = field(default_factory=list)  # email, push, webhook
    
    # State
    last_run: Optional[datetime] = None
    last_matches: list[str] = field(default_factory=list)
```

### R7: Screen Backtesting

#### R7.1: Backtest Configuration
```python
@dataclass
class ScreenBacktest:
    screen_id: str
    start_date: date
    end_date: date
    
    # Portfolio settings
    rebalance_frequency: str = "monthly"
    max_positions: int = 20
    equal_weight: bool = True
    
    # Results
    returns: list[float] = field(default_factory=list)
    benchmark_returns: list[float] = field(default_factory=list)
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Screen execution time | <2 seconds for 5000 stocks |
| Filter coverage | 100+ built-in filters |
| User adoption | 50%+ users create custom screens |
| Alert accuracy | 99%+ correct triggers |

---

## Dependencies

- Data infrastructure (PRD-01)
- Factor engine (PRD-02)
- Alerting system (PRD-13)

---

*Owner: Product Engineering Lead*
*Last Updated: January 2026*
