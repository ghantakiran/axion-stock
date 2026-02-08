"""PRD-113: ML Model Registry & Deployment Pipeline Dashboard."""

import streamlit as st
from datetime import datetime, timedelta, timezone

from src.model_registry import (
    ModelStage,
    ModelFramework,
    ExperimentStatus,
    ModelRegistryConfig,
    ModelVersion,
    ModelRegistry,
    StageTransition,
    ModelVersionManager,
    ABExperiment,
    ABTestManager,
    ExperimentRun,
    ExperimentTracker,
    ModelServer,
)


def _build_sample_data():
    """Build sample registry, experiments, and A/B test data."""
    config = ModelRegistryConfig(require_staging_before_production=False)
    registry = ModelRegistry(config)
    manager = ModelVersionManager(registry, config)

    # Register sample models
    models_data = [
        ("alpha_ranker", "1.0.0", ModelFramework.XGBOOST, {"accuracy": 0.91, "sharpe": 1.8}, {"n_estimators": 200, "max_depth": 6}),
        ("alpha_ranker", "1.1.0", ModelFramework.XGBOOST, {"accuracy": 0.93, "sharpe": 2.1}, {"n_estimators": 300, "max_depth": 8}),
        ("alpha_ranker", "2.0.0", ModelFramework.LIGHTGBM, {"accuracy": 0.95, "sharpe": 2.4}, {"num_leaves": 31, "learning_rate": 0.05}),
        ("sentiment_scorer", "1.0.0", ModelFramework.PYTORCH, {"accuracy": 0.87, "f1": 0.84}, {"hidden_size": 256, "layers": 3}),
        ("sentiment_scorer", "1.1.0", ModelFramework.PYTORCH, {"accuracy": 0.90, "f1": 0.88}, {"hidden_size": 512, "layers": 4}),
        ("risk_predictor", "1.0.0", ModelFramework.SKLEARN, {"accuracy": 0.88, "auc": 0.92}, {"n_estimators": 100}),
        ("regime_detector", "1.0.0", ModelFramework.CUSTOM, {"accuracy": 0.82, "precision": 0.85}, {"window": 60}),
        ("regime_detector", "1.1.0", ModelFramework.CUSTOM, {"accuracy": 0.86, "precision": 0.89}, {"window": 90}),
    ]

    for name, ver, fw, metrics, hparams in models_data:
        registry.register(name, ver, framework=fw, metrics=metrics, hyperparameters=hparams)

    # Set stages
    manager.promote("alpha_ranker", "1.0.0", ModelStage.ARCHIVED, reason="Superseded")
    manager.promote("alpha_ranker", "1.1.0", ModelStage.STAGING, reason="Testing")
    manager.promote("alpha_ranker", "2.0.0", ModelStage.PRODUCTION, reason="Best accuracy")
    manager.promote("sentiment_scorer", "1.0.0", ModelStage.ARCHIVED)
    manager.promote("sentiment_scorer", "1.1.0", ModelStage.PRODUCTION, reason="Improved F1")
    manager.promote("risk_predictor", "1.0.0", ModelStage.STAGING)
    manager.promote("regime_detector", "1.0.0", ModelStage.STAGING)
    manager.promote("regime_detector", "1.1.0", ModelStage.STAGING)

    # Experiments
    tracker = ExperimentTracker()
    experiments_data = [
        ("hp_search_alpha", "alpha_ranker", {"lr": 0.01, "depth": 6}, {"accuracy": 0.91, "sharpe": 1.8}),
        ("hp_search_alpha", "alpha_ranker", {"lr": 0.005, "depth": 8}, {"accuracy": 0.93, "sharpe": 2.1}),
        ("hp_search_alpha", "alpha_ranker", {"lr": 0.001, "depth": 10}, {"accuracy": 0.90, "sharpe": 1.9}),
        ("finetune_sentiment", "sentiment_scorer", {"lr": 0.0001, "epochs": 10}, {"accuracy": 0.87, "f1": 0.84}),
        ("finetune_sentiment", "sentiment_scorer", {"lr": 0.00005, "epochs": 20}, {"accuracy": 0.90, "f1": 0.88}),
        ("regime_ensemble", "regime_detector", {"n_models": 5}, {"accuracy": 0.86}),
    ]
    for exp_name, model_name, hparams, metrics in experiments_data:
        run = tracker.start_run(exp_name, model_name, hparams)
        for k, v in metrics.items():
            tracker.log_metric(run.run_id, k, v)
        tracker.end_run(run.run_id)

    # A/B tests
    ab_manager = ABTestManager()
    ab1 = ab_manager.create_experiment("Alpha v1.1 vs v2.0", "alpha_ranker", "1.1.0", "2.0.0", 0.2)
    ab_manager.record_metrics(ab1.experiment_id, "1.1.0", {"accuracy": 0.93, "sharpe": 2.1})
    ab_manager.record_metrics(ab1.experiment_id, "2.0.0", {"accuracy": 0.95, "sharpe": 2.4})
    ab_manager.end_experiment(ab1.experiment_id, winner="2.0.0")

    ab2 = ab_manager.create_experiment("Sentiment v1.0 vs v1.1", "sentiment_scorer", "1.0.0", "1.1.0", 0.3)
    ab_manager.record_metrics(ab2.experiment_id, "1.0.0", {"accuracy": 0.87, "f1": 0.84})
    ab_manager.record_metrics(ab2.experiment_id, "1.1.0", {"accuracy": 0.90, "f1": 0.88})

    # Model server
    server = ModelServer(registry)
    server.load_model("alpha_ranker", "2.0.0")
    server.load_model("sentiment_scorer", "1.1.0")
    for _ in range(10):
        server.predict("alpha_ranker", {"features": [1, 2, 3]})
    for _ in range(5):
        server.predict("sentiment_scorer", {"text": "sample"})

    return registry, manager, tracker, ab_manager, server


def render():
    try:
        st.set_page_config(page_title="Model Registry", page_icon="\U0001f9e0", layout="wide")
    except st.errors.StreamlitAPIException:
        pass
    st.title("\U0001f9e0 ML Model Registry & Deployment Pipeline")

    registry, manager, tracker, ab_manager, server = _build_sample_data()

    tabs = st.tabs(["Model Registry", "Experiments", "A/B Tests", "Deployment"])

    # ── Tab 1: Model Registry ────────────────────────────────────────
    with tabs[0]:
        st.subheader("Registered Models")

        model_names = registry.list_models()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Models", len(model_names))

        total_versions = sum(len(registry.list_versions(n)) for n in model_names)
        col2.metric("Total Versions", total_versions)

        prod_count = sum(1 for n in model_names if registry.get_production(n) is not None)
        col3.metric("In Production", prod_count)

        # Model table
        rows = []
        for name in model_names:
            versions = registry.list_versions(name)
            prod = registry.get_production(name)
            latest = registry.get_latest(name)
            rows.append({
                "Model": name,
                "Versions": len(versions),
                "Latest": latest.version if latest else "-",
                "Production": prod.version if prod else "-",
                "Framework": latest.framework.value if latest else "-",
            })
        st.dataframe(rows, use_container_width=True)

        # Version details
        st.subheader("Version Details")
        selected_model = st.selectbox("Select Model", model_names)
        if selected_model:
            versions = registry.list_versions(selected_model)
            version_rows = []
            for v in versions:
                version_rows.append({
                    "Version": v.version,
                    "Stage": v.stage.value.upper(),
                    "Framework": v.framework.value,
                    "Metrics": str(v.metrics),
                    "Created": v.created_at.strftime("%Y-%m-%d %H:%M"),
                })
            st.dataframe(version_rows, use_container_width=True)

        # Transition history
        st.subheader("Transition History")
        history = manager.get_transition_history(selected_model) if selected_model else []
        if history:
            hist_rows = []
            for t in history:
                hist_rows.append({
                    "Version": t.version,
                    "From": t.from_stage.value,
                    "To": t.to_stage.value,
                    "By": t.transitioned_by,
                    "Reason": t.reason,
                    "At": t.transitioned_at.strftime("%Y-%m-%d %H:%M"),
                })
            st.dataframe(hist_rows, use_container_width=True)
        else:
            st.info("No transitions recorded.")

    # ── Tab 2: Experiments ───────────────────────────────────────────
    with tabs[1]:
        st.subheader("Experiment Tracking")

        all_runs = tracker.list_runs()
        exp_names = sorted(set(r.experiment_name for r in all_runs))

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Experiments", len(exp_names))
        col2.metric("Total Runs", len(all_runs))
        completed = sum(1 for r in all_runs if r.status == ExperimentStatus.COMPLETED)
        col3.metric("Completed Runs", completed)

        for exp_name in exp_names:
            with st.expander(f"Experiment: {exp_name}", expanded=True):
                runs = tracker.list_runs(experiment_name=exp_name)
                run_rows = []
                for r in runs:
                    run_rows.append({
                        "Run ID": r.run_id[:8] + "...",
                        "Model": r.model_name,
                        "Status": r.status.value,
                        "Hyperparameters": str(r.hyperparameters),
                        "Metrics": str(r.metrics),
                    })
                st.dataframe(run_rows, use_container_width=True)

                # Best run
                if runs and runs[0].metrics:
                    first_metric = list(runs[0].metrics.keys())[0]
                    best = tracker.get_best_run(exp_name, first_metric)
                    if best:
                        st.success(
                            f"Best run by {first_metric}: {best.run_id[:8]}... "
                            f"({first_metric}={best.metrics.get(first_metric, 'N/A')})"
                        )

    # ── Tab 3: A/B Tests ─────────────────────────────────────────────
    with tabs[2]:
        st.subheader("A/B Testing")

        experiments = ab_manager.list_experiments()
        col1, col2 = st.columns(2)
        col1.metric("Total A/B Tests", len(experiments))
        running = sum(1 for e in experiments if e.status == ExperimentStatus.RUNNING)
        col2.metric("Running", running)

        for exp in experiments:
            status_icon = "\u2705" if exp.status == ExperimentStatus.COMPLETED else "\u23f3"
            with st.expander(f"{status_icon} {exp.name} ({exp.model_name})", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("Champion", exp.champion_version)
                c2.metric("Challenger", exp.challenger_version)
                c3.metric("Traffic Split", f"{exp.traffic_split:.0%} challenger")

                st.write("**Champion Metrics:**", exp.metrics_champion)
                st.write("**Challenger Metrics:**", exp.metrics_challenger)

                if exp.winner:
                    st.success(f"Winner: version {exp.winner}")
                elif exp.status == ExperimentStatus.RUNNING:
                    st.info("Experiment in progress...")

    # ── Tab 4: Deployment ────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Model Deployment & Serving")

        loaded = server.get_loaded_models()
        st.metric("Loaded Models", len(loaded))

        if loaded:
            serve_rows = []
            for name in loaded:
                stats = server.get_prediction_stats(name)
                prod = registry.get_production(name)
                serve_rows.append({
                    "Model": name,
                    "Version": prod.version if prod else "-",
                    "Predictions": stats["count"],
                    "Avg Latency (ms)": f"{stats['avg_latency_ms']:.3f}",
                    "Status": "Serving",
                })
            st.dataframe(serve_rows, use_container_width=True)
        else:
            st.info("No models currently loaded.")

        # Deployment pipeline status
        st.subheader("Deployment Pipeline")
        pipeline_stages = [
            {"Stage": "Model Training", "Status": "Completed", "Duration": "45 min"},
            {"Stage": "Validation", "Status": "Completed", "Duration": "12 min"},
            {"Stage": "Staging Tests", "Status": "Completed", "Duration": "8 min"},
            {"Stage": "A/B Testing", "Status": "In Progress", "Duration": "2 days"},
            {"Stage": "Production Deploy", "Status": "Pending", "Duration": "-"},
        ]
        st.dataframe(pipeline_stages, use_container_width=True)

        # Registry summary
        st.subheader("Registry Summary")
        model_names = registry.list_models()
        summary_data = []
        for name in model_names:
            versions = registry.list_versions(name)
            stage_counts = {}
            for v in versions:
                stage_counts[v.stage.value] = stage_counts.get(v.stage.value, 0) + 1
            summary_data.append({
                "Model": name,
                "Total Versions": len(versions),
                "Draft": stage_counts.get("draft", 0),
                "Staging": stage_counts.get("staging", 0),
                "Production": stage_counts.get("production", 0),
                "Archived": stage_counts.get("archived", 0),
            })
        st.dataframe(summary_data, use_container_width=True)



render()
