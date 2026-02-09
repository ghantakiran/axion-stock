# PRD-159: Webull Broker Integration

## Overview
Retail-friendly broker integration with zero-commission trading, extended hours (4am-8pm ET), crypto support, and built-in stock screener. Webull is popular with self-directed retail and day traders. Uses device-based authentication with trade PIN for security.

## Architecture
```
WebullConfig → WebullClient (3-mode fallback)
                     ↓
            _TokenManager → device_id + trade_pin auth
                     ↓
            Extended hours trading (pre-market + after-hours)
                     ↓
            WebullStreaming → real-time data
```

## Components

### Client (`client.py`)
- **WebullConfig**: Device ID, trade token, separate API endpoints for trading/quotes
- **WebullClient**: Full REST API — account, positions, orders, quotes, screener, crypto
- **Extended hours**: Pre-market (4:00am-9:30am ET) and after-hours (4:00pm-8:00pm ET)
- **7 response models**: Account, Position, Order, Quote, Candle, ScreenerResult

### Streaming (`streaming.py`)
- **StreamChannel**: QUOTE, TRADES, DEPTH, ORDERS
- **WebullStreaming**: Polling-based streaming

## Unique Features
- **Extended hours**: 4am-8pm ET trading (widest among retail brokers)
- **Zero commission**: No fees on stock, ETF, and options trades
- **Built-in screener**: Filter by price, volume, market cap, sector
- **Pre/post market prices**: Quotes include pre_market_price, after_hours_price
- **Ticker IDs**: Internal integer IDs alongside symbol strings
- **Crypto**: BTC, ETH, DOGE and more in the same account
- **Day trade tracking**: PDT rule monitoring with day_trades_remaining

## Database Tables
- `webull_connections`: Connection state with device_id, day trades remaining
- `webull_order_log`: Order audit with ticker_id, outside_regular_hours flag

## Dashboard
4-tab Streamlit interface:
1. **Account**: Portfolio overview with day-trade counter
2. **Trading**: Order entry with extended hours toggle
3. **Market Data**: Quotes with pre/post market pricing, crypto
4. **Screener**: Built-in stock screener with filters

## Integration Points
- **brokers** (base): BrokerType.WEBULL already defined in config
- **multi_broker** (PRD-146): Auto-registered for unified routing
