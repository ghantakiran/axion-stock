"""PRD-113: ML Model Registry & Deployment Pipeline - Experiment Tracking."""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import ExperimentStatus

logger = logging.getLogger(__name__)


@dataclass
class ExperimentRun:
    """A single experiment run with metrics, artifacts, and status."""

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    experiment_name: str = ""
    model_name: str = ""
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    status: ExperimentStatus = ExperimentStatus.RUNNING
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: Optional[datetime] = None
    notes: str = ""


class ExperimentTracker:
    """Track experiment runs, metrics, artifacts, and comparisons.

    Thread-safe experiment management with support for finding the
    best run and comparing multiple runs side-by-side.
    """

    def __init__(self) -> None:
        self._runs: Dict[str, ExperimentRun] = {}
        self._lock = threading.Lock()

    # ── Run lifecycle ────────────────────────────────────────────────

    def start_run(
        self,
        experiment_name: str,
        model_name: str,
        hyperparameters: Optional[Dict[str, Any]] = None,
    ) -> ExperimentRun:
        """Start a new experiment run."""
        run = ExperimentRun(
            experiment_name=experiment_name,
            model_name=model_name,
            hyperparameters=hyperparameters or {},
        )
        with self._lock:
            self._runs[run.run_id] = run

        logger.info(
            "Started experiment run '%s' for '%s' / '%s'.",
            run.run_id,
            experiment_name,
            model_name,
        )
        return run

    def end_run(
        self,
        run_id: str,
        status: ExperimentStatus = ExperimentStatus.COMPLETED,
    ) -> ExperimentRun:
        """End an experiment run and set its final status."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise ValueError(f"Run '{run_id}' not found.")
            run.status = status
            run.completed_at = datetime.now(timezone.utc)

        logger.info("Ended run '%s' with status '%s'.", run_id, status.value)
        return run

    # ── Logging ──────────────────────────────────────────────────────

    def log_metric(self, run_id: str, name: str, value: float) -> None:
        """Log a metric value for a run."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise ValueError(f"Run '{run_id}' not found.")
            run.metrics[name] = value

        logger.debug("Run '%s': metric '%s' = %s.", run_id, name, value)

    def log_artifact(self, run_id: str, path: str) -> None:
        """Log an artifact path for a run."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise ValueError(f"Run '{run_id}' not found.")
            run.artifacts.append(path)

        logger.debug("Run '%s': artifact '%s'.", run_id, path)

    # ── Lookups ──────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> Optional[ExperimentRun]:
        """Return a run by ID."""
        with self._lock:
            return self._runs.get(run_id)

    def list_runs(
        self,
        experiment_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> List[ExperimentRun]:
        """List runs, optionally filtered by experiment or model name."""
        with self._lock:
            results = list(self._runs.values())
        if experiment_name is not None:
            results = [r for r in results if r.experiment_name == experiment_name]
        if model_name is not None:
            results = [r for r in results if r.model_name == model_name]
        return results

    # ── Analytics ────────────────────────────────────────────────────

    def get_best_run(
        self,
        experiment_name: str,
        metric_name: str,
        higher_is_better: bool = True,
    ) -> Optional[ExperimentRun]:
        """Return the best run for an experiment based on a metric.

        Only considers runs that have the specified metric logged and
        are in a COMPLETED state.
        """
        runs = self.list_runs(experiment_name=experiment_name)
        candidates = [
            r
            for r in runs
            if r.status == ExperimentStatus.COMPLETED
            and metric_name in r.metrics
        ]
        if not candidates:
            return None

        return (
            max(candidates, key=lambda r: r.metrics[metric_name])
            if higher_is_better
            else min(candidates, key=lambda r: r.metrics[metric_name])
        )

    def compare_runs(self, run_ids: List[str]) -> Dict[str, Any]:
        """Compare multiple runs side-by-side.

        Returns a dict with ``runs`` (list of summaries) and ``metrics``
        (metric_name -> {run_id: value}).
        """
        summaries: List[Dict[str, Any]] = []
        all_metrics: Dict[str, Dict[str, float]] = {}

        with self._lock:
            for run_id in run_ids:
                run = self._runs.get(run_id)
                if run is None:
                    continue
                summaries.append(
                    {
                        "run_id": run.run_id,
                        "experiment_name": run.experiment_name,
                        "model_name": run.model_name,
                        "status": run.status.value,
                        "hyperparameters": run.hyperparameters,
                        "metrics": dict(run.metrics),
                    }
                )
                for metric_key, metric_val in run.metrics.items():
                    all_metrics.setdefault(metric_key, {})[run.run_id] = metric_val

        return {"runs": summaries, "metrics": all_metrics}
