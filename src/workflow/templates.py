"""PRD-127: Workflow Engine & Approval System - Templates."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import ApprovalLevel, WorkflowConfig
from .state_machine import State, StateMachine, Transition


@dataclass
class WorkflowTemplate:
    """A reusable workflow template."""

    template_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    description: str = ""
    states: List[State] = field(default_factory=list)
    transitions: List[Transition] = field(default_factory=list)
    default_config: WorkflowConfig = field(default_factory=WorkflowConfig)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)


class TemplateRegistry:
    """Registry of workflow templates with built-in templates."""

    def __init__(self, load_builtins: bool = True):
        self.templates: Dict[str, WorkflowTemplate] = {}
        if load_builtins:
            self._register_builtins()

    def register_template(self, template: WorkflowTemplate) -> None:
        """Register a template."""
        self.templates[template.name] = template

    def get_template(self, name: str) -> WorkflowTemplate:
        """Retrieve a template by name."""
        tmpl = self.templates.get(name)
        if tmpl is None:
            raise KeyError(f"Unknown template: {name}")
        return tmpl

    def list_templates(self) -> List[WorkflowTemplate]:
        """List all registered templates."""
        return list(self.templates.values())

    def create_from_template(
        self,
        name: str,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> StateMachine:
        """Instantiate a StateMachine from a named template.

        *overrides* can replace state or transition attributes.
        """
        tmpl = self.get_template(name)
        overrides = overrides or {}

        sm = StateMachine(name=overrides.get("machine_name", tmpl.name))

        for state in tmpl.states:
            sm.add_state(State(
                name=state.name,
                entry_actions=list(state.entry_actions),
                exit_actions=list(state.exit_actions),
                allowed_transitions=list(state.allowed_transitions),
                is_terminal=state.is_terminal,
            ))

        for trans in tmpl.transitions:
            sm.add_transition(Transition(
                from_state=trans.from_state,
                to_state=trans.to_state,
                condition=trans.condition,
                action=trans.action,
                requires_approval=trans.requires_approval,
                label=trans.label,
            ))

        return sm

    # ── Built-in templates ────────────────────────────────────────────

    def _register_builtins(self) -> None:
        """Register the four built-in workflow templates."""
        self.register_template(self._trade_approval_template())
        self.register_template(self._compliance_review_template())
        self.register_template(self._model_deployment_template())
        self.register_template(self._account_onboarding_template())

    @staticmethod
    def _trade_approval_template() -> WorkflowTemplate:
        states = [
            State(name="submitted", allowed_transitions=["under_review", "cancelled"]),
            State(name="under_review", allowed_transitions=["approved", "rejected"]),
            State(name="approved", is_terminal=True),
            State(name="rejected", is_terminal=True),
            State(name="cancelled", is_terminal=True),
        ]
        transitions = [
            Transition(from_state="submitted", to_state="under_review", requires_approval=False, label="begin_review"),
            Transition(from_state="submitted", to_state="cancelled", label="cancel"),
            Transition(from_state="under_review", to_state="approved", requires_approval=True, label="approve"),
            Transition(from_state="under_review", to_state="rejected", requires_approval=True, label="reject"),
        ]
        return WorkflowTemplate(
            name="trade_approval",
            description="Standard trade approval workflow with review gate",
            states=states,
            transitions=transitions,
            default_config=WorkflowConfig(
                name="trade_approval",
                approval_level=ApprovalLevel.DUAL,
                timeout_seconds=1800,
                auto_escalate=True,
            ),
            tags=["trade", "approval"],
        )

    @staticmethod
    def _compliance_review_template() -> WorkflowTemplate:
        states = [
            State(name="initiated", allowed_transitions=["pre_check"]),
            State(name="pre_check", allowed_transitions=["review", "flagged"]),
            State(name="review", allowed_transitions=["cleared", "flagged"]),
            State(name="flagged", allowed_transitions=["review", "escalated"]),
            State(name="escalated", allowed_transitions=["cleared", "blocked"]),
            State(name="cleared", is_terminal=True),
            State(name="blocked", is_terminal=True),
        ]
        transitions = [
            Transition(from_state="initiated", to_state="pre_check", label="start_check"),
            Transition(from_state="pre_check", to_state="review", label="pass_precheck"),
            Transition(from_state="pre_check", to_state="flagged", label="flag_precheck"),
            Transition(from_state="review", to_state="cleared", requires_approval=True, label="clear"),
            Transition(from_state="review", to_state="flagged", label="flag"),
            Transition(from_state="flagged", to_state="review", label="review_again"),
            Transition(from_state="flagged", to_state="escalated", label="escalate"),
            Transition(from_state="escalated", to_state="cleared", requires_approval=True, label="clear_escalated"),
            Transition(from_state="escalated", to_state="blocked", requires_approval=True, label="block"),
        ]
        return WorkflowTemplate(
            name="compliance_review",
            description="Compliance review with multi-level escalation",
            states=states,
            transitions=transitions,
            default_config=WorkflowConfig(
                name="compliance_review",
                approval_level=ApprovalLevel.COMMITTEE,
                timeout_seconds=7200,
                auto_escalate=True,
            ),
            tags=["compliance", "review"],
        )

    @staticmethod
    def _model_deployment_template() -> WorkflowTemplate:
        states = [
            State(name="development", allowed_transitions=["testing"]),
            State(name="testing", allowed_transitions=["staging", "development"]),
            State(name="staging", allowed_transitions=["production", "testing"]),
            State(name="production", is_terminal=True),
        ]
        transitions = [
            Transition(from_state="development", to_state="testing", label="submit_for_testing"),
            Transition(from_state="testing", to_state="staging", requires_approval=True, label="promote_staging"),
            Transition(from_state="testing", to_state="development", label="reject_to_dev"),
            Transition(from_state="staging", to_state="production", requires_approval=True, label="deploy"),
            Transition(from_state="staging", to_state="testing", label="reject_to_testing"),
        ]
        return WorkflowTemplate(
            name="model_deployment",
            description="ML model deployment pipeline with staged promotion",
            states=states,
            transitions=transitions,
            default_config=WorkflowConfig(
                name="model_deployment",
                approval_level=ApprovalLevel.DUAL,
                timeout_seconds=86400,
            ),
            tags=["ml", "deployment"],
        )

    @staticmethod
    def _account_onboarding_template() -> WorkflowTemplate:
        states = [
            State(name="application", allowed_transitions=["kyc_check"]),
            State(name="kyc_check", allowed_transitions=["documents", "rejected"]),
            State(name="documents", allowed_transitions=["review", "kyc_check"]),
            State(name="review", allowed_transitions=["approved", "documents"]),
            State(name="approved", is_terminal=True),
            State(name="rejected", is_terminal=True),
        ]
        transitions = [
            Transition(from_state="application", to_state="kyc_check", label="submit_application"),
            Transition(from_state="kyc_check", to_state="documents", label="kyc_passed"),
            Transition(from_state="kyc_check", to_state="rejected", label="kyc_failed"),
            Transition(from_state="documents", to_state="review", label="docs_submitted"),
            Transition(from_state="documents", to_state="kyc_check", label="recheck_kyc"),
            Transition(from_state="review", to_state="approved", requires_approval=True, label="approve_account"),
            Transition(from_state="review", to_state="documents", label="request_more_docs"),
        ]
        return WorkflowTemplate(
            name="account_onboarding",
            description="Account onboarding with KYC and document verification",
            states=states,
            transitions=transitions,
            default_config=WorkflowConfig(
                name="account_onboarding",
                approval_level=ApprovalLevel.SINGLE,
                timeout_seconds=604800,
            ),
            tags=["onboarding", "kyc"],
        )
