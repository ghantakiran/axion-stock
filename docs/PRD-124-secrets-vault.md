# PRD-124: Secrets Management & API Credential Vaulting

## Overview
Centralized secrets management with encryption at rest, credential rotation,
fine-grained access control, and audit logging for broker API keys, database
credentials, and OAuth tokens.

## Problem
Credentials scattered across environment variables and broker modules. No encryption
at rest for stored secrets. No rotation policies for API keys. No audit trail for
secret access. Required for SOC2, PCI-DSS, and FedRAMP compliance.

## Components

### 1. Secrets Vault (`src/secrets_vault/vault.py`)
- Encrypted key-value store with envelope encryption
- Hierarchical secret paths (service/environment/key)
- Secret versioning with rollback capability
- Bulk secret import/export for migration
- Secret expiration with automatic cleanup

### 2. Credential Rotation (`src/secrets_vault/rotation.py`)
- Scheduled rotation of API keys and passwords
- Rotation strategies (create-then-delete, swap)
- Pre/post rotation hooks for service notification
- Grace period for old credentials during rollover
- Rotation failure alerting and rollback

### 3. Access Control (`src/secrets_vault/access.py`)
- Service-level and user-level permissions
- Path-based access policies (glob patterns)
- Temporary access grants with expiration
- Access request and approval workflow
- Deny-by-default with explicit grants

### 4. Secrets Client (`src/secrets_vault/client.py`)
- SDK for services to fetch secrets
- Local caching with TTL and invalidation
- Automatic refresh on rotation events
- Fallback to environment variables
- Connection pooling for vault requests

## Database
- `secrets` table for encrypted secret storage
- `secret_access_audit` table for access trail

## Dashboard
4-tab Streamlit dashboard: Secrets Browser, Rotation Status, Access Audit, Policies
