# PRD-110: Migration Safety & Reversibility

## Overview
Create a migration validation framework that ensures all Alembic migrations are safe, reversible, and tested before deployment. Many existing migrations lack proper downgrade() implementations, and there's no automated verification of migration safety.

## Goals
1. **Migration Validator** — Static analysis of migration files for common issues (missing downgrade, destructive operations, missing indexes)
2. **Pre-Migration Checks** — Verify database state before applying migrations
3. **Post-Migration Verification** — Confirm schema matches expected state after migration
4. **Rollback Testing** — Automated upgrade/downgrade cycle testing
5. **Migration Linting** — CI-integrated linting rules for migration files

## Technical Design

### Components
- `src/migration_safety/__init__.py` — Public API exports
- `src/migration_safety/config.py` — Safety rules configuration, severity levels
- `src/migration_safety/validator.py` — MigrationValidator (AST-based analysis of migration files)
- `src/migration_safety/checks.py` — Pre/post migration check implementations
- `src/migration_safety/linter.py` — MigrationLinter with configurable rules
- `src/migration_safety/reporter.py` — Validation report generation (JSON, text, HTML)

### Database
- `migration_audit` table for recording migration execution history

### Dashboard
- Migration history, validation results, safety scores, linting issues

## Success Criteria
- All migrations are validated for presence of downgrade()
- Destructive operations (DROP TABLE, DROP COLUMN) are flagged
- Migration lint integrated into CI pipeline
- 40+ tests covering validation rules and reporting
