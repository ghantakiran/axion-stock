# PRD-60: Mobile Push Notifications

## Overview

Push notification system for delivering real-time alerts to mobile devices via Firebase Cloud Messaging (FCM) and Apple Push Notification Service (APNs). Supports price alerts, trade executions, portfolio updates, and custom triggers.

## Goals

1. Deliver time-sensitive alerts within 3 seconds
2. Support iOS and Android via unified API
3. Enable granular notification preferences
4. Provide analytics on delivery and engagement
5. Support scheduled and batched notifications

## Components

### 1. Notification Types
- **Price Alerts**: Symbol crosses target price
- **Trade Executions**: Order filled, partial, rejected
- **Portfolio Updates**: Daily P&L summary, significant changes
- **Risk Alerts**: Stop-loss triggered, margin warning
- **News Alerts**: Breaking news for watched symbols
- **System Alerts**: Maintenance, feature updates

### 2. Device Management
- Device registration with FCM/APNs tokens
- Multi-device support per user
- Token refresh handling
- Device type tracking (iOS/Android)

### 3. Preference Management
- Per-category toggle (price, trades, portfolio, etc.)
- Quiet hours configuration
- Frequency limits (max per hour)
- Priority levels (urgent, normal, low)

### 4. Delivery Engine
- Priority queue for urgent notifications
- Batch delivery for non-urgent messages
- Retry logic with exponential backoff
- Dead letter queue for failed deliveries

### 5. Analytics
- Delivery success/failure rates
- Open rates (if app reports)
- Time to delivery metrics
- Per-user engagement scores

## Database Tables

### notification_devices
- id, user_id, device_token, platform, device_name
- is_active, created_at, last_used_at

### notification_preferences
- id, user_id, category, enabled, priority
- quiet_hours_start, quiet_hours_end, timezone

### notification_queue
- id, user_id, category, title, body, data
- priority, scheduled_at, sent_at, status

### notification_history
- id, user_id, device_id, notification_id
- sent_at, delivered_at, opened_at, status

## API Endpoints

```
POST   /api/v1/notifications/devices          # Register device
DELETE /api/v1/notifications/devices/{id}     # Unregister device
GET    /api/v1/notifications/preferences      # Get preferences
PUT    /api/v1/notifications/preferences      # Update preferences
GET    /api/v1/notifications/history          # Get notification history
POST   /api/v1/notifications/test             # Send test notification
```

## Push Payload Format

```json
{
  "notification": {
    "title": "AAPL Price Alert",
    "body": "AAPL reached $190.00 (target: $189.50)"
  },
  "data": {
    "type": "price_alert",
    "symbol": "AAPL",
    "price": "190.00",
    "alert_id": "alert_123",
    "action": "open_stock"
  },
  "priority": "high"
}
```

## Integration Points

- WebSocket API (PRD-59): Real-time triggers
- Alert System (PRD-13): Alert conditions
- Trade Execution (PRD-03): Order status changes
- Portfolio (PRD-08): Value changes

## Success Metrics

| Metric | Target |
|--------|--------|
| Delivery latency | < 3 seconds |
| Delivery success | > 99% |
| Token validity | > 95% |
| User opt-in rate | > 70% |

## Files

- `src/notifications/config.py` - Configuration and enums
- `src/notifications/models.py` - Data models
- `src/notifications/devices.py` - Device registration
- `src/notifications/preferences.py` - User preferences
- `src/notifications/sender.py` - Push delivery engine
- `src/notifications/queue.py` - Notification queue management
- `app/pages/notifications.py` - Settings dashboard
