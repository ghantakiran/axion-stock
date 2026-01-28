# PRD-11: Mobile App & Public API

**Priority**: P2 | **Phase**: 5 | **Status**: Draft

---

## Problem Statement

Axion is a desktop-only Streamlit app with no mobile experience and no programmatic API. Traders need mobile alerts and monitoring. Developers and quant researchers need API access to integrate Axion's factor scores, signals, and execution into custom workflows.

---

## Goals

1. **Mobile app** (iOS + Android) for monitoring and alerts
2. **REST API** for programmatic access to all platform features
3. **WebSocket API** for real-time streaming data
4. **Webhook system** for event-driven integrations
5. **SDK** (Python, JavaScript) for easy integration

---

## Detailed Requirements

### R1: Public REST API

#### R1.1: API Endpoints

**Market Data**
```
GET  /api/v1/quotes/{symbol}                 # Current quote
GET  /api/v1/ohlcv/{symbol}?bar=1d&start=..  # Historical bars
GET  /api/v1/fundamentals/{symbol}            # Financial data
GET  /api/v1/universe/{index}                 # Universe constituents
```

**Factor Scores**
```
GET  /api/v1/factors/{symbol}                 # All factor scores
GET  /api/v1/factors/{symbol}/history         # Historical scores
GET  /api/v1/screen?factor=momentum&top=20    # Factor screening
GET  /api/v1/regime                           # Current market regime
```

**Portfolio**
```
GET  /api/v1/portfolio                        # Current positions
POST /api/v1/portfolio/optimize               # Run optimizer
POST /api/v1/portfolio/rebalance              # Generate rebalance trades
GET  /api/v1/portfolio/risk                   # Risk metrics
GET  /api/v1/portfolio/performance            # Performance history
```

**Trading**
```
POST /api/v1/orders                           # Submit order
GET  /api/v1/orders/{id}                      # Order status
DELETE /api/v1/orders/{id}                    # Cancel order
GET  /api/v1/orders?status=open               # List orders
GET  /api/v1/trades                           # Trade history
```

**AI & Predictions**
```
POST /api/v1/ai/chat                          # Chat with Claude
GET  /api/v1/predictions/{symbol}             # ML predictions
GET  /api/v1/sentiment/{symbol}               # Sentiment scores
GET  /api/v1/picks/{category}                 # AI stock picks
```

**Options**
```
GET  /api/v1/options/{symbol}/chain           # Options chain
GET  /api/v1/options/{symbol}/greeks          # Greeks for all strikes
GET  /api/v1/options/{symbol}/iv-surface      # IV surface
POST /api/v1/options/analyze                  # Strategy analysis
GET  /api/v1/options/unusual                  # Unusual activity
```

**Backtesting**
```
POST /api/v1/backtest                         # Run backtest
GET  /api/v1/backtest/{id}                    # Get results
GET  /api/v1/backtest/{id}/tearsheet          # Get tear sheet
```

#### R1.2: API Framework
```python
# FastAPI implementation
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

app = FastAPI(
    title="Axion API",
    version="1.0.0",
    description="Algorithmic Trading Platform API"
)

@app.get("/api/v1/factors/{symbol}")
async def get_factor_scores(
    symbol: str,
    date: date = None,
    user: User = Depends(get_current_user)
):
    scores = await factor_engine.get_scores(symbol, date)
    if not scores:
        raise HTTPException(404, f"No scores for {symbol}")
    return FactorResponse(
        symbol=symbol,
        date=scores.date,
        value=scores.value,
        momentum=scores.momentum,
        quality=scores.quality,
        growth=scores.growth,
        volatility=scores.volatility,
        sentiment=scores.sentiment,
        composite=scores.composite,
        regime=scores.regime,
    )
```

#### R1.3: Rate Limiting
| Tier | Rate Limit | Burst |
|------|-----------|-------|
| Free | 100/day | 10/min |
| Pro | 1,000/day | 60/min |
| Enterprise | Unlimited | 600/min |

### R2: WebSocket API

#### R2.1: Real-Time Streams
```javascript
// Connect to WebSocket
const ws = new WebSocket('wss://api.axion.io/ws');

// Subscribe to quote stream
ws.send(JSON.stringify({
    action: 'subscribe',
    channel: 'quotes',
    symbols: ['AAPL', 'NVDA', 'TSLA']
}));

// Subscribe to portfolio updates
ws.send(JSON.stringify({
    action: 'subscribe',
    channel: 'portfolio',
}));

// Subscribe to alerts
ws.send(JSON.stringify({
    action: 'subscribe',
    channel: 'alerts',
}));

// Receive messages
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // { channel: 'quotes', symbol: 'AAPL', price: 178.50, ... }
    // { channel: 'alerts', type: 'drawdown', message: '...' }
};
```

### R3: Webhook System

#### R3.1: Available Events
| Event | Trigger | Payload |
|-------|---------|---------|
| `order.filled` | Order executed | Order details, fill price |
| `alert.risk` | Risk limit breached | Alert type, current value |
| `signal.new` | New trade signal | Symbol, direction, score |
| `rebalance.due` | Rebalance triggered | Proposed trades |
| `earnings.upcoming` | Earnings in 7 days | Symbol, date, estimates |
| `factor.change` | Factor score shift >20% | Symbol, old/new scores |
| `drawdown.warning` | Drawdown exceeds threshold | Current drawdown level |

#### R3.2: Webhook Configuration
```python
POST /api/v1/webhooks
{
    "url": "https://yourapp.com/webhook",
    "events": ["order.filled", "alert.risk"],
    "secret": "whsec_...",  # HMAC signing secret
}
```

### R4: Mobile App

#### R4.1: Core Screens
| Screen | Features |
|--------|----------|
| **Dashboard** | Portfolio value, daily P&L, key metrics |
| **Positions** | All positions with real-time P&L |
| **Watchlist** | Custom watchlists with factor scores |
| **Alerts** | Push notifications for signals, risks |
| **Trade** | Quick order entry (buy/sell) |
| **AI Chat** | Chat with Claude on mobile |
| **Factor Scores** | Stock lookup with factor breakdown |

#### R4.2: Push Notifications
| Notification | Priority | Sound |
|-------------|----------|-------|
| Order filled | Normal | Default |
| Risk alert | High | Alert |
| New signal | Normal | Default |
| Drawdown warning | Critical | Alarm |
| Market hours | Low | Silent |

#### R4.3: Technology
- **Framework**: React Native (cross-platform iOS + Android)
- **State**: Redux Toolkit
- **Charts**: react-native-chart-kit
- **Push**: Firebase Cloud Messaging
- **Auth**: Biometric (Face ID / Fingerprint) + PIN

### R5: Python SDK

```python
import axion

# Initialize client
client = axion.Client(api_key="ax_...")

# Get factor scores
scores = client.factors.get("AAPL")
print(f"AAPL composite: {scores.composite}")

# Screen stocks
top_momentum = client.screen(factor="momentum", top=20)

# Get AI analysis
analysis = client.ai.analyze("NVDA")

# Submit order
order = client.orders.create(
    symbol="AAPL",
    qty=10,
    side="buy",
    type="limit",
    limit_price=175.00
)

# Stream real-time quotes
async for quote in client.stream.quotes(["AAPL", "NVDA"]):
    print(f"{quote.symbol}: ${quote.price}")

# Run backtest
result = client.backtest.run(
    strategy="balanced_factor",
    start="2020-01-01",
    end="2025-12-31",
    initial_capital=100000,
)
print(f"Sharpe: {result.sharpe_ratio}")
```

---

## API Design Principles

1. **RESTful**: Standard HTTP verbs, resource-oriented URLs
2. **JSON**: All request/response bodies in JSON
3. **Versioned**: `/api/v1/` prefix, backward compatible within version
4. **Paginated**: Cursor-based pagination for large result sets
5. **Documented**: OpenAPI 3.0 spec, auto-generated docs at `/docs`
6. **Idempotent**: Safe retry of failed requests
7. **CORS**: Configurable cross-origin support

---

## Success Metrics

| Metric | Target |
|--------|--------|
| API response time (p95) | <200ms |
| WebSocket latency | <50ms |
| Mobile app rating | >4.5 stars |
| API adoption (Pro users) | >40% |
| SDK downloads/month | >1,000 |
| Webhook delivery success | >99.9% |

---

## Dependencies

- All previous PRDs for underlying functionality
- FastAPI + Uvicorn for API server
- React Native for mobile app
- Firebase for push notifications
- Redis for rate limiting and WebSocket pub/sub
- Nginx/Kong for API gateway

---

*Owner: Platform Engineering Lead*
*Last Updated: January 2026*
