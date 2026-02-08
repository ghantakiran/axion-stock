"""PRD-120: Deployment Strategies & Rollback Automation — Validation."""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .config import DeploymentConfig, ValidationStatus

logger = logging.getLogger(__name__)


@dataclass
class ValidationCheck:
    """A single validation check for a deployment."""

    check_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    check_type: str = ""
    status: ValidationStatus = ValidationStatus.PENDING
    threshold: Optional[float] = None
    actual_value: Optional[float] = None
    passed: Optional[bool] = None
    message: str = ""
    executed_at: Optional[datetime] = None


class DeploymentValidator:
    """Runs validation checks against deployments to ensure health."""

    def __init__(self, config: Optional[DeploymentConfig] = None):
        self._config = config or DeploymentConfig()
        self._checks: Dict[str, List[ValidationCheck]] = {}
        self._lock = threading.Lock()

    @property
    def config(self) -> DeploymentConfig:
        return self._config

    def add_check(
        self,
        deployment_id: str,
        name: str,
        check_type: str,
        threshold: Optional[float] = None,
    ) -> ValidationCheck:
        """Register a validation check for a deployment."""
        with self._lock:
            check = ValidationCheck(
                name=name,
                check_type=check_type,
                threshold=threshold,
            )
            if deployment_id not in self._checks:
                self._checks[deployment_id] = []
            self._checks[deployment_id].append(check)
            logger.info(
                "Added validation check '%s' (%s) for deployment %s",
                name,
                check_type,
                deployment_id,
            )
            return check

    def run_check(
        self,
        deployment_id: str,
        check_id: str,
        actual_value: float,
    ) -> ValidationCheck:
        """Execute a single validation check by comparing actual vs threshold."""
        with self._lock:
            checks = self._checks.get(deployment_id, [])
            check = None
            for c in checks:
                if c.check_id == check_id:
                    check = c
                    break
            if check is None:
                raise KeyError(
                    f"Check {check_id} not found for deployment {deployment_id}"
                )

            check.actual_value = actual_value
            check.executed_at = datetime.utcnow()

            if check.threshold is not None:
                if check.check_type in ("error_rate", "latency"):
                    # Lower is better
                    check.passed = actual_value <= check.threshold
                else:
                    # Higher is better (e.g., uptime, success_rate)
                    check.passed = actual_value >= check.threshold

                check.status = (
                    ValidationStatus.PASSING
                    if check.passed
                    else ValidationStatus.FAILING
                )
                check.message = (
                    f"{'PASS' if check.passed else 'FAIL'}: "
                    f"{check.name} actual={actual_value} threshold={check.threshold}"
                )
            else:
                # No threshold — just record the value
                check.passed = True
                check.status = ValidationStatus.PASSING
                check.message = f"Recorded: {check.name}={actual_value}"

            logger.info(
                "Validation check '%s' for %s: %s",
                check.name,
                deployment_id,
                check.message,
            )
            return check

    def run_smoke_tests(self, deployment_id: str) -> List[ValidationCheck]:
        """Run a set of predefined smoke tests (simulated)."""
        import random

        random.seed(hash(deployment_id) % 2**32)

        smoke_tests = [
            ("health_endpoint", "health", None),
            ("api_response_time", "latency", 500.0),
            ("error_rate_check", "error_rate", 0.05),
            ("database_connectivity", "health", None),
            ("cache_connectivity", "health", None),
        ]

        results = []
        for name, check_type, threshold in smoke_tests:
            check = self.add_check(deployment_id, name, check_type, threshold)

            # Simulate realistic values
            if check_type == "latency":
                value = random.uniform(50.0, 300.0)
            elif check_type == "error_rate":
                value = random.uniform(0.001, 0.03)
            else:
                value = 1.0  # healthy

            self.run_check(deployment_id, check.check_id, value)
            results.append(check)

        logger.info(
            "Smoke tests completed for %s: %d/%d passed",
            deployment_id,
            sum(1 for r in results if r.passed),
            len(results),
        )
        return results

    def get_checks(self, deployment_id: str) -> List[ValidationCheck]:
        """Retrieve all checks for a deployment."""
        return self._checks.get(deployment_id, [])

    def is_deployment_healthy(self, deployment_id: str) -> bool:
        """Return True if all executed checks for a deployment are passing."""
        checks = self._checks.get(deployment_id, [])
        if not checks:
            return True  # No checks means no failures
        executed = [c for c in checks if c.status != ValidationStatus.PENDING]
        if not executed:
            return True
        return all(
            c.status == ValidationStatus.PASSING
            or c.status == ValidationStatus.SKIPPED
            for c in executed
        )

    def generate_report(self, deployment_id: str) -> dict:
        """Generate a validation report for a deployment."""
        checks = self._checks.get(deployment_id, [])
        passed_count = sum(
            1 for c in checks if c.status == ValidationStatus.PASSING
        )
        failed_count = sum(
            1 for c in checks if c.status == ValidationStatus.FAILING
        )
        pending_count = sum(
            1 for c in checks if c.status == ValidationStatus.PENDING
        )
        skipped_count = sum(
            1 for c in checks if c.status == ValidationStatus.SKIPPED
        )

        overall = "healthy" if failed_count == 0 else "unhealthy"

        return {
            "deployment_id": deployment_id,
            "checks": [
                {
                    "check_id": c.check_id,
                    "name": c.name,
                    "check_type": c.check_type,
                    "status": c.status.value,
                    "threshold": c.threshold,
                    "actual_value": c.actual_value,
                    "passed": c.passed,
                    "message": c.message,
                }
                for c in checks
            ],
            "passed_count": passed_count,
            "failed_count": failed_count,
            "pending_count": pending_count,
            "skipped_count": skipped_count,
            "overall": overall,
        }

    def get_validation_summary(self) -> dict:
        """Return aggregate validation statistics across all deployments."""
        total_checks = 0
        total_passed = 0
        total_failed = 0
        deployments_checked = len(self._checks)

        for checks in self._checks.values():
            total_checks += len(checks)
            total_passed += sum(
                1 for c in checks if c.status == ValidationStatus.PASSING
            )
            total_failed += sum(
                1 for c in checks if c.status == ValidationStatus.FAILING
            )

        return {
            "deployments_checked": deployments_checked,
            "total_checks": total_checks,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "pass_rate": (
                round(total_passed / total_checks, 4)
                if total_checks > 0
                else 0.0
            ),
        }

    def reset(self) -> None:
        """Clear all validation checks (for testing)."""
        with self._lock:
            self._checks.clear()
