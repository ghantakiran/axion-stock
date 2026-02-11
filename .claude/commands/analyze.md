**Purpose**: Read-only code and system analysis. Use for code review, architecture assessment, performance profiling, or security auditing without making changes (vs /improve for active refactoring).

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Analyze code, architecture, or system in $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/analyze --code src/bot_pipeline/` - Code quality review
- `/analyze --arch` - Full architecture analysis
- `/analyze --security src/api/` - Security audit on API layer
- `/analyze --perf src/db/models.py` - Performance analysis on ORM

## Flags
--code: "Quality: naming, structure, DRY, complexity | Bugs: null checks, boundaries, types"
--arch: "System design, layer coupling, scalability, maintainability"
--security: "OWASP top 10, auth, data handling, injection vectors"
--perf: "Algorithm complexity, DB queries, indexes, caching, N+1 detection"
--profile: "CPU, memory, execution time bottleneck identification"

## Analysis Output
For each finding, report:
- **Severity**: Critical / Major / Minor / Info
- **Location**: `file_path:line_number`
- **Issue**: What's wrong and why it matters
- **Suggestion**: How to fix (but don't implement — use /improve for that)

## Axion-Specific Focus Areas
- **ORM**: `src/db/models.py` — 218 tables, check for missing indexes, N+1 queries
- **API security**: `src/api/routes/` — auth middleware, input validation, rate limiting
- **Bot pipeline**: `src/bot_pipeline/orchestrator.py` — thread safety (RLock), kill switch
- **Signal chain**: ema_signals → trade_executor → options_scalper — data flow integrity
- **Bridge adapters**: `*_bridge.py` files — lazy-loading, ImportError fallbacks
