# PRD-121: Event-Driven Architecture & Message Bus

## Overview
Centralized event-driven architecture with publish-subscribe messaging, persistent
event store, async consumers, and versioned event schemas for decoupled service
communication across the Axion platform.

## Problem
Services are tightly coupled through direct function calls. No asynchronous processing
for trade events, alerts, or compliance notifications. No event replay capability for
debugging or auditing. Cannot scale consumers independently from producers.

## Components

### 1. Event Bus (`src/event_bus/bus.py`)
- Topic-based publish/subscribe with pattern matching
- Multiple subscriber support per topic
- Guaranteed delivery with at-least-once semantics
- Dead letter queue for failed events
- Event filtering by type, source, or custom predicates

### 2. Event Store (`src/event_bus/store.py`)
- Immutable append-only event log
- Event replay from any point in time
- Aggregate-based event sourcing support
- Snapshot generation for fast replay
- Event versioning and schema evolution

### 3. Async Consumer (`src/event_bus/consumer.py`)
- Background worker pool for async event processing
- Configurable concurrency and batch sizes
- Retry with exponential backoff
- Consumer group support (competing consumers)
- Checkpoint-based progress tracking

### 4. Event Schema (`src/event_bus/schema.py`)
- Versioned event definitions with validation
- Standard event envelope (id, type, source, timestamp, data)
- Schema registry for compatibility checks
- Built-in events: OrderExecuted, AlertTriggered, ModelUpdated, ComplianceViolation

## Database
- `event_log` table for persistent event storage
- `subscriber_state` table for consumer checkpoint tracking

## Dashboard
4-tab Streamlit dashboard: Event Stream, Subscribers, Dead Letters, Statistics
