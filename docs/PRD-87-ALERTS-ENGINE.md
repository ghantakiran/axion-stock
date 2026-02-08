# PRD-87: Alerts Engine

## Overview
Multi-channel alerting system with configurable rules engine, compound condition evaluation, 6 delivery channels, mobile push notifications, priority-based escalation, domain-specific alert managers, and user notification preferences.

## Components

### 1. Alert Engine (`src/alerts/engine.py`)
- **AlertEngine** — Main evaluation and dispatch orchestrator
- Evaluates alerts against market data, manages alert lifecycle
- Dispatches notifications to configured channels
- Cooldown enforcement, max trigger limits

### 2. Condition System (`src/alerts/conditions.py`)
- **ConditionBuilder** — Build conditions from templates
- **ConditionEvaluator** — Stateful evaluation with cross-detection
- Operators: GT, GTE, LT, LTE, EQ, NEQ, CROSSES_ABOVE, CROSSES_BELOW, PCT_CHANGE_GT, PCT_CHANGE_LT
- Compound conditions with AND/OR logic
- 10+ pre-built templates (price alert, volume spike, RSI, earnings, etc.)

### 3. Alert Manager (`src/alerts/manager.py`)
- **AlertManager** — High-level CRUD and lifecycle management
- Alert states: ACTIVE, TRIGGERED, SNOOZED, DISABLED, EXPIRED
- Snooze/disable/enable/delete operations
- Filtering by symbol, type, status, priority

### 4. Delivery Channels (`src/alerts/channels/`)
- **InAppChannel** — In-app notification storage with read/unread tracking
- **EmailChannel** — SMTP delivery with subject/body templates
- **SMSChannel** — Twilio-compatible SMS delivery
- **WebhookChannel** — HTTP delivery with HMAC-SHA256 signing
- **SlackChannel** — Slack webhook with formatted messages

### 5. Mobile Push (`src/notifications/`)
- **DeviceManager** — FCM (Android), APNs (iOS), Web Push registration
- **PreferenceManager** — Per-category preferences, quiet hours, priority overrides
- **NotificationSender** — Multi-device delivery orchestration
- **NotificationQueue** — Priority queue with retry logic (3 retries: 30s, 2m, 10m)

### 6. Domain-Specific Alerts
- **NewsAlertManager** (`src/news/alerts.py`) — Symbol/keyword, breaking news, earnings, SEC filings, insider transactions
- **ScreenAlertManager** (`src/screener/alerts.py`) — Entry/exit conditions, count thresholds
- **EarningsAlertManager** (`src/earnings/alerts.py`) — Upcoming earnings, surprises, revisions
- **WatchlistAlertManager** (`src/watchlist/alerts.py`) — Price thresholds, volume spikes, RSI, targets
- **EconomicAlertManager** (`src/economic/alerts.py`) — Macro events, impact levels, surprise detection

### 7. Configuration (`src/alerts/config.py`)
- AlertType, AlertPriority, AlertStatus, ComparisonOperator, LogicalOperator
- ChannelType, DeliveryStatus, DigestFrequency

### 8. Models (`src/alerts/models.py`)
- **AlertCondition** — Simple condition (metric, operator, threshold)
- **CompoundCondition** — AND/OR compound conditions
- **Alert** — Full alert definition with conditions, channels, priority, cooldown
- **AlertEvent** — Triggered event record
- **Notification** — Delivery record with status tracking
- **NotificationPreferences** — User channel/priority preferences

## Database Tables
- `alerts`, `alert_history`, `notifications`, `notification_preferences` (migration 014)
- `notification_devices`, `notification_queue`, `notification_history` (migration 060)
- `alert_rule_templates` — Shareable alert rule templates (migration 087)
- `alert_escalation_log` — Escalation tracking for critical alerts (migration 087)

## Dashboards
- `app/pages/alerts.py` — Alert management, history, notifications, settings
- `app/pages/notifications.py` — Push notification settings, device management, analytics

## Test Coverage
167 tests across 2 test files:
- `tests/test_alerts.py` — 92 tests (config, conditions, compound conditions, builder, evaluator, alerts, notifications, preferences, channels [InApp/Email/SMS/Webhook/Slack], engine, manager, full workflows, imports)
- `tests/test_notifications.py` — 75 tests (config, devices, preferences, notifications, payloads, DeviceManager, PreferenceManager, NotificationQueue, NotificationSender, DeliveryStats)
