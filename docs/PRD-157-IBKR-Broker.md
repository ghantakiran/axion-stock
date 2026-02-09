# PRD-157: Interactive Brokers (IBKR) Integration

## Overview
Professional-grade Interactive Brokers integration via Client Portal Gateway API. Unique among Axion's brokers: supports global markets (150+ countries), forex, futures, bonds, and stocks/options/ETFs. Lowest margin rates in the industry. Gateway runs locally on the user's machine, proxying API requests through a secure tunnel.

## Architecture
```
IBKRConfig → IBKRClient (3-mode fallback)
                   ↓
          IBKRGateway → localhost:5000 health/auth
                   ↓
          Contract-based trading (conid)
                   ↓
          IBKRStreaming → WebSocket data
```

## Components

### Client (`client.py`)
- **IBKRConfig**: Gateway host/port, SSL verify, account ID, rate limiting (50 req/min)
- **IBKRClient**: Full REST API — accounts, positions, orders, quotes, contract search
- **IBKRContract**: Contract-based system (conid) instead of simple symbols
- **7 response models**: Account, Position, Order, Quote, Candle, Contract

### Streaming (`streaming.py`)
- **StreamChannel**: QUOTE, TRADES, DEPTH, ORDERS, PNL
- **IBKRStreaming**: Native WebSocket support

### Gateway (`gateway.py`)
- **GatewayStatus**: Connection, auth, competing session detection
- **IBKRGateway**: Health check, reauthentication, keep-alive tickle

## Unique Features
- **Global markets**: Stocks in 150+ countries
- **Forex trading**: EUR/USD, GBP/USD, etc. (only broker with forex)
- **Futures**: ES, NQ, CL, etc. (only broker with futures)
- **Contract IDs** (conid): Unique identifier system for all instruments
- **Local gateway**: Runs on user's machine at localhost:5000
- **Competing sessions**: Detects other active API connections

## Database Tables
- `ibkr_connections`: Connection state with gateway host/port tracking
- `ibkr_order_log`: Order audit with conid, sec_type, exchange, currency

## Dashboard
4-tab Streamlit interface:
1. **Account**: Multi-currency portfolio with forex/futures positions
2. **Trading**: Multi-asset order entry with contract search
3. **Market Data**: Quotes for stocks, forex, futures
4. **Gateway**: Client Portal Gateway health monitoring

## Integration Points
- **brokers** (base): BrokerType.IBKR already defined with capabilities
- **multi_broker** (PRD-146): Auto-registered for unified routing
