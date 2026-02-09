# PRD-142: Alert & Notification Network

## Overview
Multi-channel alert system with user-configurable rules, delivery tracking, throttling, quiet hours, and batched digests. Delivers notifications via Email, SMS, Push, Slack, Discord, and Telegram.

## Architecture

### Source Files (`src/alert_network/`)

| File | Lines | Description |
|------|-------|-------------|
| `__init__.py` | ~80 | Public API: 22 exports |
| `rules.py` | ~280 | Alert rules engine with 11 trigger types |
| `channels.py` | ~230 | 6 notification channels + ChannelRegistry |
| `delivery.py` | ~180 | Delivery tracking, throttling, quiet hours, batch queue |
| `manager.py` | ~220 | Orchestrator: rules → channels → delivery |

### Key Components

1. **RuleEngine** — Evaluates user rules against incoming data:
   - 11 trigger types: price above/below, volume spike, sentiment bullish/bearish, social trending, signal generated, influencer alert, consensus formed, custom
   - Cooldown enforcement (default 30 min between repeat alerts)
   - Daily alert limits per rule (default 10/day)

2. **ChannelRegistry** — 6 auto-registered channels (all support demo mode):
   - Email (SMTP), SMS (Twilio), Push (FCM/APNs)
   - Slack (webhook), Discord (webhook), Telegram (Bot API)
   - In-app (always enabled)

3. **DeliveryTracker** — Manages delivery state:
   - Quiet hours (wraps around midnight)
   - Per-user hourly/daily limits
   - Batch digest queue for non-urgent alerts
   - Delivery history and statistics

4. **NotificationManager** — Pipeline orchestrator:
   - Evaluates rules → triggers alerts → dispatches to channels
   - Respects user preferences and throttle limits
   - Supports batch digest mode

### Integration Points

- **PRD-141** (Social Intelligence): `signals`, `volume_anomalies`, `trending`, `influencer_signals`, `consensus` data types
- **PRD-114** (Alerting System): Coexists — PRD-114 handles internal routing, PRD-142 handles user-facing notifications
- **PRD-60** (Notifications): Coexists — PRD-60 handles mobile push, PRD-142 adds rule-based multi-channel alerts

## ORM Models (`src/db/models.py`)

| Model | Table | Description |
|-------|-------|-------------|
| `AlertRuleRecord` | `alert_rules` | User-configurable alert rules |
| `NotificationDeliveryLogRecord` | `notification_delivery_log` | Delivery attempt history |
| `NotificationPreferenceRecord` | `notification_preferences` | Per-user notification settings |

## Migration

- **File**: `alembic/versions/142_alert_network.py`
- **Revision**: `142` → `down_revision`: `141`
- **Tables**: 3 new tables

## Dashboard (`app/pages/alert_network.py`)

4 tabs:
1. **Alert Rules** — Create/manage rules, test rule evaluation
2. **Notification Channels** — Channel status, credential configuration
3. **Delivery History** — Delivery log with stats
4. **Preferences** — Quiet hours, throttling, batch digest, channel priority

## Tests (`tests/test_alert_network.py`)

8 test classes, ~50 tests:

| Test Class | Tests | Coverage |
|---|---|---|
| `TestAlertRules` | 4 | Rule creation, to_dict, trigger types, defaults |
| `TestRuleEngine` | 12 | All trigger types, cooldown, symbol filter, disable |
| `TestChannels` | 8 | All 6 channels demo send, enum values, result |
| `TestChannelRegistry` | 3 | Default registration, send_to, send_to_all |
| `TestDeliveryTracker` | 5 | Can deliver, throttle, stats, batch, preferences |
| `TestNotificationManager` | 6 | Evaluate/notify, multi-channel, stats, accessors |
| `TestBatchDigest` | 2 | To payload, to dict |
| `TestModuleImports` | 4 | Exports, trigger types, channels, delivery status |

## Dependencies

- `src/alert_network/` is standalone (no hard dependency on PRD-141)
- Trigger evaluation accepts generic dicts with mock-compatible objects
