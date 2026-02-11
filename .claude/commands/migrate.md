**Purpose**: Database and code migration management. Use for Alembic schema migrations, data transformations, or framework upgrades.

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Execute migrations for $ARGUMENTS with safety checks and rollback.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/migrate --up` - Apply all pending Alembic migrations
- `/migrate --down --step 2` - Rollback last 2 migrations
- `/migrate --create "add_user_preferences"` - Generate new migration
- `/migrate --status` - Show current migration state
- `/migrate --validate` - Dry-run without applying

## Flags
--up: "Apply forward: `alembic upgrade head`"
--down: "Rollback: `alembic downgrade -N`"
--create: "Generate: `alembic revision --autogenerate -m MSG`"
--status: "Check state: `alembic current` + `alembic history`"
--validate: "Test in transaction then rollback"
--step: "Number of migrations to apply/rollback"
--data: "Data transformation migration (not schema)"

## Axion Migration Rules (176 migrations)
- **Chain**: Each migration's `down_revision` must point to the previous migration's `revision`
- **Current chain tail**: migration 178 (check `alembic history -r-1:` for latest)
- **ORM file**: `src/db/models.py` (~5280 lines, 218 tables)
- **Reserved word**: Column named `metadata` must use `extra_metadata = Column("metadata", Text, ...)`
- **Table collisions**: Check existing tablenames before creating new ones (e.g., `trade_executions` already exists)

## Pre-Migration Checklist
1. `alembic current` — verify current revision
2. `alembic history -r-1:` — get latest revision hash for down_revision
3. Review generated migration file — autogenerate misses: enum changes, data migrations, index renames
4. `alembic upgrade head --sql` — preview SQL without executing
5. After apply: `python3 -m pytest tests/ -x` — verify no ORM breakage

## Common Commands
```bash
alembic upgrade head                    # Apply all pending
alembic downgrade -1                    # Rollback one
alembic current                         # Show current
alembic history --verbose -r-5:         # Last 5 migrations
alembic revision --autogenerate -m MSG  # New migration
alembic upgrade head --sql              # Preview SQL only
```

## Known Issues
- **Chain breaks**: Background agents setting independent `down_revision` values. Always provide explicit down_revision.
- **Duplicate tablenames**: PRD-60/PRD-142 collision on `notification_preferences`. Always grep models.py before adding tables.
- **Alembic env.py**: Uses `target_metadata = Base.metadata` from `src/db/models.py`.
