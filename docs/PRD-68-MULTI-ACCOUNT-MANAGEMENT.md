# PRD-68: Multi-Account Management

## Overview
Multi-account system supporting sub-accounts, account switching, household aggregation, tax-optimized asset location, and cross-account performance tracking.

## Components

### 1. Account Manager (`src/enterprise/accounts.py`)
- **Account CRUD** — Create, update, delete accounts with subscription tier limits
- **Household Aggregation** — Aggregate metrics across linked accounts (total value, positions, allocation)
- **Performance Tracking** — Daily snapshots with P&L, returns, beta, volatility
- **Tax-Optimized Asset Location** — Suggestions for optimal asset placement across taxable/tax-deferred/tax-free accounts
- **Cross-Account Analytics** — Consolidated position view, performance comparison

### 2. Account Models (`src/enterprise/models.py`)
- **Account** — id, name, type (individual/IRA/Roth/joint/trust/corporate/paper), broker, strategy, cash/value/cost basis, tax status, benchmark, permissions
- **AccountSnapshot** — Daily snapshot with total value, cash, positions value, P&L, returns, portfolio metrics

### 3. Account Types & Enums (`src/db/models.py`)
- **AccountTypeEnum** — INDIVIDUAL, IRA_TRADITIONAL, IRA_ROTH, JOINT, TRUST, CORPORATE, PAPER
- **TaxStatusEnum** — TAXABLE, TAX_DEFERRED, TAX_FREE
- **BrokerEnum** — PAPER, ALPACA, IBKR

## Database Tables
- `accounts` — Trading accounts with strategy, financials, tax status, permissions
- `account_snapshots` — Daily performance snapshots with P&L and portfolio metrics
- `account_positions` — Current positions per account with market value and weight
- `account_links` — Household linking (spouse, child, trust) with access levels
- `rebalancing_history` — Rebalancing operation tracking with pre/post allocation

## Dashboard
4-tab Streamlit dashboard (`app/pages/accounts.py`):
1. **Household Summary** — Aggregate metrics, account list, asset location pie chart
2. **Performance Comparison** — Normalized performance chart, metrics table
3. **Consolidated Positions** — Cross-account position aggregation
4. **Tax-Optimized Asset Location** — Recommendations by tax status

## Test Coverage
50 tests in `tests/test_multi_account.py` covering account CRUD, subscription limits, household aggregation, tax inference, asset location, performance history, and ORM validation.
