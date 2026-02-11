**Purpose**: Git workflow with checkpoint management. Use for commits, PRs, branch workflows, and pre-commit hook setup.

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Manage git workflows for $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/git --commit "Add user profile API endpoint"` - Commit with message
- `/git --pr --labels feature` - Create pull request
- `/git --flow feature "payment-integration"` - Feature branch workflow
- `/git --pre-commit` - Setup pre-commit hooks

## Flags
--commit: "Stage files, generate commit message, include co-author attribution"
--pr: "Create PR with description, reviewers, labels via gh CLI"
--flow: "Branch workflow: feature|hotfix|release"
--pre-commit: "Setup/run pre-commit hook framework"

## Axion Git Conventions
- **Branch**: `main` (primary), feature branches off main
- **Commits**: Imperative mood, reference PRD number if applicable
- **Co-author**: `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`
- **Repo**: `ghantakiran/axion-stock` on GitHub

## Safety (enforced by system prompt)
- NEVER force push, reset --hard, or amend published commits without confirmation
- NEVER skip hooks (--no-verify) unless explicitly requested
- Stage specific files by name, not `git add -A`
- Create NEW commits after hook failures (don't --amend)

@include shared/pre-commit-patterns.yml#Pre_Commit_Setup
