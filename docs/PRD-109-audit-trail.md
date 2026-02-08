# PRD-109: Audit Trail & Event Sourcing

## Overview
Implement a comprehensive audit trail system that records all significant actions (trades, configuration changes, user actions, system events) as immutable events. This supports regulatory compliance (SEC, FINRA), debugging, and forensic analysis.

## Goals
1. **Audit Event Recording** — Capture who did what, when, and from where for all significant actions
2. **Immutable Event Log** — Append-only event storage with tamper detection via hash chains
3. **Event Categories** — Trading, configuration, authentication, authorization, system, compliance events
4. **Query API** — Efficient querying by time range, actor, action type, and resource
5. **Retention & Export** — Configurable retention policies and compliance-ready export formats

## Technical Design

### Audit Event Structure
```json
{
  "event_id": "uuid",
  "timestamp": "2024-01-01T00:00:00Z",
  "actor": {"id": "user_42", "type": "user", "ip": "10.0.0.1"},
  "action": "order.create",
  "resource": {"type": "order", "id": "ord-123"},
  "details": {"symbol": "AAPL", "quantity": 100, "side": "buy"},
  "outcome": "success",
  "hash": "sha256-of-previous-event+current"
}
```

### Components
- `src/audit/__init__.py` — Public API exports
- `src/audit/config.py` — Audit configuration, event categories, retention policies
- `src/audit/events.py` — AuditEvent dataclass, EventCategory enum, Actor/Resource models
- `src/audit/recorder.py` — AuditRecorder (sync/async recording), hash chain integrity
- `src/audit/query.py` — AuditQuery builder with filtering, pagination, time-range queries
- `src/audit/export.py` — CSV/JSON export, compliance report generation

### Database
- `audit_events` table with hash chain column, indexed by timestamp, actor, action

### Dashboard
- Event timeline, actor activity, action distribution, integrity verification, export

## Success Criteria
- All trading actions are automatically audited
- Hash chain provides tamper evidence
- Query performance < 100ms for typical time-range queries
- 40+ tests covering recording, querying, and integrity
