---
name: alert-configuration
description: Configuring and managing alerts in the Axion platform -- trading alerts, bot pipeline alerts, system alerts, economic event alerts. Covers AlertManager (PRD-114) with fire/acknowledge/resolve lifecycle, RoutingEngine with rules and channels (EMAIL/SLACK/SMS/WEBHOOK/IN_APP), EscalationManager with timeout-based level promotion, AlertAggregator for batching, BotAlertBridge (PRD-174) with 7 event handlers, and AlertNetwork (PRD-142) for user-facing notification rules.
metadata:
  author: axion-platform
  version: "1.0"
---

# Alert Configuration

## When to use this skill

Use this skill when you need to:
- Fire, acknowledge, resolve, or suppress alerts
- Configure routing rules that map alert severity/category to delivery channels
- Set up escalation policies with timeout-based level promotion
- Wire bot pipeline events (trade executed, kill switch, daily loss) into alerts
- Configure the user-facing alert network with trigger rules
- Set up multi-channel delivery (Email, Slack, SMS, Webhook, Push, Discord, Telegram)
- Implement alert deduplication and aggregation
- Understand the two alerting subsystems: AlertManager (PRD-114) and AlertNetwork (PRD-142)

## Step-by-step instructions

### 1. Understand the two alert subsystems

The platform has two complementary alert subsystems:

**AlertManager** (`src/alerting/`, PRD-114) -- Internal system-level alerting:
- Used by the bot pipeline, infrastructure, and platform services
- Alert lifecycle: OPEN -> ACKNOWLEDGED -> RESOLVED (or SUPPRESSED)
- Routing rules map severity + category to channels
- Thread-safe with deduplication

**AlertNetwork** (`src/alert_network/`, PRD-142) -- User-facing notification system:
- User-configurable trigger rules (price alerts, volume spikes, etc.)
- Multi-channel delivery with quiet hours and throttling
- Batch digests for grouping alerts

### 2. Fire alerts with AlertManager

```python
from src.alerting import AlertManager, AlertSeverity, AlertCategory, AlertConfig

# Create with custom config
config = AlertConfig(
    default_channels=[ChannelType.IN_APP, ChannelType.EMAIL],
    dedup_window_seconds=300,
    enable_escalation=True,
    enable_aggregation=True,
)
manager = AlertManager(config)

# Fire an alert
alert = manager.fire(
    title="Portfolio drawdown exceeds 5%",
    message="Current drawdown is 6.2% ($6,200) from peak equity $100,000",
    severity=AlertSeverity.WARNING,
    category=AlertCategory.TRADING,
    source="risk_engine",
    tags={"drawdown_pct": "6.2", "peak_equity": "100000"},
    dedup_key="portfolio_drawdown_warning",
)

print(f"Alert ID: {alert.alert_id}")
print(f"Status: {alert.status}")        # AlertStatus.OPEN
print(f"Dedup count: {alert.occurrence_count}")
```

### 3. Configure routing rules

```python
from src.alerting import RoutingRule, RoutingEngine, AlertSeverity, AlertCategory, ChannelType

# Access the router through AlertManager
router = manager.router

# Rule: CRITICAL trading alerts go to Slack + SMS
router.add_rule(RoutingRule(
    rule_id="critical_trading",
    name="Critical Trading Alerts",
    severity_min=AlertSeverity.CRITICAL,
    categories=[AlertCategory.TRADING],
    channels=[ChannelType.SLACK, ChannelType.SMS],
    enabled=True,
    priority=100,  # Higher priority = evaluated first
))

# Rule: All ERROR+ alerts go to Email + Slack
router.add_rule(RoutingRule(
    rule_id="error_notify",
    name="Error Notifications",
    severity_min=AlertSeverity.ERROR,
    categories=[],  # Empty = all categories
    channels=[ChannelType.EMAIL, ChannelType.SLACK],
    enabled=True,
    priority=50,
))

# Rule: System warnings go to webhook only
router.add_rule(RoutingRule(
    rule_id="system_webhook",
    name="System Monitoring Webhook",
    severity_min=AlertSeverity.WARNING,
    categories=[AlertCategory.SYSTEM],
    channels=[ChannelType.WEBHOOK],
    enabled=True,
    priority=30,
))

# List all rules
rules = router.get_rules()

# Remove a rule
router.remove_rule("system_webhook")
```

### 4. Set up escalation policies

```python
from src.alerting import EscalationManager, EscalationPolicy, EscalationLevel, ChannelType

esc_manager = EscalationManager()

# Create multi-level escalation policy
policy = EscalationPolicy(
    policy_id="trading_critical",
    name="Critical Trading Alert Escalation",
    levels=[
        EscalationLevel(
            level=0,
            timeout_seconds=300,      # 5 minutes
            channels=[ChannelType.SLACK],
            notify_targets=["#trading-alerts"],
        ),
        EscalationLevel(
            level=1,
            timeout_seconds=600,      # 10 minutes
            channels=[ChannelType.SLACK, ChannelType.SMS],
            notify_targets=["#trading-alerts", "+1-555-0100"],
        ),
        EscalationLevel(
            level=2,
            timeout_seconds=900,      # 15 minutes
            channels=[ChannelType.SLACK, ChannelType.SMS, ChannelType.EMAIL],
            notify_targets=["#trading-alerts", "+1-555-0100", "oncall@example.com"],
        ),
    ],
    enabled=True,
)

esc_manager.add_policy(policy)

# Start escalation for an alert
esc_manager.start_escalation(alert.alert_id, "trading_critical")

# Check escalations (call periodically)
escalations = esc_manager.check_escalations()
for alert_id, level in escalations:
    print(f"Alert {alert_id} escalated to level {level.level}")

# Inspect escalation state
state = esc_manager.get_escalation_state(alert.alert_id)
print(f"Current level: {state['current_level']}")
print(f"Time remaining: {state['time_remaining_seconds']:.0f}s")

# Cancel escalation (e.g., when alert is acknowledged)
esc_manager.cancel_escalation(alert.alert_id)
```

### 5. Alert lifecycle management

```python
# Acknowledge an alert
manager.acknowledge(alert.alert_id, by="trader_jdoe")

# Resolve an alert
manager.resolve(alert.alert_id)

# Suppress an alert (stop notifications)
manager.suppress(alert.alert_id)

# Query alerts
active = manager.get_active_alerts()  # All OPEN alerts
critical = manager.get_alerts(severity=AlertSeverity.CRITICAL)
trading = manager.get_alerts(category=AlertCategory.TRADING, status=AlertStatus.OPEN)

# Count by severity
counts = manager.get_alert_count_by_severity()
# {"info": 12, "warning": 5, "error": 2, "critical": 0}
```

### 6. Wire bot pipeline alerts (BotAlertBridge)

The `BotAlertBridge` translates bot pipeline events into structured alerts:

```python
from src.bot_pipeline.alert_bridge import BotAlertBridge, AlertBridgeConfig
from src.alerting import AlertManager

# Configure thresholds
bridge_config = AlertBridgeConfig(
    daily_loss_warning_pct=0.80,           # Warn at 80% of daily loss limit
    guard_rejection_threshold=5,            # Alert after 5 rejections
    guard_rejection_window_seconds=60.0,    # Within 60 seconds
)

bridge = BotAlertBridge(
    alert_manager=AlertManager(),
    config=bridge_config,
)

# The orchestrator calls these automatically, but you can call directly:

# 1. Trade executed (severity: INFO, category: TRADING)
bridge.on_trade_executed(
    ticker="AAPL", direction="long", shares=100, price=195.50,
)

# 2. Position closed (severity: INFO for profit, WARNING for loss)
bridge.on_position_closed(
    ticker="AAPL", direction="long", pnl=320.50, exit_reason="target_hit",
)

# 3. Kill switch activated (severity: CRITICAL)
bridge.on_kill_switch(reason="Daily loss limit hit: -$5,200")

# 4. Daily loss warning (severity: WARNING)
bridge.on_daily_loss_warning(current_pnl=-4100.0, daily_limit=5000.0)

# 5. Guard rejection spike (severity: WARNING, returns None if threshold not met)
alert = bridge.on_guard_rejection_spike(rejection_count=6)

# 6. Emergency close (severity: CRITICAL)
bridge.on_emergency_close(positions_closed=5)

# 7. Pipeline error (severity: ERROR, category: SYSTEM)
bridge.on_error(stage="fill_validation", error="Broker timeout after 3 retries")

# Get recent bot alert history
history = bridge.get_alert_history(limit=50)
```

### 7. User-facing alert network (PRD-142)

```python
from src.alert_network import (
    NotificationManager, AlertRule, TriggerType, ChannelKind,
    DeliveryPreferences,
)

mgr = NotificationManager()

# Add a user-defined alert rule
mgr.add_rule(AlertRule(
    name="AAPL Volume Spike",
    trigger_type=TriggerType.VOLUME_SPIKE,
    symbol="AAPL",
    threshold=3.0,        # 3x average volume
    channels=[ChannelKind.PUSH, ChannelKind.EMAIL],
))

# Set delivery preferences (quiet hours, throttling)
prefs = DeliveryPreferences(
    quiet_hours_start=22,   # 10 PM
    quiet_hours_end=7,      # 7 AM
    throttle_minutes=15,    # Min 15 min between alerts
)

# Evaluate data against rules and notify
result = await mgr.evaluate_and_notify(market_data)
```

## Key classes and methods

### `AlertManager` (src/alerting/manager.py)
- `fire(title, message, severity, category, source, tags, dedup_key) -> Alert`
- `acknowledge(alert_id, by) -> bool`
- `resolve(alert_id) -> bool`
- `suppress(alert_id) -> bool`
- `get_alert(alert_id) -> Optional[Alert]`
- `get_active_alerts() -> list[Alert]`
- `get_alerts(status, severity, category) -> list[Alert]`
- `get_alert_count_by_severity() -> dict[str, int]`
- Properties: `router -> RoutingEngine`, `aggregator -> AlertAggregator`, `dispatcher -> ChannelDispatcher`

### `Alert` dataclass (src/alerting/manager.py)
Fields: `alert_id`, `title`, `message`, `severity` (AlertSeverity), `category` (AlertCategory), `status` (AlertStatus), `source`, `tags`, `created_at`, `acknowledged_at`, `resolved_at`, `acknowledged_by`, `dedup_key`, `occurrence_count`

### `RoutingEngine` (src/alerting/routing.py)
- `add_rule(rule: RoutingRule)` / `remove_rule(rule_id) -> bool`
- `resolve_channels(alert) -> list[ChannelType]`
- `get_rules() -> list[RoutingRule]` / `clear_rules()`

### `EscalationManager` (src/alerting/escalation.py)
- `add_policy(policy)` / `remove_policy(policy_id) -> bool`
- `start_escalation(alert_id, policy_id) -> bool`
- `check_escalations(now) -> list[tuple[str, EscalationLevel]]`
- `cancel_escalation(alert_id) -> bool`
- `get_escalation_state(alert_id) -> Optional[dict]`

### `BotAlertBridge` (src/bot_pipeline/alert_bridge.py)
- `on_trade_executed(ticker, direction, shares, price) -> Alert`
- `on_position_closed(ticker, direction, pnl, exit_reason) -> Alert`
- `on_kill_switch(reason) -> Alert`
- `on_daily_loss_warning(current_pnl, daily_limit) -> Alert`
- `on_guard_rejection_spike(rejection_count) -> Optional[Alert]`
- `on_emergency_close(positions_closed) -> Alert`
- `on_error(stage, error) -> Alert`
- `get_alert_history(limit) -> list[dict]`

### Enums

```python
class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertStatus(Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"

class AlertCategory(Enum):
    SYSTEM = "system"
    TRADING = "trading"
    DATA = "data"
    SECURITY = "security"
    COMPLIANCE = "compliance"

class ChannelType(Enum):
    EMAIL = "email"
    SLACK = "slack"
    SMS = "sms"
    WEBHOOK = "webhook"
    IN_APP = "in_app"
```

## Common patterns

### Deduplication

Alerts with the same `dedup_key` are deduplicated within `dedup_window_seconds` (default 300s). Instead of creating a new alert, the `occurrence_count` on the existing alert is incremented:

```python
# First fire creates the alert
a1 = manager.fire(title="Drawdown", message="...", dedup_key="drawdown")
# a1.occurrence_count == 1

# Second fire within 5 min returns the same alert
a2 = manager.fire(title="Drawdown", message="...", dedup_key="drawdown")
# a2.alert_id == a1.alert_id
# a2.occurrence_count == 2
```

### Bot pipeline integration

The `BotAlertBridge` is auto-loaded by `BotOrchestrator` when `config.enable_alerting=True`. It fires alerts at these pipeline points:

1. **Stage 8.75**: After position creation -> `on_trade_executed()`
2. **close_position()**: After P&L calculation -> `on_position_closed()`
3. **Kill switch activation**: -> `on_kill_switch()`
4. **Daily loss check**: When P&L hits 80% of limit -> `on_daily_loss_warning()`

### Routing rule evaluation order

Rules are evaluated by `priority` (descending). The **first matching rule** determines the channels. If no rules match, `default_channels` (from AlertConfig) are used. Severity comparison: alert severity must be >= rule's `severity_min`.

### Source files

- `src/alerting/__init__.py` -- public API exports
- `src/alerting/config.py` -- AlertSeverity, AlertStatus, AlertCategory, ChannelType, AlertConfig
- `src/alerting/manager.py` -- Alert, AlertManager
- `src/alerting/routing.py` -- RoutingRule, RoutingEngine
- `src/alerting/escalation.py` -- EscalationLevel, EscalationPolicy, EscalationManager
- `src/alerting/aggregation.py` -- AlertDigest, AlertAggregator
- `src/alerting/channels.py` -- DeliveryResult, ChannelDispatcher
- `src/bot_pipeline/alert_bridge.py` -- BotAlertBridge, AlertBridgeConfig
- `src/alert_network/__init__.py` -- AlertNetwork public API
- `src/alert_network/rules.py` -- AlertRule, TriggerType, RuleEngine
- `src/alert_network/channels.py` -- ChannelKind, channel implementations
- `src/alert_network/delivery.py` -- DeliveryTracker, DeliveryPreferences
- `src/alert_network/manager.py` -- NotificationManager
