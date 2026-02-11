**Purpose**: Code review and quality analysis. Use for reviewing files, commits, or pull requests with optional persona specialization.

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Review code specified in $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/review --files src/bot_pipeline/` - Review bot pipeline code
- `/review --commit HEAD` - Review latest commit changes
- `/review --pr 123 --quality` - Quality-focused PR review
- `/review --files src/api/ --persona-security` - Security review of API

## Flags
--files: "Review specific files or directories"
--commit: "Review changes in commit (HEAD, hash, or range)"
--pr: "Review PR changes (diff main..branch)"
--quality: "Focus on DRY, SOLID, complexity"
--evidence: "Cite sources for all suggestions"
--fix: "Include specific fix suggestions"
--summary: "Generate executive summary"

## Persona Specialization
--persona-security: "Vulnerabilities, injection, auth, data exposure"
--persona-performance: "N+1 queries, algorithm complexity, caching, memory"
--persona-architect: "Design patterns, coupling, module boundaries, tech debt"
--persona-qa: "Test coverage, edge cases, validation strategies"

## Review Process
1. Read all changed files and understand context
2. Scan across quality, security, performance dimensions
3. Report findings with severity, location (`file:line`), and fix suggestion
4. Prioritize: Critical → Major → Minor → Info

## Axion Review Focus
- **ORM**: Check `src/db/models.py` changes for tablename collisions, missing indexes
- **Migrations**: Verify `down_revision` chain integrity
- **Thread safety**: Bot pipeline uses RLock — verify concurrent access patterns
- **Mock targets**: Patch at import site (`from src.x import y` → patch `module.y`)
- **Test coverage**: Each PRD targets 40+ tests in `tests/test_<module>.py`
