---
name: Axion Compliance & Enterprise
description: >
  Implement compliance checks, enterprise features, and notifications for the Axion
  trading platform. Covers trade surveillance (wash trade, layering, spoofing detection),
  insider trading blackout windows, best execution monitoring, regulatory reporting,
  user authentication with RBAC and 2FA, multi-account management, team workspaces,
  professional report generation, audit logging, and push notification delivery.
metadata:
  author: Axion Platform Team
  version: 1.0.0
---

# Axion Compliance & Enterprise Skill

## When to use this skill

Use this skill when you need to:

- Detect manipulative trading patterns (wash trades, layering, spoofing, churning)
- Manage insider trading blackout windows and pre-clearance requests
- Monitor best execution quality with slippage analysis and venue ranking
- Generate regulatory filings and compliance summaries
- Implement user authentication with JWT tokens, PBKDF2 password hashing, and TOTP 2FA
- Manage multi-account portfolios with household aggregation and tax-optimized asset location
- Create team workspaces with shared strategies and leaderboards
- Generate professional performance reports in PDF, Excel, or HTML
- Log and query audit trails with sensitive data masking
- Run pre-trade compliance checks (restricted lists, position limits, sector limits)
- Send push notifications with preference management and rate limiting

## Step-by-step instructions

### 1. Trade Surveillance

Scan trades for manipulative patterns and manage surveillance alerts.

```python
from src.compliance_engine import SurveillanceEngine, SurveillanceConfig

config = SurveillanceConfig(
    wash_trade_window=300, wash_trade_price_tolerance=0.001,
    layering_threshold=5, spoofing_cancel_ratio=0.90,
    excessive_trading_limit=50, marking_close_window_min=5,
)
engine = SurveillanceEngine(config)

trades = [
    {"symbol": "AAPL", "side": "buy", "price": 150.0, "quantity": 100, "timestamp": 1000},
    {"symbol": "AAPL", "side": "sell", "price": 150.05, "quantity": 100, "timestamp": 1200},
]
alerts = engine.scan_trades(trades, account_id="ACC-001")
for alert in alerts:
    print(f"[{alert.severity}] {alert.alert_type}: {alert.description}")

engine.resolve_alert(alerts[0].alert_id, resolved_by="compliance_officer")
unresolved = engine.get_alerts(unresolved_only=True, severity="critical")
```

### 2. Blackout Windows and Pre-Clearance

Manage insider trading blackout periods and pre-clearance workflow.

```python
from src.compliance_engine import BlackoutManager, BlackoutConfig
from datetime import date

mgr = BlackoutManager(BlackoutConfig(
    default_blackout_days_before=14, default_blackout_days_after=2,
    require_pre_clearance=True, pre_clearance_valid_days=5,
))

# Create earnings blackout (auto-calculates start/end from earnings date)
window = mgr.create_earnings_blackout(
    symbol="AAPL", earnings_date=date(2024, 7, 25), affected_persons=["emp-001"],
)

# Check if trading is allowed (considers blackout + pre-clearance + value thresholds)
result = mgr.can_trade(symbol="AAPL", person_id="emp-001", trade_value=50_000)
print(f"Allowed: {result['allowed']}, Reason: {result['reason']}")

# Pre-clearance workflow
request = mgr.submit_pre_clearance(
    requester_id="emp-001", symbol="AAPL", side="buy",
    quantity=100, estimated_value=15_000, reason="Personal investment",
)
mgr.approve_pre_clearance(request.request_id, approved_by="compliance_officer")
```

### 3. Best Execution Monitoring

Track execution quality, analyze slippage, and rank venues.

```python
from src.compliance_engine import BestExecutionMonitor, BestExecutionConfig
from datetime import date

monitor = BestExecutionMonitor(BestExecutionConfig(
    excellent_threshold_bps=2.0, good_threshold_bps=5.0, acceptable_threshold_bps=10.0,
))

metric = monitor.record_execution(
    order_id="ORD-001", symbol="AAPL", side="buy", quantity=100,
    limit_price=150.50, fill_price=150.45, benchmark_price=150.40, venue="NYSE",
)
print(f"Slippage: {metric.slippage_bps:.1f} bps, Quality: {metric.quality}")

report = monitor.generate_report(period_start=date(2024, 7, 1), period_end=date(2024, 7, 31))
rankings = monitor.get_venue_ranking()
```

### 4. Regulatory Reporting

Generate daily compliance reports, surveillance summaries, and filings.

```python
from src.compliance_engine import RegulatoryReporter
from datetime import date

reporter = RegulatoryReporter()
filing = reporter.generate_daily_compliance(
    report_date=date(2024, 7, 15), alerts=alerts,
    blackout_violations=0, pre_clearance_pending=2, best_exec=report,
)
summary = reporter.generate_compliance_summary(
    period="2024-Q3", alerts=alerts, blackout_violations=0, best_exec=report,
)
reporter.mark_filed(filing.filing_id)
```

### 5. Authentication and User Management

```python
from src.enterprise import AuthService, AuthConfig, UserRole, SubscriptionTier

auth = AuthService()

# Register and login
user, error = auth.register(email="trader@example.com", password="SecurePass123",
                            name="Jane Trader", role=UserRole.TRADER)
session, error = auth.login(email="trader@example.com", password="SecurePass123",
                            ip_address="192.168.1.1")

# Token verification and permissions
verified_user, error = auth.verify_token(session.access_token)
can_trade = auth.has_permission(user, "execute_trades")
allowed, msg = auth.check_feature_access(user, "live_trading")

# 2FA and API keys
secret, error = auth.enable_totp(user.id)
uri = auth.totp_manager.get_provisioning_uri(secret, user.email)
raw_key, api_key, error = auth.create_api_key(
    user_id=user.id, name="Trading Bot", scopes=["api_read", "api_execute"],
)
```

### 6. Multi-Account Management

```python
from src.enterprise import AccountManager, AccountType, TaxStatus, BrokerType

accounts = AccountManager()
taxable, error = accounts.create_account(
    user=user, name="Personal Taxable", account_type=AccountType.INDIVIDUAL,
    broker=BrokerType.ALPACA, initial_value=100_000,
)
roth, error = accounts.create_account(
    user=user, name="Roth IRA", account_type=AccountType.IRA_ROTH, initial_value=50_000,
)

# Household aggregation and tax-optimized asset location
household = accounts.get_household_summary(user.id)
print(f"Total: ${household.total_value:,.0f}")
suggestions = accounts.suggest_asset_location(user.id)
```

### 7. Team Workspaces

```python
from src.enterprise import WorkspaceManager, WorkspaceRole

ws_mgr = WorkspaceManager()
workspace, error = ws_mgr.create_workspace(owner=user, name="Quant Team Alpha",
                                            description="Systematic trading research")
member, error = ws_mgr.invite_member(workspace_id=workspace.id, inviter_id=user.id,
                                      user_id="user-456", user_name="Bob", role=WorkspaceRole.MEMBER)
strategy, error = ws_mgr.share_strategy(
    workspace_id=workspace.id, user_id=user.id, user_name=user.name,
    name="Momentum Factor", description="Cross-sectional momentum",
    config={"lookback": 252}, ytd_return=0.18, sharpe_ratio=1.45,
)
leaderboard = ws_mgr.get_leaderboard(workspace.id, metric="sharpe_ratio", limit=10)
```

### 8. Professional Report Generation

```python
from src.enterprise import ReportGenerator, ReportData, PerformanceMetrics, AttributionData
from src.enterprise.config import ReportConfig
from datetime import date

gen = ReportGenerator(ReportConfig(company_name="Axion Capital"))
data = ReportData(
    report_title="Q3 2024 Performance Report", client_name="Jane Trader",
    account_name="Personal Taxable",
    period_start=date(2024, 7, 1), period_end=date(2024, 9, 30),
    metrics=PerformanceMetrics(period_return=0.085, benchmark_return=0.065,
                                sharpe_ratio=1.8, max_drawdown=-0.08),
    attribution=AttributionData(
        sector_attribution={"Technology": 0.03, "Healthcare": 0.01},
        total_allocation=0.015, total_selection=0.01,
    ),
)
pdf_bytes = gen.generate_quarterly_report(data, format="pdf")
excel_bytes = gen.generate_quarterly_report(data, format="excel")
```

### 9. Audit Logging and Compliance Management

```python
from src.enterprise import AuditLogger, AuditQuery, AuditAction, ComplianceManager

logger = AuditLogger()
log = logger.log(action=AuditAction.ORDER_SUBMIT, user_id=user.id, user_email=user.email,
                  resource_type="order", resource_id="ORD-001",
                  details={"symbol": "AAPL", "password": "secret"}, ip_address="192.168.1.1")
# "password" field auto-redacted to "[REDACTED]"

results = logger.query(AuditQuery(user_id=user.id, action=AuditAction.ORDER_SUBMIT, limit=50))

compliance = ComplianceManager(audit_logger=logger)
compliance.add_restricted_security(symbol="XYZ", reason="Pending acquisition",
                                    restricted_by="legal_dept", restriction_type="all")
checks = compliance.run_pre_trade_checks(
    user_id=user.id, account_id=taxable.id, symbol="AAPL", action="buy",
    quantity=500, price=150.0, portfolio_value=100_000,
    current_positions={"AAPL": {"value": 10000}},
)
for check in checks:
    print(f"[{'PASS' if check.passed else 'FAIL'}] {check.rule_name}: {check.message}")
```

### 10. Push Notifications

```python
from src.notifications import (
    DeviceManager, PreferenceManager, NotificationSender,
    NotificationCategory, NotificationPriority, Platform, TokenType,
)
from src.notifications.models import Notification, PriceAlertPayload, TradeExecutionPayload

devices = DeviceManager()
prefs = PreferenceManager()
sender = NotificationSender(devices, prefs)

device = devices.register_device(user_id="user-123", device_token="fcm_token_abc123",
                                  platform=Platform.IOS, token_type=TokenType.FCM)
prefs.update_preference(user_id="user-123", category=NotificationCategory.PRICE_ALERTS,
                         enabled=True, priority=NotificationPriority.HIGH, max_per_hour=10)
prefs.set_quiet_hours("user-123", start="22:00", end="08:00", timezone="US/Eastern")

# Send with typed payload helpers
alert = PriceAlertPayload(symbol="AAPL", current_price=155.0, target_price=155.0,
                           direction="above", alert_id="alert-001")
results = sender.send(alert.to_notification(user_id="user-123"))
stats = sender.get_stats()
```

## Key classes and methods

### Compliance Engine (`src/compliance_engine/`)

| Class | Method | Description |
|-------|--------|-------------|
| `SurveillanceEngine` | `scan_trades(trades, account_id)` | Run all enabled surveillance checks on trades |
| `SurveillanceEngine` | `resolve_alert(alert_id, resolved_by)` | Mark alert as resolved |
| `SurveillanceEngine` | `get_alerts(unresolved_only, severity)` | Query surveillance alerts |
| `BlackoutManager` | `create_blackout(symbol, reason, start_date, end_date, ...)` | Create blackout window |
| `BlackoutManager` | `create_earnings_blackout(symbol, earnings_date, ...)` | Auto-create earnings blackout |
| `BlackoutManager` | `can_trade(symbol, person_id, trade_value)` | Full trade eligibility check |
| `BlackoutManager` | `submit_pre_clearance(requester_id, symbol, ...)` | Submit pre-clearance request |
| `BlackoutManager` | `approve_pre_clearance(request_id, approved_by)` | Approve pre-clearance |
| `BestExecutionMonitor` | `record_execution(order_id, symbol, ...)` | Record execution for quality analysis |
| `BestExecutionMonitor` | `generate_report(period_start, period_end)` | Generate best execution report |
| `BestExecutionMonitor` | `get_venue_ranking()` | Rank venues by execution quality |
| `RegulatoryReporter` | `generate_daily_compliance(report_date, ...)` | Daily compliance filing |
| `RegulatoryReporter` | `generate_compliance_summary(period, ...)` | Overall compliance health |

### Enterprise (`src/enterprise/`)

| Class | Method | Description |
|-------|--------|-------------|
| `AuthService` | `register(email, password, name, role)` | Register new user |
| `AuthService` | `login(email, password, totp_code, ...)` | Authenticate and create session |
| `AuthService` | `verify_token(token)` | Validate JWT and return user |
| `AuthService` | `has_permission(user, permission)` | Check RBAC permission |
| `AuthService` | `check_feature_access(user, feature)` | Check subscription tier gate |
| `AuthService` | `create_api_key(user_id, name, scopes, ...)` | Create API key |
| `AuthService` | `enable_totp(user_id)` | Generate TOTP secret for 2FA |
| `TokenManager` | `create_access_token(user_id, role, ...)` | Create JWT access token |
| `TokenManager` | `decode_token(token)` | Decode and validate JWT |
| `TOTPManager` | `verify_code(secret, code, window)` | Verify TOTP code |
| `AccountManager` | `create_account(user, name, account_type, ...)` | Create trading account |
| `AccountManager` | `get_household_summary(user_id)` | Aggregate view across all accounts |
| `AccountManager` | `suggest_asset_location(user_id)` | Tax-optimized asset placement |
| `WorkspaceManager` | `create_workspace(owner, name, description)` | Create team workspace |
| `WorkspaceManager` | `invite_member(workspace_id, ...)` | Invite to workspace |
| `WorkspaceManager` | `share_strategy(workspace_id, ...)` | Share strategy with team |
| `WorkspaceManager` | `get_leaderboard(workspace_id, metric, limit)` | Strategy performance ranking |
| `ReportGenerator` | `generate_quarterly_report(data, format)` | Generate report (pdf/excel/html) |
| `AuditLogger` | `log(action, user_id, resource_type, ...)` | Log auditable action |
| `AuditLogger` | `query(query)` | Search audit logs with filters |
| `ComplianceManager` | `run_pre_trade_checks(...)` | Pre-trade compliance validation |
| `ComplianceManager` | `add_restricted_security(symbol, ...)` | Add to restricted list |
| `ComplianceManager` | `add_rule(name, rule_type, parameters, ...)` | Add compliance rule |

### Notifications (`src/notifications/`)

| Class | Method | Description |
|-------|--------|-------------|
| `NotificationSender` | `send(notification)` | Send notification to user devices |
| `NotificationSender` | `send_bulk(notifications)` | Send multiple notifications |
| `NotificationSender` | `get_stats()` | Delivery statistics |
| `PreferenceManager` | `update_preference(user_id, category, ...)` | Update notification preference |
| `PreferenceManager` | `set_quiet_hours(user_id, start, end, ...)` | Set quiet hours |
| `PreferenceManager` | `is_notification_allowed(user_id, category)` | Check if notification allowed |
| `DeviceManager` | `register_device(user_id, device_token, ...)` | Register push device |

## Common patterns

### Enums define valid options

```python
from src.compliance_engine.config import SurveillanceType, AlertSeverity
# SurveillanceType: WASH_TRADE, LAYERING, SPOOFING, FRONT_RUNNING,
#   INSIDER_TRADING, PUMP_AND_DUMP, EXCESSIVE_TRADING, MARKING_CLOSE
from src.enterprise.config import UserRole, SubscriptionTier, AccountType, TaxStatus
# UserRole: VIEWER, TRADER, MANAGER, ADMIN, API
# SubscriptionTier: FREE, PRO, ENTERPRISE
# AccountType: INDIVIDUAL, IRA_TRADITIONAL, IRA_ROTH, JOINT, TRUST, CORPORATE, PAPER
from src.notifications.config import NotificationCategory, NotificationPriority
# Categories: PRICE_ALERTS, TRADE_EXECUTIONS, PORTFOLIO, RISK_ALERTS, NEWS, SYSTEM
```

### Enterprise methods return (result, error) tuples

```python
user, error = auth.register("user@example.com", "Pass123", "Name")
if error:
    print(f"Failed: {error}")
    return
```

### Typed notification payloads

```python
from src.notifications.models import PriceAlertPayload, TradeExecutionPayload, RiskAlertPayload
# Each has to_notification(user_id) -> Notification
```

### Config dataclasses with sensible defaults

```python
from src.compliance_engine.config import SurveillanceConfig, BlackoutConfig, BestExecutionConfig
from src.enterprise.config import AuthConfig, AuditConfig, ReportConfig
from src.notifications.config import NotificationConfig
```
