# PRD-145: Schwab Broker Integration

## Overview
Full-featured Schwab (formerly Fidelity brokerage) API integration for the Axion trading platform. Provides REST client with OAuth2 authentication, WebSocket streaming, and research tools with graceful fallback to demo mode.

## Background
Charles Schwab acquired TD Ameritrade and the Fidelity brokerage business, consolidating under the Schwab API (api.schwabapi.com). This integration allows Axion users to connect their Schwab accounts for live trading, real-time market data, and research capabilities.

## Goals
1. **Broker Connectivity** -- Connect to Schwab via 3-mode fallback: schwab-py SDK, HTTP/OAuth2, or demo mode
2. **Account Management** -- View accounts, positions, balances, and order history
3. **Order Execution** -- Place, modify, and cancel orders (market, limit, stop, trailing stop)
4. **Market Data** -- Real-time quotes, price history (OHLCV), options chains, market movers
5. **Research Tools** -- Fundamentals, stock screener, analyst ratings
6. **Streaming** -- WebSocket-based real-time quote, chart, option, time & sale, and news feeds

## Module Structure

### `src/schwab_broker/`
| File | Description | ~Lines |
|------|-------------|--------|
| `__init__.py` | Public exports | ~60 |
| `client.py` | REST API client with 3-mode fallback | ~400 |
| `streaming.py` | WebSocket streaming manager | ~170 |
| `research.py` | Research tools (fundamentals, screener, ratings) | ~150 |

### Supporting Files
| File | Description |
|------|-------------|
| `tests/test_schwab_broker.py` | 8 test classes, ~50 tests |
| `app/pages/schwab_broker.py` | 4-tab Streamlit dashboard |
| `alembic/versions/145_schwab_broker.py` | Migration (schwab_connections, schwab_order_log) |
| `src/db/models.py` | SchwabConnectionRecord, SchwabOrderLogRecord ORM models |

## API Design

### SchwabConfig
- `app_key`, `app_secret` -- OAuth2 credentials from Schwab Developer Portal
- `callback_url` -- OAuth2 redirect URI
- `base_url` -- defaults to https://api.schwabapi.com

### SchwabClient
- `connect()` -- 3-mode fallback (SDK -> HTTP/OAuth2 -> Demo)
- `get_accounts()` -- list all linked accounts
- `get_positions(account_id)` -- positions for an account
- `get_orders(account_id)` -- order history
- `place_order(account_id, order_request)` -- submit order
- `cancel_order(account_id, order_id)` -- cancel order
- `get_quote(symbols)` -- batch quotes
- `get_price_history(symbol)` -- OHLCV candles
- `get_option_chain(symbol)` -- options chain
- `get_movers(index)` -- market movers ($SPX, $DJI, $COMPX)

### SchwabStreaming
- Channels: QUOTE, CHART_EQUITY, OPTION, TIMESALE_EQUITY, NEWS_HEADLINE
- `subscribe()`, `unsubscribe()`, `on_quote()`, `on_chart()` etc.

### SchwabResearch
- `get_fundamentals(symbol)` -- PE, EPS, market cap, margins, etc.
- `get_screener(criteria)` -- filter by sector, market cap, PE, etc.
- `get_analyst_ratings(symbol)` -- consensus, target prices, analyst counts

## Database Schema

### schwab_connections (12 columns)
Tracks API connection state, account info, and sync timestamps.

### schwab_order_log (16 columns)
Immutable log of all order submissions, fills, and cancellations.

## Dashboard
4-tab Streamlit interface:
1. **Accounts** -- Connection config, account list, balances
2. **Portfolio** -- Positions table, allocation chart, P&L
3. **Trading** -- Order form, order history
4. **Research** -- Fundamentals lookup, screener, movers

## Demo Mode
All methods return realistic demo data when no credentials are configured:
- SPY ~$590, AAPL ~$230, MSFT ~$415, NVDA ~$875, GOOGL ~$185
- 3 demo positions, 3 demo orders, full options chain, market movers

## Dependencies
- `schwab-py` (optional) -- Official Schwab Python SDK
- `httpx` (optional) -- Async HTTP client for raw OAuth2 flow
- `websockets` (optional) -- WebSocket streaming

## Testing
- 8 test classes, ~50 tests
- All tests run in demo mode (no live API required)
- pytest-asyncio for async test support
