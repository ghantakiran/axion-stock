# PRD-93: Multi-Account Management

## Overview
Multi-account management system with account CRUD, household aggregation, tax-aware asset location, subscription tier enforcement, team workspaces, performance comparison, and consolidated position views.

## Components

### 1. Account Manager (`src/enterprise/accounts.py`)
- **AccountManager** — Multi-account CRUD with authorization
- Account types: INDIVIDUAL, IRA_TRADITIONAL, IRA_ROTH, JOINT, TRUST, PAPER
- Tax status: TAXABLE, TAX_DEFERRED, TAX_FREE
- Subscription tier limits (FREE: 1, PRO: 3, ENTERPRISE: unlimited)
- Performance snapshots, YTD/total returns
- Asset location optimization (tax-aware allocation suggestions)
- **AccountSummary** — Individual account metrics
- **HouseholdSummary** — Aggregated view (total value, cash, positions, P&L, tax breakdown)

### 2. Workspace Manager (`src/enterprise/workspaces.py`)
- **WorkspaceManager** — Team collaboration
- Roles: OWNER, ADMIN, MEMBER, VIEWER
- Strategy sharing and leaderboards
- Activity feeds, workspace stats
- Member seat limits (Enterprise: 10 default)

### 3. Models (`src/enterprise/models.py`)
- **Account** — Full account entity with broker, type, tax status, positions, value
- **AccountSnapshot** — Daily performance history

### 4. ORM Models (`src/db/models.py`)
- **TradingAccount** — SQLAlchemy model for account persistence
- **AccountSnapshotRecord** — Daily snapshot storage
- **AccountPositionRecord** — Position tracking
- **AccountLink** — Household/family linking
- **RebalancingHistory** — Rebalancing audit trail

## Database Tables
- `accounts` — Trading accounts with owner, type, broker (migration 054)
- `account_snapshots` — Daily performance history (migration 054)
- `account_positions` — Current positions per account (migration 054)
- `account_links` — Household/family views (migration 054)
- `rebalancing_history` — Rebalancing operations (migration 054)
- `account_transfers` — Cross-account transfers (migration 068)
- `account_benchmarks` — Performance vs benchmark (migration 068)
- `account_tax_reports` — Per-account tax summary snapshots (migration 093)
- `household_analytics` — Household-level analytics aggregation (migration 093)

## Dashboard
Streamlit dashboard (`app/pages/accounts.py`) with 4 tabs:
1. **Summary** — Household metrics (total value, P&L, cash, accounts count)
2. **Performance** — Normalized performance comparison across accounts
3. **Positions** — Consolidated positions with cross-account concentration
4. **Asset Location** — Tax-aware allocation breakdown

## Test Coverage
50 tests in `tests/test_multi_account.py` covering AccountCreation (7), AccountRetrieval (4), AccountUpdate (6), AccountDeletion (3), AccountValueUpdates (2), AccountSummary (4), HouseholdSummary (3), TaxStatusInference (4), AssetLocationSuggestions (3), PerformanceHistory (2), SubscriptionLimits (3), ORMModels (5, pre-existing ORM failures), Enums (3, pre-existing ORM failures). 42/50 business logic tests pass.
