# PRD-111: Centralized Configuration Management

## Overview
Centralized configuration service providing feature flags, secrets management,
environment-specific configs, hot-reload, and config validation for the Axion platform.

## Problem
67+ module-specific config files with no centralized management. Feature toggles
are hardcoded booleans. Secrets stored in plain environment variables. No way to
safely roll out changes or toggle features in production without redeployment.

## Components

### 1. Config Service (`src/config_service/config_store.py`)
- Centralized key-value configuration store
- Namespace-based organization (trading, ml, risk, api)
- Type-safe value retrieval with validation
- Config change history with rollback
- Thread-safe access with read-write locking

### 2. Feature Flags (`src/config_service/feature_flags.py`)
- Boolean, percentage, and user-targeted flags
- Percentage rollouts (e.g., 10% of users get new ML model)
- Flag evaluation with context (user_id, environment, tier)
- Flag lifecycle management (created, active, deprecated, archived)
- Default values for unknown flags

### 3. Secrets Manager (`src/config_service/secrets.py`)
- Encrypted secrets storage with Fernet symmetric encryption
- Secret rotation support with grace periods
- Secret access auditing
- Integration hooks for Vault/AWS Secrets Manager
- Automatic masking in logs

### 4. Environment Config (`src/config_service/environments.py`)
- Environment definitions (development, staging, production)
- Environment-specific overrides
- Config inheritance (prod inherits from base, overrides specific values)
- Environment validation on startup

### 5. Config Validation (`src/config_service/validators.py`)
- Schema-based config validation
- Type checking, range validation, dependency validation
- Startup validation report
- Custom validation rules per namespace

## Database
- `config_entries` table for persistent config storage
- `feature_flags` table for flag definitions and state

## Dashboard
4-tab Streamlit dashboard: Config Browser, Feature Flags, Secrets, Validation

## Tests
Comprehensive test suite covering store operations, flag evaluation,
secret encryption/rotation, environment resolution, and validation.
