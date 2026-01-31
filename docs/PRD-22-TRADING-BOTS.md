# PRD-22: Automated Trading Bots

**Priority**: P1 | **Phase**: 12 | **Status**: Draft

---

## Problem Statement

Manual trading requires constant attention and is prone to emotional decision-making. Traders need automated systems that can execute strategies consistently, handle recurring investments (DCA), and react to market conditions 24/7. An automated trading bot system enables disciplined execution, reduces emotional trading, and allows sophisticated strategies to run unattended.

---

## Goals

1. **Rule-Based Strategies** - Define trading rules with conditions and actions
2. **Scheduled Execution** - Time-based triggers (daily, weekly, monthly)
3. **DCA Automation** - Dollar-cost averaging with configurable schedules
4. **Signal-Based Trading** - React to technical indicators, price levels, factor scores
5. **Portfolio Rebalancing Bots** - Automatic rebalancing to target allocations
6. **Risk-Controlled Execution** - Position limits, stop-losses, drawdown protection

---

## Detailed Requirements

### R1: Bot Framework

#### R1.1: Bot Types
| Type | Description | Use Case |
|------|-------------|----------|
| **DCA Bot** | Recurring purchases at intervals | Long-term accumulation |
| **Rebalance Bot** | Maintain target allocations | Portfolio management |
| **Signal Bot** | Trade on technical/factor signals | Active trading |
| **Grid Bot** | Buy/sell at price grid levels | Range-bound markets |
| **Mean Reversion Bot** | Trade RSI/deviation extremes | Contrarian strategies |
| **Momentum Bot** | Follow trends and breakouts | Trend following |

#### R1.2: Bot Configuration
```python
@dataclass
class BotConfig:
    bot_id: str
    name: str
    bot_type: BotType
    account_id: str
    enabled: bool
    
    # Trading parameters
    symbols: list[str]
    max_position_size: float
    max_portfolio_pct: float
    
    # Schedule
    schedule: ScheduleConfig
    
    # Risk controls
    max_daily_trades: int
    max_daily_loss: float
    stop_loss_pct: Optional[float]
    take_profit_pct: Optional[float]
    
    # Execution
    order_type: str  # 'market', 'limit'
    limit_offset_pct: float  # For limit orders
```

### R2: DCA (Dollar-Cost Averaging) Bot

#### R2.1: DCA Configuration
```python
@dataclass
class DCAConfig:
    # Investment
    amount_per_period: float
    currency: str
    
    # Schedule
    frequency: str  # 'daily', 'weekly', 'biweekly', 'monthly'
    day_of_week: Optional[int]  # 0=Monday for weekly
    day_of_month: Optional[int]  # For monthly
    time_of_day: str  # 'market_open', 'market_close', 'HH:MM'
    
    # Allocation
    allocations: dict[str, float]  # symbol -> percentage
    
    # Options
    skip_if_price_above: Optional[float]  # Skip if above threshold
    increase_on_dip_pct: Optional[float]  # Buy more on dips
    dip_threshold_pct: float  # What constitutes a dip
```

#### R2.2: DCA Features
- Multiple frequency options (daily to monthly)
- Fixed amount or percentage of portfolio
- Multi-asset allocation (e.g., 60% SPY, 40% BND)
- Dip-buying enhancement
- Skip conditions (price too high, market closed)
- Reinvest dividends option

### R3: Rebalancing Bot

#### R3.1: Rebalance Configuration
```python
@dataclass
class RebalanceConfig:
    # Target allocation
    target_allocations: dict[str, float]  # symbol -> target %
    
    # Triggers
    rebalance_frequency: str  # 'daily', 'weekly', 'monthly', 'quarterly'
    drift_threshold_pct: float  # Rebalance if drift exceeds
    
    # Execution
    rebalance_method: str  # 'full', 'threshold_only', 'tax_aware'
    min_trade_size: float
    
    # Tax optimization
    tax_aware: bool
    avoid_wash_sales: bool
    prefer_long_term_lots: bool
```

#### R3.2: Rebalance Features
- Target weight maintenance
- Drift-based triggers
- Tax-aware rebalancing (sell losers first)
- Cash flow rebalancing (use new cash)
- Band-based rebalancing (5/25 rule)

### R4: Signal-Based Bot

#### R4.1: Signal Types
| Signal | Description | Parameters |
|--------|-------------|------------|
| **Price Cross** | Price crosses MA or level | Period, direction |
| **RSI** | Overbought/oversold | Period, thresholds |
| **MACD** | Crossover signals | Fast, slow, signal |
| **Bollinger** | Band touches/breaks | Period, std dev |
| **Volume Spike** | Unusual volume | Multiplier |
| **Factor Score** | Factor threshold | Factor, threshold |
| **News Sentiment** | Sentiment change | Min score |

#### R4.2: Signal Configuration
```python
@dataclass
class SignalConfig:
    signal_type: SignalType
    parameters: dict[str, Any]
    
    # Conditions
    condition: str  # 'above', 'below', 'crosses_above', 'crosses_below'
    threshold: float
    
    # Confirmation
    require_confirmation: bool
    confirmation_periods: int
    
    # Action
    action: str  # 'buy', 'sell', 'alert_only'
    position_size_method: str  # 'fixed', 'atr_based', 'volatility_scaled'
```

### R5: Grid Trading Bot

#### R5.1: Grid Configuration
```python
@dataclass
class GridConfig:
    symbol: str
    
    # Grid setup
    grid_type: str  # 'arithmetic', 'geometric'
    upper_price: float
    lower_price: float
    num_grids: int
    
    # Position sizing
    total_investment: float
    amount_per_grid: float
    
    # Options
    trailing_up: bool  # Move grid up in uptrend
    trailing_down: bool  # Move grid down in downtrend
    stop_loss_price: Optional[float]
```

### R6: Bot Execution Engine

#### R6.1: Execution Flow
```
Schedule/Signal Trigger
        │
        ▼
   Pre-Trade Checks
   (Risk, Limits, Hours)
        │
        ▼
   Generate Orders
        │
        ▼
   Execute via Broker
        │
        ▼
   Record & Notify
```

#### R6.2: Scheduler
```python
class BotScheduler:
    """Manages bot execution schedules."""
    
    def schedule_bot(self, bot: Bot) -> None:
        """Add bot to schedule."""
    
    def run_due_bots(self) -> list[BotExecution]:
        """Execute all bots due to run."""
    
    def get_next_run(self, bot_id: str) -> datetime:
        """Get next scheduled run time."""
```

### R7: Risk Controls

#### R7.1: Bot-Level Risk
| Control | Description |
|---------|-------------|
| Max Position | Maximum position size per symbol |
| Max Portfolio % | Maximum % of portfolio per bot |
| Daily Loss Limit | Stop trading after X loss |
| Daily Trade Limit | Maximum trades per day |
| Drawdown Halt | Pause if drawdown exceeds threshold |

#### R7.2: Global Risk
```python
@dataclass
class GlobalBotRisk:
    max_total_bot_allocation: float  # Max % managed by bots
    max_concurrent_orders: int
    require_manual_approval_above: float  # Large orders need approval
    emergency_stop_all: bool
    allowed_trading_hours: tuple[str, str]
```

### R8: Monitoring & Notifications

#### R8.1: Bot Events
| Event | Notification |
|-------|--------------|
| Trade Executed | Order details, P&L |
| Schedule Missed | Reason (market closed, error) |
| Risk Limit Hit | Which limit, current value |
| Bot Error | Error details |
| Performance Report | Daily/weekly summary |

#### R8.2: Dashboard Metrics
- Active bots count
- Today's executions
- Total invested via bots
- Bot performance vs benchmark
- Upcoming scheduled runs

### R9: Data Storage

#### R9.1: Database Tables
```sql
-- Bot configurations
CREATE TABLE trading_bots (
    bot_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    bot_type VARCHAR(50) NOT NULL,
    config JSONB NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bot executions
CREATE TABLE bot_executions (
    execution_id UUID PRIMARY KEY,
    bot_id UUID REFERENCES trading_bots(bot_id),
    scheduled_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    status VARCHAR(20),  -- 'success', 'failed', 'skipped'
    orders_placed INT,
    total_value DECIMAL(15,2),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bot orders
CREATE TABLE bot_orders (
    order_id UUID PRIMARY KEY,
    execution_id UUID REFERENCES bot_executions(execution_id),
    bot_id UUID REFERENCES trading_bots(bot_id),
    symbol VARCHAR(20),
    side VARCHAR(10),
    quantity DECIMAL(15,6),
    order_type VARCHAR(20),
    limit_price DECIMAL(15,4),
    filled_price DECIMAL(15,4),
    status VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bot performance
CREATE TABLE bot_performance (
    id UUID PRIMARY KEY,
    bot_id UUID REFERENCES trading_bots(bot_id),
    date DATE,
    total_invested DECIMAL(15,2),
    current_value DECIMAL(15,2),
    realized_pnl DECIMAL(15,2),
    unrealized_pnl DECIMAL(15,2),
    num_trades INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Schedule accuracy | >99% on-time execution |
| Order fill rate | >98% successful fills |
| Uptime | 99.9% availability |
| DCA consistency | 100% scheduled investments made |

---

## Dependencies

- Execution system (PRD-03)
- Risk management (PRD-04/17)
- Paper trading for testing (PRD-19)
- Alerting system (PRD-13)

---

*Owner: Trading Systems Lead*
*Last Updated: January 2026*
