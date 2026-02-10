"""Tests for PRD-127: Workflow Engine & Approval System."""

from datetime import datetime, timezone

import pytest

from src.workflow.config import (
    WorkflowStatus,
    TaskStatus,
    ApprovalLevel,
    TriggerType,
    WorkflowConfig,
)
from src.workflow.state_machine import (
    State,
    Transition,
    TransitionRecord,
    StateMachine,
)
from src.workflow.approvals import (
    ApprovalRequest,
    ApprovalDecision,
    ApprovalManager,
)
from src.workflow.pipeline import (
    PipelineStep,
    PipelineResult,
    PipelineRunner,
)
from src.workflow.templates import (
    WorkflowTemplate,
    TemplateRegistry,
)


# ── Enum & Config Tests ──────────────────────────────────────────────


class TestWorkflowEnums:
    def test_workflow_status_values(self):
        assert len(WorkflowStatus) == 6
        assert WorkflowStatus.DRAFT.value == "draft"
        assert WorkflowStatus.ACTIVE.value == "active"
        assert WorkflowStatus.PAUSED.value == "paused"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.CANCELLED.value == "cancelled"
        assert WorkflowStatus.FAILED.value == "failed"

    def test_task_status_values(self):
        assert len(TaskStatus) == 6
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.APPROVED.value == "approved"
        assert TaskStatus.REJECTED.value == "rejected"
        assert TaskStatus.SKIPPED.value == "skipped"
        assert TaskStatus.TIMED_OUT.value == "timed_out"

    def test_approval_level_values(self):
        assert len(ApprovalLevel) == 4
        assert ApprovalLevel.SINGLE.value == "single"
        assert ApprovalLevel.DUAL.value == "dual"
        assert ApprovalLevel.COMMITTEE.value == "committee"
        assert ApprovalLevel.AUTO.value == "auto"

    def test_trigger_type_values(self):
        assert len(TriggerType) == 4
        assert TriggerType.MANUAL.value == "manual"
        assert TriggerType.SCHEDULED.value == "scheduled"
        assert TriggerType.EVENT.value == "event"
        assert TriggerType.THRESHOLD.value == "threshold"


class TestWorkflowConfig:
    def test_default_config(self):
        cfg = WorkflowConfig()
        assert cfg.name == "default_workflow"
        assert cfg.timeout_seconds == 3600
        assert cfg.auto_escalate is False
        assert cfg.max_retries == 3
        assert cfg.trigger_type == TriggerType.MANUAL
        assert cfg.approval_level == ApprovalLevel.SINGLE
        assert cfg.notify_on_transition is True
        assert cfg.require_comment is False

    def test_custom_config(self):
        cfg = WorkflowConfig(
            name="trade_approval",
            states=["start", "review", "done"],
            timeout_seconds=600,
            auto_escalate=True,
            trigger_type=TriggerType.EVENT,
            approval_level=ApprovalLevel.DUAL,
        )
        assert cfg.name == "trade_approval"
        assert len(cfg.states) == 3
        assert cfg.timeout_seconds == 600
        assert cfg.auto_escalate is True
        assert cfg.trigger_type == TriggerType.EVENT
        assert cfg.approval_level == ApprovalLevel.DUAL

    def test_config_defaults_lists(self):
        cfg = WorkflowConfig()
        assert "start" in cfg.states
        assert "end" in cfg.states
        assert isinstance(cfg.transitions, list)


# ── State Machine Tests ──────────────────────────────────────────────


class TestStateMachine:
    def setup_method(self):
        self.sm = StateMachine(name="test_machine")
        self.sm.add_state(State(name="open", allowed_transitions=["in_progress"]))
        self.sm.add_state(State(name="in_progress", allowed_transitions=["closed"]))
        self.sm.add_state(State(name="closed", is_terminal=True))
        self.sm.add_transition(Transition(from_state="open", to_state="in_progress"))
        self.sm.add_transition(Transition(from_state="in_progress", to_state="closed"))

    def test_add_state(self):
        assert "open" in self.sm.states
        assert "in_progress" in self.sm.states
        assert "closed" in self.sm.states

    def test_add_transition(self):
        assert len(self.sm.transitions) == 2

    def test_valid_transition(self):
        result = self.sm.transition("open", "in_progress")
        assert result is True
        assert len(self.sm.history) == 1

    def test_invalid_transition(self):
        result = self.sm.transition("open", "closed")
        assert result is False
        assert len(self.sm.history) == 0

    def test_transition_with_context(self):
        result = self.sm.transition("open", "in_progress", {"actor": "alice"})
        assert result is True
        assert self.sm.history[0].actor == "alice"

    def test_transition_record_fields(self):
        self.sm.transition("open", "in_progress")
        rec = self.sm.history[0]
        assert rec.from_state == "open"
        assert rec.to_state == "in_progress"
        assert isinstance(rec.timestamp, datetime)
        assert len(rec.record_id) == 16

    def test_get_available_transitions(self):
        available = self.sm.get_available_transitions("open")
        assert len(available) == 1
        assert available[0].to_state == "in_progress"

    def test_get_available_transitions_terminal(self):
        available = self.sm.get_available_transitions("closed")
        assert len(available) == 0

    def test_transition_condition_pass(self):
        sm = StateMachine(name="cond_test")
        sm.add_state(State(name="a"))
        sm.add_state(State(name="b", is_terminal=True))
        sm.add_transition(Transition(
            from_state="a", to_state="b",
            condition=lambda ctx: ctx.get("allowed", False),
        ))
        assert sm.transition("a", "b", {"allowed": True}) is True

    def test_transition_condition_fail(self):
        sm = StateMachine(name="cond_test")
        sm.add_state(State(name="a"))
        sm.add_state(State(name="b", is_terminal=True))
        sm.add_transition(Transition(
            from_state="a", to_state="b",
            condition=lambda ctx: ctx.get("allowed", False),
        ))
        assert sm.transition("a", "b", {"allowed": False}) is False

    def test_entry_exit_actions(self):
        log = []
        sm = StateMachine(name="action_test")
        sm.add_state(State(
            name="s1",
            exit_actions=[lambda ctx: log.append("exit_s1")],
        ))
        sm.add_state(State(
            name="s2",
            entry_actions=[lambda ctx: log.append("enter_s2")],
            is_terminal=True,
        ))
        sm.add_transition(Transition(from_state="s1", to_state="s2"))
        sm.transition("s1", "s2")
        assert "exit_s1" in log
        assert "enter_s2" in log

    def test_transition_action(self):
        log = []
        sm = StateMachine(name="trans_action")
        sm.add_state(State(name="a"))
        sm.add_state(State(name="b", is_terminal=True))
        sm.add_transition(Transition(
            from_state="a", to_state="b",
            action=lambda ctx: log.append("trans_fired"),
        ))
        sm.transition("a", "b")
        assert "trans_fired" in log

    def test_validate_workflow_valid(self):
        errors = self.sm.validate_workflow()
        assert len(errors) == 0

    def test_validate_no_states(self):
        sm = StateMachine()
        errors = sm.validate_workflow()
        assert "No states defined" in errors

    def test_validate_no_terminal(self):
        sm = StateMachine()
        sm.add_state(State(name="a"))
        sm.add_state(State(name="b"))
        sm.add_transition(Transition(from_state="a", to_state="b"))
        errors = sm.validate_workflow()
        assert any("terminal" in e.lower() for e in errors)

    def test_validate_unknown_state_in_transition(self):
        sm = StateMachine()
        sm.add_state(State(name="a", is_terminal=True))
        sm.add_transition(Transition(from_state="a", to_state="nonexistent"))
        errors = sm.validate_workflow()
        assert any("nonexistent" in e for e in errors)

    def test_validate_unreachable_state(self):
        sm = StateMachine()
        sm.add_state(State(name="a"))
        sm.add_state(State(name="b", is_terminal=True))
        sm.add_state(State(name="island", is_terminal=True))
        sm.add_transition(Transition(from_state="a", to_state="b"))
        errors = sm.validate_workflow()
        assert any("island" in e.lower() for e in errors)

    def test_visualize(self):
        viz = self.sm.visualize()
        assert "open" in viz
        assert "in_progress" in viz["open"]
        assert "closed" in viz["in_progress"]
        assert viz["closed"] == []

    def test_multiple_transitions_from_state(self):
        self.sm.add_state(State(name="rejected", is_terminal=True))
        self.sm.add_transition(Transition(from_state="in_progress", to_state="rejected"))
        available = self.sm.get_available_transitions("in_progress")
        assert len(available) == 2

    def test_history_accumulates(self):
        self.sm.transition("open", "in_progress")
        self.sm.transition("in_progress", "closed")
        assert len(self.sm.history) == 2
        assert self.sm.history[0].to_state == "in_progress"
        assert self.sm.history[1].to_state == "closed"

    def test_transition_record_dataclass(self):
        rec = TransitionRecord(from_state="a", to_state="b", actor="bob")
        assert rec.from_state == "a"
        assert rec.to_state == "b"
        assert rec.actor == "bob"
        assert len(rec.record_id) == 16

    def test_state_dataclass_defaults(self):
        s = State(name="test")
        assert s.entry_actions == []
        assert s.exit_actions == []
        assert s.allowed_transitions == []
        assert s.is_terminal is False


# ── Approval Manager Tests ───────────────────────────────────────────


class TestApprovalManager:
    def setup_method(self):
        self.mgr = ApprovalManager()

    def test_create_single_approval(self):
        req = self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.SINGLE, approvers=["bob"],
        )
        assert req.status == TaskStatus.PENDING
        assert req.quorum_size == 1
        assert len(req.request_id) == 16

    def test_create_dual_approval(self):
        req = self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.DUAL, approvers=["bob", "carol"],
        )
        assert req.quorum_size == 2

    def test_create_committee_approval(self):
        req = self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.COMMITTEE, approvers=["b", "c", "d", "e", "f"],
        )
        assert req.quorum_size >= 3

    def test_create_auto_approval(self):
        req = self.mgr.create_request(
            workflow_id="wf1", requester="system",
            level=ApprovalLevel.AUTO,
        )
        assert req.status == TaskStatus.APPROVED

    def test_approve_single(self):
        req = self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.SINGLE, approvers=["bob"],
        )
        decision = self.mgr.approve(req.request_id, "bob", "looks good")
        assert decision.action == "approve"
        assert req.status == TaskStatus.APPROVED

    def test_approve_dual_needs_two(self):
        req = self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.DUAL, approvers=["bob", "carol"],
        )
        self.mgr.approve(req.request_id, "bob")
        assert req.status == TaskStatus.IN_PROGRESS  # Not yet met quorum
        self.mgr.approve(req.request_id, "carol")
        assert req.status == TaskStatus.APPROVED

    def test_reject(self):
        req = self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.SINGLE, approvers=["bob"],
        )
        decision = self.mgr.reject(req.request_id, "bob", "not compliant")
        assert decision.action == "reject"
        assert req.status == TaskStatus.REJECTED

    def test_reject_prevents_further_action(self):
        req = self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.SINGLE, approvers=["bob"],
        )
        self.mgr.reject(req.request_id, "bob")
        with pytest.raises(ValueError):
            self.mgr.approve(req.request_id, "carol")

    def test_approve_unknown_request(self):
        with pytest.raises(ValueError):
            self.mgr.approve("nonexistent", "bob")

    def test_reject_unknown_request(self):
        with pytest.raises(ValueError):
            self.mgr.reject("nonexistent", "bob")

    def test_escalate(self):
        req = self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.SINGLE, approvers=["bob"],
        )
        updated = self.mgr.escalate(req.request_id, ["carol", "dave"])
        assert "carol" in updated.approvers
        assert "dave" in updated.approvers
        assert "bob" in updated.approvers

    def test_escalate_no_duplicates(self):
        req = self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.SINGLE, approvers=["bob"],
        )
        self.mgr.escalate(req.request_id, ["bob", "carol"])
        assert req.approvers.count("bob") == 1

    def test_escalate_unknown_request(self):
        with pytest.raises(ValueError):
            self.mgr.escalate("nonexistent", ["carol"])

    def test_check_quorum_auto(self):
        req = self.mgr.create_request(
            workflow_id="wf1", requester="system",
            level=ApprovalLevel.AUTO,
        )
        assert self.mgr.check_quorum(req.request_id) is True

    def test_check_quorum_not_met(self):
        req = self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.DUAL, approvers=["bob", "carol"],
        )
        assert self.mgr.check_quorum(req.request_id) is False

    def test_check_quorum_unknown(self):
        assert self.mgr.check_quorum("nope") is False

    def test_get_pending_approvals(self):
        self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.SINGLE, approvers=["bob"],
        )
        self.mgr.create_request(
            workflow_id="wf2", requester="alice",
            level=ApprovalLevel.SINGLE, approvers=["carol"],
        )
        pending = self.mgr.get_pending_approvals()
        assert len(pending) == 2

    def test_get_pending_approvals_filtered(self):
        self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.SINGLE, approvers=["bob"],
        )
        self.mgr.create_request(
            workflow_id="wf2", requester="alice",
            level=ApprovalLevel.SINGLE, approvers=["carol"],
        )
        assert len(self.mgr.get_pending_approvals("bob")) == 1
        assert len(self.mgr.get_pending_approvals("carol")) == 1

    def test_decision_history(self):
        req = self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.SINGLE, approvers=["bob"],
        )
        self.mgr.approve(req.request_id, "bob")
        history = self.mgr.get_decision_history(req.request_id)
        assert len(history) == 1

    def test_decision_history_all(self):
        r1 = self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.SINGLE, approvers=["bob"],
        )
        r2 = self.mgr.create_request(
            workflow_id="wf2", requester="alice",
            level=ApprovalLevel.SINGLE, approvers=["carol"],
        )
        self.mgr.approve(r1.request_id, "bob")
        self.mgr.reject(r2.request_id, "carol")
        assert len(self.mgr.get_decision_history()) == 2

    def test_approval_decision_dataclass(self):
        d = ApprovalDecision(
            request_id="r1", approver="bob", action="approve", reason="ok",
        )
        assert len(d.decision_id) == 16
        assert isinstance(d.timestamp, datetime)

    def test_approval_request_dataclass(self):
        r = ApprovalRequest(workflow_id="wf1", requester="alice")
        assert len(r.request_id) == 16
        assert r.status == TaskStatus.PENDING
        assert isinstance(r.created_at, datetime)

    def test_create_request_with_context(self):
        req = self.mgr.create_request(
            workflow_id="wf1", requester="alice",
            level=ApprovalLevel.SINGLE,
            context={"trade_id": "T123"},
        )
        assert req.context["trade_id"] == "T123"


# ── Pipeline Tests ───────────────────────────────────────────────────


class TestPipeline:
    def setup_method(self):
        self.runner = PipelineRunner()

    def test_create_pipeline(self):
        steps = [
            PipelineStep(name="step1", action=lambda ctx: "done1"),
            PipelineStep(name="step2", action=lambda ctx: "done2"),
        ]
        pid = self.runner.create_pipeline("test", steps)
        assert len(pid) == 16
        assert pid in self.runner.pipelines

    def test_execute_simple(self):
        steps = [
            PipelineStep(name="s1", action=lambda ctx: 1),
            PipelineStep(name="s2", action=lambda ctx: 2),
        ]
        pid = self.runner.create_pipeline("simple", steps)
        result = self.runner.execute(pid)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps_completed == 2
        assert result.steps_failed == 0
        assert result.outputs["s1"] == 1
        assert result.outputs["s2"] == 2

    def test_execute_with_context(self):
        steps = [
            PipelineStep(name="s1", action=lambda ctx: ctx.get("x", 0) * 2),
        ]
        pid = self.runner.create_pipeline("ctx_test", steps)
        result = self.runner.execute(pid, {"x": 5})
        assert result.outputs["s1"] == 10

    def test_execute_failure_stops(self):
        steps = [
            PipelineStep(name="s1", action=lambda ctx: 1),
            PipelineStep(name="s2", action=lambda ctx: (_ for _ in ()).throw(RuntimeError("boom"))),
            PipelineStep(name="s3", action=lambda ctx: 3),
        ]
        pid = self.runner.create_pipeline("fail_test", steps)
        result = self.runner.execute(pid)
        assert result.status == WorkflowStatus.FAILED
        assert result.steps_completed == 1
        assert result.steps_failed == 1
        assert "boom" in result.error

    def test_execute_skip_on_failure(self):
        steps = [
            PipelineStep(name="s1", action=lambda ctx: 1),
            PipelineStep(
                name="s2",
                action=lambda ctx: (_ for _ in ()).throw(RuntimeError("skip me")),
                on_failure="skip",
            ),
            PipelineStep(name="s3", action=lambda ctx: 3),
        ]
        pid = self.runner.create_pipeline("skip_test", steps)
        result = self.runner.execute(pid)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps_completed == 2
        assert result.steps_skipped == 1

    def test_execute_condition_skip(self):
        steps = [
            PipelineStep(name="s1", action=lambda ctx: 1),
            PipelineStep(
                name="s2",
                action=lambda ctx: 2,
                condition=lambda ctx: ctx.get("run_s2", False),
            ),
            PipelineStep(name="s3", action=lambda ctx: 3),
        ]
        pid = self.runner.create_pipeline("cond_test", steps)
        result = self.runner.execute(pid, {"run_s2": False})
        assert result.steps_completed == 2
        assert result.steps_skipped == 1
        assert "s2" not in result.outputs

    def test_execute_unknown_pipeline(self):
        with pytest.raises(ValueError):
            self.runner.execute("nonexistent")

    def test_get_status(self):
        steps = [
            PipelineStep(name="s1", action=lambda ctx: 1),
        ]
        pid = self.runner.create_pipeline("status_test", steps)
        self.runner.execute(pid)
        status = self.runner.get_status(pid)
        assert status["name"] == "status_test"
        assert status["total_steps"] == 1
        assert status["status"] == "completed"

    def test_get_status_unknown(self):
        with pytest.raises(ValueError):
            self.runner.get_status("nonexistent")

    def test_pause_pipeline(self):
        self.runner.pipelines["p1"] = {
            "name": "test",
            "steps": [],
            "status": WorkflowStatus.ACTIVE,
            "created_at": datetime.now(timezone.utc),
            "current_step_index": 0,
            "context": {},
        }
        self.runner.pause("p1")
        assert self.runner.pipelines["p1"]["status"] == WorkflowStatus.PAUSED

    def test_pause_unknown(self):
        with pytest.raises(ValueError):
            self.runner.pause("nonexistent")

    def test_resume_not_paused(self):
        self.runner.pipelines["p1"] = {
            "name": "test",
            "steps": [],
            "status": WorkflowStatus.ACTIVE,
            "created_at": datetime.now(timezone.utc),
            "current_step_index": 0,
            "context": {},
        }
        with pytest.raises(ValueError):
            self.runner.resume("p1")

    def test_resume_unknown(self):
        with pytest.raises(ValueError):
            self.runner.resume("nonexistent")

    def test_retry_step(self):
        call_count = {"n": 0}

        def flaky(ctx):
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise RuntimeError("transient")
            return "ok"

        step = PipelineStep(name="flaky", action=flaky, on_failure="stop")
        pid = self.runner.create_pipeline("retry_test", [step])
        result1 = self.runner.execute(pid)
        assert result1.status == WorkflowStatus.FAILED

        result2 = self.runner.retry_step(pid, step.step_id)
        assert result2.status == WorkflowStatus.COMPLETED

    def test_retry_step_unknown_pipeline(self):
        with pytest.raises(ValueError):
            self.runner.retry_step("nope", "step1")

    def test_retry_step_unknown_step(self):
        steps = [PipelineStep(name="s1", action=lambda ctx: 1)]
        pid = self.runner.create_pipeline("test", steps)
        with pytest.raises(ValueError):
            self.runner.retry_step(pid, "nonexistent")

    def test_pipeline_result_dataclass(self):
        r = PipelineResult(pipeline_id="p1", steps_completed=3, duration_seconds=1.5)
        assert r.pipeline_id == "p1"
        assert r.steps_completed == 3
        assert r.steps_failed == 0
        assert r.status == WorkflowStatus.COMPLETED

    def test_pipeline_step_dataclass(self):
        s = PipelineStep(name="test_step")
        assert len(s.step_id) == 16
        assert s.status == TaskStatus.PENDING
        assert s.on_failure == "stop"
        assert s.timeout_seconds == 300

    def test_execute_empty_pipeline(self):
        pid = self.runner.create_pipeline("empty", [])
        result = self.runner.execute(pid)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps_completed == 0

    def test_execute_duration_positive(self):
        steps = [PipelineStep(name="s1", action=lambda ctx: 1)]
        pid = self.runner.create_pipeline("dur", steps)
        result = self.runner.execute(pid)
        assert result.duration_seconds >= 0


# ── Template Tests ───────────────────────────────────────────────────


class TestTemplates:
    def setup_method(self):
        self.registry = TemplateRegistry()

    def test_builtin_templates_loaded(self):
        templates = self.registry.list_templates()
        names = {t.name for t in templates}
        assert "trade_approval" in names
        assert "compliance_review" in names
        assert "model_deployment" in names
        assert "account_onboarding" in names

    def test_list_templates_count(self):
        assert len(self.registry.list_templates()) == 4

    def test_get_trade_approval(self):
        tmpl = self.registry.get_template("trade_approval")
        assert tmpl.name == "trade_approval"
        assert len(tmpl.states) == 5
        assert len(tmpl.transitions) == 4
        assert "trade" in tmpl.tags

    def test_get_compliance_review(self):
        tmpl = self.registry.get_template("compliance_review")
        assert tmpl.name == "compliance_review"
        assert len(tmpl.states) == 7
        assert len(tmpl.transitions) == 9

    def test_get_model_deployment(self):
        tmpl = self.registry.get_template("model_deployment")
        assert len(tmpl.states) == 4
        assert len(tmpl.transitions) == 5

    def test_get_account_onboarding(self):
        tmpl = self.registry.get_template("account_onboarding")
        assert len(tmpl.states) == 6
        assert len(tmpl.transitions) == 7

    def test_get_unknown_template(self):
        with pytest.raises(KeyError):
            self.registry.get_template("nonexistent")

    def test_register_custom_template(self):
        custom = WorkflowTemplate(
            name="custom_flow",
            description="A custom workflow",
            states=[State(name="a"), State(name="b", is_terminal=True)],
            transitions=[Transition(from_state="a", to_state="b")],
        )
        self.registry.register_template(custom)
        assert self.registry.get_template("custom_flow").name == "custom_flow"
        assert len(self.registry.list_templates()) == 5

    def test_create_from_trade_approval(self):
        sm = self.registry.create_from_template("trade_approval")
        assert sm.name == "trade_approval"
        assert "submitted" in sm.states
        assert "approved" in sm.states
        errors = sm.validate_workflow()
        assert len(errors) == 0

    def test_create_from_compliance_review(self):
        sm = self.registry.create_from_template("compliance_review")
        assert "initiated" in sm.states
        assert "blocked" in sm.states
        errors = sm.validate_workflow()
        assert len(errors) == 0

    def test_create_from_model_deployment(self):
        sm = self.registry.create_from_template("model_deployment")
        assert "production" in sm.states
        errors = sm.validate_workflow()
        assert len(errors) == 0

    def test_create_from_account_onboarding(self):
        sm = self.registry.create_from_template("account_onboarding")
        assert "application" in sm.states
        errors = sm.validate_workflow()
        assert len(errors) == 0

    def test_create_from_template_with_override(self):
        sm = self.registry.create_from_template(
            "trade_approval", overrides={"machine_name": "my_trade_wf"}
        )
        assert sm.name == "my_trade_wf"

    def test_create_from_unknown_template(self):
        with pytest.raises(KeyError):
            self.registry.create_from_template("nonexistent")

    def test_template_workflow_is_functional(self):
        sm = self.registry.create_from_template("trade_approval")
        assert sm.transition("submitted", "under_review") is True
        assert sm.transition("under_review", "approved") is True
        assert len(sm.history) == 2

    def test_template_dataclass(self):
        tmpl = WorkflowTemplate(name="t1", description="test")
        assert len(tmpl.template_id) == 16
        assert tmpl.version == "1.0"
        assert isinstance(tmpl.created_at, datetime)

    def test_no_builtins_flag(self):
        registry = TemplateRegistry(load_builtins=False)
        assert len(registry.list_templates()) == 0

    def test_visualize_trade_approval(self):
        sm = self.registry.create_from_template("trade_approval")
        viz = sm.visualize()
        assert "under_review" in viz["submitted"]
        assert "cancelled" in viz["submitted"]


# ── Integration Tests ────────────────────────────────────────────────


class TestWorkflowIntegration:
    def test_full_trade_approval_flow(self):
        """End-to-end: create workflow from template, run approval, verify."""
        registry = TemplateRegistry()
        sm = registry.create_from_template("trade_approval")

        mgr = ApprovalManager()

        # Transition submitted -> under_review
        assert sm.transition("submitted", "under_review", {"actor": "system"})

        # Create approval request
        req = mgr.create_request(
            workflow_id="trade_123",
            requester="trader_a",
            level=ApprovalLevel.DUAL,
            approvers=["risk_mgr", "compliance_mgr"],
            title="Large AAPL trade",
        )

        # First approval
        mgr.approve(req.request_id, "risk_mgr", "risk within limits")
        assert req.status == TaskStatus.IN_PROGRESS

        # Second approval - meets quorum
        mgr.approve(req.request_id, "compliance_mgr", "compliant")
        assert req.status == TaskStatus.APPROVED

        # Transition under_review -> approved
        assert sm.transition("under_review", "approved", {"actor": "system"})
        assert len(sm.history) == 2

    def test_pipeline_with_approval_gate(self):
        """Pipeline that pauses for approval mid-flow."""
        mgr = ApprovalManager()
        runner = PipelineRunner()

        def validate_trade(ctx):
            ctx["validated"] = True
            return "validated"

        def execute_trade(ctx):
            return f"executed_{ctx.get('trade_id', 'unknown')}"

        steps = [
            PipelineStep(name="validate", action=validate_trade),
            PipelineStep(name="execute", action=execute_trade),
        ]
        pid = runner.create_pipeline("trade_pipeline", steps)
        result = runner.execute(pid, {"trade_id": "T999"})
        assert result.status == WorkflowStatus.COMPLETED
        assert result.outputs["execute"] == "executed_T999"

    def test_compliance_workflow_with_escalation(self):
        """Compliance review with flag and escalation."""
        registry = TemplateRegistry()
        sm = registry.create_from_template("compliance_review")

        assert sm.transition("initiated", "pre_check")
        assert sm.transition("pre_check", "flagged")
        assert sm.transition("flagged", "escalated")
        assert sm.transition("escalated", "blocked")
        assert len(sm.history) == 4

    def test_model_deployment_rollback(self):
        """Model deployment with rollback to testing."""
        registry = TemplateRegistry()
        sm = registry.create_from_template("model_deployment")

        assert sm.transition("development", "testing")
        assert sm.transition("testing", "staging")
        assert sm.transition("staging", "testing")  # rollback
        assert sm.transition("testing", "staging")
        assert sm.transition("staging", "production")
        assert len(sm.history) == 5
