"""Load testing runner with configurable concurrency and scenarios."""

import asyncio
import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.testing.config import LoadProfile, TestConfig

logger = logging.getLogger(__name__)


@dataclass
class LoadScenario:
    """Definition of a load test scenario."""

    name: str
    func: Optional[Callable] = None
    concurrency: int = 10
    iterations: int = 100
    profile: LoadProfile = LoadProfile.CONSTANT
    ramp_up_seconds: int = 10
    think_time_ms: float = 0.0
    timeout_seconds: int = 30
    description: str = ""

    def __post_init__(self):
        if not self.description:
            self.description = f"Load test: {self.name}"


@dataclass
class LoadTestResult:
    """Results from a load test execution with percentile statistics."""

    scenario_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    latencies_ms: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    total_duration_ms: float = 0.0

    @property
    def mean_ms(self) -> float:
        """Mean latency in ms."""
        if not self.latencies_ms:
            return 0.0
        return statistics.mean(self.latencies_ms)

    @property
    def p50_ms(self) -> float:
        """Median (P50) latency in ms."""
        if not self.latencies_ms:
            return 0.0
        return statistics.median(self.latencies_ms)

    @property
    def p95_ms(self) -> float:
        """P95 latency in ms."""
        if not self.latencies_ms:
            return 0.0
        sorted_lats = sorted(self.latencies_ms)
        idx = int(len(sorted_lats) * 0.95)
        return sorted_lats[min(idx, len(sorted_lats) - 1)]

    @property
    def p99_ms(self) -> float:
        """P99 latency in ms."""
        if not self.latencies_ms:
            return 0.0
        sorted_lats = sorted(self.latencies_ms)
        idx = int(len(sorted_lats) * 0.99)
        return sorted_lats[min(idx, len(sorted_lats) - 1)]

    @property
    def max_ms(self) -> float:
        """Maximum latency in ms."""
        if not self.latencies_ms:
            return 0.0
        return max(self.latencies_ms)

    @property
    def min_ms(self) -> float:
        """Minimum latency in ms."""
        if not self.latencies_ms:
            return 0.0
        return min(self.latencies_ms)

    @property
    def success_rate(self) -> float:
        """Fraction of requests that succeeded."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def requests_per_second(self) -> float:
        """Throughput in requests per second."""
        if self.total_duration_ms == 0:
            return 0.0
        return self.total_requests / (self.total_duration_ms / 1000.0)

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict of the load test results."""
        return {
            "scenario": self.scenario_name,
            "total_requests": self.total_requests,
            "successful": self.successful_requests,
            "failed": self.failed_requests,
            "mean_ms": round(self.mean_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "success_rate": round(self.success_rate, 4),
            "rps": round(self.requests_per_second, 2),
            "duration_ms": round(self.total_duration_ms, 2),
        }


class LoadTestRunner:
    """Execute load test scenarios using asyncio for concurrency.

    Usage:
        runner = LoadTestRunner()
        scenario = LoadScenario(name="api_test", func=my_func, concurrency=50)
        result = runner.run_scenario(scenario)
    """

    def __init__(self, config: Optional[TestConfig] = None):
        self.config = config or TestConfig()
        self._results: List[LoadTestResult] = []
        logger.info("LoadTestRunner initialized")

    async def _execute_single(
        self,
        func: Callable,
        result: LoadTestResult,
    ) -> None:
        """Execute a single iteration and record latency."""
        start = time.time()
        try:
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()
            elapsed_ms = (time.time() - start) * 1000
            result.latencies_ms.append(elapsed_ms)
            result.successful_requests += 1
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            result.latencies_ms.append(elapsed_ms)
            result.failed_requests += 1
            result.errors.append(str(e))
        result.total_requests += 1

    async def _run_constant(
        self,
        scenario: LoadScenario,
        result: LoadTestResult,
    ) -> None:
        """Run scenario with constant concurrency."""
        iterations_per_worker = scenario.iterations // scenario.concurrency
        remainder = scenario.iterations % scenario.concurrency

        async def worker(n_iters: int):
            for _ in range(n_iters):
                await self._execute_single(scenario.func, result)
                if scenario.think_time_ms > 0:
                    await asyncio.sleep(scenario.think_time_ms / 1000.0)

        tasks = []
        for i in range(scenario.concurrency):
            n = iterations_per_worker + (1 if i < remainder else 0)
            if n > 0:
                tasks.append(worker(n))

        await asyncio.gather(*tasks)

    async def _run_ramp_up(
        self,
        scenario: LoadScenario,
        result: LoadTestResult,
    ) -> None:
        """Run scenario with ramping concurrency."""
        # Start with 1 concurrent worker, ramp to full concurrency
        steps = min(scenario.concurrency, 5)
        iters_per_step = scenario.iterations // steps

        for step in range(1, steps + 1):
            current_concurrency = max(1, (scenario.concurrency * step) // steps)
            iters_this_step = iters_per_step
            if step == steps:
                iters_this_step = scenario.iterations - (iters_per_step * (steps - 1))

            per_worker = iters_this_step // current_concurrency
            remainder = iters_this_step % current_concurrency

            async def worker(n_iters: int):
                for _ in range(n_iters):
                    await self._execute_single(scenario.func, result)

            tasks = []
            for i in range(current_concurrency):
                n = per_worker + (1 if i < remainder else 0)
                if n > 0:
                    tasks.append(worker(n))

            await asyncio.gather(*tasks)

    async def run_scenario_async(self, scenario: LoadScenario) -> LoadTestResult:
        """Run a load scenario asynchronously. Returns LoadTestResult."""
        if scenario.func is None:
            raise ValueError(f"Scenario '{scenario.name}' has no callable function")

        result = LoadTestResult(
            scenario_name=scenario.name,
            started_at=datetime.now(),
        )

        start = time.time()

        if scenario.profile == LoadProfile.RAMP_UP:
            await self._run_ramp_up(scenario, result)
        else:
            await self._run_constant(scenario, result)

        result.total_duration_ms = (time.time() - start) * 1000
        result.finished_at = datetime.now()
        self._results.append(result)

        logger.info(
            f"Load test '{scenario.name}' complete: "
            f"{result.total_requests} requests, "
            f"mean={result.mean_ms:.1f}ms, p95={result.p95_ms:.1f}ms"
        )
        return result

    def run_scenario(self, scenario: LoadScenario) -> LoadTestResult:
        """Synchronous wrapper to run a load scenario."""
        return asyncio.run(self.run_scenario_async(scenario))

    def get_results(self) -> List[LoadTestResult]:
        """Return all recorded load test results."""
        return list(self._results)

    def clear_results(self) -> None:
        """Clear all recorded results."""
        self._results.clear()

    @staticmethod
    def generate_sample_result(name: str = "sample_test") -> LoadTestResult:
        """Generate a sample load test result for demo/dashboard."""
        import random as _rng
        latencies = [_rng.uniform(5, 200) for _ in range(500)]
        result = LoadTestResult(
            scenario_name=name,
            total_requests=500,
            successful_requests=480,
            failed_requests=20,
            latencies_ms=latencies,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            total_duration_ms=sum(latencies) * 0.1,
        )
        return result
