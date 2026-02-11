**Purpose**: Evidence-based code enhancement and optimization. Use when actively refactoring code (vs /analyze for read-only analysis, vs /cleanup for removing dead code).

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Improve code quality, performance, or architecture in $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/improve --quality src/bot_pipeline/` - Refactor for readability & maintainability
- `/improve --perf --iterate --threshold high` - Optimize until threshold met
- `/improve --arch --safe` - Conservative architecture refactoring
- `/improve --refactor src/db/models.py` - Safe refactoring preserving behavior

## Flags
--quality: "Readability, maintainability, DRY improvements"
--perf: "Algorithm, query, caching optimizations"
--arch: "Design patterns, coupling, module boundaries"
--refactor: "Safe behavior-preserving refactoring"
--iterate: "Iterative improvement cycles until --threshold met"
--threshold: "Quality target: low|medium|high|perfect"
--metrics: "Show before/after metrics"
--safe: "Conservative mode — only changes with zero risk of behavior change"

## Process
1. **Analyze**: Read target code, identify improvement areas, prioritize by impact
2. **Plan**: Design safe refactoring path with rollback strategy
3. **Implement**: Small atomic changes, continuous testing between changes
4. **Validate**: Run tests (`python3 -m pytest`), verify no regressions

## Axion-Specific Patterns
- **ORM improvements**: `src/db/models.py` is 5280 lines — extract shared mixins carefully
- **Bridge pattern**: `src/bot_pipeline/*_bridge.py` — keep wrappers lightweight
- **Lazy imports**: Heavy deps (ML, broker SDKs) must use lazy-load pattern
- **Test impact**: Always run `python3 -m pytest tests/test_<module>.py -v` after changes
