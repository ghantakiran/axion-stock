# PRD-34: Trade Journal

**Priority**: P1 | **Phase**: 23 | **Status**: Draft

---

## Problem Statement

Successful traders maintain detailed journals of their trades to identify patterns, improve decision-making, and track performance over time. A digital trade journal captures not just the trade mechanics (entry, exit, P&L) but also the context (setup, rationale, emotions) that led to each trade. This data enables powerful analytics to identify strengths, weaknesses, and areas for improvement.

---

## Goals

1. **Trade Logging** - Comprehensive trade entry with all relevant details
2. **Setup Tagging** - Categorize trades by strategy, setup type, and patterns
3. **Emotional Tracking** - Log psychological state before, during, and after trades
4. **Performance Analytics** - Win rate, profit factor, expectancy by various dimensions
5. **Pattern Recognition** - Identify what setups work best for the trader
6. **Review System** - Daily, weekly, monthly trade reviews

---

## Detailed Requirements

### R1: Trade Entry Model

#### R1.1: Trade Structure
```python
@dataclass
class Trade:
    trade_id: str
    symbol: str
    
    # Direction & Type
    direction: TradeDirection  # long, short
    trade_type: TradeType  # swing, day, scalp, position
    
    # Entry
    entry_date: datetime
    entry_price: float
    entry_quantity: int
    entry_reason: str
    
    # Exit
    exit_date: Optional[datetime]
    exit_price: Optional[float]
    exit_reason: str
    
    # P&L
    realized_pnl: float
    realized_pnl_pct: float
    fees: float
    
    # Setup & Strategy
    setup: str  # breakout, pullback, reversal, etc.
    strategy: str  # user-defined strategy name
    timeframe: str  # 1m, 5m, 1h, 1d, etc.
    
    # Tags
    tags: list[str]
    
    # Notes
    notes: str
    lessons_learned: str
    
    # Emotions
    pre_trade_emotion: EmotionalState
    during_trade_emotion: EmotionalState
    post_trade_emotion: EmotionalState
    
    # Screenshots
    screenshots: list[str]  # URLs/paths
    
    # Risk
    initial_stop: float
    initial_target: float
    risk_reward_planned: float
    risk_reward_actual: float
```

#### R1.2: Trade Types
| Type | Typical Duration |
|------|------------------|
| **Scalp** | Seconds to minutes |
| **Day Trade** | Intraday |
| **Swing** | Days to weeks |
| **Position** | Weeks to months |

### R2: Setup & Strategy Management

#### R2.1: Setup Categories
| Setup | Description |
|-------|-------------|
| **Breakout** | Price breaks key level |
| **Pullback** | Entry on retracement |
| **Reversal** | Counter-trend entry |
| **Momentum** | Following strong move |
| **Mean Reversion** | Fading extreme moves |
| **Gap Play** | Trading gap fills/continuations |
| **Earnings** | Around earnings announcements |
| **News** | News-driven trades |

#### R2.2: Strategy Tracking
```python
@dataclass
class Strategy:
    strategy_id: str
    name: str
    description: str
    
    # Rules
    entry_rules: list[str]
    exit_rules: list[str]
    
    # Risk parameters
    max_risk_per_trade: float
    target_risk_reward: float
    
    # Performance
    total_trades: int
    win_rate: float
    profit_factor: float
    expectancy: float
```

### R3: Emotional Tracking

#### R3.1: Emotional States
| State | Description |
|-------|-------------|
| **Calm** | Neutral, focused |
| **Confident** | High conviction |
| **Anxious** | Worried, uncertain |
| **FOMO** | Fear of missing out |
| **Greedy** | Overreaching |
| **Fearful** | Hesitant, scared |
| **Frustrated** | After losses |
| **Euphoric** | After wins |
| **Revenge** | Trying to recover losses |

#### R3.2: Emotion Analytics
- Correlation between emotions and outcomes
- Best/worst emotional states for trading
- Patterns in emotional sequences

### R4: Performance Analytics

#### R4.1: Core Metrics
| Metric | Formula |
|--------|---------|
| **Win Rate** | Winning trades / Total trades |
| **Profit Factor** | Gross profit / Gross loss |
| **Expectancy** | (Win% × Avg Win) - (Loss% × Avg Loss) |
| **Avg Winner** | Total profit / Winning trades |
| **Avg Loser** | Total loss / Losing trades |
| **Largest Win** | Max single trade profit |
| **Largest Loss** | Max single trade loss |
| **Max Drawdown** | Largest peak-to-trough decline |

#### R4.2: Breakdown Dimensions
- By setup type
- By strategy
- By time of day
- By day of week
- By symbol/sector
- By market condition
- By emotional state
- By trade duration

### R5: Pattern Recognition

#### R5.1: Analysis Features
| Feature | Description |
|---------|-------------|
| **Best Setups** | Highest win rate/profit factor setups |
| **Worst Setups** | Setups to avoid |
| **Time Patterns** | Best/worst trading times |
| **Streak Analysis** | Win/loss streak patterns |
| **Sizing Impact** | Performance vs position size |
| **Hold Time** | Optimal trade duration |

#### R5.2: Insights Generation
- Automated pattern detection
- Personalized recommendations
- Weakness identification
- Strength amplification

### R6: Review System

#### R6.1: Daily Review
```python
@dataclass
class DailyReview:
    review_date: date
    
    # Summary
    trades_taken: int
    gross_pnl: float
    net_pnl: float
    win_rate: float
    
    # Self-assessment
    followed_plan: bool
    mistakes_made: list[str]
    did_well: list[str]
    
    # Goals
    tomorrow_focus: str
    
    # Rating
    overall_rating: int  # 1-5
```

#### R6.2: Weekly/Monthly Review
- Performance summary
- Goal tracking
- Strategy adjustments
- Key learnings
- Action items

---

## Analytics Dashboard

### Key Visualizations
| Chart | Purpose |
|-------|---------|
| **Equity Curve** | P&L over time |
| **Win Rate by Setup** | Setup performance comparison |
| **P&L by Day/Hour** | Time-based patterns |
| **Emotion vs P&L** | Psychological impact |
| **R-Multiple Distribution** | Risk management quality |
| **Drawdown Chart** | Risk visualization |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Journal completion rate | 90%+ trades logged |
| User engagement | 80%+ daily review |
| Performance improvement | Measurable over time |
| Pattern accuracy | Actionable insights |

---

## Dependencies

- Portfolio tracking (PRD-08)
- Market data (PRD-01)
- File storage (screenshots)

---

*Owner: Product Engineering Lead*
*Last Updated: January 2026*
