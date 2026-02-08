"""Configuration for integration & load testing framework."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class TestType(str, Enum):
    """Classification of test types."""

    UNIT = "unit"
    INTEGRATION = "integration"
    LOAD = "load"
    BENCHMARK = "benchmark"
    SMOKE = "smoke"
    E2E = "end_to_end"


class LoadProfile(str, Enum):
    """Load testing traffic profiles."""

    CONSTANT = "constant"
    RAMP_UP = "ramp_up"
    SPIKE = "spike"
    STRESS = "stress"
    SOAK = "soak"


class TestStatus(str, Enum):
    """Status of a test run."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


# Default thresholds
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_CONCURRENCY = 10
DEFAULT_ITERATIONS = 100
DEFAULT_RAMP_UP_SECONDS = 10
DEFAULT_BENCHMARK_ITERATIONS = 1000
DEFAULT_REGRESSION_THRESHOLD = 0.10  # 10% regression


@dataclass
class TestConfig:
    """Master configuration for the testing framework."""

    test_type: TestType = TestType.INTEGRATION
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    concurrency: int = DEFAULT_CONCURRENCY
    iterations: int = DEFAULT_ITERATIONS
    load_profile: LoadProfile = LoadProfile.CONSTANT
    ramp_up_seconds: int = DEFAULT_RAMP_UP_SECONDS
    benchmark_iterations: int = DEFAULT_BENCHMARK_ITERATIONS
    regression_threshold: float = DEFAULT_REGRESSION_THRESHOLD
    db_url: str = "sqlite:///:memory:"
    redis_url: str = "redis://localhost:6379/15"
    api_base_url: str = "http://localhost:8000"
    mock_broker_latency_ms: float = 10.0
    mock_broker_fill_probability: float = 0.95
    mock_market_data_volatility: float = 0.02
    tags: List[str] = field(default_factory=list)
    environment: str = "test"
    verbose: bool = False
