# PRD-118: Data Archival & GDPR Compliance

## Overview
Data archival engine with tiered storage management, GDPR compliance workflows,
retention policy enforcement, and data lifecycle automation for the Axion platform.

## Problem
TimescaleDB compression exists but no cold storage archival. No GDPR "right to
be forgotten" capability. No data lifecycle policies. No way to manage storage
costs as data grows. No compliance audit trail for data deletions.

## Components

### 1. Archival Engine (`src/archival/engine.py`)
- Data export to Parquet format with compression
- Storage backend abstraction (local, S3, Glacier)
- Archival job scheduling and tracking
- Archived data metadata catalog
- Restore from archive capability

### 2. Retention Manager (`src/archival/retention.py`)
- Per-table retention policy definitions
- Automatic data expiration enforcement
- Legal hold management (prevent deletion)
- Retention policy validation
- Storage tier transitions (hot → warm → cold)

### 3. GDPR Compliance (`src/archival/gdpr.py`)
- User data deletion request handling
- Cross-table cascade deletion planning
- Deletion audit trail with compliance proof
- Data export for subject access requests (Article 20)
- Anonymization as alternative to deletion

### 4. Data Lifecycle (`src/archival/lifecycle.py`)
- Storage tier management with cost tracking
- Access pattern analysis for tier optimization
- Automated tier transitions based on age/access
- Lifecycle policy templates for common data types
- Cost projection and optimization recommendations

## Database
- `archival_jobs` table for archival execution history
- `gdpr_requests` table for compliance request tracking

## Dashboard
4-tab Streamlit dashboard: Storage Tiers, Archival Jobs, GDPR Requests, Policies
