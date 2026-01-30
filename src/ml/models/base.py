"""Base model interface for ML prediction models."""

import json
import logging
import os
import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Metadata for a trained model."""

    model_name: str = ""
    model_version: str = ""
    trained_at: str = ""
    train_start: str = ""
    train_end: str = ""
    n_train_samples: int = 0
    n_features: int = 0
    feature_names: list[str] = field(default_factory=list)
    hyperparameters: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    status: str = "trained"  # trained, production, deprecated


class BaseModel(ABC):
    """Abstract base class for ML prediction models.

    All models implement the same interface for training,
    prediction, saving, and loading.
    """

    def __init__(self, model_name: str = "base"):
        self.model_name = model_name
        self.model = None
        self.metadata = ModelMetadata(model_name=model_name)
        self._is_fitted = False

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted

    @abstractmethod
    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        **kwargs,
    ) -> dict:
        """Train the model.

        Args:
            X: Feature matrix.
            y: Target variable.
            **kwargs: Additional training parameters.

        Returns:
            Dict of training metrics.
        """
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        """Make predictions.

        Args:
            X: Feature matrix.

        Returns:
            DataFrame with predictions.
        """
        pass

    @abstractmethod
    def get_feature_importance(self) -> pd.Series:
        """Get feature importance scores.

        Returns:
            Series of feature importances indexed by feature name.
        """
        pass

    def save(self, path: str) -> None:
        """Save model to disk.

        Args:
            path: Directory to save model files.
        """
        os.makedirs(path, exist_ok=True)

        # Save model
        model_path = os.path.join(path, "model.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(self.model, f)

        # Save metadata
        meta_path = os.path.join(path, "metadata.json")
        with open(meta_path, "w") as f:
            json.dump({
                "model_name": self.metadata.model_name,
                "model_version": self.metadata.model_version,
                "trained_at": self.metadata.trained_at,
                "train_start": self.metadata.train_start,
                "train_end": self.metadata.train_end,
                "n_train_samples": self.metadata.n_train_samples,
                "n_features": self.metadata.n_features,
                "feature_names": self.metadata.feature_names,
                "hyperparameters": self.metadata.hyperparameters,
                "metrics": self.metadata.metrics,
                "status": self.metadata.status,
            }, f, indent=2)

        logger.info(f"Model saved to {path}")

    def load(self, path: str) -> None:
        """Load model from disk.

        Args:
            path: Directory containing model files.
        """
        # Load model
        model_path = os.path.join(path, "model.pkl")
        with open(model_path, "rb") as f:
            self.model = pickle.load(f)

        # Load metadata
        meta_path = os.path.join(path, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                meta_dict = json.load(f)
            self.metadata = ModelMetadata(**meta_dict)

        self._is_fitted = True
        logger.info(f"Model loaded from {path}")

    def _update_metadata(
        self,
        X: pd.DataFrame,
        metrics: dict,
        train_start: str = "",
        train_end: str = "",
        hyperparameters: Optional[dict] = None,
    ) -> None:
        """Update metadata after training."""
        self.metadata.trained_at = datetime.now().isoformat()
        self.metadata.n_train_samples = len(X)
        self.metadata.n_features = X.shape[1]
        self.metadata.feature_names = list(X.columns)
        self.metadata.metrics = metrics
        self.metadata.train_start = train_start
        self.metadata.train_end = train_end
        if hyperparameters:
            self.metadata.hyperparameters = hyperparameters
