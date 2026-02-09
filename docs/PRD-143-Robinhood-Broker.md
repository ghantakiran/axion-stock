# PRD-143: Robinhood Broker Integration

## Overview

Full-featured Robinhood broker integration for the Axion trading platform. Provides
REST API client with 3-mode fallback (robin_stocks SDK, raw HTTP, demo), polling-based
streaming for quotes and orders, portfolio tracking with analytics, and a 4-tab
Streamlit dashboard.

## Architecture

### Modules

| Module | File | Purpose |
|--------|------|---------|
| Client | `src/robinhood_broker/client.py` | REST API client, response models, demo data |
| Streaming | `src/robinhood_broker/streaming.py` | Polling-based quote/order updates |
| Portfolio | `src/robinhood_broker/portfolio.py` | Position tracking, allocation, P&L |
| Dashboard | `app/pages/robinhood_broker.py` | 4-tab Streamlit UI |

### Connection Modes

1. **SDK Mode**: Uses `robin_stocks` Python library for full API access
2. **HTTP Mode**: Direct REST API calls via `requests` library
3. **Demo Mode**: Returns realistic fake data for all endpoints (default)

The client always falls back gracefully through these modes, ensuring the
platform works without any API credentials.

### Data Models

- `RobinhoodConfig`: Connection configuration (username, password, MFA, etc.)
- `RobinhoodAccount`: Account info (equity, buying power, cash, margin status)
- `RobinhoodPosition`: Position data (symbol, qty, cost, market value, P&L)
- `RobinhoodOrder`: Order data (symbol, side, qty, type, status, fills)
- `RobinhoodQuote`: Real-time quote (bid, ask, last, volume, OHLC)

All models use Python dataclasses with `from_api(data)` class methods and
`to_dict()` serialization.

## Database Tables

### `robinhood_connections` (15 columns)

Stores connection state and account snapshots.

| Column | Type | Notes |
|--------|------|-------|
| id | Integer | Primary key |
| connection_id | String(50) | Unique, indexed |
| username | String(200) | Robinhood email |
| status | String(20) | connected/disconnected/error |
| mode | String(10) | sdk/http/demo |
| account_number | String(50) | RH account number |
| equity | Float | Total equity |
| buying_power | Float | Available buying power |
| cash | Float | Cash balance |
| position_count | Integer | Number of open positions |
| last_sync | DateTime | Last successful sync |
| error_message | Text | Last error if any |
| config_json | Text | Serialized config |
| created_at | DateTime | Record creation time |
| updated_at | DateTime | Last update time |

### `robinhood_order_log` (19 columns)

Logs all order activity for audit and analysis.

| Column | Type | Notes |
|--------|------|-------|
| id | Integer | Primary key |
| local_id | String(50) | Local tracking ID |
| rh_order_id | String(100) | Robinhood order ID |
| symbol | String(10) | Ticker symbol |
| side | String(10) | buy/sell |
| qty | Float | Order quantity |
| order_type | String(20) | market/limit/stop/stop_limit |
| time_in_force | String(10) | gfd/gtc/ioc/opg |
| limit_price | Float | Limit price (nullable) |
| stop_price | Float | Stop price (nullable) |
| status | String(20) | Order status |
| filled_qty | Float | Filled quantity |
| filled_avg_price | Float | Average fill price |
| signal_id | String(50) | Originating signal |
| strategy | String(50) | Strategy name |
| error_message | Text | Error details |
| submitted_at | DateTime | Submission time |
| filled_at | DateTime | Fill time |
| canceled_at | DateTime | Cancellation time |
| created_at | DateTime | Record creation time |

## Dashboard Tabs

1. **Connection**: Login form, connection status, account summary, demo mode indicator
2. **Portfolio**: Positions table, allocation chart, P&L breakdown, portfolio value history
3. **Orders**: Order placement form, order history table, order statistics
4. **Crypto**: Crypto positions, real-time crypto quotes, BTC price chart

## Tests Summary

- **8 test classes** with **~50 tests** in `tests/test_robinhood_broker.py`
- `TestRobinhoodConfig` (4): Default values, custom values, base URL
- `TestRobinhoodClient` (13): Connect/disconnect, account, positions, orders, quotes, crypto, options
- `TestResponseModels` (5): from_api parsing, to_dict serialization
- `TestRobinhoodStreaming` (5): Start/stop polling, symbol management, callbacks
- `TestPortfolioTracker` (7): Sync, total value, P&L, allocation, history, summary
- `TestStreamingModels` (4): QuoteUpdate and OrderStatusUpdate creation and serialization
- `TestModuleImports` (3): All exports, config defaults, class instantiation

## Migration

- **Revision**: 143
- **Down Revision**: 142
- **Tables Created**: `robinhood_connections`, `robinhood_order_log`
- **ORM Models**: `RobinhoodConnectionRecord`, `RobinhoodOrderLogRecord`
