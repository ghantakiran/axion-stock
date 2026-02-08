"""PRD-113: ML Model Registry & Deployment Pipeline - Model Serving."""

from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .registry import ModelRegistry

logger = logging.getLogger(__name__)


@dataclass
class _PredictionStats:
    """Internal tracker for per-model prediction statistics."""

    count: int = 0
    total_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        if self.count == 0:
            return 0.0
        return self.total_latency_ms / self.count


class ModelServer:
    """Simulated model serving layer.

    Loads model versions from the registry, caches them in memory,
    serves predictions, and tracks per-model latency stats.
    """

    def __init__(self, registry: ModelRegistry) -> None:
        self._registry = registry
        self._loaded_models: Dict[str, Dict[str, Any]] = {}
        self._stats: Dict[str, _PredictionStats] = {}
        self._lock = threading.Lock()

    # ── Loading ──────────────────────────────────────────────────────

    def load_model(
        self, name: str, version: Optional[str] = None
    ) -> bool:
        """Load a model from the registry into the serving cache.

        If *version* is None, the latest version is loaded.
        Returns True on success, False if the model version is not found.
        """
        if version:
            mv = self._registry.get_version(name, version)
        else:
            mv = self._registry.get_latest(name)

        if mv is None:
            logger.warning(
                "Cannot load model '%s' version '%s': not found.",
                name,
                version,
            )
            return False

        with self._lock:
            self._loaded_models[name] = {
                "model_name": mv.model_name,
                "version": mv.version,
                "framework": mv.framework.value,
                "artifact_path": mv.artifact_path,
                "loaded_at": time.time(),
            }
            if name not in self._stats:
                self._stats[name] = _PredictionStats()

        logger.info(
            "Loaded model '%s' version '%s' (framework=%s).",
            name,
            mv.version,
            mv.framework.value,
        )
        return True

    def unload_model(self, name: str) -> bool:
        """Unload a model from the serving cache."""
        with self._lock:
            if name in self._loaded_models:
                del self._loaded_models[name]
                logger.info("Unloaded model '%s'.", name)
                return True
        return False

    # ── Prediction ───────────────────────────────────────────────────

    def predict(self, name: str, data: Any) -> Dict[str, Any]:
        """Run a prediction through a loaded model (simulated).

        Returns a dict with the prediction result and latency.
        Raises ValueError if the model is not loaded.
        """
        with self._lock:
            model_info = self._loaded_models.get(name)
            if model_info is None:
                raise ValueError(
                    f"Model '{name}' is not loaded. Call load_model first."
                )

        start = time.time()

        # Simulated prediction - produces a deterministic-ish result
        # based on model info and input data
        prediction = {
            "model_name": name,
            "version": model_info["version"],
            "prediction": round(random.random(), 4),
            "confidence": round(random.uniform(0.5, 1.0), 4),
        }

        elapsed_ms = (time.time() - start) * 1000

        with self._lock:
            stats = self._stats.setdefault(name, _PredictionStats())
            stats.count += 1
            stats.total_latency_ms += elapsed_ms

        prediction["latency_ms"] = round(elapsed_ms, 3)
        return prediction

    # ── Introspection ────────────────────────────────────────────────

    def get_loaded_models(self) -> List[str]:
        """Return list of currently loaded model names."""
        with self._lock:
            return list(self._loaded_models.keys())

    def is_loaded(self, name: str) -> bool:
        """Check whether a model is currently loaded."""
        with self._lock:
            return name in self._loaded_models

    def get_prediction_stats(self, name: str) -> Dict[str, Any]:
        """Return prediction statistics for a loaded model."""
        with self._lock:
            stats = self._stats.get(name)
            if stats is None:
                return {"count": 0, "avg_latency_ms": 0.0}
            return {
                "count": stats.count,
                "avg_latency_ms": round(stats.avg_latency_ms, 3),
            }
