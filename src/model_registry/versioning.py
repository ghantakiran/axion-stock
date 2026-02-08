"""PRD-113: ML Model Registry & Deployment Pipeline - Versioning & Promotion."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from .config import ModelRegistryConfig, ModelStage
from .registry import ModelRegistry

logger = logging.getLogger(__name__)

# Valid stage transitions (from -> set of allowed targets)
_VALID_TRANSITIONS = {
    ModelStage.DRAFT: {ModelStage.STAGING, ModelStage.ARCHIVED},
    ModelStage.STAGING: {ModelStage.PRODUCTION, ModelStage.ARCHIVED, ModelStage.DRAFT},
    ModelStage.PRODUCTION: {ModelStage.ARCHIVED, ModelStage.DEPRECATED},
    ModelStage.ARCHIVED: {ModelStage.STAGING, ModelStage.DRAFT, ModelStage.PRODUCTION},
    ModelStage.DEPRECATED: {ModelStage.ARCHIVED},
}


@dataclass
class StageTransition:
    """Record of a model stage transition."""

    model_name: str
    version: str
    from_stage: ModelStage
    to_stage: ModelStage
    transitioned_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    transitioned_by: str = "system"
    reason: str = ""


class ModelVersionManager:
    """Manages stage transitions, promotion rules, and rollback logic."""

    def __init__(
        self,
        registry: ModelRegistry,
        config: Optional[ModelRegistryConfig] = None,
    ) -> None:
        self._registry = registry
        self._config = config or ModelRegistryConfig()
        self._transitions: List[StageTransition] = []

    # ── Promotion ────────────────────────────────────────────────────

    def promote(
        self,
        name: str,
        version: str,
        to_stage: ModelStage,
        reason: str = "",
        by: str = "system",
    ) -> StageTransition:
        """Promote a model version to a new stage.

        Validates the transition, enforces staging-before-production,
        and auto-archives previous production versions when configured.
        """
        mv = self._registry.get_version(name, version)
        if mv is None:
            raise ValueError(f"Model '{name}' version '{version}' not found.")

        allowed, msg = self.can_promote(name, version, to_stage)
        if not allowed:
            raise ValueError(msg)

        from_stage = mv.stage

        # Auto-archive current production version if promoting to production
        if (
            to_stage == ModelStage.PRODUCTION
            and self._config.auto_archive_on_new_production
        ):
            current_prod = self._registry.get_production(name)
            if current_prod is not None and current_prod.version != version:
                old_stage = current_prod.stage
                current_prod.stage = ModelStage.ARCHIVED
                current_prod.promoted_at = datetime.now(timezone.utc)
                archive_transition = StageTransition(
                    model_name=name,
                    version=current_prod.version,
                    from_stage=old_stage,
                    to_stage=ModelStage.ARCHIVED,
                    transitioned_by=by,
                    reason=f"Auto-archived: new production version '{version}'",
                )
                self._transitions.append(archive_transition)
                logger.info(
                    "Auto-archived model '%s' version '%s'.",
                    name,
                    current_prod.version,
                )

        # Perform the promotion
        mv.stage = to_stage
        mv.promoted_at = datetime.now(timezone.utc)

        transition = StageTransition(
            model_name=name,
            version=version,
            from_stage=from_stage,
            to_stage=to_stage,
            transitioned_by=by,
            reason=reason,
        )
        self._transitions.append(transition)

        logger.info(
            "Promoted model '%s' version '%s': %s -> %s (by %s).",
            name,
            version,
            from_stage.value,
            to_stage.value,
            by,
        )
        return transition

    # ── Rollback ─────────────────────────────────────────────────────

    def rollback(
        self,
        name: str,
        reason: str = "",
        by: str = "system",
    ) -> Optional[StageTransition]:
        """Roll back to the previous production version.

        Finds the most recent *prior* production version in the transition
        history and promotes it back to PRODUCTION.
        """
        # Find all transitions to PRODUCTION for this model, most recent first
        prod_transitions = [
            t
            for t in reversed(self._transitions)
            if t.model_name == name and t.to_stage == ModelStage.PRODUCTION
        ]

        if len(prod_transitions) < 2:
            logger.warning(
                "Cannot rollback model '%s': not enough production history.",
                name,
            )
            return None

        # The most recent is current; the one before is the rollback target
        previous = prod_transitions[1]
        target_version = previous.version

        # The target may have been auto-archived; promote it back
        mv = self._registry.get_version(name, target_version)
        if mv is None:
            logger.error(
                "Rollback target version '%s' no longer exists.", target_version
            )
            return None

        # If the target was archived, re-stage it first so it can go to production
        if mv.stage == ModelStage.ARCHIVED:
            self.promote(
                name,
                target_version,
                ModelStage.STAGING,
                reason=f"Re-staging for rollback to '{target_version}'",
                by=by,
            )

        return self.promote(
            name,
            target_version,
            ModelStage.PRODUCTION,
            reason=reason or f"Rollback to previous production version '{target_version}'",
            by=by,
        )

    # ── Validation ───────────────────────────────────────────────────

    def can_promote(
        self, name: str, version: str, to_stage: ModelStage
    ) -> Tuple[bool, str]:
        """Check whether a promotion is allowed, returning (ok, reason)."""
        mv = self._registry.get_version(name, version)
        if mv is None:
            return False, f"Model '{name}' version '{version}' not found."

        if not self._validate_transition(mv.stage, to_stage):
            return (
                False,
                f"Transition from '{mv.stage.value}' to '{to_stage.value}' "
                f"is not allowed.",
            )

        # Enforce staging-before-production
        if (
            to_stage == ModelStage.PRODUCTION
            and self._config.require_staging_before_production
            and mv.stage != ModelStage.STAGING
        ):
            return (
                False,
                "Model must be in STAGING before promoting to PRODUCTION.",
            )

        # Enforce minimum metrics
        if to_stage == ModelStage.PRODUCTION:
            for metric_key in self._config.min_metrics_for_promotion:
                if metric_key not in mv.metrics:
                    return (
                        False,
                        f"Missing required metric '{metric_key}' for production promotion.",
                    )

        return True, "Promotion allowed."

    def get_transition_history(self, name: str) -> List[StageTransition]:
        """Return all transitions for a model, ordered chronologically."""
        return [t for t in self._transitions if t.model_name == name]

    @staticmethod
    def _validate_transition(from_stage: ModelStage, to_stage: ModelStage) -> bool:
        """Check whether a direct transition is valid."""
        return to_stage in _VALID_TRANSITIONS.get(from_stage, set())
