# PRD-30: Market Scanner

**Priority**: P1 | **Phase**: 19 | **Status**: Draft

---

## Problem Statement

Active traders need to quickly identify trading opportunities across thousands of stocks. Manual screening is too slow for catching fast-moving setups like gaps, breakouts, unusual volume, and momentum shifts. A real-time market scanner automatically detects these patterns and alerts traders to opportunities as they develop.

---

## Goals

1. **Real-Time Scanning** - Continuously scan markets for trading setups
2. **Pre-Built Scans** - Ready-to-use scans for common patterns
3. **Custom Scans** - Build custom scans with flexible criteria
4. **Unusual Activity** - Detect unusual volume, options activity, price moves
5. **Technical Patterns** - Identify chart patterns and technical setups
6. **Alerts Integration** - Push notifications when scans trigger

---

## Detailed Requirements

### R1: Scanner Architecture

#### R1.1: Scanner Model
```python
@dataclass
class Scanner:
    scanner_id: str
    name: str
    description: str
    
    # Criteria
    criteria: list[ScanCriterion]
    universe: ScanUniverse
    
    # Configuration
    is_active: bool = True
    scan_interval: int = 60  # seconds
    max_results: int = 50
    
    # Scheduling
    active_hours: Optional[tuple[time, time]] = None  # Market hours
    active_days: list[int] = field(default_factory=lambda: [0,1,2,3,4])  # Mon-Fri
    
    # Results
    last_scan: Optional[datetime] = None
    last_results: list[ScanResult] = field(default_factory=list)
```

#### R1.2: Scan Criterion
```python
@dataclass
class ScanCriterion:
    criterion_id: str
    field: str  # price, volume, rsi, etc.
    operator: Operator  # gt, lt, eq, between, crosses_above, etc.
    value: Union[float, tuple[float, float]]
    
    # Time-based
    timeframe: Optional[str] = None  # 1m, 5m, 1h, 1d
    periods_back: int = 0
```

### R2: Pre-Built Scans

#### R2.1: Price Action Scans
| Scan | Description |
|------|-------------|
| **Gap Up >3%** | Stocks gapping up more than 3% |
| **Gap Down >3%** | Stocks gapping down more than 3% |
| **New 52W High** | Making new 52-week highs |
| **New 52W Low** | Making new 52-week lows |
| **Breaking Resistance** | Price breaking above key resistance |
| **Breaking Support** | Price breaking below key support |

#### R2.2: Volume Scans
| Scan | Description |
|------|-------------|
| **Volume Spike** | Volume > 200% of average |
| **High Relative Volume** | Volume significantly above normal |
| **Increasing Volume** | Volume trend increasing |
| **Volume Breakout** | Price + volume breakout |

#### R2.3: Technical Scans
| Scan | Description |
|------|-------------|
| **RSI Oversold** | RSI < 30 |
| **RSI Overbought** | RSI > 70 |
| **MACD Crossover** | MACD crossing signal line |
| **Golden Cross** | 50 SMA crossing above 200 SMA |
| **Death Cross** | 50 SMA crossing below 200 SMA |
| **Bollinger Squeeze** | Bands narrowing significantly |

#### R2.4: Momentum Scans
| Scan | Description |
|------|-------------|
| **Up >5% Today** | Stocks up more than 5% intraday |
| **Down >5% Today** | Stocks down more than 5% intraday |
| **Momentum Leaders** | Top momentum stocks |
| **Reversal Candidates** | Oversold with bullish divergence |

### R3: Custom Scan Builder

#### R3.1: Available Fields
| Category | Fields |
|----------|--------|
| **Price** | open, high, low, close, change, change_pct, gap_pct |
| **Volume** | volume, avg_volume, relative_volume |
| **Moving Averages** | sma_5, sma_10, sma_20, sma_50, sma_200, ema_9, ema_21 |
| **Oscillators** | rsi, stochastic_k, stochastic_d, cci, williams_r |
| **Trend** | macd, macd_signal, macd_histogram, adx, plus_di, minus_di |
| **Volatility** | atr, bb_upper, bb_lower, bb_width |
| **Fundamentals** | market_cap, pe_ratio, volume_dollar |

#### R3.2: Operators
| Operator | Description |
|----------|-------------|
| `gt`, `lt`, `eq` | Greater than, less than, equals |
| `gte`, `lte` | Greater/less than or equal |
| `between` | Value between two numbers |
| `crosses_above` | Crosses above a value/indicator |
| `crosses_below` | Crosses below a value/indicator |
| `increasing` | Value increasing over N periods |
| `decreasing` | Value decreasing over N periods |

### R4: Unusual Activity Detection

#### R4.1: Unusual Activity Model
```python
@dataclass
class UnusualActivity:
    symbol: str
    activity_type: ActivityType
    
    # Metrics
    current_value: float
    normal_value: float
    deviation: float  # Standard deviations from normal
    
    # Context
    detected_at: datetime
    description: str
```

#### R4.2: Activity Types
| Type | Detection Method |
|------|------------------|
| **Volume Surge** | Volume > 3 std dev above average |
| **Price Spike** | Price move > 3 std dev |
| **Options Activity** | Unusual options volume/OI |
| **Dark Pool Prints** | Large block trades |
| **Halt/Resume** | Trading halts and resumes |

### R5: Pattern Detection

#### R5.1: Chart Patterns
| Pattern | Description |
|---------|-------------|
| **Double Top** | Bearish reversal pattern |
| **Double Bottom** | Bullish reversal pattern |
| **Head & Shoulders** | Reversal pattern |
| **Triangle** | Ascending, descending, symmetric |
| **Flag/Pennant** | Continuation patterns |
| **Cup & Handle** | Bullish continuation |

#### R5.2: Candlestick Patterns
| Pattern | Type |
|---------|------|
| **Doji** | Indecision |
| **Hammer** | Bullish reversal |
| **Shooting Star** | Bearish reversal |
| **Engulfing** | Reversal (bullish/bearish) |
| **Morning Star** | Bullish reversal |
| **Evening Star** | Bearish reversal |

### R6: Scan Results & Alerts

#### R6.1: Scan Result Model
```python
@dataclass
class ScanResult:
    result_id: str
    scanner_id: str
    symbol: str
    
    # Match data
    matched_at: datetime
    match_criteria: list[str]
    
    # Current values
    price: float
    change_pct: float
    volume: int
    
    # Scores
    signal_strength: float  # 0-100
    
    # Context
    sector: str
    market_cap: float
```

#### R6.2: Alert Integration
- Push notification on scan trigger
- Email digest of scan results
- Webhook integration
- Custom alert sounds

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Scan latency | < 5 seconds |
| Pattern accuracy | > 80% |
| User engagement | 60%+ daily use |
| Alert accuracy | > 90% valid signals |

---

## Dependencies

- Market data (PRD-01)
- Technical indicators (internal)
- Alerting system (PRD-13)
- Screener (PRD-24)

---

*Owner: Product Engineering Lead*
*Last Updated: January 2026*
