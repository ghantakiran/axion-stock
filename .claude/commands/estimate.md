**Purpose**: Estimate complexity, effort, and time for tasks. Use when planning features, PRDs, or refactoring scope.

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Estimate effort for $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/estimate "Add WebSocket auth"` - Quick feature estimate
- `/estimate --scope prd --detail high "PRD-180: New Strategy"` - Detailed PRD estimate
- `/estimate --scope refactor "src/db/models.py"` - Refactoring effort

## Flags
--scope: "feature|epic|prd|refactor|migration"
--team: "solo|small (2-3)|medium (4-8)|large (9+)"
--detail: "low (rough)|medium (standard)|high (detailed breakdown)"

## Axion Estimation Baselines
Based on 179 implemented PRDs:
- **Simple PRD** (single module, no cross-refs): ~40 tests, 5 files → solo, 1 session
- **Medium PRD** (cross-module bridges, ORM changes): ~60 tests, 8 files → solo, 2 sessions
- **Complex PRD** (multi-broker, pipeline integration): ~80+ tests, 12+ files → solo, 3+ sessions
- **Migration**: Alembic schema change → 15 min; data migration → varies by table size
- **Dashboard page**: Streamlit with 4 tabs → ~200 lines, 30 min

## Estimation Output
Provide for each task:
- **Complexity**: Low / Medium / High / Very High
- **Files affected**: List with estimated change scope
- **Test count**: Expected new tests
- **Risks**: Known pitfalls (ORM collisions, migration chain, mock patterns)
