---
name: broker-integration
description: Connecting and managing broker accounts across 9 supported brokers in the Axion platform. Covers the BrokerInterface Protocol and BaseBroker ABC, BrokerManager for multi-broker coordination, credential management (API keys and OAuth2), individual broker modules (Alpaca, Schwab, Robinhood, Coinbase, Fidelity, IBKR, tastytrade, Webull), and the MultiBrokerExecutor for intelligent order routing with failover and portfolio aggregation.
metadata:
  author: axion-platform
  version: "1.0"
---

# Broker Integration

## When to use this skill

Use this skill when you need to:
- Connect to one or more brokerage accounts
- Place, modify, or cancel orders across different brokers
- Retrieve positions, balances, and order history
- Understand the unified BrokerInterface protocol
- Configure OAuth2 or API key authentication for each broker
- Route orders intelligently across multiple brokers
- Aggregate portfolio positions from all connected brokers
- Understand each broker's unique capabilities and limitations

## Step-by-step instructions

### 1. Understand the broker architecture

The platform has three layers:

1. **BrokerInterface Protocol** (`src/brokers/interface.py`) -- Defines the contract all brokers implement
2. **Individual broker modules** (`src/<broker_name>/`) -- 9 broker-specific implementations
3. **Multi-broker layer** (`src/multi_broker/`) -- Unified routing, aggregation, and failover

### 2. Use the BrokerManager (single-broker or multi-broker)

```python
from src.brokers import BrokerManager, BrokerType, OrderRequest, OrderSide, OrderType

# Create manager
manager = BrokerManager()

# Add a broker connection
await manager.add_broker(
    BrokerType.ALPACA,
    credentials={"api_key": "PK...", "api_secret": "abc123..."},
    sandbox=True,  # Paper trading
)

# Get all positions across connected brokers
positions = await manager.get_all_positions()
for pos in positions:
    print(f"{pos.symbol}: {pos.quantity} shares @ ${pos.current_price}")

# Place an order
order = OrderRequest(
    symbol="AAPL",
    side=OrderSide.BUY,
    quantity=10,
    order_type=OrderType.MARKET,
)
result = await manager.place_order(order)
print(f"Order ID: {result.order_id}, Status: {result.status}")

# Get account balances
balances = await manager.get_balances()
print(f"Equity: ${balances.equity}, Cash: ${balances.cash}")
```

### 3. Use individual broker implementations directly

#### Alpaca (stocks, ETFs, crypto)

```python
from src.alpaca_live import AlpacaLiveClient

client = AlpacaLiveClient(
    api_key="PK...",
    api_secret="...",
    paper=True,
)

await client.connect()
positions = await client.get_positions()
quote = await client.get_quote("AAPL")

# Streaming support
async for bar in client.stream_bars(["AAPL", "MSFT"]):
    print(f"{bar.symbol}: ${bar.close}")
```

#### Charles Schwab (full service, OAuth2)

```python
from src.schwab_broker import SchwabClient

client = SchwabClient(
    client_id="your_app_key",
    client_secret="your_secret",
    redirect_uri="https://localhost/callback",
)

# OAuth2 flow
auth_url = client.get_authorization_url()
# User visits auth_url, grants access, gets redirected with code
await client.exchange_code(code="auth_code_from_redirect")

# Now authenticated
account = await client.get_account()
positions = await client.get_positions()
```

#### Robinhood (zero-commission, crypto, fractional shares)

```python
from src.robinhood_broker import RobinhoodClient

client = RobinhoodClient(
    username="user@example.com",
    password="...",
    mfa_code="123456",   # 2FA code
)

await client.connect()
# Supports fractional shares
order = OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=0.5, order_type=OrderType.MARKET)
result = await client.place_order(order)
```

#### Coinbase (crypto-native)

```python
from src.coinbase_broker import CoinbaseClient

client = CoinbaseClient(
    api_key="...",
    api_secret="...",
)

await client.connect()
# Crypto pairs
quote = await client.get_quote("BTC-USD")
positions = await client.get_positions()
```

#### Fidelity (mutual funds, research)

```python
from src.fidelity_broker import FidelityClient

client = FidelityClient(
    client_id="...",
    client_secret="...",
    redirect_uri="https://localhost/callback",
)
# OAuth2 authentication
# Supports mutual fund screening and research tools
```

#### Interactive Brokers (global markets, forex, futures)

```python
from src.ibkr_broker import IBKRClient

client = IBKRClient(
    host="localhost",
    port=5000,          # Client Portal Gateway port
    account_id="U12345",
)

await client.connect()
# Supports conid-based contracts, forex, futures, global markets
positions = await client.get_positions()
```

#### tastytrade (options-first, multi-leg)

```python
from src.tastytrade_broker import TastytradeClient

client = TastytradeClient(
    username="...",
    password="...",
)

await client.connect()
# Options-first platform with IV rank/percentile
# Supports multi-leg options orders and futures/crypto
```

#### Webull (extended hours 4am-8pm)

```python
from src.webull_broker import WebullClient

client = WebullClient(
    device_id="...",
    access_token="...",
)

await client.connect()
# Extended hours: 4am-8pm
# Built-in screener, pre/post market pricing
```

### 4. Multi-broker routing with MultiBrokerExecutor

```python
from src.multi_broker import (
    BrokerRegistry, OrderRouter, PortfolioAggregator,
    MultiBrokerExecutor, BrokerAdapter, RoutingCriteria,
)

# Register brokers
registry = BrokerRegistry()
registry.register("alpaca", alpaca_adapter)
registry.register("schwab", schwab_adapter)
registry.register("coinbase", coinbase_adapter)

# Create router with routing criteria
router = OrderRouter(registry)

# Route an order intelligently
decision = router.route(order)
print(f"Route to: {decision.broker_name}")
print(f"Reason: {decision.reason}")

# Execute with failover
executor = MultiBrokerExecutor(registry, router)
result = executor.execute(order)

if result.status == ExecutionStatus.FILLED:
    print(f"Filled on {result.broker_name} @ ${result.fill_price}")
elif result.status == ExecutionStatus.FAILED:
    print(f"Failed: {result.error}")
```

### 5. Portfolio aggregation

```python
from src.multi_broker import PortfolioAggregator

aggregator = PortfolioAggregator(registry)

# Get aggregated portfolio across all brokers
portfolio = aggregator.aggregate()
print(f"Total equity: ${portfolio.total_equity:,.2f}")
print(f"Total positions: {len(portfolio.positions)}")

for pos in portfolio.positions:
    print(f"{pos.symbol}: {pos.total_quantity} shares across {len(pos.broker_positions)} brokers")
    for bp in pos.broker_positions:
        print(f"  {bp.broker}: {bp.quantity} shares @ ${bp.avg_cost:.2f}")
```

### 6. Credential management

```python
from src.brokers import CredentialManager, OAuthManager, BrokerCredentials

# Store credentials securely
cred_manager = CredentialManager()

# API key-based brokers
cred_manager.store(BrokerCredentials(
    broker_type=BrokerType.ALPACA,
    api_key="PK...",
    api_secret="...",
))

# OAuth2-based brokers
oauth = OAuthManager()
auth_url = oauth.get_authorization_url(
    broker_type=BrokerType.SCHWAB,
    client_id="...",
    redirect_uri="...",
)
tokens = await oauth.exchange_code(code="...", broker_type=BrokerType.SCHWAB)
await oauth.refresh_token(broker_type=BrokerType.SCHWAB)
```

## Key classes and methods

### `BrokerInterface` Protocol (src/brokers/interface.py)

All brokers implement this unified interface:

```python
@runtime_checkable
class BrokerInterface(Protocol):
    @property
    def broker_type(self) -> BrokerType: ...
    @property
    def capabilities(self) -> BrokerCapabilities: ...

    # Authentication
    async def connect(self) -> bool
    async def disconnect(self) -> None
    async def refresh_token(self) -> bool
    def is_connected(self) -> bool

    # Account
    async def get_account(self) -> BrokerAccount
    async def get_balances(self) -> AccountBalances
    async def get_positions(self) -> list[Position]
    async def get_position(self, symbol: str) -> Optional[Position]

    # Orders
    async def place_order(self, order: OrderRequest) -> OrderResult
    async def modify_order(self, order_id: str, changes: OrderModify) -> OrderResult
    async def cancel_order(self, order_id: str) -> bool
    async def get_order(self, order_id: str) -> Optional[Order]
    async def get_orders(self, status, limit) -> list[Order]

    # History
    async def get_order_history(self, start, end, symbol) -> list[Order]
    async def get_transactions(self, start, end, transaction_type) -> list[Transaction]

    # Market Data
    async def get_quote(self, symbol: str) -> Quote
    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]
```

### `BaseBroker` ABC (src/brokers/interface.py)
Abstract base class with default implementations for `get_position()`, `get_quotes()`, `get_order_history()`, `get_transactions()`.

### `BrokerManager` (src/brokers/manager.py)
- `add_broker(broker_type, credentials, sandbox) -> bool`
- `get_all_positions() -> list[Position]`
- `place_order(order: OrderRequest) -> OrderResult`
- `get_balances() -> AccountBalances`

### `BrokerRegistry` (src/multi_broker/registry.py)
- `register(name, adapter: BrokerAdapter)` / `unregister(name)`
- `get(name) -> BrokerAdapter` / `list_brokers() -> list[BrokerInfo]`

### `OrderRouter` (src/multi_broker/router.py)
- `route(order) -> RouteDecision` -- intelligent broker selection
- `add_rule(rule: RoutingRule)` -- custom routing rules

### `MultiBrokerExecutor` (src/multi_broker/executor.py)
- `execute(order) -> ExecutionResult` -- route + execute with failover

### `PortfolioAggregator` (src/multi_broker/aggregator.py)
- `aggregate() -> AggregatedPortfolio` -- combine all broker positions

### Key models (src/brokers/models.py)

```python
@dataclass
class OrderRequest:
    symbol: str
    side: OrderSide        # BUY, SELL
    quantity: float
    order_type: OrderType  # MARKET, LIMIT, STOP, STOP_LIMIT
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY

@dataclass
class OrderResult:
    order_id: str
    status: OrderStatus
    filled_qty: float
    filled_price: float
    broker: str
    rejection_reason: Optional[str] = None
```

### Key enums (src/brokers/config.py)

```python
class BrokerType(Enum):
    ALPACA = "alpaca"
    SCHWAB = "schwab"
    ROBINHOOD = "robinhood"
    COINBASE = "coinbase"
    TRADIER = "tradier"
    INTERACTIVE_BROKERS = "interactive_brokers"
    FIDELITY = "fidelity"
    TASTYTRADE = "tastytrade"
    WEBULL = "webull"

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class TimeInForce(Enum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
```

## Common patterns

### Broker capabilities matrix

| Broker | Stocks | Options | Crypto | Fractional | Extended Hours | Auth |
|--------|--------|---------|--------|------------|----------------|------|
| Alpaca | Yes | No | Yes | Yes | Pre/Post | API Key |
| Schwab | Yes | Yes | No | Yes | Pre/Post | OAuth2 |
| Robinhood | Yes | Yes | Yes | Yes | Extended | Username/2FA |
| Coinbase | No | No | Yes | Yes | 24/7 | API Key |
| Fidelity | Yes | Yes | No | Yes | Pre/Post | OAuth2 |
| IBKR | Yes | Yes | No | No | Global | Gateway |
| tastytrade | Yes | Yes | Yes | No | Standard | Session |
| Webull | Yes | Yes | Yes | No | 4am-8pm | Device Auth |

### OAuth2 flow (Schwab, Fidelity)

```
1. client.get_authorization_url() -> URL
2. User visits URL, grants access
3. Redirect returns auth code
4. client.exchange_code(code) -> tokens
5. client.refresh_token() -> new tokens (periodic)
```

### Multi-broker failover pattern

```python
executor = MultiBrokerExecutor(registry, router)

# If primary broker (e.g., Alpaca) fails, automatically tries next broker
result = executor.execute(order)
# result.broker_name tells you which broker actually filled it
```

### Credential storage

Never commit credentials. Use environment variables or the secrets vault:

```python
import os
from src.brokers import CredentialManager

cred_manager = CredentialManager()
cred_manager.store(BrokerCredentials(
    broker_type=BrokerType.ALPACA,
    api_key=os.environ["ALPACA_API_KEY"],
    api_secret=os.environ["ALPACA_API_SECRET"],
))
```

### Source files

- `src/brokers/__init__.py` -- public API (BrokerManager, BrokerInterface, models, enums)
- `src/brokers/interface.py` -- BrokerInterface Protocol, BaseBroker ABC
- `src/brokers/config.py` -- BrokerType, OrderSide, OrderType, BrokerCapabilities
- `src/brokers/models.py` -- BrokerAccount, Position, Order, OrderRequest, OrderResult, Quote
- `src/brokers/credentials.py` -- CredentialManager, OAuthManager
- `src/brokers/manager.py` -- BrokerManager
- `src/brokers/implementations.py` -- create_broker factory
- `src/alpaca_live/` -- Alpaca live trading with streaming
- `src/schwab_broker/` -- Charles Schwab with OAuth2
- `src/robinhood_broker/` -- Robinhood with crypto and fractional shares
- `src/coinbase_broker/` -- Coinbase crypto exchange
- `src/fidelity_broker/` -- Fidelity with mutual fund screening
- `src/ibkr_broker/` -- Interactive Brokers Client Portal Gateway
- `src/tastytrade_broker/` -- tastytrade options-first platform
- `src/webull_broker/` -- Webull with extended hours
- `src/multi_broker/__init__.py` -- multi-broker public API
- `src/multi_broker/registry.py` -- BrokerRegistry, BrokerAdapter
- `src/multi_broker/router.py` -- OrderRouter, RoutingRule, RouteDecision
- `src/multi_broker/aggregator.py` -- PortfolioAggregator, AggregatedPortfolio
- `src/multi_broker/executor.py` -- MultiBrokerExecutor, ExecutionResult
