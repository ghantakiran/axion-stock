"""Request Context Management.

Thread-safe request context using contextvars for binding
request IDs, user IDs, and correlation IDs to log entries.
"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# Context variables for request-scoped data
_request_id_var: ContextVar[str] = ContextVar("request_id", default="")
_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
_user_id_var: ContextVar[str] = ContextVar("user_id", default="")
_extra_context_var: ContextVar[dict] = ContextVar("extra_context", default={})


def generate_request_id() -> str:
    """Generate a unique request ID using UUID4."""
    return str(uuid.uuid4())


def get_request_id() -> str:
    """Get the current request ID from context."""
    return _request_id_var.get()


def get_correlation_id() -> str:
    """Get the current correlation ID from context."""
    return _correlation_id_var.get()


def get_user_id() -> str:
    """Get the current user ID from context."""
    return _user_id_var.get()


def get_context_dict() -> dict[str, Any]:
    """Get all context variables as a dictionary for log binding."""
    ctx = {}
    req_id = _request_id_var.get()
    if req_id:
        ctx["request_id"] = req_id
    corr_id = _correlation_id_var.get()
    if corr_id:
        ctx["correlation_id"] = corr_id
    user_id = _user_id_var.get()
    if user_id:
        ctx["user_id"] = user_id
    extra = _extra_context_var.get()
    if extra:
        ctx.update(extra)
    return ctx


@dataclass
class RequestContext:
    """Context manager for request-scoped logging context.

    Binds request_id, user_id, and correlation_id to all log entries
    within the context. Automatically cleans up on exit.

    Example:
        with RequestContext(request_id="abc-123", user_id="user_1"):
            logger.info("processing request")  # includes request_id, user_id
    """

    request_id: str = ""
    correlation_id: str = ""
    user_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    _tokens: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        if not self.request_id:
            self.request_id = generate_request_id()
        if not self.correlation_id:
            self.correlation_id = self.request_id

    def __enter__(self) -> "RequestContext":
        self._tokens = [
            _request_id_var.set(self.request_id),
            _correlation_id_var.set(self.correlation_id),
            _user_id_var.set(self.user_id),
            _extra_context_var.set(self.extra.copy()),
        ]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        _request_id_var.set("")
        _correlation_id_var.set("")
        _user_id_var.set("")
        _extra_context_var.set({})
        self._tokens.clear()

    @property
    def elapsed_ms(self) -> float:
        """Milliseconds since context was created."""
        delta = datetime.now(timezone.utc) - self.started_at
        return delta.total_seconds() * 1000

    def bind(self, **kwargs: Any) -> None:
        """Add extra key-value pairs to the context."""
        current = _extra_context_var.get()
        updated = {**current, **kwargs}
        _extra_context_var.set(updated)
        self.extra.update(kwargs)
