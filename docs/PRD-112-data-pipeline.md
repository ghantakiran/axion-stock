# PRD-112: Data Pipeline Orchestration & Monitoring

## Overview
Pipeline orchestration engine with DAG-based job dependencies, execution monitoring,
data lineage tracking, SLA management, and quality gates for the Axion data stack.

## Problem
Data ingestion relies on ad-hoc scripts (backfill_daily.py, etc.) with no dependency
management, monitoring, or failure recovery. ML models may train on stale data.
Factor scores may use outdated prices. No alerts when data providers fail.

## Components

### 1. Pipeline Engine (`src/pipeline/engine.py`)
- DAG-based job execution with topological sort
- Parallel execution of independent nodes
- Job status tracking (pending, running, success, failed, skipped)
- Retry logic with configurable backoff
- Execution timeout enforcement
- Pipeline run history

### 2. Pipeline Definition (`src/pipeline/definition.py`)
- Pipeline and PipelineNode dataclasses
- Dependency declaration (node A depends on B, C)
- Job configuration (schedule, timeout, retries, priority)
- Pipeline templates for common patterns (market data, ML training)

### 3. Data Lineage (`src/pipeline/lineage.py`)
- Source → transformation → destination tracking
- LineageNode and LineageEdge graph
- Impact analysis (what downstream is affected if source X fails?)
- Lineage query API

### 4. Scheduler (`src/pipeline/scheduler.py`)
- Cron-based pipeline scheduling
- Market-hours-aware scheduling (run only during trading hours)
- One-shot and recurring schedules
- Schedule conflict detection

### 5. Monitoring (`src/pipeline/monitoring.py`)
- Pipeline execution metrics (duration, success rate, data volume)
- SLA tracking with breach detection
- Data freshness monitoring
- Pipeline health scoring

## Database
- `pipeline_runs` table for execution history
- `pipeline_nodes` table for node-level tracking

## Dashboard
4-tab Streamlit dashboard: Pipeline Runs, DAG Viewer, Data Lineage, SLA Monitor

## Tests
Test suite covering DAG execution, dependency resolution, lineage tracking,
scheduling, and monitoring with mock pipelines.
