# PRD-122: Data Isolation & Row-Level Security

## Overview
Workspace-aware data isolation with row-level security, tenant context management,
automatic query filtering, and RBAC policy engine for multi-tenant SaaS compliance.

## Problem
Workspaces exist but lack systematic data isolation. No automatic query filtering by
tenant. No row-level security policies. Risk of horizontal privilege escalation in
multi-tenant environments. Required for SOC2 and regulated financial services.

## Components

### 1. Tenant Context (`src/multi_tenancy/context.py`)
- Thread-local context manager for workspace/user binding
- Async-compatible context propagation
- Context extraction from JWT claims
- Workspace membership validation
- Context inheritance for background tasks

### 2. Query Filter (`src/multi_tenancy/filters.py`)
- Automatic WHERE clause injection for workspace_id
- ORM query interceptor for all read operations
- Cross-workspace query prevention
- Shared resource access (global data like market data)
- Query audit logging for compliance

### 3. Data Isolation Middleware (`src/multi_tenancy/middleware.py`)
- FastAPI middleware for tenant context establishment
- Request-level workspace validation
- Cross-tenant request detection and blocking
- IP-based workspace restrictions
- Rate limiting per workspace

### 4. Policy Engine (`src/multi_tenancy/policies.py`)
- Role-based access control (RBAC) evaluation
- Resource-level permissions (view/edit/delete)
- Custom policy rules with condition expressions
- Policy inheritance (workspace → team → user)
- Policy evaluation caching for performance

## Database
- `workspace_data_policies` table for RLS policy definitions
- `tenant_audit_log` table for data access audit trail

## Dashboard
4-tab Streamlit dashboard: Tenant Overview, Policies, Access Audit, Isolation Health
