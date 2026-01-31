# PRD-33: Sector Rotation Analysis

**Priority**: P1 | **Phase**: 22 | **Status**: Draft

---

## Problem Statement

Sector rotation is a key investment strategy where capital flows between sectors based on economic cycles and market conditions. Understanding which sectors are gaining or losing momentum helps investors position portfolios ahead of major moves. A sector rotation analysis system tracks relative performance, identifies rotation patterns, and maps sectors to business cycle phases.

---

## Goals

1. **Sector Rankings** - Real-time sector strength and momentum rankings
2. **Rotation Detection** - Identify when money flows between sectors
3. **Relative Performance** - Compare sector performance vs benchmarks
4. **Business Cycle Mapping** - Map sectors to economic cycle phases
5. **ETF Recommendations** - Suggest sector ETFs based on analysis
6. **Historical Patterns** - Analyze historical rotation patterns

---

## Detailed Requirements

### R1: Sector Model

#### R1.1: Sector Structure
```python
@dataclass
class Sector:
    sector_id: str
    name: str
    
    # ETF tracking
    etf_symbol: str  # Primary sector ETF (XLK, XLF, etc.)
    
    # Current metrics
    price: float
    change_1d: float
    change_1w: float
    change_1m: float
    change_3m: float
    change_ytd: float
    
    # Relative strength
    rs_vs_spy: float  # Relative strength vs S&P 500
    rs_rank: int      # Rank among sectors
    
    # Momentum
    momentum_score: float
    trend: str  # up, down, neutral
```

#### R1.2: GICS Sectors (11)
| Sector | ETF | Description |
|--------|-----|-------------|
| Technology | XLK | Information Technology |
| Healthcare | XLV | Healthcare |
| Financials | XLF | Financial Services |
| Consumer Discretionary | XLY | Consumer Cyclical |
| Consumer Staples | XLP | Consumer Defensive |
| Energy | XLE | Oil, Gas, Energy |
| Utilities | XLU | Utilities |
| Real Estate | XLRE | Real Estate |
| Materials | XLB | Basic Materials |
| Industrials | XLI | Industrial |
| Communication Services | XLC | Communication |

### R2: Rotation Detection

#### R2.1: Rotation Signal
```python
@dataclass
class RotationSignal:
    signal_id: str
    signal_date: date
    
    # Flow direction
    from_sector: str
    to_sector: str
    
    # Strength
    signal_strength: SignalStrength
    confidence: float
    
    # Evidence
    relative_performance_change: float
    volume_confirmation: bool
    breadth_confirmation: bool
```

#### R2.2: Detection Methods
| Method | Description |
|--------|-------------|
| **Relative Strength** | RS line breakouts/breakdowns |
| **Money Flow** | Volume-weighted price trends |
| **Breadth** | % of stocks above moving averages |
| **Momentum Divergence** | Sector momentum vs market |

### R3: Relative Performance Analysis

#### R3.1: Performance Metrics
```python
@dataclass
class SectorPerformance:
    sector: str
    period: str  # 1d, 1w, 1m, 3m, 6m, 1y
    
    # Returns
    absolute_return: float
    relative_return: float  # vs benchmark
    
    # Risk-adjusted
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    
    # Comparison
    rank: int
    percentile: float
```

#### R3.2: Relative Strength Calculation
- RS = Sector Price / Benchmark Price
- RS Ratio = Current RS / RS Moving Average
- RS Momentum = Rate of change of RS

### R4: Business Cycle Mapping

#### R4.1: Cycle Phases
| Phase | Description | Favored Sectors |
|-------|-------------|-----------------|
| **Early Expansion** | Recovery from recession | Financials, Consumer Disc, Industrials |
| **Mid Expansion** | Sustained growth | Technology, Industrials, Materials |
| **Late Expansion** | Peak growth, rising rates | Energy, Materials, Healthcare |
| **Early Contraction** | Slowdown begins | Healthcare, Consumer Staples, Utilities |
| **Late Contraction** | Recession | Utilities, Consumer Staples, Healthcare |

#### R4.2: Cycle Detection
```python
@dataclass
class BusinessCycle:
    current_phase: CyclePhase
    phase_confidence: float
    
    # Indicators
    gdp_trend: str
    employment_trend: str
    inflation_trend: str
    yield_curve: str
    
    # Sector implications
    overweight_sectors: list[str]
    underweight_sectors: list[str]
```

### R5: Sector ETF Recommendations

#### R5.1: Recommendation Model
```python
@dataclass
class SectorRecommendation:
    sector: str
    etf_symbol: str
    
    # Rating
    recommendation: str  # overweight, neutral, underweight
    conviction: str  # low, medium, high
    
    # Rationale
    momentum_score: float
    relative_strength: float
    cycle_alignment: bool
    
    # Targets
    target_weight: float
    current_weight: float
```

#### R5.2: ETF Selection Criteria
- Liquidity (AUM, volume)
- Expense ratio
- Tracking error
- Options availability

### R6: Historical Analysis

#### R6.1: Rotation History
- Track historical rotation patterns
- Seasonal patterns by sector
- Performance after rotation signals
- Drawdown analysis

#### R6.2: Pattern Recognition
| Pattern | Description |
|---------|-------------|
| **Risk-On** | Rotation to cyclicals |
| **Risk-Off** | Rotation to defensives |
| **Inflation Trade** | Energy, Materials, TIPS |
| **Growth to Value** | Tech to Financials |
| **Rate Sensitive** | Impact of rate changes |

---

## Sector ETF Reference

### Primary Sector ETFs (SPDR)
| Sector | Symbol | Name |
|--------|--------|------|
| Technology | XLK | Technology Select Sector SPDR |
| Healthcare | XLV | Health Care Select Sector SPDR |
| Financials | XLF | Financial Select Sector SPDR |
| Consumer Disc | XLY | Consumer Discretionary Select Sector |
| Consumer Staples | XLP | Consumer Staples Select Sector |
| Energy | XLE | Energy Select Sector SPDR |
| Utilities | XLU | Utilities Select Sector SPDR |
| Real Estate | XLRE | Real Estate Select Sector SPDR |
| Materials | XLB | Materials Select Sector SPDR |
| Industrials | XLI | Industrial Select Sector SPDR |
| Communication | XLC | Communication Services Select Sector |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Rotation signal accuracy | 65%+ |
| Cycle phase accuracy | 70%+ |
| Recommendation performance | Beat SPY |
| User engagement | 50%+ weekly check |

---

## Dependencies

- Market data (PRD-01)
- Economic data (PRD-31)
- Technical indicators (internal)

---

*Owner: Product Engineering Lead*
*Last Updated: January 2026*
