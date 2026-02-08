"""Benchmark suite with regression detection."""

import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.testing.config import DEFAULT_BENCHMARK_ITERATIONS, DEFAULT_REGRESSION_THRESHOLD

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result from a single benchmark execution."""

    name: str
    iterations: int = 0
    mean_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    stdev_ms: float = 0.0
    total_ms: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    def has_regression(self, baseline: "BenchmarkResult", threshold: float = DEFAULT_REGRESSION_THRESHOLD) -> bool:
        """Check if this result regressed compared to a baseline.

        Args:
            baseline: Previous benchmark result to compare against.
            threshold: Fractional threshold (e.g. 0.10 = 10% regression).

        Returns:
            True if mean_ms exceeds baseline by more than threshold.
        """
        if baseline.mean_ms == 0:
            return False
        degradation = (self.mean_ms - baseline.mean_ms) / baseline.mean_ms
        return degradation > threshold

    def summary(self) -> Dict[str, Any]:
        """Return summary dict."""
        return {
            "name": self.name,
            "iterations": self.iterations,
            "mean_ms": round(self.mean_ms, 3),
            "p50_ms": round(self.p50_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "stdev_ms": round(self.stdev_ms, 3),
        }


class BenchmarkSuite:
    """Suite for running and tracking benchmarks with regression detection.

    Usage:
        suite = BenchmarkSuite("my_suite")
        suite.add_benchmark("sort_1000", lambda: sorted(range(1000, 0, -1)))
        results = suite.run_all()
    """

    def __init__(
        self,
        name: str,
        iterations: int = DEFAULT_BENCHMARK_ITERATIONS,
        regression_threshold: float = DEFAULT_REGRESSION_THRESHOLD,
    ):
        self.name = name
        self.iterations = iterations
        self.regression_threshold = regression_threshold
        self._benchmarks: Dict[str, Callable] = {}
        self._results: List[BenchmarkResult] = []
        self._baselines: Dict[str, BenchmarkResult] = {}
        logger.info("BenchmarkSuite '%s' initialized", name)

    def add_benchmark(self, name: str, func: Callable) -> None:
        """Register a benchmark function."""
        self._benchmarks[name] = func

    def remove_benchmark(self, name: str) -> bool:
        """Remove a benchmark by name."""
        if name in self._benchmarks:
            del self._benchmarks[name]
            return True
        return False

    def set_baseline(self, name: str, baseline: BenchmarkResult) -> None:
        """Set a baseline result for regression comparison."""
        self._baselines[name] = baseline

    def get_baselines(self) -> Dict[str, BenchmarkResult]:
        """Return all baselines."""
        return dict(self._baselines)

    def run_benchmark(self, name: str, iterations: Optional[int] = None) -> BenchmarkResult:
        """Run a single benchmark and return its result."""
        if name not in self._benchmarks:
            raise KeyError(f"Benchmark '{name}' not found")

        func = self._benchmarks[name]
        n = iterations or self.iterations
        latencies: List[float] = []

        for _ in range(n):
            start = time.perf_counter()
            func()
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        sorted_lats = sorted(latencies)
        result = BenchmarkResult(
            name=name,
            iterations=n,
            mean_ms=statistics.mean(latencies),
            p50_ms=statistics.median(latencies),
            p95_ms=sorted_lats[int(len(sorted_lats) * 0.95)] if len(sorted_lats) > 1 else sorted_lats[0],
            p99_ms=sorted_lats[int(len(sorted_lats) * 0.99)] if len(sorted_lats) > 1 else sorted_lats[0],
            min_ms=min(latencies),
            max_ms=max(latencies),
            stdev_ms=statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
            total_ms=sum(latencies),
        )
        self._results.append(result)
        return result

    def run_all(self) -> List[BenchmarkResult]:
        """Run all registered benchmarks."""
        results = []
        for name in self._benchmarks:
            result = self.run_benchmark(name)
            results.append(result)
        return results

    def get_results(self) -> List[BenchmarkResult]:
        """Return all recorded results."""
        return list(self._results)

    def detect_regressions(self) -> List[Dict[str, Any]]:
        """Compare latest results against baselines and find regressions."""
        regressions: List[Dict[str, Any]] = []
        latest: Dict[str, BenchmarkResult] = {}
        for r in reversed(self._results):
            if r.name not in latest:
                latest[r.name] = r

        for name, result in latest.items():
            if name in self._baselines:
                baseline = self._baselines[name]
                if result.has_regression(baseline, self.regression_threshold):
                    degradation = (
                        (result.mean_ms - baseline.mean_ms) / baseline.mean_ms * 100
                    )
                    regressions.append({
                        "benchmark": name,
                        "baseline_ms": round(baseline.mean_ms, 3),
                        "current_ms": round(result.mean_ms, 3),
                        "degradation_pct": round(degradation, 1),
                    })
        return regressions

    def clear_results(self) -> None:
        """Clear all recorded results."""
        self._results.clear()

    def get_benchmark_names(self) -> List[str]:
        """Return names of all registered benchmarks."""
        return list(self._benchmarks.keys())
