# PRD-69: Team Workspaces

## Overview
Collaborative team workspaces for sharing strategies, research notes, watchlists, and activity feeds with role-based access control.

## Components

### 1. Workspace Manager (`src/enterprise/workspaces.py`)
- **Workspace CRUD** — Create, retrieve workspaces with Enterprise subscription enforcement
- **Member Management** — Invite, remove, update roles with permission hierarchy (OWNER > ADMIN > MEMBER > VIEWER)
- **Strategy Sharing** — Share strategies with performance metrics, leaderboard with sorting (by return, Sharpe)
- **Activity Feed** — Automatic activity recording for creation, invites, strategy sharing; custom activity logging
- **Workspace Statistics** — Member count, strategy count, total AUM, activity metrics
- **Subscription Limits** — Enterprise-only access, 10-seat limit enforcement

### 2. Workspace Models (`src/enterprise/models.py`)
- **WorkspaceRole** — OWNER, ADMIN, MEMBER, VIEWER enum
- **Workspace** — id, name, description, owner, settings, member/strategy counts, total AUM
- **WorkspaceMember** — user_id, role, invited_by, joined timestamp
- **SharedStrategy** — name, config, performance metrics (YTD return, Sharpe, max DD, win rate)
- **ActivityItem** — user, action, resource type/id, details, timestamp

## Database Tables
- `workspaces` — Team workspace with settings, stats, status
- `workspace_members` — Membership with roles (unique constraint on workspace+user)
- `shared_strategies` — Strategies with cached performance metrics and usage counts
- `workspace_activities` — Activity feed with action logging and timestamps
- `workspace_watchlists` — Shared symbol watchlists
- `workspace_research_notes` — Research notes with tags, pinning, view counts

## Dashboard
Streamlit dashboard (`app/pages/workspaces.py`) with:
- Workspace list view with creation form
- Workspace detail view with 5 tabs:
  1. **Activity Feed** — Timestamped actions with icons
  2. **Strategy Leaderboard** — Sortable by return/Sharpe, performance chart
  3. **Members** — Role management, invitation interface
  4. **Watchlists** — Shared watchlists with symbol performance
  5. **Research Notes** — Pinned/unpinned notes with tags

## Test Coverage
37 tests in `tests/test_workspaces.py` covering workspace CRUD, member management (invite/remove/roles/permissions), strategy sharing, leaderboard, activity feed, statistics, subscription limits, and ORM validation.
