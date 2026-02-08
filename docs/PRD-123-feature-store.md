# PRD-123: Feature Store & ML Feature Management

## Overview
Centralized feature store with online/offline split, feature catalog, versioning,
lineage tracking, and consistency guarantees for ML model training and serving.

## Problem
Features computed ad-hoc in training and serving paths. No feature reuse across
models. Training-serving skew causes model degradation in production. No feature
catalog for discoverability. No lineage tracking for impact analysis.

## Components

### 1. Feature Catalog (`src/feature_store/catalog.py`)
- Feature registry with metadata (owner, description, data type, freshness SLA)
- Feature search and discovery
- Feature dependency tracking
- Feature deprecation workflow
- Version management for feature definitions

### 2. Offline Store (`src/feature_store/offline.py`)
- Batch feature computation and storage
- Point-in-time correct feature retrieval for training
- Feature materialization scheduling
- Historical feature snapshots for backtesting
- Bulk feature extraction for dataset generation

### 3. Online Store (`src/feature_store/online.py`)
- Low-latency feature serving from Redis-like cache
- Write-through from batch computation
- TTL-based invalidation with freshness guarantees
- Feature vector assembly for model inference
- Cache hit/miss metrics and monitoring

### 4. Feature Lineage (`src/feature_store/lineage.py`)
- DAG tracking of feature dependencies
- Impact analysis (which models use this feature)
- Data source to feature to model traceability
- Freshness propagation through dependency chain
- Lineage visualization support

## Database
- `feature_definitions` table for feature catalog
- `feature_values` table for offline feature storage

## Dashboard
4-tab Streamlit dashboard: Feature Catalog, Online/Offline Status, Lineage, Monitoring
