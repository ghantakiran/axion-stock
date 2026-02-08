"""FastAPI Request Tracing Middleware.

Injects request IDs, logs request/response lifecycle,
and propagates tracing headers for cross-service correlation.
"""

import logging
import time
from typing import Optional

from src.logging_config.config import DEFAULT_LOGGING_CONFIG, LoggingConfig
from src.logging_config.context import RequestContext, generate_request_id

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"


class RequestTracingMiddleware:
    """ASGI middleware that injects request tracing into every request.

    Features:
    - Generates or propagates X-Request-ID header
    - Binds request context (request_id, correlation_id) to all logs
    - Logs request start and completion with timing
    - Adds request_id to response headers

    Usage:
        app.add_middleware(RequestTracingMiddleware)
    """

    def __init__(self, app, config: Optional[LoggingConfig] = None):
        self.app = app
        self.config = config or DEFAULT_LOGGING_CONFIG

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract or generate request ID
        headers = dict(scope.get("headers", []))
        request_id = self._get_header(headers, REQUEST_ID_HEADER) or generate_request_id()
        correlation_id = self._get_header(headers, CORRELATION_ID_HEADER) or request_id

        method = scope.get("method", "")
        path = scope.get("path", "")
        query = scope.get("query_string", b"").decode("utf-8", errors="replace")

        # Skip logging for excluded paths
        should_log = path not in self.config.exclude_paths

        start_time = time.perf_counter()

        with RequestContext(
            request_id=request_id,
            correlation_id=correlation_id,
        ):
            if should_log:
                logger.info(
                    "Request started",
                    extra={"method": method, "path": path},
                )

            status_code = 500  # default in case of unhandled error

            async def send_wrapper(message):
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message.get("status", 500)
                    # Inject request ID into response headers
                    response_headers = list(message.get("headers", []))
                    response_headers.append(
                        (REQUEST_ID_HEADER.lower().encode(), request_id.encode())
                    )
                    response_headers.append(
                        (CORRELATION_ID_HEADER.lower().encode(), correlation_id.encode())
                    )
                    message = {**message, "headers": response_headers}
                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
            except Exception:
                status_code = 500
                raise
            finally:
                duration_ms = (time.perf_counter() - start_time) * 1000
                if should_log:
                    log_level = logging.WARNING if status_code >= 400 else logging.INFO
                    logger.log(
                        log_level,
                        "Request completed",
                        extra={
                            "method": method,
                            "path": path,
                            "status_code": status_code,
                            "duration_ms": round(duration_ms, 2),
                        },
                    )

    @staticmethod
    def _get_header(headers: dict, name: str) -> Optional[str]:
        """Extract a header value from ASGI-style headers dict."""
        key = name.lower().encode()
        value = headers.get(key)
        if value:
            return value.decode("utf-8", errors="replace")
        return None
