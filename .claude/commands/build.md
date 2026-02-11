**Purpose**: Build new features, modules, or projects. Use when implementing PRDs, adding features, or creating new modules in the Axion platform.

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Build feature or module specified in $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/build --prd "PRD-180: New Module"` - Implement a PRD following standard pattern
- `/build --feature "add WebSocket auth"` - Add feature to existing module
- `/build --tdd "signal validation"` - Test-driven development

## Flags
--prd: "Full PRD implementation (source + tests + dashboard + migration + docs)"
--feature: "Add feature to existing module, maintaining patterns"
--tdd: "Write failing tests → implement → pass → refactor"
--init: "Initialize new module skeleton"

## Axion PRD Build Pattern
Each PRD produces 5 artifacts:
1. **Source**: `src/<module>/__init__.py` — dataclasses + business logic
2. **Tests**: `tests/test_<module>.py` — pytest class-based, aim for 40+ tests
3. **Dashboard**: `app/pages/<module>.py` — Streamlit with `st.tabs()`, typically 4 tabs
4. **Migration**: `alembic/versions/XXX_<name>.py` — chain to latest migration
5. **Docs**: `docs/PRD-XX-<name>.md` — requirements doc

## Module Conventions
- Models: dataclasses in `src/<module>/`; ORM records in `src/db/models.py`
- ORM: Class name `<Name>Record`, table name `<snake_name>` (check for collisions)
- Imports: Lazy-load heavy deps inside methods, `try/except ImportError` for optional deps
- Bridge pattern: Lightweight wrappers connecting modules (see `src/bot_pipeline/*_bridge.py`)

## Pre-Build Checklist
- Read existing module patterns: `src/` for conventions, `tests/` for test style
- Check ORM tablenames: grep `src/db/models.py` for duplicates
- Check migration chain: `alembic history -r-1:` for latest revision
- Check `app/nav_config.py` for dashboard registration

## Test Conventions
- Class-based: `class TestFeatureName:`
- Run: `python3 -m pytest tests/test_<module>.py -v`
- Mock pattern: Patch at import site, not definition site
- Time-dependent: Use `timeframe="1d"` to bypass market hours
