"""Signal handler registration for graceful shutdown."""

import logging
import signal
import threading
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SignalHandler:
    """Manages OS signal handlers for graceful application shutdown.

    Registers handlers for SIGTERM and SIGINT that set a shutdown flag
    and trigger orderly teardown via a configurable callback.
    """

    def __init__(self):
        self._shutdown_flag = threading.Event()
        self._shutdown_callbacks: List[Callable] = []
        self._original_handlers: Dict[int, Optional[signal.Handlers]] = {}
        self._signal_count: int = 0
        self._registered_signals: List[int] = []
        self._max_signals: int = 3  # Force-exit after this many signals

    @property
    def shutdown_requested(self) -> bool:
        """Whether a shutdown signal has been received."""
        return self._shutdown_flag.is_set()

    @property
    def signal_count(self) -> int:
        """Number of shutdown signals received."""
        return self._signal_count

    def register_shutdown_callback(self, callback: Callable) -> None:
        """Register a callback to be invoked on shutdown signal."""
        self._shutdown_callbacks.append(callback)
        logger.info("Registered shutdown callback: %s", callback.__name__ if hasattr(callback, '__name__') else str(callback))

    def _handle_signal(self, signum: int, frame) -> None:
        """Internal signal handler."""
        self._signal_count += 1
        sig_name = signal.Signals(signum).name
        logger.warning(
            "Received signal %s (%d/%d)",
            sig_name,
            self._signal_count,
            self._max_signals,
        )

        if self._signal_count >= self._max_signals:
            logger.critical("Max signal count reached, forcing exit")
            return

        if not self._shutdown_flag.is_set():
            self._shutdown_flag.set()
            self._trigger_shutdown()

    def _trigger_shutdown(self) -> None:
        """Execute registered shutdown callbacks."""
        for callback in self._shutdown_callbacks:
            try:
                callback()
            except Exception as exc:
                logger.error("Shutdown callback failed: %s", exc)

    def register_signals(self, signals: Optional[List[int]] = None) -> None:
        """Register signal handlers for graceful shutdown.

        Args:
            signals: Signal numbers to handle. Defaults to [SIGTERM, SIGINT].
        """
        if signals is None:
            signals = [signal.SIGTERM, signal.SIGINT]

        for sig in signals:
            try:
                original = signal.getsignal(sig)
                self._original_handlers[sig] = original
                signal.signal(sig, self._handle_signal)
                self._registered_signals.append(sig)
                logger.info("Registered handler for signal %s", signal.Signals(sig).name)
            except (OSError, ValueError) as exc:
                logger.warning("Cannot register handler for signal %d: %s", sig, exc)

    def restore_signals(self) -> None:
        """Restore original signal handlers."""
        for sig, handler in self._original_handlers.items():
            try:
                if handler is not None:
                    signal.signal(sig, handler)
                else:
                    signal.signal(sig, signal.SIG_DFL)
                logger.info("Restored original handler for signal %s", signal.Signals(sig).name)
            except (OSError, ValueError) as exc:
                logger.warning("Cannot restore handler for signal %d: %s", sig, exc)
        self._original_handlers.clear()
        self._registered_signals.clear()

    def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """Block until shutdown signal is received or timeout expires.

        Returns True if shutdown was requested, False on timeout.
        """
        return self._shutdown_flag.wait(timeout=timeout)

    def reset(self) -> None:
        """Reset the signal handler state."""
        self._shutdown_flag.clear()
        self._signal_count = 0
        self._shutdown_callbacks.clear()

    def get_state(self) -> Dict:
        """Return current signal handler state."""
        return {
            "shutdown_requested": self.shutdown_requested,
            "signal_count": self._signal_count,
            "registered_signals": [
                signal.Signals(s).name for s in self._registered_signals
            ],
            "callback_count": len(self._shutdown_callbacks),
        }
