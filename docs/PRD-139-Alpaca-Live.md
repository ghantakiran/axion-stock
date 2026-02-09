# PRD-139: Alpaca Live Broker Integration

## Overview

Upgrades the existing demo Alpaca broker stub to full real-time API integration. Provides REST client, WebSocket streaming, account synchronization, order lifecycle management, and market data access with graceful fallback to demo mode when credentials aren't available.

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  AlpacaClient    │     │  AlpacaStreaming  │     │  AccountSync     │
│  (REST API)      │     │  (WebSocket)     │     │  (Polling)       │
│  3 modes:        │     │  2 channels:     │     │  3 intervals:    │
│  sdk/http/demo   │     │  data + trading  │     │  acct/pos/order  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
        │                         │                         │
        ▼                         ▼                         ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  OrderManager    │◀────│  OrderUpdate     │     │  SyncState       │
│  (Lifecycle)     │     │  (Stream Events) │     │  (Current View)  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
        │
        ▼
┌──────────────────┐
│  MarketData      │
│  (OHLCV + Cache) │
└──────────────────┘
```

## Source Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/alpaca_live/__init__.py` | ~70 | Public API exports |
| `src/alpaca_live/client.py` | ~550 | REST API client with SDK/HTTP/demo modes |
| `src/alpaca_live/streaming.py` | ~310 | WebSocket streaming for quotes, trades, orders |
| `src/alpaca_live/account_sync.py` | ~210 | Periodic account/position/order sync |
| `src/alpaca_live/order_manager.py` | ~290 | Order lifecycle management |
| `src/alpaca_live/market_data.py` | ~220 | OHLCV bars, snapshots, quotes with caching |

## ORM Models

- `AlpacaConnectionRecord` → `alpaca_connections` (15 columns)
- `AlpacaOrderLogRecord` → `alpaca_order_log` (19 columns)
- `AlpacaPositionSnapshotRecord` → `alpaca_position_snapshots` (9 columns)

## Migration

- `alembic/versions/139_alpaca_live.py` — revision `139`, down_revision `138`

## Dashboard

- `app/pages/alpaca_live.py` — 4 tabs: Connection, Positions, Orders, Market Data

## Tests

- `tests/test_alpaca_live.py` — 8 test classes, ~55 tests
- Run: `python3 -m pytest tests/test_alpaca_live.py -v`

## Key Design Decisions

1. **3-mode fallback**: SDK → HTTP → Demo mode ensures the module always works
2. **WebSocket reconnection**: Exponential backoff (1s → 60s max) for resilience
3. **Separate data + trading streams**: Alpaca uses different WebSocket endpoints
4. **In-memory cache**: TTL-based caching (60s default) reduces API calls
5. **OHLCV DataFrame output**: Directly compatible with EMACloudCalculator (PRD-134)
6. **Order lifecycle tracking**: Maps Alpaca's 10+ order states to 9 lifecycle states
