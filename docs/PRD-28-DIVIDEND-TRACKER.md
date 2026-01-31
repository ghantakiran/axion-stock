# PRD-28: Dividend Tracker

**Priority**: P1 | **Phase**: 17 | **Status**: Draft

---

## Problem Statement

Income-focused investors need comprehensive tools to track dividends across their portfolio. They want to know upcoming ex-dates, project future income, analyze dividend safety, and understand the tax implications of their dividend strategy. A dividend tracker helps investors build and maintain income-generating portfolios with confidence.

---

## Goals

1. **Dividend Calendar** - Track ex-dates, payment dates, and amounts
2. **Income Projections** - Forecast monthly/annual dividend income
3. **Yield Analysis** - Current yield, yield-on-cost, forward yield
4. **Dividend Safety** - Payout ratios, coverage, growth sustainability
5. **DRIP Simulation** - Model dividend reinvestment growth
6. **Tax Optimization** - Qualified vs non-qualified, tax-loss harvesting

---

## Detailed Requirements

### R1: Dividend Calendar

#### R1.1: Dividend Event Model
```python
@dataclass
class DividendEvent:
    event_id: str
    symbol: str
    company_name: str
    
    # Key dates
    declaration_date: Optional[date] = None
    ex_dividend_date: date
    record_date: Optional[date] = None
    payment_date: Optional[date] = None
    
    # Amount
    amount: float  # Per share
    frequency: DividendFrequency  # monthly, quarterly, semi-annual, annual
    dividend_type: DividendType  # regular, special, return_of_capital
    
    # Tax classification
    is_qualified: bool = True
    
    # Changes
    previous_amount: Optional[float] = None
    change_pct: Optional[float] = None
```

#### R1.2: Calendar Views
| View | Description |
|------|-------------|
| **Upcoming Ex-Dates** | Next 30 days ex-dividend dates |
| **Payment Schedule** | Expected payment dates |
| **Portfolio Calendar** | Only portfolio holdings |
| **Monthly Summary** | Aggregated by month |

### R2: Income Projections

#### R2.1: Income Model
```python
@dataclass
class DividendIncome:
    symbol: str
    shares: float
    
    # Annual projections
    annual_dividend_per_share: float
    annual_income: float
    
    # Monthly breakdown
    monthly_income: list[float]  # 12 months
    
    # Yield metrics
    current_yield: float
    yield_on_cost: float
    forward_yield: float
```

#### R2.2: Portfolio Income
```python
@dataclass
class PortfolioIncome:
    # Total projections
    annual_income: float
    monthly_average: float
    
    # Monthly breakdown
    monthly_projections: dict[str, float]  # month -> amount
    
    # By holding
    income_by_symbol: dict[str, float]
    
    # Yield metrics
    portfolio_yield: float
    weighted_yield_on_cost: float
```

### R3: Yield Analysis

#### R3.1: Yield Metrics
| Metric | Calculation |
|--------|-------------|
| **Current Yield** | Annual dividend / Current price |
| **Yield on Cost** | Annual dividend / Cost basis |
| **Forward Yield** | Forward dividend / Current price |
| **Trailing Yield** | TTM dividends / Current price |

#### R3.2: Yield Model
```python
@dataclass
class YieldAnalysis:
    symbol: str
    
    # Yields
    current_yield: float
    forward_yield: float
    trailing_yield: float
    yield_on_cost: float
    
    # Comparison
    sector_avg_yield: float
    yield_vs_sector: float
    
    # Historical
    yield_5y_avg: float
    yield_percentile: float  # Current vs 5yr range
```

### R4: Dividend Safety

#### R4.1: Safety Metrics
| Metric | Description | Safe Threshold |
|--------|-------------|----------------|
| **Payout Ratio** | Dividends / EPS | < 60% |
| **Cash Payout** | Dividends / FCF | < 70% |
| **Coverage Ratio** | EPS / DPS | > 1.5x |
| **Debt/EBITDA** | Leverage check | < 3x |
| **Interest Coverage** | EBIT / Interest | > 3x |

#### R4.2: Safety Model
```python
@dataclass
class DividendSafety:
    symbol: str
    
    # Payout ratios
    payout_ratio: float
    cash_payout_ratio: float
    coverage_ratio: float
    
    # Balance sheet
    debt_to_ebitda: float
    interest_coverage: float
    
    # Scoring
    safety_score: float  # 0-100
    safety_rating: SafetyRating  # safe, moderate, risky, dangerous
    
    # Red flags
    red_flags: list[str]
```

### R5: Dividend Growth

#### R5.1: Growth Metrics
```python
@dataclass
class DividendGrowth:
    symbol: str
    
    # Historical growth
    cagr_1y: float
    cagr_3y: float
    cagr_5y: float
    cagr_10y: float
    
    # Streak
    consecutive_increases: int
    dividend_aristocrat: bool  # 25+ years
    dividend_king: bool  # 50+ years
    
    # History
    dividend_history: list[DividendRecord]
```

#### R5.2: Growth Categories
| Category | Criteria |
|----------|----------|
| **Dividend King** | 50+ years consecutive increases |
| **Dividend Aristocrat** | 25+ years consecutive increases |
| **Dividend Achiever** | 10+ years consecutive increases |
| **Dividend Contender** | 5-9 years consecutive increases |

### R6: DRIP Simulation

#### R6.1: DRIP Model
```python
@dataclass
class DRIPSimulation:
    symbol: str
    initial_shares: float
    initial_investment: float
    
    # Simulation parameters
    years: int
    dividend_growth_rate: float
    price_growth_rate: float
    
    # Results
    final_shares: float
    final_value: float
    total_dividends_received: float
    total_dividends_reinvested: float
    
    # Year-by-year
    yearly_projections: list[DRIPYear]
```

#### R6.2: DRIP Year
```python
@dataclass
class DRIPYear:
    year: int
    starting_shares: float
    dividends_received: float
    shares_purchased: float
    ending_shares: float
    ending_value: float
    yield_on_original_cost: float
```

### R7: Tax Considerations

#### R7.1: Tax Classification
| Type | Tax Treatment |
|------|---------------|
| **Qualified** | Long-term capital gains rates |
| **Non-Qualified** | Ordinary income rates |
| **Return of Capital** | Reduces cost basis |
| **Foreign** | May have withholding |

#### R7.2: Tax Model
```python
@dataclass
class DividendTaxAnalysis:
    # Income breakdown
    qualified_dividends: float
    non_qualified_dividends: float
    return_of_capital: float
    foreign_dividends: float
    foreign_tax_withheld: float
    
    # Tax estimates
    estimated_tax_qualified: float
    estimated_tax_ordinary: float
    total_estimated_tax: float
    after_tax_income: float
    
    # Effective rate
    effective_tax_rate: float
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Ex-date accuracy | 99%+ |
| Income projection accuracy | Within 5% |
| Coverage | 95%+ of dividend stocks |
| User adoption | 50%+ income investors |

---

## Dependencies

- Market data (PRD-01)
- Portfolio management (PRD-08)
- Tax optimization (PRD-20)
- Alerting (PRD-13)

---

*Owner: Product Engineering Lead*
*Last Updated: January 2026*
