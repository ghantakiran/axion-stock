"""Base classes for integration, API, and database tests."""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.testing.config import TestConfig, TestStatus, TestType

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result from a single test execution."""

    name: str
    status: TestStatus = TestStatus.PENDING
    duration_ms: float = 0.0
    message: str = ""
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class IntegrationTestBase:
    """Base class for integration tests with setup/teardown helpers.

    Provides common infrastructure for tests that need external
    services (database, cache, broker, etc.).
    """

    def __init__(self, config: Optional[TestConfig] = None):
        self.config = config or TestConfig()
        self._resources: List[str] = []
        self._setup_done = False
        self._teardown_done = False
        self._results: List[TestResult] = []
        self._start_time: Optional[float] = None
        logger.info("IntegrationTestBase initialized")

    def setup(self) -> None:
        """Set up test resources. Override in subclasses."""
        self._setup_done = True
        self._start_time = time.time()
        logger.info("IntegrationTestBase setup complete")

    def teardown(self) -> None:
        """Tear down test resources. Override in subclasses."""
        self._teardown_done = True
        self._resources.clear()
        logger.info("IntegrationTestBase teardown complete")

    def register_resource(self, name: str) -> None:
        """Register a resource for cleanup during teardown."""
        self._resources.append(name)

    def get_resources(self) -> List[str]:
        """Return list of registered resources."""
        return list(self._resources)

    def record_result(self, result: TestResult) -> None:
        """Record a test result."""
        self._results.append(result)

    def get_results(self) -> List[TestResult]:
        """Return all recorded test results."""
        return list(self._results)

    def get_elapsed_ms(self) -> float:
        """Return elapsed time in ms since setup."""
        if self._start_time is None:
            return 0.0
        return (time.time() - self._start_time) * 1000

    @property
    def is_setup(self) -> bool:
        return self._setup_done

    @property
    def is_teardown(self) -> bool:
        return self._teardown_done

    def run_test(self, name: str, func, *args, **kwargs) -> TestResult:
        """Execute a test function and capture results."""
        result = TestResult(name=name, started_at=datetime.now())
        start = time.time()
        try:
            func(*args, **kwargs)
            result.status = TestStatus.PASSED
            result.message = "Test passed"
        except AssertionError as e:
            result.status = TestStatus.FAILED
            result.message = str(e)
            result.error = str(e)
        except Exception as e:
            result.status = TestStatus.ERROR
            result.message = f"Unexpected error: {e}"
            result.error = str(e)
        finally:
            result.duration_ms = (time.time() - start) * 1000
            result.finished_at = datetime.now()
            self.record_result(result)
        return result


class APITestBase(IntegrationTestBase):
    """Base class for API integration tests.

    Extends IntegrationTestBase with HTTP client helpers.
    """

    def __init__(self, config: Optional[TestConfig] = None):
        super().__init__(config)
        self._base_url = self.config.api_base_url
        self._headers: Dict[str, str] = {"Content-Type": "application/json"}
        self._request_history: List[Dict[str, Any]] = []

    def setup(self) -> None:
        super().setup()
        self.register_resource("api_client")
        logger.info(f"APITestBase setup with base_url={self._base_url}")

    def teardown(self) -> None:
        self._request_history.clear()
        super().teardown()

    def set_header(self, key: str, value: str) -> None:
        """Set a request header."""
        self._headers[key] = value

    def get_headers(self) -> Dict[str, str]:
        """Return current headers."""
        return dict(self._headers)

    @property
    def base_url(self) -> str:
        return self._base_url

    def simulate_request(
        self,
        method: str,
        path: str,
        status_code: int = 200,
        response_data: Optional[Dict] = None,
        latency_ms: float = 0.0,
    ) -> Dict[str, Any]:
        """Simulate an HTTP request for testing (no real network call)."""
        record = {
            "method": method.upper(),
            "url": f"{self._base_url}{path}",
            "headers": dict(self._headers),
            "status_code": status_code,
            "response": response_data or {},
            "latency_ms": latency_ms,
            "timestamp": datetime.now(),
        }
        self._request_history.append(record)
        return record

    def get_request_history(self) -> List[Dict[str, Any]]:
        """Return history of simulated requests."""
        return list(self._request_history)


class DatabaseTestBase(IntegrationTestBase):
    """Base class for database integration tests.

    Extends IntegrationTestBase with database setup/teardown.
    """

    def __init__(self, config: Optional[TestConfig] = None):
        super().__init__(config)
        self._db_url = self.config.db_url
        self._tables_created: List[str] = []
        self._transaction_active = False

    def setup(self) -> None:
        super().setup()
        self.register_resource("database")
        self._transaction_active = True
        logger.info(f"DatabaseTestBase setup with db_url={self._db_url}")

    def teardown(self) -> None:
        if self._transaction_active:
            self.rollback()
        self._tables_created.clear()
        super().teardown()

    @property
    def db_url(self) -> str:
        return self._db_url

    @property
    def transaction_active(self) -> bool:
        return self._transaction_active

    def create_table(self, table_name: str) -> None:
        """Track a created table for cleanup."""
        self._tables_created.append(table_name)
        logger.info(f"Table registered: {table_name}")

    def get_tables(self) -> List[str]:
        """Return list of created tables."""
        return list(self._tables_created)

    def rollback(self) -> None:
        """Simulate rolling back a transaction."""
        self._transaction_active = False
        logger.info("Transaction rolled back")

    def commit(self) -> None:
        """Simulate committing a transaction."""
        self._transaction_active = False
        logger.info("Transaction committed")
