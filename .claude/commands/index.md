**Purpose**: SuperClaude Commands Reference. Use to see available commands and workflow patterns.

---

## Commands (20 total)
| Command | Purpose | Key Flags |
|---|---|---|
| `/analyze` | Read-only code/arch analysis | --code, --arch, --security, --perf |
| `/build` | Build features & PRDs | --prd, --feature, --tdd |
| `/cleanup` | Remove dead code & artifacts | --code, --files, --deps, --git, --dry-run |
| `/deploy` | Deploy with safety checks | --env, --rollback, --docker |
| `/design` | Architecture & API design | --api, --ddd, --prd |
| `/dev-setup` | Configure dev environment | --tools, --ci, --docker |
| `/document` | Generate documentation | --type, --format, --style |
| `/estimate` | Complexity & time estimates | --scope, --team, --detail |
| `/explain` | Teach concepts & code | --depth, --style, --visual |
| `/git` | Git workflows & commits | --commit, --pr, --flow, --pre-commit |
| `/improve` | Refactor & optimize code | --quality, --perf, --arch, --iterate |
| `/load` | Load project context | --scope, --focus, --format |
| `/migrate` | Alembic & code migrations | --up, --down, --create, --status |
| `/review` | Code review & quality | --files, --commit, --pr, --quality |
| `/scan` | Security & dependency audit | --security, --deps, --validate, --quick |
| `/spawn` | Parallel sub-agents | --parallel, --sequential, --explore |
| `/task` | Cross-session task mgmt | :create, :status, :resume, :complete |
| `/test` | Run & create tests | --tdd, --coverage, --unit, --integration |
| `/troubleshoot` | Debug & resolve issues | --performance, --memory, --bisect |

## Workflow Patterns
- **New PRD**: `/load` → `/design --prd` → `/build --prd` → `/test` → `/git --commit`
- **Feature**: `/analyze` → `/build --feature` → `/test` → `/review` → `/git --pr`
- **Debug**: `/troubleshoot` → `/test` → `/git --commit`
- **Quality**: `/review --quality` → `/improve` → `/scan --validate`
- **Deploy**: `/test --coverage` → `/scan --security` → `/deploy --env prod`

@include shared/flag-inheritance.yml#Universal_Always
