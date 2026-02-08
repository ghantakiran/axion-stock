# PRD-127: Workflow Engine & Approval System

## Overview
General-purpose workflow engine supporting approval workflows, state machines, and automated task pipelines. Enables governance for trade approvals, compliance reviews, and operational processes.

## Goals
1. Configurable state machine engine for arbitrary workflows
2. Approval workflows with multi-level sign-off
3. Task pipeline automation with conditional branching
4. Workflow templates for common trading operations
5. Audit trail for all state transitions

## Components

### 1. Workflow Config (`config.py`)
- WorkflowStatus enum: DRAFT, ACTIVE, PAUSED, COMPLETED, CANCELLED, FAILED
- TaskStatus enum: PENDING, IN_PROGRESS, APPROVED, REJECTED, SKIPPED, TIMED_OUT
- ApprovalLevel enum: SINGLE, DUAL, COMMITTEE, AUTO
- TriggerType enum: MANUAL, SCHEDULED, EVENT, THRESHOLD
- WorkflowConfig dataclass (name, states, transitions, timeout, auto_escalate)

### 2. State Machine (`state_machine.py`)
- State dataclass (name, entry_actions, exit_actions, allowed_transitions)
- Transition dataclass (from_state, to_state, condition, action, requires_approval)
- StateMachine class:
  - add_state(state) -> None
  - add_transition(transition) -> None
  - transition(current, target, context) -> bool
  - get_available_transitions(current) -> list
  - validate_workflow() -> list of errors
  - visualize() -> adjacency representation

### 3. Approval Manager (`approvals.py`)
- ApprovalRequest dataclass (request_id, workflow_id, requester, approvers, level, status)
- ApprovalDecision dataclass (decision_id, request_id, approver, action, reason, timestamp)
- ApprovalManager class:
  - create_request(workflow_id, requester, level) -> ApprovalRequest
  - approve(request_id, approver, reason) -> ApprovalDecision
  - reject(request_id, approver, reason) -> ApprovalDecision
  - escalate(request_id, new_approvers) -> ApprovalRequest
  - check_quorum(request_id) -> bool
  - get_pending_approvals(approver) -> list

### 4. Pipeline Runner (`pipeline.py`)
- PipelineStep dataclass (step_id, name, action, condition, on_failure, timeout)
- PipelineResult dataclass (pipeline_id, steps_completed, steps_failed, duration, outputs)
- PipelineRunner class:
  - create_pipeline(name, steps) -> pipeline_id
  - execute(pipeline_id, context) -> PipelineResult
  - pause(pipeline_id) -> None
  - resume(pipeline_id) -> PipelineResult
  - get_status(pipeline_id) -> dict
  - retry_step(pipeline_id, step_id) -> PipelineResult

### 5. Workflow Templates (`templates.py`)
- WorkflowTemplate dataclass (template_id, name, description, states, transitions, default_config)
- TemplateRegistry class:
  - register_template(template) -> None
  - get_template(name) -> WorkflowTemplate
  - list_templates() -> list
  - create_from_template(name, overrides) -> StateMachine
  - Built-in templates: trade_approval, compliance_review, model_deployment, account_onboarding

## Database Tables
- `workflow_instances`: Workflow instance tracking
- `workflow_transitions`: State transition audit log

## Dashboard (4 tabs)
1. Active Workflows — running workflows, status overview
2. Approvals — pending approvals, decision history
3. Pipelines — pipeline execution status, step details
4. Templates — available templates, workflow designer

## Test Coverage
- State machine transition tests
- Approval workflow lifecycle tests
- Pipeline execution (success/failure/retry)
- Template instantiation tests
- ~85+ tests
