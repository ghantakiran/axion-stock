# PRD-03: Order Execution & Brokerage Integration

**Priority**: P0 | **Phase**: 2 | **Status**: Draft

---

## Problem Statement

Axion is currently a recommendation-only platform. Users see stock picks but must manually execute trades through a separate brokerage. This creates friction, timing delays, and prevents automated strategy execution. To be the best algo platform, Axion must execute trades natively.

---

## Goals

1. **Paper trading** with simulated execution and realistic fills
2. **Live trading** via Alpaca (primary) and Interactive Brokers (secondary)
3. **Smart order routing** with slippage minimization
4. **Automated rebalancing** based on factor model signals
5. **Position sizing** using Kelly Criterion and volatility targeting
6. **Trade journaling** with full audit trail

---

## Non-Goals

- Building a brokerage (we integrate with existing ones)
- High-frequency trading (<1 second holding periods)
- Cryptocurrency order execution (covered in PRD-12)
- Options order execution (covered in PRD-06)

---

## Detailed Requirements

### R1: Brokerage Integration Layer

#### R1.1: Alpaca Integration (Primary)
```python
class AlpacaBroker:
    """Primary brokerage integration."""

    async def connect(self, api_key: str, secret_key: str, paper: bool = True)
    async def get_account(self) -> AccountInfo
    async def get_positions(self) -> list[Position]
    async def get_orders(self, status: str = 'all') -> list[Order]
    async def submit_order(self, order: OrderRequest) -> Order
    async def cancel_order(self, order_id: str) -> bool
    async def cancel_all_orders(self) -> int
    async def get_portfolio_history(self, period: str) -> PortfolioHistory
    async def stream_trade_updates(self, callback: Callable)
```

**Why Alpaca**:
- Free commission trading
- Excellent REST + WebSocket API
- Paper trading built-in
- Fractional shares supported
- Python SDK available

#### R1.2: Interactive Brokers Integration (Secondary)
- TWS API integration via `ib_insync`
- Support for IB paper accounts
- Access to international markets
- Options execution support (future)

#### R1.3: Broker Abstraction Layer
```python
class BrokerInterface(Protocol):
    """Unified interface for all brokerages."""

    async def get_account(self) -> AccountInfo
    async def get_positions(self) -> list[Position]
    async def submit_order(self, order: OrderRequest) -> Order
    async def cancel_order(self, order_id: str) -> bool
    async def stream_updates(self, callback: Callable)

class AccountInfo:
    buying_power: float
    cash: float
    portfolio_value: float
    equity: float
    margin_used: float
    day_trades_remaining: int  # PDT tracking

class Position:
    symbol: str
    qty: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    side: str  # 'long' or 'short'
```

### R2: Order Management System

#### R2.1: Order Types
| Type | Description | Use Case |
|------|-------------|----------|
| Market | Execute immediately at best price | Urgent rebalancing |
| Limit | Execute at specified price or better | Normal entries |
| Stop | Trigger market order at stop price | Stop-loss exits |
| Stop-Limit | Trigger limit order at stop price | Controlled exits |
| Trailing Stop | Dynamic stop that follows price | Profit protection |
| MOC | Market-on-Close | End-of-day rebalancing |
| Bracket | Entry + take-profit + stop-loss | Full trade management |

#### R2.2: Smart Order Execution
```python
class SmartOrderRouter:
    """Minimize slippage and market impact."""

    async def execute(self, target: OrderRequest) -> ExecutionResult:
        # 1. Check order size vs average volume
        impact_est = self._estimate_market_impact(target)

        # 2. Choose execution strategy
        if target.shares > self._adv_threshold(target.symbol):
            return await self._twap_execution(target)  # Split over time
        elif impact_est > 0.001:  # >10bps impact
            return await self._limit_order(target)  # Passive
        else:
            return await self._market_order(target)  # Immediate

    async def _twap_execution(self, target: OrderRequest) -> ExecutionResult:
        """Time-Weighted Average Price execution over N minutes."""
        slices = self._calculate_slices(target)
        results = []
        for slice_order in slices:
            result = await self.broker.submit_order(slice_order)
            results.append(result)
            await asyncio.sleep(self.slice_interval)
        return self._aggregate_results(results)
```

#### R2.3: Pre-Trade Validation
Before any order is submitted:
1. **Buying power check**: Sufficient cash/margin available
2. **Position limit check**: Single position <25% of portfolio
3. **Sector concentration check**: Single sector <40% of portfolio
4. **Daily trade limit**: PDT rule compliance (accounts <$25k)
5. **Risk check**: Order doesn't violate stop-loss or drawdown limits
6. **Duplicate check**: No identical order submitted within 60 seconds
7. **Market hours check**: Warn if submitting outside regular hours

### R3: Paper Trading Engine

#### R3.1: Simulated Execution
```python
class PaperBroker(BrokerInterface):
    """Realistic paper trading with simulated fills."""

    def __init__(self, initial_cash: float = 100_000):
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}
        self.orders: list[Order] = []
        self.trade_log: list[Trade] = []

    async def submit_order(self, order: OrderRequest) -> Order:
        # Simulate realistic fill
        fill_price = self._simulate_fill(order)
        slippage = self._apply_slippage(order, fill_price)
        commission = self._calculate_commission(order)

        # Execute
        final_price = fill_price + slippage
        self._update_position(order.symbol, order.qty, final_price)
        self.cash -= (order.qty * final_price) + commission

        return Order(
            id=uuid4(),
            filled_price=final_price,
            slippage=slippage,
            commission=commission,
            status='filled'
        )

    def _apply_slippage(self, order, price) -> float:
        """Slippage model based on order size vs liquidity."""
        adv = self._get_avg_daily_volume(order.symbol)
        participation = order.qty / adv
        # Linear impact model: 10bps per 1% of ADV
        impact_bps = participation * 100 * 10
        return price * impact_bps / 10_000
```

#### R3.2: Paper Trading Features
- Real-time P&L tracking against live market data
- Commission simulation ($0 for Alpaca-equivalent, configurable)
- Slippage modeling (volume-based market impact)
- Margin simulation (2x for RegT, 4x for day trades)
- Dividend crediting on ex-dates
- Corporate action handling (splits, mergers)

### R4: Position Sizing

#### R4.1: Sizing Methods
```python
class PositionSizer:
    def equal_weight(self, portfolio_value: float, n_positions: int) -> float:
        """Equal allocation across all positions."""
        return portfolio_value / n_positions

    def score_weighted(self, portfolio_value: float,
                       scores: dict[str, float]) -> dict[str, float]:
        """Allocate proportional to factor scores."""
        total = sum(scores.values())
        return {s: (score / total) * portfolio_value
                for s, score in scores.items()}

    def volatility_targeted(self, portfolio_value: float,
                            target_vol: float,
                            stock_vols: dict[str, float]) -> dict[str, float]:
        """Size positions to achieve target portfolio volatility."""
        inv_vol = {s: 1 / v for s, v in stock_vols.items()}
        total_inv_vol = sum(inv_vol.values())
        return {s: (iv / total_inv_vol) * portfolio_value
                for s, iv in inv_vol.items()}

    def kelly_criterion(self, win_rate: float, avg_win: float,
                        avg_loss: float, fraction: float = 0.25) -> float:
        """Kelly fraction with conservative scaling."""
        kelly = (win_rate / avg_loss) - ((1 - win_rate) / avg_win)
        return max(0, kelly * fraction)  # Quarter-Kelly for safety

    def risk_parity(self, portfolio_value: float,
                    cov_matrix: pd.DataFrame) -> dict[str, float]:
        """Equal risk contribution from each position."""
        # Inverse volatility as starting point
        vols = np.sqrt(np.diag(cov_matrix))
        inv_vol_weights = 1 / vols
        weights = inv_vol_weights / inv_vol_weights.sum()
        return {s: w * portfolio_value
                for s, w in zip(cov_matrix.columns, weights)}
```

#### R4.2: Position Constraints
- Maximum single position: 15% of portfolio (configurable)
- Maximum sector exposure: 35% of portfolio
- Minimum position size: $500 (avoid micro-positions)
- Cash buffer: 2% minimum cash always held
- Leverage limit: 1x (no margin by default)

### R5: Automated Rebalancing

#### R5.1: Rebalancing Triggers
| Trigger | Condition | Action |
|---------|-----------|--------|
| **Calendar** | First trading day of month | Full rebalance |
| **Drift** | Any position >5% from target | Rebalance drifted positions |
| **Signal** | Factor score drops below 30th pctile | Exit position |
| **Stop-Loss** | Position down >15% from entry | Close position |
| **New Signal** | New stock enters top decile | Evaluate for addition |

#### R5.2: Rebalancing Engine
```python
class RebalanceEngine:
    async def generate_trades(self,
                              current: dict[str, Position],
                              target: dict[str, float]) -> list[OrderRequest]:
        """Generate trade list to move from current to target allocation."""
        trades = []

        # 1. Calculate deltas
        for symbol in set(list(current.keys()) + list(target.keys())):
            current_value = current.get(symbol, Position()).market_value
            target_value = target.get(symbol, 0)
            delta = target_value - current_value

            if abs(delta) > self.min_trade_size:
                side = 'buy' if delta > 0 else 'sell'
                qty = abs(delta) / self._get_price(symbol)
                trades.append(OrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    type='limit',
                    limit_price=self._get_limit(symbol, side)
                ))

        # 2. Order sells first (free up cash), then buys
        sells = [t for t in trades if t.side == 'sell']
        buys = [t for t in trades if t.side == 'buy']

        return sells + buys

    def _get_limit(self, symbol: str, side: str) -> float:
        """Set limit price with small buffer for fills."""
        price = self._get_price(symbol)
        buffer = 0.001  # 10bps
        if side == 'buy':
            return price * (1 + buffer)
        return price * (1 - buffer)
```

### R6: Trade Journal & Audit Trail

#### R6.1: Trade Log Schema
```python
class TradeRecord:
    id: str
    timestamp: datetime
    symbol: str
    side: str  # buy, sell
    quantity: float
    price: float
    commission: float
    slippage: float
    order_type: str
    trigger: str  # 'rebalance', 'signal', 'stop_loss', 'manual'
    factor_scores_at_entry: dict
    regime_at_entry: str
    portfolio_value_at_time: float
    notes: str
```

#### R6.2: Performance Tracking
- Per-trade P&L with holding period
- Win/loss ratio by strategy, sector, regime
- Average holding period
- Slippage analysis (expected vs actual)
- Commission impact analysis
- Trade frequency and turnover metrics

### R7: UI Components

#### R7.1: Trading Dashboard
- Real-time positions table with P&L
- Pending orders with cancel capability
- Trade history with filtering
- Account summary (equity, buying power, margin)

#### R7.2: Rebalance Preview
- Show proposed trades before execution
- Compare current vs target allocations
- Estimated transaction costs
- One-click approval or modification

#### R7.3: Trade Chat Integration
Claude can execute trades via natural language:
```
User: "Buy $5,000 worth of AAPL"
Claude: [uses submit_order tool] → Order submitted: 28 shares AAPL at limit $178.50

User: "Rebalance my portfolio based on latest scores"
Claude: [uses rebalance tool] → Generating 7 trades... [shows preview]
```

---

## Security Requirements

- API keys encrypted at rest (AES-256)
- API keys never logged or displayed in full
- Paper trading as mandatory first step (can't go live without paper history)
- Rate limiting on order submissions (max 10 orders/minute)
- All order actions require explicit user confirmation (no fully autonomous trading without opt-in)
- Session timeout after 30 minutes of inactivity

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Order fill rate | >99% within 60 seconds |
| Average slippage (limit orders) | <5bps |
| Paper → Live conversion | >30% of paper users |
| Rebalance execution time | <2 minutes for 20-stock portfolio |
| Trade log completeness | 100% of trades logged |

---

## Dependencies

- PRD-01 (Data Infrastructure) for real-time prices
- PRD-02 (Factor Engine) for rebalancing signals
- PRD-04 (Risk Management) for pre-trade validation
- Alpaca API account (free)
- Interactive Brokers TWS (optional, $0 min with activity)

---

*Owner: Trading Systems Lead*
*Last Updated: January 2026*
