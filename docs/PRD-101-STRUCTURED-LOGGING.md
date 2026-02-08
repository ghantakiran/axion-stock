# PRD-101: Structured Logging & Request Tracing

## Overview
Replace ad-hoc Python logging with structured JSON logging using structlog, adding request ID propagation, correlation IDs for cross-service tracing, and performance timing context. This is foundational for production observability.

## Components

### 1. Logging Configuration (`src/logging_config/setup.py`)
- **configure_logging()** — One-call setup for structured logging
- JSON output format for production, colored console for development
- Automatic context binding: timestamp, level, logger name, module, function
- Log level configuration via AXION_LOG_LEVEL environment variable
- Processor chain: add timestamp, add log level, add caller info, format to JSON

### 2. Context Management (`src/logging_config/context.py`)
- **RequestContext** — Thread-local/contextvars-based request context
- Bind request_id, user_id, correlation_id to all log entries
- Context manager for automatic cleanup
- generate_request_id() with UUID4

### 3. FastAPI Middleware (`src/logging_config/middleware.py`)
- **RequestTracingMiddleware** — Inject request_id into every request
- Log request start (method, path, query params)
- Log request completion (status code, duration_ms)
- Propagate X-Request-ID header (use incoming or generate new)
- Add request_id to response headers

### 4. Performance Logger (`src/logging_config/performance.py`)
- **@log_performance** decorator — Time any function call
- Log slow operations (configurable threshold, default 1s)
- Include function name, args summary, duration_ms in structured output

### 5. Configuration (`src/logging_config/config.py`)
- LogLevel enum (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- LogFormat enum (JSON, CONSOLE)
- LoggingConfig dataclass with defaults

## Integration Points
- FastAPI app factory adds RequestTracingMiddleware
- All new modules use structlog.get_logger() instead of logging.getLogger()
- Existing modules remain compatible (structlog wraps stdlib logging)

## Dependencies Added
- structlog >= 24.0.0
- python-json-logger >= 2.0.0
