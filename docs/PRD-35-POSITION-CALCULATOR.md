# PRD-35: Position Calculator

**Priority**: P1 | **Phase**: 24 | **Status**: Draft

---

## Problem Statement

Proper position sizing is critical to risk management and long-term survival. Traders need to calculate position sizes based on account risk, stop-loss distance, and portfolio constraints. A position calculator helps determine how many shares or contracts to trade, tracks portfolio heat (total risk exposure), and enforces max drawdown limits.

---

## Goals

1. **Risk-Based Sizing** - Size positions by dollar or percentage risk per trade
2. **Kelly Criterion** - Optional Kelly-based sizing for edge estimation
3. **Portfolio Heat** - Track total risk exposure across open positions
4. **Max Drawdown Limits** - Enforce and monitor drawdown constraints
5. **Multi-Asset Support** - Stocks, options, futures with different conventions
6. **Integration** - Work with execution and risk modules

---

## Detailed Requirements

### R1: Position Sizing Model

#### R1.1: Sizing Inputs
```python
@dataclass
class SizingInputs:
    account_value: float
    risk_per_trade_pct: float  # e.g., 1.0 = 1%
    risk_per_trade_dollars: Optional[float] = None  # Override % if set
    
    # Entry/Stop
    entry_price: float
    stop_price: float
    stop_type: StopType  # fixed, atr_based, percent
    
    # Optional target
    target_price: Optional[float] = None
    
    # Instrument
    instrument_type: InstrumentType  # stock, option, future
    contract_multiplier: int = 1  # 100 for options, varies for futures
```

#### R1.2: Sizing Output
```python
@dataclass
class SizingResult:
    position_size: int  # shares or contracts
    position_value: float
    risk_amount: float
    risk_pct: float
    
    # Risk/Reward
    risk_reward_ratio: Optional[float] = None
    r_multiple: Optional[float] = None  # 1R = initial risk
    
    # Warnings
    exceeds_max_position: bool = False
    exceeds_portfolio_heat: bool = False
    warnings: list[str] = field(default_factory=list)
```

### R2: Risk-Based Sizing

#### R2.1: Fixed Risk Formula
- Risk Amount = Account × Risk%
- Shares = Risk Amount / (Entry - Stop) per share
- For shorts: Shares = Risk Amount / (Stop - Entry)

#### R2.2: Stop Types
| Type | Description |
|------|-------------|
| **Fixed** | User provides stop price |
| **ATR Based** | Stop = Entry ± (N × ATR) |
| **Percent** | Stop = Entry × (1 ± pct) |

### R3: Kelly Criterion

#### R3.1: Full Kelly
- f* = (p × b - q) / b
- p = win probability, q = 1-p, b = win/loss ratio (avg win / avg loss)
- Optional: use half-Kelly or quarter-Kelly for safety

#### R3.2: Inputs
- Win rate (historical or estimated)
- Average win / average loss ratio
- Kelly fraction (1.0 = full, 0.5 = half)

### R4: Portfolio Heat

#### R4.1: Heat Definition
```python
@dataclass
class PortfolioHeat:
    total_heat_pct: float  # Sum of (position risk / account) across all positions
    total_heat_dollars: float
    position_heats: dict[str, float]  # symbol -> risk %
    exceeds_limit: bool
    heat_limit_pct: float
```

#### R4.2: Heat Calculation
- Per position: risk from entry to stop (or ATR-based)
- Total heat = sum of all position risks as % of account
- Typical limit: 5–10% total portfolio heat

### R5: Max Drawdown Limits

#### R5.1: Drawdown Tracking
```python
@dataclass
class DrawdownState:
    peak_value: float
    current_value: float
    drawdown_pct: float
    drawdown_dollars: float
    at_limit: bool
    limit_pct: float
```

#### R5.2: Actions
- Reduce position sizes when approaching limit
- Block new trades when at limit
- Alert when drawdown exceeds threshold

### R6: Multi-Asset Support

#### R6.1: Instrument Types
| Type | Multiplier | Risk Calculation |
|------|------------|------------------|
| **Stock** | 1 | (Entry - Stop) × Shares |
| **Option** | 100 | Per contract delta-adjusted or nominal |
| **Future** | Contract specific | Tick value × ticks to stop |

#### R6.2: Conventions
- Round down shares to whole numbers
- Option contracts in whole numbers
- Futures in whole contracts

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Sizing accuracy | Correct to 1 share/contract |
| Heat tracking | Real-time, < 1 min delay |
| Drawdown alerts | 100% when limit hit |
| User adoption | 70%+ use before trading |

---

## Dependencies

- Risk module (PRD-04, PRD-17)
- Execution (PRD-03)
- Portfolio (PRD-08)

---

*Owner: Product Engineering Lead*
*Last Updated: January 2026*
