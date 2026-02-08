"""Tests for PRD-113: ML Model Registry & Deployment Pipeline."""

from datetime import datetime, timezone

import pytest

from src.model_registry.config import (
    ModelStage,
    ModelFramework,
    ExperimentStatus,
    ModelRegistryConfig,
)
from src.model_registry.registry import ModelVersion, ModelRegistry
from src.model_registry.versioning import StageTransition, ModelVersionManager
from src.model_registry.ab_testing import ABExperiment, ABTestManager
from src.model_registry.experiments import ExperimentRun, ExperimentTracker
from src.model_registry.serving import ModelServer


# ── Config Tests ─────────────────────────────────────────────────────


class TestModelRegistryConfig:
    def test_model_stage_enum(self):
        assert ModelStage.DRAFT.value == "draft"
        assert ModelStage.STAGING.value == "staging"
        assert ModelStage.PRODUCTION.value == "production"
        assert ModelStage.ARCHIVED.value == "archived"
        assert ModelStage.DEPRECATED.value == "deprecated"
        assert len(ModelStage) == 5

    def test_model_framework_enum(self):
        assert ModelFramework.XGBOOST.value == "xgboost"
        assert ModelFramework.LIGHTGBM.value == "lightgbm"
        assert ModelFramework.SKLEARN.value == "sklearn"
        assert ModelFramework.PYTORCH.value == "pytorch"
        assert ModelFramework.TENSORFLOW.value == "tensorflow"
        assert ModelFramework.CUSTOM.value == "custom"
        assert len(ModelFramework) == 6

    def test_experiment_status_enum(self):
        assert ExperimentStatus.RUNNING.value == "running"
        assert ExperimentStatus.COMPLETED.value == "completed"
        assert ExperimentStatus.FAILED.value == "failed"
        assert ExperimentStatus.CANCELLED.value == "cancelled"
        assert len(ExperimentStatus) == 4

    def test_default_config(self):
        cfg = ModelRegistryConfig()
        assert cfg.storage_path == "models/"
        assert cfg.max_versions_per_model == 50
        assert cfg.auto_archive_on_new_production is True
        assert cfg.require_staging_before_production is True
        assert cfg.min_metrics_for_promotion == ["accuracy"]

    def test_custom_config(self):
        cfg = ModelRegistryConfig(
            storage_path="/tmp/models",
            max_versions_per_model=10,
            auto_archive_on_new_production=False,
            require_staging_before_production=False,
            min_metrics_for_promotion=["rmse", "r2"],
        )
        assert cfg.storage_path == "/tmp/models"
        assert cfg.max_versions_per_model == 10
        assert cfg.auto_archive_on_new_production is False
        assert cfg.min_metrics_for_promotion == ["rmse", "r2"]


# ── Registry Tests ───────────────────────────────────────────────────


class TestModelRegistry:
    def setup_method(self):
        self.registry = ModelRegistry()

    def test_register_model(self):
        mv = self.registry.register(
            "alpha_model",
            "1.0.0",
            framework=ModelFramework.XGBOOST,
            metrics={"accuracy": 0.92},
            hyperparameters={"n_estimators": 100},
            description="First version",
        )
        assert mv.model_name == "alpha_model"
        assert mv.version == "1.0.0"
        assert mv.framework == ModelFramework.XGBOOST
        assert mv.stage == ModelStage.DRAFT
        assert mv.metrics["accuracy"] == 0.92
        assert mv.hyperparameters["n_estimators"] == 100

    def test_register_duplicate_version_raises(self):
        self.registry.register("m1", "1.0.0")
        with pytest.raises(ValueError, match="already registered"):
            self.registry.register("m1", "1.0.0")

    def test_get_version(self):
        self.registry.register("m1", "1.0.0")
        self.registry.register("m1", "2.0.0")
        mv = self.registry.get_version("m1", "1.0.0")
        assert mv is not None
        assert mv.version == "1.0.0"

    def test_get_version_not_found(self):
        result = self.registry.get_version("nonexistent", "1.0.0")
        assert result is None

    def test_get_latest(self):
        self.registry.register("m1", "1.0.0")
        self.registry.register("m1", "2.0.0")
        latest = self.registry.get_latest("m1")
        assert latest is not None
        assert latest.version == "2.0.0"

    def test_get_latest_empty(self):
        assert self.registry.get_latest("nonexistent") is None

    def test_get_production(self):
        self.registry.register("m1", "1.0.0")
        self.registry.register("m1", "2.0.0")
        # Manually set stage for test
        mv = self.registry.get_version("m1", "2.0.0")
        mv.stage = ModelStage.PRODUCTION
        mv.promoted_at = datetime.now(timezone.utc)

        prod = self.registry.get_production("m1")
        assert prod is not None
        assert prod.version == "2.0.0"

    def test_get_production_none(self):
        self.registry.register("m1", "1.0.0")
        assert self.registry.get_production("m1") is None

    def test_list_models(self):
        self.registry.register("alpha", "1.0.0")
        self.registry.register("beta", "1.0.0")
        self.registry.register("gamma", "1.0.0")
        models = self.registry.list_models()
        assert set(models) == {"alpha", "beta", "gamma"}

    def test_list_versions(self):
        self.registry.register("m1", "1.0.0")
        self.registry.register("m1", "2.0.0")
        self.registry.register("m1", "3.0.0")
        versions = self.registry.list_versions("m1")
        assert len(versions) == 3

    def test_list_versions_with_stage_filter(self):
        self.registry.register("m1", "1.0.0")
        self.registry.register("m1", "2.0.0")
        mv = self.registry.get_version("m1", "2.0.0")
        mv.stage = ModelStage.STAGING
        versions = self.registry.list_versions("m1", stage=ModelStage.STAGING)
        assert len(versions) == 1
        assert versions[0].version == "2.0.0"

    def test_delete_version(self):
        self.registry.register("m1", "1.0.0")
        self.registry.register("m1", "2.0.0")
        result = self.registry.delete_version("m1", "1.0.0")
        assert result is True
        assert self.registry.get_version("m1", "1.0.0") is None
        assert len(self.registry.list_versions("m1")) == 1

    def test_delete_version_not_found(self):
        assert self.registry.delete_version("m1", "999") is False

    def test_delete_last_version_removes_model(self):
        self.registry.register("m1", "1.0.0")
        self.registry.delete_version("m1", "1.0.0")
        assert "m1" not in self.registry.list_models()

    def test_search_by_name_pattern(self):
        self.registry.register("alpha_model", "1.0.0")
        self.registry.register("beta_model", "1.0.0")
        self.registry.register("alpha_v2", "1.0.0")
        results = self.registry.search(name_pattern="alpha")
        assert len(results) == 2

    def test_search_by_framework(self):
        self.registry.register("m1", "1.0.0", framework=ModelFramework.XGBOOST)
        self.registry.register("m2", "1.0.0", framework=ModelFramework.LIGHTGBM)
        results = self.registry.search(framework=ModelFramework.XGBOOST)
        assert len(results) == 1
        assert results[0].model_name == "m1"

    def test_search_by_min_metric(self):
        self.registry.register("m1", "1.0.0", metrics={"accuracy": 0.9})
        self.registry.register("m1", "2.0.0", metrics={"accuracy": 0.95})
        self.registry.register("m2", "1.0.0", metrics={"accuracy": 0.8})
        results = self.registry.search(min_metric=0.91, metric_name="accuracy")
        assert len(results) == 1
        assert results[0].version == "2.0.0"

    def test_search_by_stage(self):
        self.registry.register("m1", "1.0.0")
        self.registry.register("m1", "2.0.0")
        mv = self.registry.get_version("m1", "2.0.0")
        mv.stage = ModelStage.STAGING
        results = self.registry.search(stage=ModelStage.STAGING)
        assert len(results) == 1

    def test_model_version_defaults(self):
        mv = ModelVersion(model_name="test", version="1.0")
        assert mv.stage == ModelStage.DRAFT
        assert mv.framework == ModelFramework.CUSTOM
        assert mv.metrics == {}
        assert mv.created_by == "system"
        assert mv.promoted_at is None
        assert isinstance(mv.created_at, datetime)


# ── Versioning Tests ─────────────────────────────────────────────────


class TestModelVersionManager:
    def setup_method(self):
        self.config = ModelRegistryConfig(
            min_metrics_for_promotion=["accuracy"],
        )
        self.registry = ModelRegistry(self.config)
        self.manager = ModelVersionManager(self.registry, self.config)

    def test_promote_draft_to_staging(self):
        self.registry.register("m1", "1.0.0", metrics={"accuracy": 0.9})
        t = self.manager.promote("m1", "1.0.0", ModelStage.STAGING)
        assert t.from_stage == ModelStage.DRAFT
        assert t.to_stage == ModelStage.STAGING
        mv = self.registry.get_version("m1", "1.0.0")
        assert mv.stage == ModelStage.STAGING

    def test_promote_staging_to_production(self):
        self.registry.register("m1", "1.0.0", metrics={"accuracy": 0.9})
        self.manager.promote("m1", "1.0.0", ModelStage.STAGING)
        t = self.manager.promote("m1", "1.0.0", ModelStage.PRODUCTION)
        assert t.to_stage == ModelStage.PRODUCTION
        mv = self.registry.get_version("m1", "1.0.0")
        assert mv.stage == ModelStage.PRODUCTION

    def test_promote_direct_to_production_blocked(self):
        """Cannot skip staging when require_staging_before_production is True."""
        self.registry.register("m1", "1.0.0", metrics={"accuracy": 0.9})
        with pytest.raises(ValueError, match="not allowed"):
            self.manager.promote("m1", "1.0.0", ModelStage.PRODUCTION)

    def test_promote_without_required_metric_blocked(self):
        self.registry.register("m1", "1.0.0", metrics={})
        self.manager.promote("m1", "1.0.0", ModelStage.STAGING)
        with pytest.raises(ValueError, match="Missing required metric"):
            self.manager.promote("m1", "1.0.0", ModelStage.PRODUCTION)

    def test_invalid_transition_blocked(self):
        self.registry.register("m1", "1.0.0")
        with pytest.raises(ValueError, match="not allowed"):
            self.manager.promote("m1", "1.0.0", ModelStage.PRODUCTION)

    def test_promote_nonexistent_raises(self):
        with pytest.raises(ValueError, match="not found"):
            self.manager.promote("ghost", "1.0.0", ModelStage.STAGING)

    def test_auto_archive_previous_production(self):
        self.registry.register("m1", "1.0.0", metrics={"accuracy": 0.9})
        self.registry.register("m1", "2.0.0", metrics={"accuracy": 0.95})

        # Promote v1 to production
        self.manager.promote("m1", "1.0.0", ModelStage.STAGING)
        self.manager.promote("m1", "1.0.0", ModelStage.PRODUCTION)

        # Promote v2 to production -> v1 auto-archived
        self.manager.promote("m1", "2.0.0", ModelStage.STAGING)
        self.manager.promote("m1", "2.0.0", ModelStage.PRODUCTION)

        v1 = self.registry.get_version("m1", "1.0.0")
        assert v1.stage == ModelStage.ARCHIVED
        v2 = self.registry.get_version("m1", "2.0.0")
        assert v2.stage == ModelStage.PRODUCTION

    def test_rollback(self):
        self.registry.register("m1", "1.0.0", metrics={"accuracy": 0.9})
        self.registry.register("m1", "2.0.0", metrics={"accuracy": 0.95})

        # v1 -> staging -> production
        self.manager.promote("m1", "1.0.0", ModelStage.STAGING)
        self.manager.promote("m1", "1.0.0", ModelStage.PRODUCTION)

        # v2 -> staging -> production (v1 auto-archived)
        self.manager.promote("m1", "2.0.0", ModelStage.STAGING)
        self.manager.promote("m1", "2.0.0", ModelStage.PRODUCTION)

        # Rollback -> v1 should become production again
        t = self.manager.rollback("m1", reason="v2 regression")
        assert t is not None
        assert t.version == "1.0.0"
        assert t.to_stage == ModelStage.PRODUCTION

    def test_rollback_insufficient_history(self):
        self.registry.register("m1", "1.0.0", metrics={"accuracy": 0.9})
        self.manager.promote("m1", "1.0.0", ModelStage.STAGING)
        self.manager.promote("m1", "1.0.0", ModelStage.PRODUCTION)
        # Only one production transition; rollback returns None
        result = self.manager.rollback("m1")
        assert result is None

    def test_transition_history(self):
        self.registry.register("m1", "1.0.0", metrics={"accuracy": 0.9})
        self.manager.promote("m1", "1.0.0", ModelStage.STAGING, by="user1")
        self.manager.promote("m1", "1.0.0", ModelStage.PRODUCTION, by="user2")

        history = self.manager.get_transition_history("m1")
        assert len(history) == 2
        assert history[0].transitioned_by == "user1"
        assert history[1].transitioned_by == "user2"

    def test_can_promote_valid(self):
        self.registry.register("m1", "1.0.0", metrics={"accuracy": 0.9})
        ok, reason = self.manager.can_promote("m1", "1.0.0", ModelStage.STAGING)
        assert ok is True
        assert "allowed" in reason.lower()

    def test_can_promote_invalid(self):
        self.registry.register("m1", "1.0.0")
        ok, reason = self.manager.can_promote("m1", "1.0.0", ModelStage.DEPRECATED)
        assert ok is False

    def test_validate_transition_static(self):
        assert ModelVersionManager._validate_transition(ModelStage.DRAFT, ModelStage.STAGING) is True
        assert ModelVersionManager._validate_transition(ModelStage.DRAFT, ModelStage.PRODUCTION) is False
        assert ModelVersionManager._validate_transition(ModelStage.STAGING, ModelStage.PRODUCTION) is True
        assert ModelVersionManager._validate_transition(ModelStage.PRODUCTION, ModelStage.ARCHIVED) is True
        assert ModelVersionManager._validate_transition(ModelStage.PRODUCTION, ModelStage.DRAFT) is False

    def test_stage_transition_dataclass(self):
        t = StageTransition(
            model_name="m1",
            version="1.0",
            from_stage=ModelStage.DRAFT,
            to_stage=ModelStage.STAGING,
            transitioned_by="admin",
            reason="Ready for testing",
        )
        assert t.model_name == "m1"
        assert t.reason == "Ready for testing"
        assert isinstance(t.transitioned_at, datetime)


# ── A/B Testing Tests ───────────────────────────────────────────────


class TestABTestManager:
    def setup_method(self):
        self.manager = ABTestManager()

    def test_create_experiment(self):
        exp = self.manager.create_experiment(
            name="test_ab",
            model_name="m1",
            champion="1.0.0",
            challenger="2.0.0",
            traffic_split=0.2,
        )
        assert exp.name == "test_ab"
        assert exp.champion_version == "1.0.0"
        assert exp.challenger_version == "2.0.0"
        assert exp.traffic_split == 0.2
        assert exp.status == ExperimentStatus.RUNNING

    def test_create_experiment_invalid_split(self):
        with pytest.raises(ValueError, match="traffic_split"):
            self.manager.create_experiment("t", "m", "1", "2", traffic_split=0.0)
        with pytest.raises(ValueError, match="traffic_split"):
            self.manager.create_experiment("t", "m", "1", "2", traffic_split=1.0)

    def test_route_request_deterministic(self):
        exp = self.manager.create_experiment("t", "m", "1.0", "2.0", 0.5)
        # Same request_id should always route to the same version
        result_a = self.manager.route_request(exp.experiment_id, "req_001")
        result_b = self.manager.route_request(exp.experiment_id, "req_001")
        assert result_a == result_b

    def test_route_request_distributes_traffic(self):
        exp = self.manager.create_experiment("t", "m", "1.0", "2.0", 0.5)
        results = set()
        for i in range(100):
            results.add(self.manager.route_request(exp.experiment_id, f"req_{i}"))
        # With 50/50 split and 100 requests, both versions should appear
        assert "1.0" in results
        assert "2.0" in results

    def test_record_metrics(self):
        exp = self.manager.create_experiment("t", "m", "1.0", "2.0")
        self.manager.record_metrics(exp.experiment_id, "1.0", {"accuracy": 0.85})
        self.manager.record_metrics(exp.experiment_id, "2.0", {"accuracy": 0.90})
        fetched = self.manager.get_experiment(exp.experiment_id)
        assert fetched.metrics_champion["accuracy"] == 0.85
        assert fetched.metrics_challenger["accuracy"] == 0.90

    def test_record_metrics_invalid_version(self):
        exp = self.manager.create_experiment("t", "m", "1.0", "2.0")
        with pytest.raises(ValueError, match="not part of experiment"):
            self.manager.record_metrics(exp.experiment_id, "3.0", {"accuracy": 0.5})

    def test_evaluate_challenger_wins(self):
        exp = self.manager.create_experiment("t", "m", "1.0", "2.0")
        self.manager.record_metrics(exp.experiment_id, "1.0", {"accuracy": 0.85})
        self.manager.record_metrics(exp.experiment_id, "2.0", {"accuracy": 0.92})
        winner = self.manager.evaluate(exp.experiment_id, "accuracy", min_improvement=0.05)
        assert winner == "2.0"

    def test_evaluate_champion_wins(self):
        exp = self.manager.create_experiment("t", "m", "1.0", "2.0")
        self.manager.record_metrics(exp.experiment_id, "1.0", {"accuracy": 0.90})
        self.manager.record_metrics(exp.experiment_id, "2.0", {"accuracy": 0.88})
        winner = self.manager.evaluate(exp.experiment_id, "accuracy")
        assert winner == "1.0"

    def test_evaluate_missing_metrics(self):
        exp = self.manager.create_experiment("t", "m", "1.0", "2.0")
        result = self.manager.evaluate(exp.experiment_id, "accuracy")
        assert result is None

    def test_end_experiment(self):
        exp = self.manager.create_experiment("t", "m", "1.0", "2.0")
        ended = self.manager.end_experiment(exp.experiment_id, winner="2.0")
        assert ended.status == ExperimentStatus.COMPLETED
        assert ended.winner == "2.0"
        assert ended.ended_at is not None

    def test_list_experiments_filter(self):
        self.manager.create_experiment("t1", "m1", "1.0", "2.0")
        self.manager.create_experiment("t2", "m2", "1.0", "2.0")
        self.manager.create_experiment("t3", "m1", "3.0", "4.0")
        results = self.manager.list_experiments(model_name="m1")
        assert len(results) == 2

    def test_get_experiment(self):
        exp = self.manager.create_experiment("t", "m", "1.0", "2.0")
        fetched = self.manager.get_experiment(exp.experiment_id)
        assert fetched is not None
        assert fetched.name == "t"

    def test_get_experiment_not_found(self):
        assert self.manager.get_experiment("nonexistent") is None

    def test_ab_experiment_defaults(self):
        exp = ABExperiment()
        assert exp.traffic_split == 0.1
        assert exp.status == ExperimentStatus.RUNNING
        assert exp.winner is None
        assert exp.ended_at is None


# ── Experiment Tracker Tests ─────────────────────────────────────────


class TestExperimentTracker:
    def setup_method(self):
        self.tracker = ExperimentTracker()

    def test_start_run(self):
        run = self.tracker.start_run(
            "exp1", "m1", hyperparameters={"lr": 0.01}
        )
        assert run.experiment_name == "exp1"
        assert run.model_name == "m1"
        assert run.status == ExperimentStatus.RUNNING
        assert run.hyperparameters["lr"] == 0.01

    def test_end_run(self):
        run = self.tracker.start_run("exp1", "m1")
        ended = self.tracker.end_run(run.run_id)
        assert ended.status == ExperimentStatus.COMPLETED
        assert ended.completed_at is not None

    def test_end_run_with_status(self):
        run = self.tracker.start_run("exp1", "m1")
        ended = self.tracker.end_run(run.run_id, status=ExperimentStatus.FAILED)
        assert ended.status == ExperimentStatus.FAILED

    def test_end_run_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            self.tracker.end_run("nonexistent")

    def test_log_metric(self):
        run = self.tracker.start_run("exp1", "m1")
        self.tracker.log_metric(run.run_id, "accuracy", 0.95)
        self.tracker.log_metric(run.run_id, "loss", 0.05)
        fetched = self.tracker.get_run(run.run_id)
        assert fetched.metrics["accuracy"] == 0.95
        assert fetched.metrics["loss"] == 0.05

    def test_log_metric_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            self.tracker.log_metric("nonexistent", "acc", 0.5)

    def test_log_artifact(self):
        run = self.tracker.start_run("exp1", "m1")
        self.tracker.log_artifact(run.run_id, "/path/to/model.pkl")
        self.tracker.log_artifact(run.run_id, "/path/to/report.html")
        fetched = self.tracker.get_run(run.run_id)
        assert len(fetched.artifacts) == 2
        assert "/path/to/model.pkl" in fetched.artifacts

    def test_log_artifact_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            self.tracker.log_artifact("nonexistent", "/path")

    def test_get_run(self):
        run = self.tracker.start_run("exp1", "m1")
        fetched = self.tracker.get_run(run.run_id)
        assert fetched is not None
        assert fetched.run_id == run.run_id

    def test_get_run_not_found(self):
        assert self.tracker.get_run("nonexistent") is None

    def test_list_runs(self):
        self.tracker.start_run("exp1", "m1")
        self.tracker.start_run("exp1", "m2")
        self.tracker.start_run("exp2", "m1")
        all_runs = self.tracker.list_runs()
        assert len(all_runs) == 3

    def test_list_runs_filter_experiment(self):
        self.tracker.start_run("exp1", "m1")
        self.tracker.start_run("exp2", "m1")
        runs = self.tracker.list_runs(experiment_name="exp1")
        assert len(runs) == 1

    def test_list_runs_filter_model(self):
        self.tracker.start_run("exp1", "m1")
        self.tracker.start_run("exp1", "m2")
        runs = self.tracker.list_runs(model_name="m2")
        assert len(runs) == 1

    def test_get_best_run(self):
        r1 = self.tracker.start_run("exp1", "m1")
        self.tracker.log_metric(r1.run_id, "accuracy", 0.85)
        self.tracker.end_run(r1.run_id)

        r2 = self.tracker.start_run("exp1", "m1")
        self.tracker.log_metric(r2.run_id, "accuracy", 0.92)
        self.tracker.end_run(r2.run_id)

        r3 = self.tracker.start_run("exp1", "m1")
        self.tracker.log_metric(r3.run_id, "accuracy", 0.88)
        self.tracker.end_run(r3.run_id)

        best = self.tracker.get_best_run("exp1", "accuracy")
        assert best is not None
        assert best.run_id == r2.run_id

    def test_get_best_run_lower_is_better(self):
        r1 = self.tracker.start_run("exp1", "m1")
        self.tracker.log_metric(r1.run_id, "loss", 0.15)
        self.tracker.end_run(r1.run_id)

        r2 = self.tracker.start_run("exp1", "m1")
        self.tracker.log_metric(r2.run_id, "loss", 0.05)
        self.tracker.end_run(r2.run_id)

        best = self.tracker.get_best_run("exp1", "loss", higher_is_better=False)
        assert best is not None
        assert best.run_id == r2.run_id

    def test_get_best_run_no_completed(self):
        r1 = self.tracker.start_run("exp1", "m1")
        self.tracker.log_metric(r1.run_id, "accuracy", 0.9)
        # Not ended -> still RUNNING, should not be returned
        best = self.tracker.get_best_run("exp1", "accuracy")
        assert best is None

    def test_compare_runs(self):
        r1 = self.tracker.start_run("exp1", "m1")
        self.tracker.log_metric(r1.run_id, "accuracy", 0.85)
        self.tracker.log_metric(r1.run_id, "f1", 0.80)

        r2 = self.tracker.start_run("exp1", "m1")
        self.tracker.log_metric(r2.run_id, "accuracy", 0.92)
        self.tracker.log_metric(r2.run_id, "f1", 0.88)

        comparison = self.tracker.compare_runs([r1.run_id, r2.run_id])
        assert len(comparison["runs"]) == 2
        assert "accuracy" in comparison["metrics"]
        assert comparison["metrics"]["accuracy"][r1.run_id] == 0.85
        assert comparison["metrics"]["accuracy"][r2.run_id] == 0.92

    def test_compare_runs_empty(self):
        comparison = self.tracker.compare_runs(["nonexistent"])
        assert len(comparison["runs"]) == 0

    def test_experiment_run_defaults(self):
        run = ExperimentRun()
        assert run.status == ExperimentStatus.RUNNING
        assert run.metrics == {}
        assert run.artifacts == []
        assert run.notes == ""
        assert run.completed_at is None


# ── Model Server Tests ───────────────────────────────────────────────


class TestModelServer:
    def setup_method(self):
        self.registry = ModelRegistry()
        self.server = ModelServer(self.registry)

    def test_load_model(self):
        self.registry.register("m1", "1.0.0")
        result = self.server.load_model("m1", "1.0.0")
        assert result is True
        assert self.server.is_loaded("m1")

    def test_load_model_latest(self):
        self.registry.register("m1", "1.0.0")
        self.registry.register("m1", "2.0.0")
        result = self.server.load_model("m1")
        assert result is True
        assert self.server.is_loaded("m1")

    def test_load_model_not_found(self):
        result = self.server.load_model("nonexistent", "1.0.0")
        assert result is False

    def test_unload_model(self):
        self.registry.register("m1", "1.0.0")
        self.server.load_model("m1", "1.0.0")
        result = self.server.unload_model("m1")
        assert result is True
        assert not self.server.is_loaded("m1")

    def test_unload_model_not_loaded(self):
        result = self.server.unload_model("nonexistent")
        assert result is False

    def test_predict(self):
        self.registry.register("m1", "1.0.0")
        self.server.load_model("m1", "1.0.0")
        result = self.server.predict("m1", {"feature1": 1.0})
        assert "prediction" in result
        assert "confidence" in result
        assert "latency_ms" in result
        assert result["model_name"] == "m1"
        assert result["version"] == "1.0.0"

    def test_predict_not_loaded(self):
        with pytest.raises(ValueError, match="not loaded"):
            self.server.predict("m1", {"feature1": 1.0})

    def test_get_loaded_models(self):
        self.registry.register("m1", "1.0.0")
        self.registry.register("m2", "1.0.0")
        self.server.load_model("m1", "1.0.0")
        self.server.load_model("m2", "1.0.0")
        loaded = self.server.get_loaded_models()
        assert set(loaded) == {"m1", "m2"}

    def test_is_loaded(self):
        self.registry.register("m1", "1.0.0")
        assert self.server.is_loaded("m1") is False
        self.server.load_model("m1", "1.0.0")
        assert self.server.is_loaded("m1") is True

    def test_prediction_stats(self):
        self.registry.register("m1", "1.0.0")
        self.server.load_model("m1", "1.0.0")
        # Run several predictions
        for _ in range(5):
            self.server.predict("m1", {"x": 1})
        stats = self.server.get_prediction_stats("m1")
        assert stats["count"] == 5
        assert stats["avg_latency_ms"] >= 0

    def test_prediction_stats_no_model(self):
        stats = self.server.get_prediction_stats("nonexistent")
        assert stats["count"] == 0
        assert stats["avg_latency_ms"] == 0.0
