# PRD-59: Real-time WebSocket API

## Overview

Real-time streaming infrastructure providing live market data, order status updates,
portfolio changes, and alert notifications via WebSocket connections. Enables
responsive trading experiences with sub-second data delivery and bidirectional
communication for order management.

## Components

### 1. WebSocket Server (`src/websocket/server.py`)
- **Connection Manager**: Handle client connections, authentication, heartbeats
- **Channel Router**: Route messages to appropriate handlers
- **Rate Limiter**: Prevent abuse with per-connection limits
- **Reconnection Logic**: Graceful reconnect with state recovery

### 2. Data Channels (`src/websocket/channels.py`)
- **Market Data**: Real-time quotes, trades, OHLC bars
- **Order Updates**: Order status changes, fills, cancellations
- **Portfolio**: Position changes, P&L updates, balance changes
- **Alerts**: Triggered alerts and notifications
- **News**: Breaking news and events

### 3. Subscription Manager (`src/websocket/subscriptions.py`)
- **Symbol Subscriptions**: Subscribe/unsubscribe to symbols
- **Channel Subscriptions**: Subscribe to data channels
- **Throttling**: Control update frequency per subscription
- **Batching**: Aggregate updates for efficiency

### 4. Message Protocol (`src/websocket/protocol.py`)
- **Message Types**: Subscribe, unsubscribe, snapshot, update, error
- **Compression**: Optional gzip for large payloads
- **Sequencing**: Message ordering and gap detection
- **Acknowledgments**: Delivery confirmation for critical messages

## Data Models

### WebSocketConnection
- `connection_id`: Unique connection identifier
- `user_id`: Authenticated user
- `subscriptions`: Active subscriptions
- `connected_at`: Connection timestamp
- `last_heartbeat`: Last activity time

### Subscription
- `subscription_id`: Unique subscription ID
- `channel`: Data channel type
- `symbols`: Subscribed symbols (if applicable)
- `throttle_ms`: Update throttle interval

### StreamMessage
- `type`: Message type (quote, trade, order, etc.)
- `channel`: Source channel
- `data`: Payload data
- `sequence`: Message sequence number
- `timestamp`: Server timestamp

## Message Format

### Client -> Server
```json
{
  "action": "subscribe",
  "channel": "quotes",
  "symbols": ["AAPL", "MSFT", "GOOGL"],
  "throttle_ms": 100
}
```

### Server -> Client
```json
{
  "type": "quote",
  "channel": "quotes",
  "sequence": 12345,
  "timestamp": "2026-02-07T14:30:00.123Z",
  "data": {
    "symbol": "AAPL",
    "bid": 185.50,
    "ask": 185.52,
    "last": 185.51,
    "volume": 45000000
  }
}
```

## Channels

### quotes
Real-time bid/ask/last quotes
- Fields: symbol, bid, ask, last, bid_size, ask_size, volume

### trades
Individual trade executions
- Fields: symbol, price, size, timestamp, exchange

### bars
OHLC aggregations (1s, 1m, 5m)
- Fields: symbol, open, high, low, close, volume, vwap

### orders
User order status updates
- Fields: order_id, symbol, status, filled_qty, avg_price

### portfolio
Portfolio value and position updates
- Fields: total_value, day_pnl, positions (array)

### alerts
Triggered alert notifications
- Fields: alert_id, type, message, symbol, triggered_at

### news
Breaking news and events
- Fields: headline, source, symbols, sentiment, timestamp

## Database Tables

### websocket_connections
- Active connection tracking

### websocket_subscriptions
- Subscription state persistence

### websocket_metrics
- Connection and message statistics

## API Endpoints

### REST (Setup)
- `GET /api/ws/token` - Get WebSocket auth token
- `GET /api/ws/channels` - List available channels
- `GET /api/ws/status` - Connection status

### WebSocket
- `wss://api.axion.io/v1/stream` - Main streaming endpoint

## Dashboard

Integrate real-time updates into existing dashboards:
- Live quote tickers
- Real-time portfolio value
- Order status notifications
- Alert popups

Dedicated WebSocket monitor page:
- Connection status
- Active subscriptions
- Message throughput
- Latency metrics

## Performance Requirements

- Connection capacity: 10,000 concurrent connections
- Message latency: <50ms from source
- Throughput: 100,000 messages/second aggregate
- Reconnection: <1s automatic reconnect
- Heartbeat: 30s interval

## Security

- JWT authentication required
- Per-user rate limiting
- IP-based connection limits
- TLS 1.3 encryption
- Message signing for orders

## Success Metrics

- Average latency: <50ms
- Connection uptime: 99.9%
- Message delivery rate: 99.99%
- Reconnection success: >99%
