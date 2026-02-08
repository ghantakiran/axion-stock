"""Integration & Load Testing Framework (PRD-108).

Provides base classes, mock services, test fixtures, load testing,
and benchmark utilities for the Axion platform test suite.
"""

from src.testing.config import LoadProfile, TestConfig, TestStatus, TestType
from src.testing.base import (
    APITestBase,
    DatabaseTestBase,
    IntegrationTestBase,
    TestResult,
)
from src.testing.mocks import MockBroker, MockMarketData, MockRedis, MockOrder, OHLCVBar
from src.testing.fixtures import (
    TestMarketData,
    TestOrder,
    TestPortfolio,
    TestSignal,
    create_test_market_data,
    create_test_order,
    create_test_orders_batch,
    create_test_portfolio,
    create_test_portfolio_with_positions,
    create_test_signal,
)
from src.testing.load import LoadScenario, LoadTestResult, LoadTestRunner
from src.testing.benchmarks import BenchmarkResult, BenchmarkSuite

__all__ = [
    # Config
    "LoadProfile",
    "TestConfig",
    "TestStatus",
    "TestType",
    # Base
    "APITestBase",
    "DatabaseTestBase",
    "IntegrationTestBase",
    "TestResult",
    # Mocks
    "MockBroker",
    "MockMarketData",
    "MockRedis",
    "MockOrder",
    "OHLCVBar",
    # Fixtures
    "TestMarketData",
    "TestOrder",
    "TestPortfolio",
    "TestSignal",
    "create_test_market_data",
    "create_test_order",
    "create_test_orders_batch",
    "create_test_portfolio",
    "create_test_portfolio_with_positions",
    "create_test_signal",
    # Load
    "LoadScenario",
    "LoadTestResult",
    "LoadTestRunner",
    # Benchmarks
    "BenchmarkResult",
    "BenchmarkSuite",
]
