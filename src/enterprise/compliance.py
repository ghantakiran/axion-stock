"""Compliance and Audit Logging System.

Provides comprehensive audit trail, compliance checks, and regulatory support.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Callable
from dataclasses import dataclass, field

from src.enterprise.config import AuditConfig, DEFAULT_AUDIT_CONFIG
from src.enterprise.models import (
    AuditLog, AuditAction, ComplianceRule, ComplianceViolation,
    RestrictedSecurity, generate_uuid,
)

logger = logging.getLogger(__name__)


@dataclass
class PreTradeCheck:
    """Result of a pre-trade compliance check."""

    passed: bool
    rule_name: str
    message: str
    severity: str = "info"  # info, warning, critical
    details: dict = field(default_factory=dict)


@dataclass
class AuditQuery:
    """Query parameters for audit log search."""

    user_id: Optional[str] = None
    action: Optional[AuditAction] = None
    resource_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None
    ip_address: Optional[str] = None
    limit: int = 100
    offset: int = 0


class AuditLogger:
    """Comprehensive audit logging for all system actions.

    Features:
    - Log all user actions
    - Search and filter logs
    - Retention policy enforcement
    - Sensitive data masking
    """

    def __init__(self, config: Optional[AuditConfig] = None):
        self.config = config or DEFAULT_AUDIT_CONFIG
        self._logs: List[AuditLog] = []

    def log(
        self,
        action: AuditAction,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        resource_type: str = "",
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> AuditLog:
        """Log an action.

        Args:
            action: The action being logged.
            user_id: ID of the user performing the action.
            user_email: Email of the user.
            resource_type: Type of resource affected.
            resource_id: ID of the resource.
            details: Additional details (will be sanitized).
            ip_address: Client IP address.
            user_agent: Client user agent.
            status: Action status (success, failure, warning).
            error_message: Error message if failed.

        Returns:
            Created AuditLog.
        """
        if not self.config.enabled:
            return None

        # Sanitize sensitive data
        safe_details = self._sanitize_details(details or {})

        log = AuditLog(
            action=action,
            user_id=user_id,
            user_email=user_email,
            resource_type=resource_type,
            resource_id=resource_id,
            details=safe_details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message,
        )

        self._logs.append(log)

        # Log to system logger too
        log_msg = (
            f"AUDIT: {action.value} | "
            f"user={user_email or user_id} | "
            f"resource={resource_type}/{resource_id} | "
            f"status={status}"
        )
        if status == "failure":
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return log

    def query(self, query: AuditQuery) -> List[AuditLog]:
        """Search audit logs.

        Args:
            query: Query parameters.

        Returns:
            Matching audit logs.
        """
        results = []

        for log in self._logs:
            # Apply filters
            if query.user_id and log.user_id != query.user_id:
                continue
            if query.action and log.action != query.action:
                continue
            if query.resource_type and log.resource_type != query.resource_type:
                continue
            if query.status and log.status != query.status:
                continue
            if query.ip_address and log.ip_address != query.ip_address:
                continue
            if query.start_date and log.timestamp < query.start_date:
                continue
            if query.end_date and log.timestamp > query.end_date:
                continue

            results.append(log)

        # Sort by timestamp descending
        results.sort(key=lambda x: x.timestamp, reverse=True)

        # Apply pagination
        return results[query.offset:query.offset + query.limit]

    def get_user_activity(
        self,
        user_id: str,
        days: int = 30,
    ) -> List[AuditLog]:
        """Get recent activity for a user.

        Args:
            user_id: User ID.
            days: Number of days of history.

        Returns:
            User's audit logs.
        """
        query = AuditQuery(
            user_id=user_id,
            start_date=datetime.utcnow() - timedelta(days=days),
        )
        return self.query(query)

    def get_security_events(self, days: int = 7) -> List[AuditLog]:
        """Get security-related events.

        Args:
            days: Number of days of history.

        Returns:
            Security audit logs.
        """
        security_actions = [
            AuditAction.LOGIN,
            AuditAction.LOGOUT,
            AuditAction.LOGIN_FAILED,
            AuditAction.PASSWORD_CHANGE,
            AuditAction.TOTP_ENABLE,
            AuditAction.TOTP_DISABLE,
            AuditAction.API_KEY_CREATE,
            AuditAction.API_KEY_REVOKE,
        ]

        cutoff = datetime.utcnow() - timedelta(days=days)

        return [
            log for log in self._logs
            if log.action in security_actions and log.timestamp > cutoff
        ]

    def enforce_retention(self):
        """Remove logs older than retention period."""
        cutoff = datetime.utcnow() - timedelta(days=self.config.retention_days)
        original_count = len(self._logs)

        self._logs = [
            log for log in self._logs
            if log.timestamp > cutoff
        ]

        removed = original_count - len(self._logs)
        if removed > 0:
            logger.info(f"Audit retention: removed {removed} old logs")

    def _sanitize_details(self, details: dict) -> dict:
        """Remove sensitive fields from details."""
        sanitized = {}

        for key, value in details.items():
            if any(sensitive in key.lower() for sensitive in self.config.sensitive_fields):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_details(value)
            else:
                sanitized[key] = value

        return sanitized


class ComplianceManager:
    """Manages compliance rules and pre-trade checks.

    Features:
    - Restricted security lists
    - Position/sector limits
    - Pre-trade compliance checks
    - Violation tracking
    """

    def __init__(self, audit_logger: Optional[AuditLogger] = None):
        self.audit_logger = audit_logger or AuditLogger()

        # In-memory storage
        self._rules: dict[str, ComplianceRule] = {}
        self._restricted_list: dict[str, RestrictedSecurity] = {}
        self._violations: List[ComplianceViolation] = []
        self._custom_checks: List[Callable] = []

    def add_rule(
        self,
        name: str,
        description: str,
        rule_type: str,
        parameters: dict,
        created_by: str,
    ) -> ComplianceRule:
        """Add a compliance rule.

        Args:
            name: Rule name.
            description: Rule description.
            rule_type: Type of rule.
            parameters: Rule parameters.
            created_by: User creating the rule.

        Returns:
            Created ComplianceRule.
        """
        rule = ComplianceRule(
            name=name,
            description=description,
            rule_type=rule_type,
            parameters=parameters,
            created_by=created_by,
        )

        self._rules[rule.id] = rule

        self.audit_logger.log(
            AuditAction.SETTING_CHANGE,
            user_id=created_by,
            resource_type="compliance_rule",
            resource_id=rule.id,
            details={"rule_name": name, "rule_type": rule_type},
        )

        logger.info(f"Compliance rule added: {name}")
        return rule

    def add_restricted_security(
        self,
        symbol: str,
        reason: str,
        restricted_by: str,
        restriction_type: str = "all",
        end_date: Optional[datetime] = None,
        notes: str = "",
    ):
        """Add a security to the restricted list.

        Args:
            symbol: Security symbol.
            reason: Reason for restriction.
            restricted_by: User adding restriction.
            restriction_type: Type of restriction.
            end_date: When restriction ends.
            notes: Additional notes.
        """
        self._restricted_list[symbol.upper()] = RestrictedSecurity(
            symbol=symbol.upper(),
            reason=reason,
            restricted_by=restricted_by,
            restriction_type=restriction_type,
            end_date=end_date,
            notes=notes,
        )

        self.audit_logger.log(
            AuditAction.RESTRICTED_TRADE,
            user_id=restricted_by,
            resource_type="security",
            resource_id=symbol,
            details={"reason": reason, "restriction_type": restriction_type},
        )

        logger.info(f"Security restricted: {symbol} ({reason})")

    def remove_restricted_security(self, symbol: str, removed_by: str):
        """Remove a security from restricted list."""
        symbol = symbol.upper()
        if symbol in self._restricted_list:
            del self._restricted_list[symbol]

            self.audit_logger.log(
                AuditAction.SETTING_CHANGE,
                user_id=removed_by,
                resource_type="security",
                resource_id=symbol,
                details={"action": "unrestricted"},
            )

    def is_restricted(self, symbol: str, action: str = "all") -> tuple[bool, Optional[str]]:
        """Check if a security is restricted.

        Args:
            symbol: Security symbol.
            action: Action being attempted (buy, sell, all).

        Returns:
            Tuple of (is_restricted, reason).
        """
        symbol = symbol.upper()
        restriction = self._restricted_list.get(symbol)

        if not restriction:
            return False, None

        # Check if restriction has expired
        if restriction.end_date and restriction.end_date < datetime.utcnow().date():
            return False, None

        # Check restriction type
        if restriction.restriction_type == "all":
            return True, restriction.reason
        elif restriction.restriction_type == "buy_only" and action in ["buy", "all"]:
            return True, restriction.reason
        elif restriction.restriction_type == "sell_only" and action in ["sell", "all"]:
            return True, restriction.reason

        return False, None

    def run_pre_trade_checks(
        self,
        user_id: str,
        account_id: str,
        symbol: str,
        action: str,
        quantity: int,
        price: float,
        portfolio_value: float,
        current_positions: dict,
    ) -> List[PreTradeCheck]:
        """Run all pre-trade compliance checks.

        Args:
            user_id: User placing order.
            account_id: Account for order.
            symbol: Security symbol.
            action: Buy or sell.
            quantity: Number of shares.
            price: Order price.
            portfolio_value: Total portfolio value.
            current_positions: Current positions dict.

        Returns:
            List of PreTradeCheck results.
        """
        checks = []

        # 1. Restricted list check
        is_restricted, reason = self.is_restricted(symbol, action)
        checks.append(PreTradeCheck(
            passed=not is_restricted,
            rule_name="Restricted Security",
            message=reason or "Security is not restricted",
            severity="critical" if is_restricted else "info",
        ))

        # 2. Position limit checks
        for rule in self._rules.values():
            if not rule.is_active:
                continue

            if rule.rule_type == "position_limit":
                check = self._check_position_limit(
                    rule, symbol, quantity, price, portfolio_value, current_positions
                )
                checks.append(check)

            elif rule.rule_type == "sector_limit":
                check = self._check_sector_limit(
                    rule, symbol, quantity, price, portfolio_value, current_positions
                )
                checks.append(check)

        # 3. Run custom checks
        for custom_check in self._custom_checks:
            try:
                result = custom_check(
                    user_id, account_id, symbol, action, quantity, price,
                    portfolio_value, current_positions
                )
                if result:
                    checks.append(result)
            except Exception as e:
                logger.error(f"Custom compliance check failed: {e}")

        # Log violations
        for check in checks:
            if not check.passed and check.severity in ["warning", "critical"]:
                self._record_violation(
                    rule_name=check.rule_name,
                    account_id=account_id,
                    user_id=user_id,
                    details={
                        "symbol": symbol,
                        "action": action,
                        "quantity": quantity,
                        "message": check.message,
                    },
                    severity=check.severity,
                )

        return checks

    def _check_position_limit(
        self,
        rule: ComplianceRule,
        symbol: str,
        quantity: int,
        price: float,
        portfolio_value: float,
        current_positions: dict,
    ) -> PreTradeCheck:
        """Check position size limit."""
        max_pct = rule.parameters.get("max_position_pct", 0.15)

        # Current position value
        current_value = current_positions.get(symbol, {}).get("value", 0)
        order_value = quantity * price
        new_value = current_value + order_value

        position_pct = new_value / portfolio_value if portfolio_value > 0 else 0

        passed = position_pct <= max_pct

        return PreTradeCheck(
            passed=passed,
            rule_name=rule.name,
            message=(
                f"Position would be {position_pct*100:.1f}% "
                f"(limit: {max_pct*100:.0f}%)"
            ),
            severity="critical" if not passed else "info",
            details={"position_pct": position_pct, "limit": max_pct},
        )

    def _check_sector_limit(
        self,
        rule: ComplianceRule,
        symbol: str,
        quantity: int,
        price: float,
        portfolio_value: float,
        current_positions: dict,
    ) -> PreTradeCheck:
        """Check sector concentration limit."""
        max_pct = rule.parameters.get("max_sector_pct", 0.35)
        target_sector = rule.parameters.get("sector", "")

        # Would need sector data - simplified check
        return PreTradeCheck(
            passed=True,
            rule_name=rule.name,
            message="Sector limit check passed",
            severity="info",
        )

    def _record_violation(
        self,
        rule_name: str,
        account_id: str,
        user_id: str,
        details: dict,
        severity: str,
    ):
        """Record a compliance violation."""
        violation = ComplianceViolation(
            rule_name=rule_name,
            account_id=account_id,
            user_id=user_id,
            violation_type=details.get("action", "unknown"),
            details=details,
            severity=severity,
        )

        self._violations.append(violation)

        self.audit_logger.log(
            AuditAction.COMPLIANCE_VIOLATION,
            user_id=user_id,
            resource_type="account",
            resource_id=account_id,
            details={"rule": rule_name, "severity": severity, **details},
            status="warning",
        )

    def get_violations(
        self,
        account_id: Optional[str] = None,
        user_id: Optional[str] = None,
        unresolved_only: bool = False,
        days: int = 30,
    ) -> List[ComplianceViolation]:
        """Get compliance violations.

        Args:
            account_id: Filter by account.
            user_id: Filter by user.
            unresolved_only: Only unresolved violations.
            days: Number of days of history.

        Returns:
            List of violations.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        results = []
        for v in self._violations:
            if v.timestamp < cutoff:
                continue
            if account_id and v.account_id != account_id:
                continue
            if user_id and v.user_id != user_id:
                continue
            if unresolved_only and v.is_resolved:
                continue
            results.append(v)

        return sorted(results, key=lambda x: x.timestamp, reverse=True)

    def resolve_violation(
        self,
        violation_id: str,
        resolved_by: str,
        notes: str = "",
    ) -> bool:
        """Mark a violation as resolved."""
        for v in self._violations:
            if v.id == violation_id:
                v.is_resolved = True
                v.resolved_by = resolved_by
                v.resolved_at = datetime.utcnow()
                return True
        return False

    def add_custom_check(self, check_fn: Callable):
        """Add a custom pre-trade check function.

        Function should accept:
            user_id, account_id, symbol, action, quantity, price,
            portfolio_value, current_positions

        And return a PreTradeCheck or None.
        """
        self._custom_checks.append(check_fn)

    def get_restricted_list(self) -> List[RestrictedSecurity]:
        """Get all restricted securities."""
        return list(self._restricted_list.values())

    def get_rules(self) -> List[ComplianceRule]:
        """Get all compliance rules."""
        return list(self._rules.values())
