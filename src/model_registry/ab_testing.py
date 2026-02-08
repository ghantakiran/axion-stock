"""PRD-113: ML Model Registry & Deployment Pipeline - A/B Testing."""

from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .config import ExperimentStatus

logger = logging.getLogger(__name__)


@dataclass
class ABExperiment:
    """An A/B test comparing a champion model against a challenger."""

    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    model_name: str = ""
    champion_version: str = ""
    challenger_version: str = ""
    traffic_split: float = 0.1  # fraction of traffic to challenger
    status: ExperimentStatus = ExperimentStatus.RUNNING
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    ended_at: Optional[datetime] = None
    winner: Optional[str] = None
    metrics_champion: Dict[str, float] = field(default_factory=dict)
    metrics_challenger: Dict[str, float] = field(default_factory=dict)


class ABTestManager:
    """Manage A/B experiments between model versions.

    Provides deterministic routing, metric recording, and automated
    evaluation to declare a winner.
    """

    def __init__(self) -> None:
        self._experiments: Dict[str, ABExperiment] = {}
        self._lock = threading.Lock()

    # ── Experiment CRUD ──────────────────────────────────────────────

    def create_experiment(
        self,
        name: str,
        model_name: str,
        champion: str,
        challenger: str,
        traffic_split: float = 0.1,
    ) -> ABExperiment:
        """Create and register a new A/B experiment."""
        if not 0.0 < traffic_split < 1.0:
            raise ValueError("traffic_split must be between 0 and 1 (exclusive).")

        exp = ABExperiment(
            name=name,
            model_name=model_name,
            champion_version=champion,
            challenger_version=challenger,
            traffic_split=traffic_split,
        )

        with self._lock:
            self._experiments[exp.experiment_id] = exp

        logger.info(
            "Created A/B experiment '%s' (%s): champion=%s vs challenger=%s, split=%.1f%%.",
            name,
            exp.experiment_id,
            champion,
            challenger,
            traffic_split * 100,
        )
        return exp

    def get_experiment(self, experiment_id: str) -> Optional[ABExperiment]:
        """Return an experiment by ID."""
        with self._lock:
            return self._experiments.get(experiment_id)

    def list_experiments(
        self,
        model_name: Optional[str] = None,
        status: Optional[ExperimentStatus] = None,
    ) -> List[ABExperiment]:
        """List experiments, optionally filtered by model or status."""
        with self._lock:
            results = list(self._experiments.values())
        if model_name is not None:
            results = [e for e in results if e.model_name == model_name]
        if status is not None:
            results = [e for e in results if e.status == status]
        return results

    # ── Routing ──────────────────────────────────────────────────────

    def route_request(self, experiment_id: str, request_id: str) -> str:
        """Deterministically route a request to champion or challenger.

        Uses a stable hash of the request_id so the same request always
        goes to the same variant.
        """
        exp = self.get_experiment(experiment_id)
        if exp is None:
            raise ValueError(f"Experiment '{experiment_id}' not found.")
        if exp.status != ExperimentStatus.RUNNING:
            # If experiment ended, always return the winner (or champion)
            return exp.winner or exp.champion_version

        # Deterministic routing based on hash
        digest = hashlib.sha256(request_id.encode()).hexdigest()
        hash_value = int(digest, 16) % 1000
        threshold = int(exp.traffic_split * 1000)

        if hash_value < threshold:
            return exp.challenger_version
        return exp.champion_version

    # ── Metrics ──────────────────────────────────────────────────────

    def record_metrics(
        self,
        experiment_id: str,
        version: str,
        metrics: Dict[str, float],
    ) -> None:
        """Record observed metrics for a version within an experiment."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if exp is None:
                raise ValueError(f"Experiment '{experiment_id}' not found.")

            if version == exp.champion_version:
                for k, v in metrics.items():
                    exp.metrics_champion[k] = v
            elif version == exp.challenger_version:
                for k, v in metrics.items():
                    exp.metrics_challenger[k] = v
            else:
                raise ValueError(
                    f"Version '{version}' not part of experiment '{experiment_id}'."
                )

        logger.info(
            "Recorded metrics for experiment '%s', version '%s': %s.",
            experiment_id,
            version,
            metrics,
        )

    # ── Evaluation ───────────────────────────────────────────────────

    def evaluate(
        self,
        experiment_id: str,
        metric_name: str,
        min_improvement: float = 0.0,
    ) -> Optional[str]:
        """Evaluate the experiment and return the winner, if any.

        Returns the winning version string if the challenger beats
        the champion by at least *min_improvement* on the given metric,
        or the champion if champion is better. Returns None if metric
        data is missing for either variant.
        """
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if exp is None:
                raise ValueError(f"Experiment '{experiment_id}' not found.")

            champ_val = exp.metrics_champion.get(metric_name)
            chall_val = exp.metrics_challenger.get(metric_name)

        if champ_val is None or chall_val is None:
            return None

        if chall_val >= champ_val + min_improvement:
            return exp.challenger_version
        return exp.champion_version

    def end_experiment(
        self, experiment_id: str, winner: Optional[str] = None
    ) -> ABExperiment:
        """End an experiment and declare a winner."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if exp is None:
                raise ValueError(f"Experiment '{experiment_id}' not found.")

            exp.status = ExperimentStatus.COMPLETED
            exp.ended_at = datetime.now(timezone.utc)
            exp.winner = winner

        logger.info(
            "Ended experiment '%s' (%s). Winner: %s.",
            exp.name,
            experiment_id,
            winner or "none",
        )
        return exp
