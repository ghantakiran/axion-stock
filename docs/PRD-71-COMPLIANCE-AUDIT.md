# PRD-71: Compliance & Audit

## Overview
Comprehensive compliance and audit logging system with pre-trade checks, restricted security lists, violation tracking, regulatory reporting, and sensitive data masking.

## Components

### 1. Audit Logger (`src/enterprise/compliance.py`)
- **AuditLogger** — Full audit trail with configurable retention, sensitive data masking, and structured query support
- **AuditQuery** — Parameterized log search by user, action, resource, date range, status, IP address with pagination
- **Security Events** — Filtered view of auth-related actions (login, logout, password change, TOTP, API keys)
- **Retention Enforcement** — Automatic purge of logs older than configured retention period

### 2. Compliance Manager (`src/enterprise/compliance.py`)
- **ComplianceManager** — Rule management, restricted securities, pre-trade checks, violation tracking
- **PreTradeCheck** — Result dataclass with pass/fail, rule name, message, severity, details
- **Restricted Securities** — Add/remove/query restricted symbols with type (all, buy_only, sell_only) and expiration
- **Position Limit Checks** — Validates position size against max percentage rules
- **Sector Limit Checks** — Validates sector concentration limits
- **Custom Checks** — Pluggable check functions via add_custom_check()
- **Violation Management** — Record, query (by account/user/resolved status), and resolve violations

### 3. Models (`src/enterprise/models.py`)
- **AuditLog** — id, action, user, resource, details, IP, user_agent, status, error, timestamp
- **AuditAction** — LOGIN, LOGOUT, LOGIN_FAILED, ORDER_SUBMIT, ORDER_CANCEL, STRATEGY_CREATE/UPDATE/DELETE, ACCOUNT_CREATE/UPDATE, SETTING_CHANGE, PASSWORD_CHANGE, TOTP_ENABLE/DISABLE, API_KEY_CREATE/REVOKE, DATA_EXPORT, COMPLIANCE_VIOLATION, RESTRICTED_TRADE
- **ComplianceRule** — id, name, description, rule_type, parameters, is_active, created_by
- **ComplianceViolation** — id, rule_name, account_id, user_id, violation_type, details, severity, resolution fields
- **RestrictedSecurity** — symbol, reason, restricted_by, restriction_type, end_date, notes

### 4. Configuration (`src/enterprise/config.py`)
- **AuditConfig** — enabled, retention_days, sensitive_fields list, log_level
- Subscription tier gating: FREE (basic audit), PRO (extended), ENTERPRISE (full compliance suite)

### 5. Enums (`src/db/models.py`)
- **ComplianceRuleTypeEnum** — POSITION_LIMIT, SECTOR_LIMIT, CONCENTRATION, TRADING_FREQUENCY, WASH_SALE, CUSTOM
- **ComplianceSeverityEnum** — INFO, WARNING, CRITICAL
- **RestrictionTypeEnum** — ALL, BUY_ONLY, SELL_ONLY
- **AuditActionEnum** — LOGIN, LOGOUT, ORDER_SUBMIT, SETTING_CHANGE, DATA_EXPORT, etc.

## Database Tables
- `compliance_rules` — Rule definitions with parameters, severity, scope (accounts/symbols), blocking flag
- `restricted_securities` — Restricted symbols with reason, restriction type, validity period, unique constraint per owner+symbol
- `compliance_violations` — Violation records with trade context, resolution tracking, blocking status
- `audit_logs` — Comprehensive action logs with user, resource, details, changes, session, IP/user-agent
- `pretrade_checks` — Pre-trade check audit trail with check results, blocking violations, override support
- `compliance_reports` — Regulatory report records (best execution, 13F, Form ADV, audit summary) with submission tracking

## Dashboard
Streamlit dashboard (`app/pages/compliance.py`) with compliance management interface.

## Test Coverage
39 tests in `tests/test_compliance.py` covering audit logging (log creation, query, user activity, security events, sanitization, retention), compliance rules (add/restricted securities/remove), pre-trade checks (restricted, position limits, custom checks), violations (recording, filtering, resolution), and ORM/enum validation.
