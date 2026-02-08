"""PRD-127: Workflow Engine & Approval System - State Machine."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


@dataclass
class State:
    """A single state in the workflow state machine."""

    name: str
    entry_actions: List[Callable] = field(default_factory=list)
    exit_actions: List[Callable] = field(default_factory=list)
    allowed_transitions: List[str] = field(default_factory=list)
    is_terminal: bool = False


@dataclass
class Transition:
    """A transition between two states."""

    from_state: str
    to_state: str
    condition: Optional[Callable] = None
    action: Optional[Callable] = None
    requires_approval: bool = False
    label: str = ""


@dataclass
class TransitionRecord:
    """Audit record for a state transition."""

    record_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    from_state: str = ""
    to_state: str = ""
    actor: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: Dict[str, Any] = field(default_factory=dict)


class StateMachine:
    """Configurable state machine engine for workflows."""

    def __init__(self, name: str = "default"):
        self.name = name
        self.states: Dict[str, State] = {}
        self.transitions: List[Transition] = []
        self.history: List[TransitionRecord] = []

    def add_state(self, state: State) -> None:
        """Register a state in the machine."""
        self.states[state.name] = state

    def add_transition(self, transition: Transition) -> None:
        """Register a transition between states."""
        self.transitions.append(transition)
        # Also update the source state's allowed_transitions
        if transition.from_state in self.states:
            src = self.states[transition.from_state]
            if transition.to_state not in src.allowed_transitions:
                src.allowed_transitions.append(transition.to_state)

    def transition(self, current: str, target: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Attempt a transition from *current* to *target*.

        Returns True on success, False if the transition is not valid.
        """
        context = context or {}
        matching = [
            t for t in self.transitions
            if t.from_state == current and t.to_state == target
        ]

        if not matching:
            return False

        trans = matching[0]

        # Check condition if present
        if trans.condition and not trans.condition(context):
            return False

        # Execute exit actions of current state
        if current in self.states:
            for action in self.states[current].exit_actions:
                action(context)

        # Execute transition action
        if trans.action:
            trans.action(context)

        # Execute entry actions of target state
        if target in self.states:
            for action in self.states[target].entry_actions:
                action(context)

        # Record in history
        record = TransitionRecord(
            from_state=current,
            to_state=target,
            actor=context.get("actor", "system"),
            context=context,
        )
        self.history.append(record)

        return True

    def get_available_transitions(self, current: str) -> List[Transition]:
        """Return transitions available from *current* state."""
        return [t for t in self.transitions if t.from_state == current]

    def validate_workflow(self) -> List[str]:
        """Validate the workflow definition. Returns a list of error strings."""
        errors: List[str] = []

        if not self.states:
            errors.append("No states defined")
            return errors

        # Check all transition endpoints reference valid states
        for trans in self.transitions:
            if trans.from_state not in self.states:
                errors.append(f"Transition references unknown source state: {trans.from_state}")
            if trans.to_state not in self.states:
                errors.append(f"Transition references unknown target state: {trans.to_state}")

        # Check for at least one terminal state
        terminals = [s for s in self.states.values() if s.is_terminal]
        if not terminals:
            errors.append("No terminal state defined")

        # Check for unreachable states (no incoming transitions except the first state)
        state_names = list(self.states.keys())
        if state_names:
            targets = {t.to_state for t in self.transitions}
            first_state = state_names[0]
            for sname in state_names:
                if sname != first_state and sname not in targets:
                    errors.append(f"State '{sname}' is unreachable")

        return errors

    def visualize(self) -> Dict[str, List[str]]:
        """Return an adjacency-list representation of the state machine."""
        adj: Dict[str, List[str]] = {name: [] for name in self.states}
        for t in self.transitions:
            if t.from_state in adj:
                adj[t.from_state].append(t.to_state)
        return adj
