# PRD-25: Broker Integrations

**Priority**: P1 | **Phase**: 14 | **Status**: Draft

---

## Problem Statement

Users want to connect their actual brokerage accounts to execute trades, sync positions, and view consolidated portfolio data. Currently, they must manually execute trades or use paper trading. Direct broker integrations enable seamless order execution, real-time position sync, and unified portfolio management across multiple brokers.

---

## Goals

1. **Multi-Broker Support** - Connect to major brokers (Schwab, Fidelity, IBKR, Robinhood, TD Ameritrade)
2. **Account Sync** - Real-time positions, balances, and order status
3. **Order Execution** - Place, modify, and cancel orders through unified API
4. **OAuth Integration** - Secure authentication without storing credentials
5. **Unified Interface** - Consistent API regardless of broker
6. **Error Handling** - Graceful handling of broker-specific quirks

---

## Detailed Requirements

### R1: Supported Brokers

#### R1.1: Broker Matrix
| Broker | Auth Method | Trading | Positions | History | Options |
|--------|-------------|---------|-----------|---------|---------|
| **Interactive Brokers** | OAuth/API Key | ✓ | ✓ | ✓ | ✓ |
| **Charles Schwab** | OAuth 2.0 | ✓ | ✓ | ✓ | ✓ |
| **Fidelity** | OAuth 2.0 | ✓ | ✓ | ✓ | ✓ |
| **TD Ameritrade** | OAuth 2.0 | ✓ | ✓ | ✓ | ✓ |
| **Robinhood** | OAuth 2.0 | ✓ | ✓ | ✓ | Limited |
| **Alpaca** | API Key | ✓ | ✓ | ✓ | ✗ |
| **Tradier** | OAuth 2.0 | ✓ | ✓ | ✓ | ✓ |

### R2: Unified Broker Interface

#### R2.1: Base Interface
```python
class BrokerInterface(Protocol):
    """Unified broker interface."""
    
    # Authentication
    async def connect(self) -> bool
    async def disconnect(self) -> None
    async def refresh_token(self) -> bool
    def is_connected(self) -> bool
    
    # Account
    async def get_account(self) -> BrokerAccount
    async def get_balances(self) -> AccountBalances
    async def get_positions(self) -> list[Position]
    
    # Orders
    async def place_order(self, order: OrderRequest) -> OrderResult
    async def modify_order(self, order_id: str, changes: OrderModify) -> OrderResult
    async def cancel_order(self, order_id: str) -> bool
    async def get_order(self, order_id: str) -> Order
    async def get_orders(self, status: OrderStatus = None) -> list[Order]
    
    # History
    async def get_order_history(self, start: date, end: date) -> list[Order]
    async def get_transactions(self, start: date, end: date) -> list[Transaction]
    
    # Market Data (if available)
    async def get_quote(self, symbol: str) -> Quote
    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]
```

### R3: Account Models

#### R3.1: Account Information
```python
@dataclass
class BrokerAccount:
    account_id: str
    broker: BrokerType
    account_type: str  # individual, ira, margin, etc.
    account_name: str
    status: str  # active, restricted, closed
    
    # Capabilities
    can_trade_stocks: bool
    can_trade_options: bool
    can_trade_margin: bool
    can_short: bool
    
    # Metadata
    opened_date: Optional[date]
    last_sync: datetime

@dataclass
class AccountBalances:
    account_id: str
    currency: str
    
    # Cash
    cash: float
    cash_available: float
    cash_withdrawable: float
    
    # Buying power
    buying_power: float
    day_trading_buying_power: Optional[float]
    
    # Margin (if applicable)
    margin_balance: float
    margin_buying_power: float
    margin_maintenance: float
    
    # Portfolio value
    total_value: float
    market_value: float
    
    # P&L
    day_pnl: float
    total_pnl: float
```

#### R3.2: Position Model
```python
@dataclass
class Position:
    account_id: str
    symbol: str
    asset_type: str  # stock, option, etf, etc.
    
    # Quantity
    quantity: float
    quantity_available: float  # For selling
    
    # Prices
    average_cost: float
    current_price: float
    market_value: float
    
    # P&L
    unrealized_pnl: float
    unrealized_pnl_pct: float
    day_pnl: float
    
    # For options
    option_type: Optional[str]  # call, put
    strike: Optional[float]
    expiration: Optional[date]
```

### R4: Order Management

#### R4.1: Order Request
```python
@dataclass
class OrderRequest:
    symbol: str
    side: OrderSide  # buy, sell, sell_short, buy_to_cover
    quantity: float
    order_type: OrderType  # market, limit, stop, stop_limit
    
    # Prices
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    
    # Time in force
    time_in_force: TimeInForce = TimeInForce.DAY
    # day, gtc, ioc, fok, opg, cls
    
    # Extended hours
    extended_hours: bool = False
    
    # Advanced
    trail_amount: Optional[float] = None
    trail_percent: Optional[float] = None
    
    # Options specific
    option_type: Optional[str] = None
    strike: Optional[float] = None
    expiration: Optional[date] = None
```

#### R4.2: Order Result
```python
@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str]
    status: OrderStatus
    message: str
    
    # Fill info (if filled)
    filled_quantity: float = 0
    filled_price: float = 0
    
    # Timestamps
    submitted_at: datetime
    filled_at: Optional[datetime] = None
```

### R5: Authentication

#### R5.1: OAuth Flow
```
1. User initiates connection
2. Redirect to broker OAuth page
3. User authorizes application
4. Receive authorization code
5. Exchange code for access/refresh tokens
6. Store encrypted tokens
7. Auto-refresh before expiration
```

#### R5.2: Token Management
```python
@dataclass
class BrokerCredentials:
    broker: BrokerType
    account_id: str
    
    # OAuth tokens
    access_token: str
    refresh_token: str
    token_expiry: datetime
    
    # API keys (for brokers that use them)
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    
    # Encryption
    encrypted: bool = True
```

### R6: Multi-Account Management

#### R6.1: Account Aggregation
```python
class BrokerManager:
    """Manages multiple broker connections."""
    
    async def add_broker(self, broker_type: BrokerType, credentials: dict) -> str
    async def remove_broker(self, connection_id: str) -> bool
    async def get_connections(self) -> list[BrokerConnection]
    
    # Aggregated views
    async def get_all_positions(self) -> list[Position]
    async def get_all_balances(self) -> list[AccountBalances]
    async def get_total_portfolio_value(self) -> float
    
    # Cross-broker operations
    async def find_best_execution(self, order: OrderRequest) -> BrokerType
```

### R7: Error Handling

#### R7.1: Error Types
| Error | Description | Recovery |
|-------|-------------|----------|
| **AuthError** | Authentication failed | Re-authenticate |
| **RateLimitError** | Too many requests | Exponential backoff |
| **InsufficientFundsError** | Not enough buying power | Adjust order |
| **InvalidOrderError** | Order parameters invalid | Fix parameters |
| **MarketClosedError** | Market not open | Queue for market open |
| **SymbolNotFoundError** | Unknown symbol | Validate symbol |
| **ConnectionError** | Network issue | Retry with backoff |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Broker coverage | 5+ major brokers |
| Order success rate | >99% |
| Position sync latency | <5 seconds |
| Token refresh success | >99.9% |

---

## Security Requirements

1. **Never store plain-text credentials**
2. **Encrypt all tokens at rest**
3. **Use secure OAuth flows only**
4. **Implement token rotation**
5. **Audit all broker operations**
6. **Support 2FA where available**

---

## Dependencies

- Execution system (PRD-03)
- Risk management (PRD-04)
- Paper trading (PRD-19)

---

*Owner: Platform Engineering Lead*
*Last Updated: January 2026*
