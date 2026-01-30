# PRD-13: Alerting & Notifications System

## Overview

Real-time alerting and multi-channel notification system for the Axion platform. Users can create alerts on price movements, factor score changes, portfolio events, technical signals, and risk thresholds, with delivery via in-app, email, SMS, webhook, and Slack.

---

## Components

### 1. Alert Types
| Type | Description | Example |
|------|-------------|---------|
| Price | Price crosses threshold | AAPL > $200 |
| Factor | Factor score change | MSFT composite > 0.8 |
| Portfolio | Portfolio-level events | Drawdown > 5%, rebalance needed |
| Technical | Technical indicator signals | RSI > 70, MA crossover |
| Risk | Risk threshold breach | VaR > 2%, leverage > 1.5x |
| Volume | Unusual volume/activity | Volume > 2x 20-day avg |
| Sentiment | Sentiment shift | Sentiment drops below -0.5 |

### 2. Delivery Channels
- **In-App**: Stored notifications with read/unread state
- **Email**: SMTP-based delivery with HTML templates
- **SMS**: Twilio-compatible SMS delivery
- **Webhook**: HTTP POST with HMAC signing
- **Slack**: Channel/DM delivery via webhook URL

### 3. Condition Engine
- Comparison operators: >, <, >=, <=, ==, crosses_above, crosses_below
- Compound conditions: AND, OR grouping
- Percentage change conditions
- Cooldown periods to prevent alert fatigue

### 4. Alert Management
- Create/update/delete alerts
- Pre-built templates for common alerts
- Snooze/mute with expiration
- Alert history with delivery tracking
- Per-user notification preferences
- Quiet hours (Do Not Disturb)
- Digest mode (batch notifications)

### 5. Database Tables
- `alerts`: Alert definitions and conditions
- `alert_history`: Triggered alert records
- `notifications`: Delivery records per channel
- `notification_preferences`: Per-user channel settings

### 6. Success Metrics
- Alert evaluation latency: <1s
- Delivery success rate: >99%
- False positive rate: <5%

---

*Priority: P1 | Phase: 7*
