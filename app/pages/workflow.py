"""PRD-127: Workflow Engine & Approval System Dashboard."""

import streamlit as st

from src.workflow import (
    ApprovalLevel,
    ApprovalManager,
    PipelineRunner,
    PipelineStep,
    StateMachine,
    State,
    TaskStatus,
    TemplateRegistry,
    WorkflowConfig,
    WorkflowStatus,
)


def render():
    st.title("Workflow Engine & Approval System")

    tabs = st.tabs(["Active Workflows", "Approvals", "Pipelines", "Templates"])

    # ── Tab 1: Active Workflows ──────────────────────────────────────
    with tabs[0]:
        st.subheader("Active Workflows")

        registry = TemplateRegistry()

        # Create demo workflows from templates
        demos = []
        for tname in ["trade_approval", "compliance_review", "model_deployment"]:
            sm = registry.create_from_template(tname)
            demos.append((tname, sm))

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Workflows", len(demos))
        col2.metric("Templates Available", len(registry.list_templates()))
        col3.metric("Active", len(demos))

        st.markdown("---")
        st.markdown("**Workflow Instances**")

        for name, sm in demos:
            states = list(sm.states.keys())
            current = states[0] if states else "N/A"
            transitions = len(sm.transitions)
            st.markdown(
                f"- **{name}** | Current: `{current}` | "
                f"States: {len(states)} | Transitions: {transitions}"
            )

        # Run a demo workflow
        st.markdown("---")
        st.markdown("**Demo: Trade Approval Flow**")
        sm = registry.create_from_template("trade_approval")
        steps_log = []
        if sm.transition("submitted", "under_review"):
            steps_log.append("submitted -> under_review")
        if sm.transition("under_review", "approved"):
            steps_log.append("under_review -> approved")

        for entry in steps_log:
            st.success(f"Transition: {entry}")

        st.markdown(f"History entries: {len(sm.history)}")

    # ── Tab 2: Approvals ─────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Approval Manager")

        mgr = ApprovalManager()

        # Create sample approval requests
        req1 = mgr.create_request(
            workflow_id="wf_trade_001",
            requester="trader_a",
            level=ApprovalLevel.DUAL,
            approvers=["risk_mgr", "compliance_mgr"],
            title="AAPL 10k share purchase",
        )
        req2 = mgr.create_request(
            workflow_id="wf_trade_002",
            requester="trader_b",
            level=ApprovalLevel.SINGLE,
            approvers=["risk_mgr"],
            title="MSFT position rebalance",
        )
        req3 = mgr.create_request(
            workflow_id="wf_model_001",
            requester="quant_team",
            level=ApprovalLevel.COMMITTEE,
            approvers=["head_risk", "cto", "coo", "head_compliance", "pm_lead"],
            title="Deploy new alpha model v2.3",
        )

        # Approve one
        mgr.approve(req2.request_id, "risk_mgr", "Looks fine")

        col1, col2, col3 = st.columns(3)
        all_reqs = list(mgr.requests.values())
        col1.metric("Total Requests", len(all_reqs))
        col2.metric("Pending", len(mgr.get_pending_approvals()))
        col3.metric(
            "Approved",
            len([r for r in all_reqs if r.status == TaskStatus.APPROVED]),
        )

        st.markdown("---")
        st.markdown("**Pending Approvals**")
        for req in mgr.get_pending_approvals():
            st.warning(
                f"**{req.title}** | Requester: {req.requester} | "
                f"Level: {req.level.value} | Approvers: {', '.join(req.approvers)}"
            )

        st.markdown("**Decision History**")
        for d in mgr.get_decision_history():
            icon = "approved" if d.action == "approve" else "rejected"
            st.info(f"{d.approver} {icon} request {d.request_id[:8]}... | {d.reason}")

    # ── Tab 3: Pipelines ─────────────────────────────────────────────
    with tabs[2]:
        st.subheader("Pipeline Execution")

        runner = PipelineRunner()

        # Build a demo pipeline
        steps = [
            PipelineStep(name="data_validation", action=lambda ctx: "valid"),
            PipelineStep(name="risk_check", action=lambda ctx: "passed"),
            PipelineStep(name="order_generation", action=lambda ctx: "3 orders"),
            PipelineStep(name="execution", action=lambda ctx: "filled"),
        ]
        pid = runner.create_pipeline("trade_execution_pipeline", steps)
        result = runner.execute(pid)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Steps Completed", result.steps_completed)
        col2.metric("Steps Failed", result.steps_failed)
        col3.metric("Steps Skipped", result.steps_skipped)
        col4.metric("Duration (s)", f"{result.duration_seconds:.4f}")

        st.markdown("---")
        status = runner.get_status(pid)
        st.markdown(f"**Pipeline:** {status['name']} | **Status:** {status['status']}")

        st.markdown("**Step Details**")
        for step_info in status["steps"]:
            color = "green" if step_info["status"] == "approved" else "gray"
            st.markdown(
                f"- {step_info['name']}: :{color}[{step_info['status']}]"
            )

        st.markdown("**Outputs**")
        for name, output in result.outputs.items():
            st.text(f"  {name}: {output}")

    # ── Tab 4: Templates ─────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Workflow Templates")

        registry = TemplateRegistry()
        templates = registry.list_templates()

        st.metric("Available Templates", len(templates))
        st.markdown("---")

        for tmpl in templates:
            with st.expander(f"{tmpl.name} (v{tmpl.version})"):
                st.markdown(f"**Description:** {tmpl.description}")
                st.markdown(f"**Tags:** {', '.join(tmpl.tags)}")

                st.markdown("**States:**")
                for s in tmpl.states:
                    terminal_badge = " (terminal)" if s.is_terminal else ""
                    st.markdown(f"  - `{s.name}`{terminal_badge}")

                st.markdown("**Transitions:**")
                for t in tmpl.transitions:
                    approval_badge = " [requires approval]" if t.requires_approval else ""
                    st.markdown(f"  - {t.from_state} -> {t.to_state}{approval_badge}")

                # Visualize adjacency
                sm = registry.create_from_template(tmpl.name)
                viz = sm.visualize()
                st.markdown("**Adjacency Graph:**")
                for src, targets in viz.items():
                    if targets:
                        st.text(f"  {src} -> {', '.join(targets)}")
                    else:
                        st.text(f"  {src} (no outgoing)")

                st.markdown(f"**Default Config:** timeout={tmpl.default_config.timeout_seconds}s, "
                            f"approval={tmpl.default_config.approval_level.value}")



render()
