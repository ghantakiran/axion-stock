---
name: axion-api-usage
description: Using the Axion REST API and WebSocket for market data, trading, portfolio management, AI features, bot control, and more. Covers all route modules (market_data, factors, portfolio, trading, ai, options, backtesting, bot, keys), authentication (API keys with scopes and tiers), rate limiting (FREE/PRO/ENTERPRISE tiers), WebSocket channels, health endpoint, and Prometheus metrics endpoint.
metadata:
  author: axion-platform
  version: "1.0"
---

# Axion API Usage

## When to use this skill

Use this skill when you need to:
- Interact with the Axion REST API for market data, trading, portfolio, or AI features
- Authenticate with API keys and understand scope/tier permissions
- Connect to WebSocket channels for real-time streaming
- Understand rate limiting tiers and headers
- Use the bot control API (start/stop/kill/status)
- Access Prometheus metrics or health checks
- Build integrations against the Axion API

## Step-by-step instructions

### 1. API overview

The API is built with FastAPI and served via uvicorn. Base URL: `http://localhost:8000`

- **Docs**: `http://localhost:8000/docs` (Swagger UI)
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI spec**: `http://localhost:8000/openapi.json`
- **Health**: `http://localhost:8000/health`
- **Metrics**: `http://localhost:8000/metrics` (Prometheus format)
- **API prefix**: `/api/v1`

Start the API server:

```bash
uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

### 2. Authentication

Authentication uses API keys passed via the `X-API-Key` header. Auth is opt-in via the `AXION_REQUIRE_API_KEY=true` environment variable. When disabled (default for local dev), all requests get full enterprise-level access.

```bash
# With auth enabled
export AXION_REQUIRE_API_KEY=true

# All requests require X-API-Key header
curl -H "X-API-Key: ax_your_key_here" http://localhost:8000/api/v1/market/quotes/AAPL
```

**API key format**: Keys are prefixed with `ax_` (configurable in `src/api/config.py`).

**Scopes**: Endpoints require specific scopes:
- `read` -- GET endpoints (status, positions, history, config, market data)
- `write` -- POST/PUT endpoints (start, stop, kill, config update, order placement)
- `admin` -- Administrative operations

**Auth dependencies** (from `src/api/dependencies.py`):

```python
from src.api.dependencies import AuthContext, require_auth, require_scope, check_rate_limit

# Basic auth -- validates API key, returns AuthContext
@router.get("/data")
async def get_data(auth: AuthContext = Depends(require_auth)):
    print(auth.user_id, auth.tier, auth.scopes)

# Scope-required auth
@router.post("/orders")
async def create_order(auth: AuthContext = Depends(require_scope("write"))):
    ...

# Auth + rate limiting (adds X-RateLimit-* response headers)
@router.get("/quotes/{symbol}")
async def get_quote(auth: AuthContext = Depends(check_rate_limit)):
    ...
```

The `AuthContext` dataclass:

```python
@dataclass
class AuthContext:
    user_id: str
    tier: APITier       # FREE, PRO, ENTERPRISE
    scopes: list[str]   # ["read", "write", "admin"]
    authenticated: bool
```

### 3. Rate limiting

Limits are per-tier and enforced per user:

| Tier | Per Minute | Daily | Burst |
|------|-----------|-------|-------|
| FREE | 10 | 100 | 10 |
| PRO | 60 | 1,000 | 60 |
| ENTERPRISE | 600 | Unlimited | 600 |

Rate limit headers are returned on every response:
- `X-RateLimit-Limit` -- requests allowed per window
- `X-RateLimit-Remaining` -- requests remaining
- `X-RateLimit-Daily-Remaining` -- daily requests remaining
- `Retry-After` -- seconds to wait (on 429 response)

### 4. Route modules

#### Market Data (`/api/v1/market/`)

```bash
# Get current quote
curl http://localhost:8000/api/v1/market/quotes/AAPL

# Get OHLCV bars
curl "http://localhost:8000/api/v1/market/ohlcv/AAPL?bar=1d&limit=100"
# bar options: 1m, 5m, 15m, 1h, 1d, 1w, 1M

# Get fundamentals
curl http://localhost:8000/api/v1/market/fundamentals/AAPL
```

#### Factors (`/api/v1/factors/`)

```bash
# Get factor scores for a symbol
curl http://localhost:8000/api/v1/factors/scores/AAPL

# Get factor rankings
curl "http://localhost:8000/api/v1/factors/rankings?universe=sp500&factor=momentum"
```

#### Portfolio (`/api/v1/portfolio/`)

```bash
# Get portfolio summary
curl http://localhost:8000/api/v1/portfolio/summary

# Get portfolio positions
curl http://localhost:8000/api/v1/portfolio/positions

# Get optimization recommendation
curl -X POST http://localhost:8000/api/v1/portfolio/optimize \
  -H "Content-Type: application/json" \
  -d '{"target_risk": 0.15}'
```

#### Trading (`/api/v1/trading/`)

```bash
# Place an order
curl -X POST http://localhost:8000/api/v1/trading/orders \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ax_your_key" \
  -d '{"symbol": "AAPL", "side": "buy", "quantity": 100, "order_type": "market"}'

# Get open orders
curl http://localhost:8000/api/v1/trading/orders

# Cancel an order
curl -X DELETE http://localhost:8000/api/v1/trading/orders/{order_id}
```

#### AI (`/api/v1/ai/`)

```bash
# Chat with AI assistant
curl -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the outlook for AAPL?", "context": {}}'

# Get AI analysis
curl -X POST http://localhost:8000/api/v1/ai/analyze \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "analysis_type": "fundamental"}'
```

#### Options (`/api/v1/options/`)

```bash
# Get options chain
curl "http://localhost:8000/api/v1/options/chain/AAPL?expiry=2026-03-21"

# Get Greeks for a specific contract
curl http://localhost:8000/api/v1/options/greeks/AAPL260321C00200000
```

#### Backtesting (`/api/v1/backtesting/`)

```bash
# Run a backtest
curl -X POST http://localhost:8000/api/v1/backtesting/run \
  -H "Content-Type: application/json" \
  -d '{"strategy": "ema_cloud", "symbol": "SPY", "start": "2025-01-01", "end": "2025-12-31"}'

# Get backtest results
curl http://localhost:8000/api/v1/backtesting/results/{backtest_id}
```

#### Bot Control (`/api/v1/bot/`)

See the `bot-management` skill for full details. Summary:

```bash
POST /api/v1/bot/start          # Start bot
POST /api/v1/bot/stop           # Stop bot
POST /api/v1/bot/pause          # Pause signal processing
POST /api/v1/bot/resume         # Resume processing
POST /api/v1/bot/kill           # Emergency kill switch
POST /api/v1/bot/kill/reset     # Reset kill switch
GET  /api/v1/bot/status         # Full status snapshot
GET  /api/v1/bot/positions      # Open positions
GET  /api/v1/bot/history        # Execution history (paginated)
PUT  /api/v1/bot/config         # Hot-update config
GET  /api/v1/bot/config         # Get current config
```

#### API Keys (`/api/v1/keys/`)

```bash
# Create a new API key
curl -X POST http://localhost:8000/api/v1/keys/create \
  -H "Content-Type: application/json" \
  -d '{"user_id": "trader1", "scopes": ["read", "write"], "tier": "pro"}'

# List keys
curl http://localhost:8000/api/v1/keys/list

# Revoke a key
curl -X DELETE http://localhost:8000/api/v1/keys/{key_id}
```

### 5. WebSocket channels

```python
import asyncio
import json
import websockets

# Bot events WebSocket
async def monitor():
    async with websockets.connect("ws://localhost:8000/ws/bot?user_id=trader1") as ws:
        # Auto-subscribed to: signals, orders, alerts, lifecycle, metrics

        # Subscribe to specific channel
        await ws.send(json.dumps({"action": "subscribe", "channel": "signals"}))

        # Unsubscribe
        await ws.send(json.dumps({"action": "unsubscribe", "channel": "metrics"}))

        # Heartbeat (keep-alive)
        await ws.send(json.dumps({"action": "heartbeat"}))

        while True:
            msg = json.loads(await ws.recv())
            print(msg)

asyncio.run(monitor())
```

Bot WebSocket channels:
- `signals` -- signal_received, signal_rejected, signal_fused
- `orders` -- trade_executed, position_closed, order_submitted
- `alerts` -- kill_switch, emergency_close, daily_loss_warning, error
- `lifecycle` -- bot_started, bot_stopped, bot_paused, bot_resumed
- `metrics` -- performance_snapshot, weight_update

### 6. Health check

```bash
curl http://localhost:8000/health
```

Response:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "components": {
    "database": "ok",
    "redis": "ok",
    "bot": "ready",
    "metrics": "ok (42 metrics)"
  }
}
```

Status is `"ok"` when all components are healthy, `"degraded"` otherwise.

### 7. Prometheus metrics

```bash
curl http://localhost:8000/metrics
```

Returns metrics in Prometheus exposition format for scraping by Prometheus/Grafana.

## Code examples

### Python client example

```python
import httpx

BASE = "http://localhost:8000/api/v1"
HEADERS = {"X-API-Key": "ax_your_key"}

# Sync client
with httpx.Client(base_url=BASE, headers=HEADERS) as client:
    # Get quote
    r = client.get("/market/quotes/AAPL")
    quote = r.json()

    # Start bot
    r = client.post("/bot/start", json={"paper_mode": True})
    print(r.json()["message"])

    # Get status
    r = client.get("/bot/status")
    status = r.json()
    print(f"Bot: {status['status']}, P&L: ${status['daily_pnl']}")

    # Kill switch
    r = client.post("/bot/kill", json={"reason": "Manual stop"})
```

### Async Python client

```python
import httpx

async def main():
    async with httpx.AsyncClient(
        base_url="http://localhost:8000/api/v1",
        headers={"X-API-Key": "ax_your_key"},
    ) as client:
        r = await client.get("/market/quotes/AAPL")
        quote = r.json()

        r = await client.get("/bot/status")
        status = r.json()
```

### Creating the app programmatically

```python
from src.api.app import create_app
from src.api.config import APIConfig

config = APIConfig(
    title="My Axion Instance",
    version="2.0.0",
    prefix="/api/v2",
    docs_url="/swagger",
)

app = create_app(config)
# app is a FastAPI instance ready for uvicorn
```

## Key classes and methods

### `create_app(config) -> FastAPI` (src/api/app.py)
Factory function that creates the configured FastAPI application with full middleware stack.

### `APIConfig` (src/api/config.py)
Fields: `title`, `version`, `description`, `prefix` (default `/api/v1`), `docs_url`, `cors_origins`, `cors_methods`, `cors_headers`, `api_key_prefix` (default `ax_`), `max_page_size`, `default_page_size`

### `APITier` enum (src/api/config.py)
Values: `FREE`, `PRO`, `ENTERPRISE`

### `AuthContext` (src/api/dependencies.py)
Fields: `user_id`, `tier` (APITier), `scopes` (list[str]), `authenticated` (bool)

### Dependency functions (src/api/dependencies.py)
- `require_auth` -- validates API key, returns AuthContext
- `require_scope(scope)` -- factory returning dependency that checks scope
- `check_rate_limit` -- validates auth + checks rate limit, adds headers

### Route modules (src/api/routes/)
- `market_data.py` -- `/market/quotes/{symbol}`, `/market/ohlcv/{symbol}`, `/market/fundamentals/{symbol}`
- `factors.py` -- factor scores and rankings
- `portfolio.py` -- portfolio summary, positions, optimization
- `trading.py` -- order placement, listing, cancellation
- `ai.py` -- AI chat and analysis
- `options.py` -- options chain and Greeks
- `backtesting.py` -- strategy backtesting
- `bot.py` -- 11 bot control endpoints
- `bot_ws.py` -- WebSocket endpoint at `/ws/bot`
- `keys.py` -- API key management

## Common patterns

### Middleware stack (outermost to innermost)

1. `SecurityHeadersMiddleware` -- X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
2. `RequestTracingMiddleware` -- assigns X-Request-ID, logs lifecycle (from `src/logging_config/`)
3. `ErrorHandlingMiddleware` -- catches exceptions, returns structured JSON (from `src/api_errors/`)
4. `CORSMiddleware` -- handles preflight, configurable origins

### Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AXION_REQUIRE_API_KEY` | Enable API key auth | `false` |
| `AXION_CORS_ORIGINS` | Comma-separated CORS origins | localhost:8501,8000,3000 |
| `AXION_ENABLE_HSTS` | Enable HSTS header | `false` |
| `AXION_DATABASE_SYNC_URL` | PostgreSQL connection string | localhost:5432/axion |
| `AXION_REDIS_URL` | Redis connection string | redis://localhost:6379/0 |

### Error response format

When `ErrorHandlingMiddleware` is active, errors return structured JSON:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded (per_minute)",
    "detail": null,
    "request_id": "abc123"
  }
}
```

HTTP status codes:
- 401 -- Missing or invalid API key
- 403 -- Insufficient scope
- 409 -- Conflict (e.g., bot already running)
- 429 -- Rate limit exceeded (includes Retry-After header)

### Source files

- `src/api/app.py` -- create_app factory, middleware stack, health endpoint
- `src/api/config.py` -- APIConfig, APITier, WebSocketChannel, WebhookEvent, RATE_LIMITS
- `src/api/dependencies.py` -- AuthContext, require_auth, require_scope, check_rate_limit
- `src/api/auth.py` -- APIKeyManager, RateLimiter
- `src/api/models.py` -- Pydantic request/response models
- `src/api/websocket.py` -- WebSocketManager
- `src/api/routes/market_data.py` -- market data endpoints
- `src/api/routes/factors.py` -- factor endpoints
- `src/api/routes/portfolio.py` -- portfolio endpoints
- `src/api/routes/trading.py` -- trading endpoints
- `src/api/routes/ai.py` -- AI endpoints
- `src/api/routes/options.py` -- options endpoints
- `src/api/routes/backtesting.py` -- backtesting endpoints
- `src/api/routes/bot.py` -- bot control endpoints
- `src/api/routes/bot_ws.py` -- bot WebSocket endpoint
- `src/api/routes/keys.py` -- API key management endpoints
