"""PRD-112: Data Pipeline Orchestration — Execution Engine."""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .config import NodeStatus, PipelineConfig, PipelineStatus
from .definition import Pipeline, PipelineNode, PipelineRun

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing a single pipeline node."""

    node_id: str
    status: NodeStatus = NodeStatus.SUCCESS
    duration_ms: float = 0.0
    error: Optional[str] = None
    retries_used: int = 0


class PipelineEngine:
    """Execute pipelines respecting dependency order and parallelism."""

    def __init__(self, config: Optional[PipelineConfig] = None) -> None:
        self.config = config or PipelineConfig()
        self._runs: Dict[str, PipelineRun] = {}
        self._lock = threading.Lock()

    # ── Public API ───────────────────────────────────────────────────

    def execute(self, pipeline: Pipeline) -> PipelineRun:
        """Execute a full pipeline, returning the completed PipelineRun."""
        errors = pipeline.validate()
        if errors:
            raise ValueError(f"Invalid pipeline: {errors}")

        run = pipeline.create_run()
        run.status = PipelineStatus.RUNNING
        run.started_at = datetime.utcnow()

        with self._lock:
            self._runs[run.run_id] = run

        try:
            levels = pipeline.get_execution_order()
            has_failure = False

            for level in levels:
                if run.status == PipelineStatus.CANCELLED:
                    break

                # Filter out nodes that should be skipped
                runnable: List[str] = []
                for nid in level:
                    if has_failure and self._has_failed_ancestor(nid, run):
                        run.nodes[nid].status = NodeStatus.SKIPPED
                        logger.info("Skipping node '%s' due to upstream failure", nid)
                    else:
                        runnable.append(nid)

                if not runnable:
                    continue

                # Execute runnable nodes in parallel
                results: Dict[str, ExecutionResult] = {}
                max_workers = min(len(runnable), self.config.max_parallel_nodes)

                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    futures = {
                        pool.submit(self._execute_node, run.nodes[nid], run): nid
                        for nid in runnable
                    }
                    for future in futures:
                        nid = futures[future]
                        result = future.result()
                        results[nid] = result

                # Check for failures in this level
                for nid, result in results.items():
                    if result.status == NodeStatus.FAILED:
                        has_failure = True

            # Determine overall status
            if run.status == PipelineStatus.CANCELLED:
                pass  # keep CANCELLED
            elif any(n.status == NodeStatus.FAILED for n in run.nodes.values()):
                run.status = PipelineStatus.FAILED
                failed_ids = [
                    nid for nid, n in run.nodes.items() if n.status == NodeStatus.FAILED
                ]
                run.error = f"Nodes failed: {', '.join(failed_ids)}"
            else:
                run.status = PipelineStatus.SUCCESS

        except Exception as exc:
            run.status = PipelineStatus.FAILED
            run.error = str(exc)
            logger.exception("Pipeline '%s' execution error", pipeline.pipeline_id)

        run.completed_at = datetime.utcnow()
        return run

    def _execute_node(self, node: PipelineNode, run: PipelineRun) -> ExecutionResult:
        """Execute a single node with retries and timeout."""
        node.status = NodeStatus.RUNNING
        start = time.monotonic()
        retries_used = 0
        last_error: Optional[str] = None

        max_attempts = node.retries + 1  # first attempt + retries

        for attempt in range(max_attempts):
            if run.status == PipelineStatus.CANCELLED:
                node.status = NodeStatus.CANCELLED
                elapsed = (time.monotonic() - start) * 1000
                return ExecutionResult(
                    node_id=node.node_id,
                    status=NodeStatus.CANCELLED,
                    duration_ms=elapsed,
                )

            try:
                if node.func is not None:
                    # Run the function with a timeout via a thread pool
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(node.func)
                        future.result(timeout=node.timeout_seconds)

                node.status = NodeStatus.SUCCESS
                elapsed = (time.monotonic() - start) * 1000
                return ExecutionResult(
                    node_id=node.node_id,
                    status=NodeStatus.SUCCESS,
                    duration_ms=elapsed,
                    retries_used=retries_used,
                )

            except FuturesTimeoutError:
                last_error = f"Node '{node.node_id}' timed out after {node.timeout_seconds}s"
                retries_used = attempt
                logger.warning(last_error)

            except Exception as exc:
                last_error = str(exc)
                retries_used = attempt
                logger.warning(
                    "Node '%s' attempt %d failed: %s",
                    node.node_id,
                    attempt + 1,
                    last_error,
                )

            # Exponential backoff before next retry (skip on last attempt)
            if attempt < max_attempts - 1:
                backoff = self.config.retry_backoff_base ** attempt
                # Cap the backoff for testing sanity
                backoff = min(backoff, 30.0)
                time.sleep(backoff * 0.01)  # small sleep for tests

        # All retries exhausted
        node.status = NodeStatus.FAILED
        elapsed = (time.monotonic() - start) * 1000
        return ExecutionResult(
            node_id=node.node_id,
            status=NodeStatus.FAILED,
            duration_ms=elapsed,
            error=last_error,
            retries_used=retries_used,
        )

    # ── Helpers ──────────────────────────────────────────────────────

    def _has_failed_ancestor(self, node_id: str, run: PipelineRun) -> bool:
        """Check whether any dependency of *node_id* has FAILED or SKIPPED status."""
        node = run.nodes.get(node_id)
        if node is None:
            return False
        for dep_id in node.dependencies:
            dep = run.nodes.get(dep_id)
            if dep and dep.status in (NodeStatus.FAILED, NodeStatus.SKIPPED):
                return True
        return False

    def get_run(self, run_id: str) -> Optional[PipelineRun]:
        """Retrieve a specific pipeline run."""
        return self._runs.get(run_id)

    def get_runs(self) -> List[PipelineRun]:
        """Return all tracked pipeline runs."""
        return list(self._runs.values())

    def cancel_run(self, run_id: str) -> bool:
        """Cancel a running pipeline."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return False
            if run.status == PipelineStatus.RUNNING:
                run.status = PipelineStatus.CANCELLED
                logger.info("Cancelled run '%s'", run_id)
                return True
            return False
