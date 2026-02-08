# PRD-89: Advanced Watchlists

## Overview
Advanced watchlist management system with stock tracking, price/technical alerts, research notes with tags, sharing with granular permissions, custom column configuration, and performance metrics.

## Components

### 1. Watchlist Manager (`src/watchlist/manager.py`)
- **WatchlistManager** — CRUD for watchlists and items
- Add/remove items, prevent duplicates, set targets (buy/sell/stop-loss)
- Search: find symbol across watchlists, filter by tags, conviction
- Performance calculation (hypothetical returns, win rate, targets hit)

### 2. Alert Manager (`src/watchlist/alerts.py`)
- **AlertManager** — 12 alert types for watchlist items
- PRICE_ABOVE/BELOW, PCT_CHANGE_UP/DOWN, VOLUME_SPIKE
- RSI_OVERSOLD/OVERBOUGHT, MA_CROSS_UP/DOWN
- TARGET_HIT, STOP_HIT, EARNINGS_SOON
- Alert checking with notification generation

### 3. Notes Manager (`src/watchlist/notes.py`)
- **NotesManager** — Research notes with categorization
- 6 note types: research, thesis, earnings, news, technical, general
- Tag system with usage tracking and suggestions
- Note search across watchlists

### 4. Sharing Manager (`src/watchlist/sharing.py`)
- **SharingManager** — Collaboration and sharing
- User sharing with VIEW/EDIT/ADMIN permissions
- Link-based sharing with auto-generated URLs
- Public/private toggles, access checking, share revocation

### 5. Configuration (`src/watchlist/config.py`)
- AlertType (12 types), NoteType (6 types), Permission (3 levels)
- ColumnCategory (7 categories), DataType (6 types), ConvictionLevel (1-5)
- 42+ configurable columns: price, volume, valuation (P/E, P/S, EV/EBITDA), fundamentals, technical (RSI, SMA), performance (1D-1Y), custom

### 6. Models (`src/watchlist/models.py`)
- **Watchlist** — Container with metadata (name, description, color, icon)
- **WatchlistItem** — Stock entry with targets, conviction, tags, notes; properties: gain_since_added, distance_to_targets
- **WatchlistView** — Display configuration (columns, sorting, filtering)
- **WatchlistAlert** — Alert definition with notification preferences
- **WatchlistNote** — Research note with type and tags
- **WatchlistShare** — Sharing record with permissions
- **WatchlistPerformance** — Hypothetical returns, win rate, targets hit

## Database Tables
- `watchlists` and `watchlist_items` referenced in workspace schema
- `watchlist_snapshots` — Historical watchlist state tracking (migration 089)
- `watchlist_activity_log` — User activity audit trail (migration 089)

## Dashboard
Streamlit dashboard (`app/pages/watchlist.py`) with tabs for watchlist management, alerts, and notes.

## Test Coverage
23 tests in `tests/test_watchlist.py` covering WatchlistItem (gain calculation, target distances), WatchlistManager (CRUD, duplicates, targets, search, filter, performance), AlertManager (creation, price triggers, non-triggers), NotesManager (notes, tags, search), SharingManager (user sharing, link sharing, access control, revocation).
