# PRD-117: Performance Profiling & Query Optimization

## Overview
Query profiling engine with slow query detection, index recommendations,
connection pool monitoring, and performance analysis for the Axion platform.

## Problem
Basic observability metrics exist but no proactive performance monitoring.
No slow query detection, no index recommendations, no N+1 detection, no
connection pool exhaustion alerts. Performance issues are discovered only
when users complain.

## Components

### 1. Query Profiler (`src/profiling/query_profiler.py`)
- Query fingerprinting and aggregation
- Slow query detection with configurable thresholds
- Query execution statistics (count, avg, p95, p99)
- Query plan tracking (simulated EXPLAIN ANALYZE)
- Query regression detection (sudden slowdowns)

### 2. Performance Analyzer (`src/profiling/analyzer.py`)
- Endpoint-to-query correlation
- N+1 query detection heuristics
- Memory usage tracking by component
- CPU bottleneck identification
- Performance snapshot comparisons

### 3. Index Advisor (`src/profiling/index_advisor.py`)
- Missing index detection from query patterns
- Unused index identification
- Index impact estimation
- Index creation recommendations with rationale
- Composite index suggestions

### 4. Connection Monitor (`src/profiling/connections.py`)
- Connection pool utilization tracking
- Long-running query detection
- Idle connection monitoring
- Pool exhaustion prediction
- Connection leak detection

## Database
- `query_profiles` table for query execution statistics
- `index_recommendations` table for index suggestions

## Dashboard
4-tab Streamlit dashboard: Query Profiler, Performance, Index Advisor, Connections
