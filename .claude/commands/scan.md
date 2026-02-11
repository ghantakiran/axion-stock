**Purpose**: Security audits, dependency scanning, and code validation. Use for security reviews, vulnerability detection, or pre-deploy validation.

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Scan code in $ARGUMENTS for security, quality, and dependency issues.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/scan --security src/api/` - Security scan on API layer
- `/scan --deps` - Dependency vulnerability audit
- `/scan --validate` - Full validation scan
- `/scan --quick` - Critical issues only

## Flags
--security: "OWASP top 10, injection, auth flaws, hardcoded secrets, CVEs"
--deps: "Dependency vulnerabilities, outdated packages, license compliance"
--validate: "Comprehensive validation: syntax, types, logic, security"
--quick: "Fast scan — critical security only"
--fix: "Auto-fix safe issues"
--strict: "Zero-tolerance mode (fail on any finding)"
--report: "Generate detailed report to .claudedocs/scans/"
--ci: "CI-friendly exit codes and JSON output"

## Validation Levels
- **Quick** (--quick): Hardcoded secrets, SQL injection, XSS, known CVEs
- **Standard** (default): All security + major quality + dependency vulnerabilities
- **Strict** (--strict): Everything + minor issues, style, coverage, performance warnings

## Axion Security Focus
- **API routes**: `src/api/routes/` — auth middleware, input validation, rate limiting
- **Broker credentials**: Ensure no API keys in source — check `.env`, broker config files
- **WebSocket**: `src/api/routes/bot_ws.py` — auth on connect, channel access control
- **Encryption**: Fernet for secrets vault (`src/secrets_vault/`), no MD5/pickle in auth paths
- **CI tools**: bandit (SAST), pip-audit (deps) — configured in GitHub Actions
