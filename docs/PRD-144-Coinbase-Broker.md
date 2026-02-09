# PRD-144: Coinbase Broker Integration

## Overview

Full-featured Coinbase Advanced Trade API integration for the Axion trading platform. Provides REST client, WebSocket streaming, and crypto portfolio tracking with seamless fallback to demo mode when API credentials are unavailable.

## Goals

1. Enable live crypto trading through Coinbase Advanced Trade API
2. Provide real-time market data via WebSocket streaming
3. Track crypto portfolio value, allocation, and P&L
4. Support 3-mode fallback: SDK -> HTTP -> Demo
5. Dashboard with connection management, portfolio view, trading, and market data

## Architecture

### Module Structure

```
src/coinbase_broker/
    __init__.py          # Public exports
    client.py            # REST API client with 3-mode fallback
    streaming.py         # WebSocket client for real-time data
    portfolio.py         # Portfolio tracking and P&L
```

### Key Classes

- **CoinbaseConfig**: API credentials and connection settings
- **CoinbaseClient**: REST client with SDK/HTTP/Demo modes
- **CoinbaseWebSocket**: Real-time ticker, level2, and match data
- **CryptoPortfolioTracker**: Portfolio sync, allocation, and P&L tracking

### Response Models (dataclasses)

- **CoinbaseAccount**: Wallet with currency, balance, available, hold
- **CoinbaseOrder**: Order with product, side, size, status, fills
- **CoinbaseFill**: Trade fill with price, size, fee
- **CoinbaseProduct**: Trading pair with min/max size, status
- **CoinbaseCandle**: OHLCV candle data

## Connection Modes

1. **SDK Mode**: Uses `coinbase` Python SDK when installed
2. **HTTP Mode**: Raw HTTP via `httpx` with HMAC signature auth
3. **Demo Mode**: Generates realistic crypto data (BTC ~$95K, ETH ~$3.5K, SOL ~$200, etc.)

## Demo Data

All methods work in demo mode with realistic crypto prices:
- BTC: $95,000
- ETH: $3,500
- SOL: $200
- DOGE: $0.32
- ADA: $0.95
- XRP: $2.30

## Database Tables

- `coinbase_connections`: API connection state and metadata
- `coinbase_order_log`: Order execution history
- `coinbase_account_snapshots`: Point-in-time account/wallet snapshots

## Dashboard

4-tab Streamlit dashboard:
1. **Connection**: API key form, connection status, account summary
2. **Crypto Portfolio**: Holdings table, allocation chart, P&L metrics
3. **Trading**: Order form, active orders, recent fills
4. **Market Data**: Spot prices, price chart, available products

## Testing

~50 tests across 8 test classes covering:
- Configuration defaults and custom values
- Client demo mode operations
- Response model parsing
- WebSocket subscription management
- Portfolio tracking and P&L calculations
- Module import integrity

## Dependencies

- Required: None (demo mode works without external packages)
- Optional: `coinbase` (SDK mode), `httpx` (HTTP mode), `websockets` (streaming)
