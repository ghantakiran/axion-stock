# PRD-156: Fidelity Broker Integration

## Overview
Full-featured Fidelity brokerage integration with OAuth2 authentication, supporting stocks, options, ETFs, mutual funds, and bonds. Fidelity manages ~$4.5T AUM with ~12M retail accounts, making it the largest independent broker. Uses 3-mode fallback (SDK → HTTP/OAuth2 → Demo) for flexible deployment.

## Architecture
```
FidelityConfig → FidelityClient (3-mode fallback)
                       ↓
              OAuth2 _TokenManager → API calls
                       ↓
              Response Models (from_api + to_dict)
                       ↓
              FidelityStreaming → real-time data
              FidelityResearch → fundamentals, funds, ratings
```

## Components

### Client (`client.py`)
- **FidelityConfig**: OAuth2 credentials, rate limiting (60 req/min), retry config
- **FidelityClient**: Full REST API — accounts, positions, orders, quotes, price history, option chains
- **FidelityMutualFund**: Fidelity-specific mutual fund data with Morningstar ratings
- **6 response models**: Account, Position, Order, Quote, Candle, MutualFund

### Streaming (`streaming.py`)
- **StreamChannel**: QUOTE, CHART, OPTION, TIMESALE, NEWS
- **FidelityStreaming**: WebSocket/polling with callback registration

### Research (`research.py`)
- **FidelityResearch**: Fundamentals, mutual fund screener, analyst ratings
- **FundamentalData**: P/E, EPS, dividend yield, market cap, revenue, margins
- **FundScreenResult**: Morningstar rating, expense ratio, returns, AUM

## Unique Features
- Mutual fund screening (largest fund family in the world)
- Fractional share trading
- Comprehensive research tools
- Bond trading support

## Database Tables
- `fidelity_connections`: Connection state and account sync tracking
- `fidelity_order_log`: Order audit trail

## Dashboard
4-tab Streamlit interface:
1. **Account**: Portfolio overview with positions and P&L
2. **Trading**: Order entry with multiple order types
3. **Market Data**: Real-time quotes and price history
4. **Research**: Fundamentals, mutual fund screener, analyst ratings

## Integration Points
- **brokers** (base): BrokerType.FIDELITY already defined in config
- **multi_broker** (PRD-146): Auto-registered for unified routing
