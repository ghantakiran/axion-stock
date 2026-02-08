# PRD-119: WebSocket Scaling & Real-time Infrastructure

## Overview
Distributed WebSocket management with Redis-backed connection registry,
backpressure handling, reconnection logic, and horizontal scaling support.

## Problem
Current WebSocket implementation is single-instance with in-memory connection
state. Cannot scale horizontally. No backpressure handling for slow consumers.
No reconnection logic or message ordering guarantees. Limits the platform to
a single API server instance.

## Components

### 1. Connection Registry (`src/ws_scaling/registry.py`)
- Redis-backed distributed connection tracking
- Connection metadata (user_id, subscriptions, instance_id)
- Connection lifecycle management (connect, disconnect, migrate)
- Cross-instance connection lookup
- Connection count limits per user and global

### 2. Message Router (`src/ws_scaling/router.py`)
- Redis pub/sub for cross-instance message broadcasting
- Channel-based message routing
- Message priority levels (critical, normal, low)
- Message ordering guarantees within a channel
- Broadcast, multicast, and unicast patterns

### 3. Backpressure Handler (`src/ws_scaling/backpressure.py`)
- Per-connection message queue depth monitoring
- Slow consumer detection with configurable thresholds
- Message dropping strategies (oldest-first, lowest-priority)
- Client notification on message loss
- Automatic subscription throttling

### 4. Reconnection Manager (`src/ws_scaling/reconnection.py`)
- Server-side reconnection tracking
- Session persistence across reconnections
- Missed message replay from buffer
- Exponential backoff enforcement
- Connection deduplication (prevent double connections)

## Database
- `ws_connections` table for connection state tracking

## Dashboard
4-tab Streamlit dashboard: Connections, Message Throughput, Backpressure, Health
