# PRD-162: Signal Persistence & Audit Trail

## Overview

Provides durable storage for every trading signal generated across the platform, maintaining an immutable audit trail with cryptographic hash chaining. Enables regulatory replay, signal provenance tracking, and historical analysis across all signal sources.

## Problem Statement

Trading signals are ephemeral — once consumed by the executor or dismissed, they vanish. There is no centralized, tamper-evident record of what signals were generated, when, by which module, and whether they were acted upon. This gap blocks regulatory compliance, post-incident analysis, and cross-module signal lineage.

## Solution

A three-layer persistence pipeline:

1. **Signal Sink** — Intercepts signals from all producers (EMA, social, fusion, agents) via a unified write interface
2. **Audit Ledger** — Stores each signal as an immutable row with SHA-256 hash chain linking to the previous entry
3. **Query & Replay API** — Provides filtered retrieval by source, ticker, time range, and conviction, plus full-sequence replay for compliance export

## Architecture

```
Signal Producers (PRD-134/141/147/154)
        ↓
    SignalSink.record()
        ↓
    Hash Chain (SHA-256)
        ↓
    signal_audit_ledger table
        ↓
  ┌─────┴─────┐
  │            │
Query API   Replay API
(filter)    (chronological)
  │            │
  └─────┬─────┘
        ↓
    Export (CSV/JSON)
```

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `PersistenceConfig` | `src/signal_persistence/config.py` | Retention days, hash algorithm, batch size |
| `SignalSink` | `src/signal_persistence/sink.py` | Unified write interface for all signal types |
| `AuditLedger` | `src/signal_persistence/ledger.py` | Hash-chained immutable storage, integrity verification |
| `SignalQueryAPI` | `src/signal_persistence/query.py` | Filtered retrieval, aggregation, export |
| `SignalReplayAPI` | `src/signal_persistence/replay.py` | Chronological replay for compliance and testing |

## Data Models

- `SignalAuditRecord` -> `signal_audit_ledger` (22 columns) — signal_id, source_module, ticker, direction, conviction, timestamp, payload_json, prev_hash, row_hash, acted_upon, execution_id, latency_ms, etc.
- `SignalIntegrityCheck` -> `signal_integrity_checks` (8 columns) — check_id, range_start, range_end, expected_count, actual_count, chain_valid, checked_at, errors_json

## Implementation

### Source Files
- `src/signal_persistence/__init__.py` — Public API exports
- `src/signal_persistence/config.py` — Configuration dataclass with defaults
- `src/signal_persistence/sink.py` — SignalSink with batch buffering and async flush
- `src/signal_persistence/ledger.py` — AuditLedger with hash chain and integrity verification
- `src/signal_persistence/query.py` — Query builder with filtering, pagination, export
- `src/signal_persistence/replay.py` — Chronological replay with speed control

### Database
- Migration `alembic/versions/162_signal_persistence.py` — revision `162`, down_revision `161`

### Dashboard
- `app/pages/signal_persistence.py` — 4 tabs: Signal Feed, Audit Ledger, Integrity Check, Export & Replay

### Tests
- `tests/test_signal_persistence.py` — ~55 tests covering sink ingestion, hash chain integrity, query filtering, replay ordering, export formats, and integrity verification

## Dependencies

- Depends on: PRD-134 (EMA Signals), PRD-141 (Social Intelligence), PRD-147 (Signal Fusion), PRD-154 (Agent Consensus), PRD-109 (Audit Trail patterns)
- Depended on by: PRD-166 (Signal Feedback Loop), PRD-169 (Integration Tests)

## Success Metrics

- 100% of generated signals persisted within 500ms of creation
- Hash chain integrity verification passes on every scheduled check
- Query API returns filtered results in < 200ms for 1M-row ledger
- Full compliance export of 30-day window completes in < 60s
