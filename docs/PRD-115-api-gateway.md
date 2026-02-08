# PRD-115: API Gateway & Advanced Rate Limiting

## Overview
API gateway layer with per-endpoint rate limiting, per-user quotas, API analytics,
request queueing, versioning middleware, and OpenAPI spec management.

## Problem
Current API has basic per-IP token-bucket rate limiting and hardcoded /api/v1 prefix.
No per-endpoint limits (quotes vs orders need different limits), no per-user quotas,
no usage analytics, no API versioning strategy for v1→v2 migration.

## Components

### 1. Gateway Core (`src/api_gateway/gateway.py`)
- Request interception and processing pipeline
- Pre/post request hooks
- Request/response transformation
- Health endpoint bypass
- Gateway metrics collection

### 2. Rate Limiter (`src/api_gateway/rate_limiter.py`)
- Per-endpoint rate limiting (different limits per route)
- Per-user quota management (daily/monthly request budgets)
- Sliding window rate limiting algorithm
- Rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
- Burst allowance configuration
- Tier-based limits (free, pro, enterprise)

### 3. API Analytics (`src/api_gateway/analytics.py`)
- Request counting by endpoint, user, status code
- Latency tracking (p50, p95, p99 per endpoint)
- Error rate monitoring
- Usage trends and top consumers
- Analytics query API

### 4. API Versioning (`src/api_gateway/versioning.py`)
- Version registry with deprecation tracking
- Version negotiation (header, URL path, query param)
- Sunset headers for deprecated versions
- Migration guides per version transition
- Version-specific middleware chains

### 5. Request Validator (`src/api_gateway/validator.py`)
- Schema-based request validation
- Content-type enforcement
- Payload size limits
- Required header validation
- IP allowlist/blocklist

## Database
- `api_usage_records` table for request analytics
- `api_quotas` table for per-user quota tracking

## Dashboard
4-tab Streamlit dashboard: API Overview, Rate Limits, Analytics, Versioning

## Tests
Test suite covering rate limiting, quota management, analytics tracking,
versioning negotiation, and request validation.
