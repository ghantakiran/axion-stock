"""PRD-127: Workflow Engine & Approval System - Pipeline Runner."""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .config import WorkflowStatus, TaskStatus


@dataclass
class PipelineStep:
    """A single step in a pipeline."""

    step_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    action: Optional[Callable] = None
    condition: Optional[Callable] = None
    on_failure: str = "stop"  # "stop", "skip", "retry"
    timeout_seconds: int = 300
    retries: int = 0
    max_retries: int = 3
    status: TaskStatus = TaskStatus.PENDING
    output: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class PipelineResult:
    """Result of a pipeline execution."""

    pipeline_id: str = ""
    steps_completed: int = 0
    steps_failed: int = 0
    steps_skipped: int = 0
    duration_seconds: float = 0.0
    outputs: Dict[str, Any] = field(default_factory=dict)
    status: WorkflowStatus = WorkflowStatus.COMPLETED
    error: Optional[str] = None


class PipelineRunner:
    """Executes multi-step pipelines with conditional branching."""

    def __init__(self):
        self.pipelines: Dict[str, Dict[str, Any]] = {}

    def create_pipeline(self, name: str, steps: List[PipelineStep]) -> str:
        """Create a new pipeline. Returns pipeline_id."""
        pipeline_id = uuid.uuid4().hex[:16]
        self.pipelines[pipeline_id] = {
            "name": name,
            "steps": steps,
            "status": WorkflowStatus.DRAFT,
            "created_at": datetime.now(timezone.utc),
            "current_step_index": 0,
            "context": {},
        }
        return pipeline_id

    def execute(self, pipeline_id: str, context: Optional[Dict[str, Any]] = None) -> PipelineResult:
        """Execute all steps in a pipeline sequentially."""
        pipeline = self.pipelines.get(pipeline_id)
        if pipeline is None:
            raise ValueError(f"Unknown pipeline: {pipeline_id}")

        context = context or {}
        pipeline["context"] = context
        pipeline["status"] = WorkflowStatus.ACTIVE

        steps: List[PipelineStep] = pipeline["steps"]
        start_time = time.monotonic()
        completed = 0
        failed = 0
        skipped = 0
        outputs: Dict[str, Any] = {}

        start_index = pipeline.get("current_step_index", 0)

        for i in range(start_index, len(steps)):
            step = steps[i]
            pipeline["current_step_index"] = i

            # Check if pipeline was paused
            if pipeline["status"] == WorkflowStatus.PAUSED:
                break

            # Evaluate condition
            if step.condition and not step.condition(context):
                step.status = TaskStatus.SKIPPED
                skipped += 1
                continue

            # Execute the step
            step.status = TaskStatus.IN_PROGRESS
            step.started_at = datetime.now(timezone.utc)

            try:
                if step.action:
                    result = step.action(context)
                    step.output = result
                    outputs[step.name] = result
                step.status = TaskStatus.APPROVED  # Completed successfully
                step.completed_at = datetime.now(timezone.utc)
                completed += 1
            except Exception as exc:
                step.error = str(exc)
                step.retries += 1

                if step.on_failure == "skip":
                    step.status = TaskStatus.SKIPPED
                    skipped += 1
                    continue
                elif step.on_failure == "retry" and step.retries <= step.max_retries:
                    # Retry once immediately
                    try:
                        if step.action:
                            result = step.action(context)
                            step.output = result
                            outputs[step.name] = result
                        step.status = TaskStatus.APPROVED
                        step.completed_at = datetime.now(timezone.utc)
                        completed += 1
                        continue
                    except Exception:
                        pass

                # Mark failed and stop
                step.status = TaskStatus.REJECTED
                failed += 1
                pipeline["status"] = WorkflowStatus.FAILED
                duration = time.monotonic() - start_time
                return PipelineResult(
                    pipeline_id=pipeline_id,
                    steps_completed=completed,
                    steps_failed=failed,
                    steps_skipped=skipped,
                    duration_seconds=duration,
                    outputs=outputs,
                    status=WorkflowStatus.FAILED,
                    error=step.error,
                )

        duration = time.monotonic() - start_time

        if pipeline["status"] == WorkflowStatus.PAUSED:
            status = WorkflowStatus.PAUSED
        else:
            pipeline["status"] = WorkflowStatus.COMPLETED
            status = WorkflowStatus.COMPLETED

        return PipelineResult(
            pipeline_id=pipeline_id,
            steps_completed=completed,
            steps_failed=failed,
            steps_skipped=skipped,
            duration_seconds=duration,
            outputs=outputs,
            status=status,
        )

    def pause(self, pipeline_id: str) -> None:
        """Pause a running pipeline."""
        pipeline = self.pipelines.get(pipeline_id)
        if pipeline is None:
            raise ValueError(f"Unknown pipeline: {pipeline_id}")
        pipeline["status"] = WorkflowStatus.PAUSED

    def resume(self, pipeline_id: str) -> PipelineResult:
        """Resume a paused pipeline from where it left off."""
        pipeline = self.pipelines.get(pipeline_id)
        if pipeline is None:
            raise ValueError(f"Unknown pipeline: {pipeline_id}")

        if pipeline["status"] != WorkflowStatus.PAUSED:
            raise ValueError(f"Pipeline {pipeline_id} is not paused (status: {pipeline['status'].value})")

        # Advance to the next step (the one after where we paused)
        pipeline["current_step_index"] = pipeline.get("current_step_index", 0) + 1
        pipeline["status"] = WorkflowStatus.ACTIVE
        return self.execute(pipeline_id, pipeline.get("context"))

    def get_status(self, pipeline_id: str) -> Dict[str, Any]:
        """Get the current status of a pipeline."""
        pipeline = self.pipelines.get(pipeline_id)
        if pipeline is None:
            raise ValueError(f"Unknown pipeline: {pipeline_id}")

        steps: List[PipelineStep] = pipeline["steps"]
        return {
            "pipeline_id": pipeline_id,
            "name": pipeline["name"],
            "status": pipeline["status"].value,
            "total_steps": len(steps),
            "current_step": pipeline.get("current_step_index", 0),
            "steps": [
                {
                    "step_id": s.step_id,
                    "name": s.name,
                    "status": s.status.value,
                    "error": s.error,
                }
                for s in steps
            ],
        }

    def retry_step(self, pipeline_id: str, step_id: str) -> PipelineResult:
        """Retry a specific failed step, then continue the pipeline."""
        pipeline = self.pipelines.get(pipeline_id)
        if pipeline is None:
            raise ValueError(f"Unknown pipeline: {pipeline_id}")

        steps: List[PipelineStep] = pipeline["steps"]
        target_index = None
        for i, step in enumerate(steps):
            if step.step_id == step_id:
                target_index = i
                break

        if target_index is None:
            raise ValueError(f"Unknown step: {step_id}")

        # Reset the step
        step = steps[target_index]
        step.status = TaskStatus.PENDING
        step.error = None
        step.retries = 0

        # Resume from this step
        pipeline["current_step_index"] = target_index
        pipeline["status"] = WorkflowStatus.ACTIVE
        return self.execute(pipeline_id, pipeline.get("context"))
