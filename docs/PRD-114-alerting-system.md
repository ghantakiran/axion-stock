# PRD-114: Notification & Alerting System

## Overview
Unified alerting service for system, trading, and data events with multi-channel
routing, alert aggregation, escalation policies, and acknowledgment workflow.

## Problem
Existing notification system (src/notifications/) handles only mobile push.
Alert channels (src/alerts/) provide basic email/Slack/SMS but lack production
features: no escalation, no aggregation (alert spam), no acknowledgment workflow,
no on-call rotation, no maintenance windows.

## Components

### 1. Alert Manager (`src/alerting/manager.py`)
- Centralized alert ingestion and routing
- Alert deduplication (same alert within window = single notification)
- Alert grouping by category (system, trading, data, security)
- Alert lifecycle (open, acknowledged, resolved, suppressed)
- Alert history with search

### 2. Routing Rules (`src/alerting/routing.py`)
- Severity-based channel routing (critical=SMS+Slack, warning=email, info=in-app)
- Rule evaluation engine with conditions
- Default and custom routing rules
- Channel fallback (if Slack fails, try email)

### 3. Escalation (`src/alerting/escalation.py`)
- Escalation policies (if not ack'd in 5min, escalate to manager)
- Multi-level escalation chains
- On-call rotation schedules
- Escalation timeout tracking

### 4. Aggregation (`src/alerting/aggregation.py`)
- Time-window aggregation (batch alerts within 60s)
- Count-based aggregation (after 10 similar alerts, send summary)
- Alert digest generation
- Suppression rules (maintenance windows, known issues)

### 5. Channel Dispatchers (`src/alerting/channels.py`)
- Email, Slack, SMS, Webhook, In-App dispatcher interfaces
- Channel health monitoring
- Delivery confirmation tracking
- Retry with exponential backoff

## Database
- `alert_records` table for alert history and status

## Dashboard
4-tab Streamlit dashboard: Active Alerts, Alert History, Routing Rules, Escalation

## Tests
Test suite covering alert routing, escalation, aggregation, suppression,
channel dispatch, and alert lifecycle management.
