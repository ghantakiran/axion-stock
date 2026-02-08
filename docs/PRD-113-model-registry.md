# PRD-113: ML Model Registry & Deployment Pipeline

## Overview
Centralized ML model registry with versioning, staging workflow, A/B testing,
experiment tracking, and safe deployment pipeline for the Axion ML stack.

## Problem
4 production ML models (ranking, regime, earnings, factor timing) save/load via
pickle with no versioning database. No safe way to deploy model updates, compare
versions, or rollback. No experiment tracking or A/B testing.

## Components

### 1. Model Registry (`src/model_registry/registry.py`)
- Model registration with metadata (name, version, framework, metrics)
- Semantic versioning (major.minor.patch)
- Model artifact storage (path-based with metadata sidecar)
- Model search and listing with filters
- Model comparison (metrics side-by-side)

### 2. Model Versioning (`src/model_registry/versioning.py`)
- Version lifecycle (draft, staging, production, archived, deprecated)
- Stage transitions with validation gates
- Promotion workflow (draft → staging → production)
- Automatic version bumping
- Rollback to previous production version

### 3. A/B Testing (`src/model_registry/ab_testing.py`)
- Experiment definition (champion vs challenger)
- Traffic splitting (percentage-based)
- Statistical significance testing
- Experiment lifecycle management
- Winner selection with configurable criteria

### 4. Experiment Tracking (`src/model_registry/experiments.py`)
- Experiment logging (hyperparameters, metrics, artifacts)
- Run comparison across experiments
- Metric visualization data
- Best run selection

### 5. Model Serving (`src/model_registry/serving.py`)
- Model loader with caching
- Prediction API abstraction
- Model warm-up on deployment
- Prediction latency tracking
- Fallback to previous version on error

## Database
- `model_versions` table for model metadata and versioning
- `model_experiments` table for experiment tracking

## Dashboard
4-tab Streamlit dashboard: Model Registry, Experiments, A/B Tests, Deployment

## Tests
Test suite covering registration, versioning, A/B testing, experiment tracking,
and model serving with mock models.
