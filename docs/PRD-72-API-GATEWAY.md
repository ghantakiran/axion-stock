# PRD-72: API Gateway & Rate Limiting

## Overview
Advanced API gateway with tiered rate limiting, API key management, webhook delivery system, WebSocket real-time streaming, SDK client, and FastAPI route architecture.

## Components

### 1. API Configuration (`src/api/config.py`)
- **APITier** — FREE, PRO, ENTERPRISE tier enum
- **RATE_LIMITS** — Tier-based limits (FREE: 100/day, 10/min; PRO: 1,000/day, 60/min; ENTERPRISE: unlimited, 600/min)
- **APIConfig** — Title, version, prefix (`/api/v1`), CORS, token expiry settings
- **WebSocketConfig** — Heartbeat interval, max connections, message rate limits
- **WebhookConfig** — Max retries, timeout, signing key, delivery queue size

### 2. API Key Manager & Rate Limiter (`src/api/auth.py`)
- **APIKeyManager** — Create (SHA-256 hashed, `ax_` prefix), validate, revoke, list keys with scope checking (read, write, admin)
- **RateLimiter** — Token bucket implementation with per-minute and daily limits, usage tracking
- **WebhookSigner** — HMAC payload signing and verification for webhook security

### 3. Webhook System (`src/api/webhooks.py`)
- **WebhookManager** — Register webhooks, dispatch events with filtering, delivery tracking with success/failure stats
- **Webhook** — Endpoint registration with URL, events, secret, active status
- **DeliveryRecord** — Delivery attempt tracking with status, response, timing

### 4. WebSocket Manager (`src/api/websocket.py`)
- **WebSocketManager** — Connection management, subscription handling, heartbeat tracking
- **WSConnection** — Connection state with user_id, subscriptions, message counts
- Per-user connection limits, channel subscription management

### 5. FastAPI Application (`src/api/app.py`)
- **create_app()** — Factory function with CORS middleware, health check, route mounting under `/api/v1`

### 6. API Routes (`src/api/routes/`)
- **market_data.py** — Quote endpoints with real-time pricing
- **ai.py** — Prediction and sentiment analysis endpoints
- **orders.py** — Order CRUD (create, get, cancel)
- **portfolio.py** — Portfolio positions and holdings

### 7. API Models (`src/api/models.py`)
- Request/response models: APIKeyCreateRequest, APIKeyResponse, WebhookCreateRequest, WebhookResponse
- Market data: QuoteResponse, BarResponse, OptionsChainResponse
- Trading: OrderRequest, OrderResponse, PortfolioResponse
- System: ErrorResponse, HealthResponse, PaginatedResponse

### 8. SDK Client (`src/api/sdk.py`)
- **AxionClient** — Full SDK with namespace APIs (_FactorsAPI, _PortfolioAPI, etc.)
- Rate limit status checking, authentication header management

### 9. ORM Models (`src/db/models.py`)
- **UserAPIKey** — key_hash, key_prefix, scopes, is_active, expires_at, request_count
- **RateLimitRecord** — key, count, window_start/end
- **WebSocketRateLimitRecord** — user_id, connection_id, limit_type, violations, blocked_until

## Database Tables
- `api_keys` — API key storage with user_id, key_hash, scopes, tier (migration 012)
- `webhooks` — Webhook registrations with URL, events, secret (migration 012)
- `webhook_deliveries` — Delivery history with status codes, response times (migration 012)
- `rate_limit_log` — Rate limit tracking per endpoint (migration 012)
- `api_usage` — Daily usage analytics (migration 012)
- `user_api_keys` — API key management with scopes and expiry (migration 053)
- `websocket_connections` — WebSocket connection tracking (migration 059)
- `websocket_subscriptions` — Channel subscriptions (migration 059)
- `websocket_metrics` — Time-series WebSocket metrics (migration 059)
- `websocket_rate_limits` — WebSocket-specific rate limiting (migration 059)

## Dashboard
Streamlit dashboard (`app/pages/api_dashboard.py`) with 4 tabs:
1. **API Keys** — Key creation and management interface
2. **Webhooks** — Webhook registration and monitoring
3. **Rate Limits** — Rate limit status display by tier
4. **SDK** — Documentation and quick-start code examples

## Test Coverage
88 tests in `tests/test_api.py` covering API config (tiers, rate limits, channels, events), APIKeyManager (create/validate/revoke/scopes), RateLimiter (limits/reset/usage), WebhookSigner (sign/verify), WebSocketManager (connect/disconnect/limits/subscriptions), Pydantic models, and FastAPI routes.
