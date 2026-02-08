"""PRD-112: Data Pipeline Orchestration Dashboard."""

import time
from datetime import datetime, timedelta

import streamlit as st

from src.pipeline import (
    Pipeline,
    PipelineConfig,
    PipelineEngine,
    PipelineMetrics,
    PipelineMonitor,
    PipelineNode,
    PipelineScheduler,
    PipelineStatus,
    NodeStatus,
    SLAConfig,
    Schedule,
    ScheduleType,
    LineageGraph,
    LineageNode,
    LineageEdge,
    FreshnessCheck,
)

st.set_page_config(page_title="Data Pipeline", page_icon="\U0001f504", layout="wide")


def render():
    st.title("\U0001f504 Data Pipeline Orchestration")

    tabs = st.tabs(["Pipeline Runs", "DAG Viewer", "Data Lineage", "SLA Monitor"])

    # ── Tab 1: Pipeline Runs ─────────────────────────────────────────
    with tabs[0]:
        st.subheader("Pipeline Runs")

        # Build sample pipelines and execute
        monitor = PipelineMonitor()

        def _task():
            time.sleep(0.01)

        def _fail_task():
            raise RuntimeError("sample failure")

        # Create and run a few sample pipelines
        sample_runs = []
        for i in range(5):
            pipe = Pipeline(f"market-data-{i}", f"Market Data Pipeline {i}")
            pipe.add_node(PipelineNode(node_id="fetch", name="Fetch Data", func=_task))
            pipe.add_node(
                PipelineNode(
                    node_id="clean", name="Clean Data", func=_task, dependencies=["fetch"]
                )
            )
            pipe.add_node(
                PipelineNode(
                    node_id="store", name="Store Data", func=_task, dependencies=["clean"]
                )
            )

            engine = PipelineEngine(PipelineConfig(max_parallel_nodes=2))
            run = engine.execute(pipe)
            monitor.record_run(pipe.pipeline_id, run)
            sample_runs.append(run)

        # Failed pipeline
        fail_pipe = Pipeline("sentiment-ingest", "Sentiment Ingest")
        fail_pipe.add_node(
            PipelineNode(node_id="scrape", name="Scrape", func=_fail_task, retries=0)
        )
        fail_engine = PipelineEngine()
        fail_run = fail_engine.execute(fail_pipe)
        monitor.record_run("sentiment-ingest", fail_run)
        sample_runs.append(fail_run)

        # Metrics row
        all_metrics = monitor.get_all_metrics()
        total_runs = sum(m.total_runs for m in all_metrics.values())
        total_success = sum(m.successful_runs for m in all_metrics.values())
        total_failed = sum(m.failed_runs for m in all_metrics.values())
        overall_rate = (total_success / total_runs * 100) if total_runs else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Runs", total_runs)
        col2.metric("Success Rate", f"{overall_rate:.1f}%")
        col3.metric("Failed Runs", total_failed)
        col4.metric("Active Pipelines", len(all_metrics))

        st.markdown("---")
        st.subheader("Recent Runs")
        for run in sample_runs[-10:]:
            status_icon = {
                PipelineStatus.SUCCESS: "OK",
                PipelineStatus.FAILED: "FAIL",
                PipelineStatus.RUNNING: "RUN",
                PipelineStatus.CANCELLED: "CANCEL",
            }.get(run.status, "?")
            duration = ""
            if run.started_at and run.completed_at:
                dur_ms = (run.completed_at - run.started_at).total_seconds() * 1000
                duration = f"{dur_ms:.0f}ms"
            st.text(
                f"[{status_icon}] {run.pipeline_id} | Run: {run.run_id[:8]}... | "
                f"Duration: {duration} | Nodes: {len(run.nodes)}"
            )

    # ── Tab 2: DAG Viewer ────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Pipeline DAG Viewer")

        # Build a sample pipeline for visualization
        demo_pipe = Pipeline("etl-pipeline", "ETL Pipeline", "Sample ETL DAG")
        demo_pipe.add_node(PipelineNode(node_id="source_api", name="API Source"))
        demo_pipe.add_node(PipelineNode(node_id="source_db", name="DB Source"))
        demo_pipe.add_node(
            PipelineNode(
                node_id="join",
                name="Join Data",
                dependencies=["source_api", "source_db"],
            )
        )
        demo_pipe.add_node(
            PipelineNode(
                node_id="transform", name="Transform", dependencies=["join"]
            )
        )
        demo_pipe.add_node(
            PipelineNode(
                node_id="validate", name="Validate", dependencies=["transform"]
            )
        )
        demo_pipe.add_node(
            PipelineNode(
                node_id="load_warehouse",
                name="Load Warehouse",
                dependencies=["validate"],
            )
        )
        demo_pipe.add_node(
            PipelineNode(
                node_id="load_cache",
                name="Load Cache",
                dependencies=["validate"],
            )
        )

        st.markdown("**Pipeline:** `etl-pipeline` — ETL Pipeline")
        st.markdown(f"**Nodes:** {len(demo_pipe.nodes)}")

        # Text-based DAG
        try:
            levels = demo_pipe.get_execution_order()
            st.markdown("**Execution Order (topological levels):**")
            dag_text = ""
            for i, level in enumerate(levels):
                node_names = [demo_pipe.nodes[nid].name for nid in level]
                dag_text += f"Level {i}: {' | '.join(node_names)}\n"
                if i < len(levels) - 1:
                    dag_text += "  " + "  |  " * len(level) + "\n"
                    dag_text += "  v\n"
            st.code(dag_text, language="text")
        except ValueError as e:
            st.error(f"DAG error: {e}")

        st.markdown("---")
        st.subheader("Node Details")
        for nid, node in demo_pipe.nodes.items():
            deps = ", ".join(node.dependencies) if node.dependencies else "None"
            dependents = ", ".join(demo_pipe.get_node_dependents(nid)) or "None"
            st.text(
                f"  [{nid}] {node.name} | Deps: {deps} | Dependents: {dependents} | "
                f"Timeout: {node.timeout_seconds}s | Retries: {node.retries}"
            )

    # ── Tab 3: Data Lineage ──────────────────────────────────────────
    with tabs[2]:
        st.subheader("Data Lineage Graph")

        graph = LineageGraph()
        # Build sample lineage
        graph.add_node(LineageNode("polygon_api", "source", "Polygon API"))
        graph.add_node(LineageNode("yahoo_fin", "source", "Yahoo Finance"))
        graph.add_node(LineageNode("news_feed", "source", "News Feed"))
        graph.add_node(LineageNode("price_clean", "transform", "Price Cleaner"))
        graph.add_node(LineageNode("sentiment_model", "transform", "Sentiment Model"))
        graph.add_node(LineageNode("factor_engine", "transform", "Factor Engine"))
        graph.add_node(LineageNode("signal_db", "sink", "Signal Database"))
        graph.add_node(LineageNode("dashboard", "sink", "Dashboard"))

        graph.add_edge(LineageEdge("polygon_api", "price_clean", "feeds_into"))
        graph.add_edge(LineageEdge("yahoo_fin", "price_clean", "feeds_into"))
        graph.add_edge(LineageEdge("news_feed", "sentiment_model", "feeds_into"))
        graph.add_edge(LineageEdge("price_clean", "factor_engine", "feeds_into"))
        graph.add_edge(LineageEdge("sentiment_model", "factor_engine", "feeds_into"))
        graph.add_edge(LineageEdge("factor_engine", "signal_db", "feeds_into"))
        graph.add_edge(LineageEdge("factor_engine", "dashboard", "feeds_into"))

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Data Sources (Roots):**")
            for r in graph.get_roots():
                st.text(f"  [SOURCE] {r}")
        with col2:
            st.markdown("**Data Sinks (Leaves):**")
            for leaf in graph.get_leaves():
                st.text(f"  [SINK]   {leaf}")

        st.markdown("---")
        st.subheader("Impact Analysis")
        selected = st.selectbox(
            "Select a node to see impact:",
            list(graph._nodes.keys()),
        )
        if selected:
            impact = graph.get_impact(selected)
            lineage = graph.get_lineage(selected)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Downstream impact of `{selected}`:**")
                if impact:
                    for n in impact:
                        st.text(f"  -> {n}")
                else:
                    st.text("  (no downstream nodes)")
            with col2:
                st.markdown(f"**Upstream lineage of `{selected}`:**")
                if lineage:
                    for n in lineage:
                        st.text(f"  <- {n}")
                else:
                    st.text("  (no upstream nodes)")

        st.markdown("---")
        st.subheader("Full Lineage Graph (serialized)")
        st.json(graph.to_dict())

    # ── Tab 4: SLA Monitor ───────────────────────────────────────────
    with tabs[3]:
        st.subheader("SLA Monitor")

        sla_monitor = PipelineMonitor()

        # Simulate some pipelines with SLAs
        pipelines_sla = {
            "market-data": SLAConfig(max_duration_seconds=10, max_failure_rate=0.1),
            "sentiment": SLAConfig(max_duration_seconds=30, max_failure_rate=0.2),
            "factor-calc": SLAConfig(max_duration_seconds=60, max_failure_rate=0.05),
        }

        for pid, sla in pipelines_sla.items():
            sla_monitor.set_sla(pid, sla)

        # Record some sample runs
        now = datetime.utcnow()
        for pid in pipelines_sla:
            for j in range(5):
                status = PipelineStatus.SUCCESS if j < 4 else PipelineStatus.FAILED
                run = type("Run", (), {
                    "status": status,
                    "started_at": now - timedelta(seconds=2),
                    "completed_at": now,
                    "pipeline_id": pid,
                })()
                sla_monitor.record_run(pid, run)

        st.markdown("**SLA Status:**")
        for pid in pipelines_sla:
            result = sla_monitor.check_sla(pid)
            health = sla_monitor.get_health_score(pid)
            metrics = sla_monitor.get_metrics(pid)
            status_str = "PASS" if result.passed else "FAIL"
            st.text(
                f"  [{status_str}] {pid} | Health: {health:.0%} | "
                f"Success: {metrics.success_rate:.0%} | Runs: {metrics.total_runs}"
            )
            if result.violations:
                for v in result.violations:
                    st.text(f"        Violation: {v}")

        st.markdown("---")
        st.subheader("Data Freshness")

        sla_monitor.add_freshness_check("polygon_prices", max_staleness_seconds=300)
        sla_monitor.add_freshness_check("yahoo_quotes", max_staleness_seconds=600)
        sla_monitor.add_freshness_check("news_articles", max_staleness_seconds=1800)
        sla_monitor.add_freshness_check("sec_filings", max_staleness_seconds=86400)

        # Mark some as fresh
        sla_monitor.update_freshness("polygon_prices")
        sla_monitor.update_freshness("yahoo_quotes")
        sla_monitor.update_freshness(
            "news_articles", datetime.utcnow() - timedelta(hours=1)
        )
        # sec_filings never updated -> stale

        stale = sla_monitor.get_stale_sources()
        for name in ["polygon_prices", "yahoo_quotes", "news_articles", "sec_filings"]:
            freshness = "FRESH" if name not in stale else "STALE"
            st.text(f"  [{freshness}] {name}")

        st.markdown("---")
        st.subheader("Health Scores")
        for pid in pipelines_sla:
            score = sla_monitor.get_health_score(pid)
            bar_len = int(score * 20)
            bar = "#" * bar_len + "-" * (20 - bar_len)
            st.text(f"  {pid:20s} [{bar}] {score:.0%}")


render()
