# PRD-158: tastytrade Broker Integration

## Overview
Options-specialist broker integration with deep chain analytics, multi-leg order support, futures, and crypto. tastytrade is built by options traders for options traders, with the deepest options chain data available. Uses session-based authentication (username/password → session token) rather than OAuth2.

## Architecture
```
TastytradeConfig → TastytradeClient (3-mode fallback)
                          ↓
                 _SessionManager → session token auth
                          ↓
                 OptionsChainAnalyzer → deep chain analytics
                          ↓
                 TastytradeStreaming → real-time Greeks
```

## Components

### Client (`client.py`)
- **TastytradeConfig**: Session auth (username/password), sandbox toggle
- **TastytradeClient**: Full REST API — accounts, positions, orders, quotes, chains
- **Multi-leg orders**: Spreads, strangles, iron condors via `place_complex_order()`
- **5 response models**: Account, Position, Order, Quote, Candle

### Streaming (`streaming.py`)
- **StreamChannel**: QUOTE, GREEKS, TRADES, ORDERS
- **TastytradeStreaming**: Real-time Greeks streaming

### Options Chain (`options_chain.py`)
- **OptionGreeks**: Full Greeks suite (delta, gamma, theta, vega, rho, IV)
- **OptionsChainAnalyzer**: Expirations, chains, optimal strike finder, IV surface
- **OptionStrike**: Call/put bid/ask/last/volume/OI/Greeks per strike

## Unique Features
- **Options-first**: IV rank/percentile on every quote
- **Multi-leg orders**: Native spread, combo, complex order support
- **Futures**: /ES, /NQ, /CL with leading slash notation
- **Crypto**: BTC/USD, ETH/USD in the same account
- **Session auth**: Username/password instead of OAuth2
- **IV Surface**: Strike × expiration implied volatility matrix

## Database Tables
- `tastytrade_connections`: Connection state with option level, futures flag
- `tastytrade_order_log`: Order audit with instrument_type, order_class, legs_json

## Dashboard
4-tab Streamlit interface:
1. **Account**: Portfolio with multi-asset positions (equity, options, futures, crypto)
2. **Trading**: Single and multi-leg order entry
3. **Options Chain**: Deep chain analysis with Greeks, IV surface
4. **Streaming**: Real-time quote and Greeks streaming

## Integration Points
- **brokers** (base): TASTYTRADE added to BrokerType enum
- **multi_broker** (PRD-146): Auto-registered for unified routing
- **options** (PRD-09): Deep options chain data complements analytics
