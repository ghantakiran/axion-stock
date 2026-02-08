# PRD-107: Application Lifecycle Management

## Overview
Add graceful shutdown handling, health probe endpoints, connection pool management, and startup/shutdown hooks to ensure clean application lifecycle management. Currently the platform lacks shutdown hooks and health probes needed for production orchestration (Kubernetes, Docker Compose).

## Goals
1. **Graceful Shutdown** — Handle SIGTERM/SIGINT signals, drain in-flight requests, close connections cleanly
2. **Health Probes** — Kubernetes-compatible liveness, readiness, and startup probe endpoints
3. **Connection Management** — Centralized manager for database pools, Redis connections, WebSocket connections
4. **Startup Hooks** — Ordered initialization of services with dependency awareness
5. **Shutdown Hooks** — Ordered teardown with configurable timeout and error handling

## Technical Design

### Health Probe Responses
- `/health/live` — Returns 200 if process is alive (liveness)
- `/health/ready` — Returns 200 if all dependencies are connected (readiness)
- `/health/startup` — Returns 200 once initialization is complete (startup)

### Components
- `src/lifecycle/__init__.py` — Public API exports
- `src/lifecycle/config.py` — Lifecycle configuration dataclass
- `src/lifecycle/manager.py` — LifecycleManager singleton (startup/shutdown orchestration)
- `src/lifecycle/health.py` — Health check registry, probe endpoints, dependency checks
- `src/lifecycle/signals.py` — Signal handler registration (SIGTERM, SIGINT)
- `src/lifecycle/hooks.py` — Hook registry for startup/shutdown callbacks with priority ordering

### Database
- `lifecycle_events` table for recording startup/shutdown events

### Dashboard
- Service status, dependency health, uptime, shutdown history

## Success Criteria
- Clean shutdown completes within configurable timeout (default 30s)
- Health probes accurately reflect service state
- All registered connections are properly closed on shutdown
- 40+ tests covering lifecycle scenarios
