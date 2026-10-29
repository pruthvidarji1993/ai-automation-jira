# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the `dev-workflow` plugin uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.3.0] - 2026-10-29

### Added
- `secure-review`: new `references/database.md` (wildcard `SELECT *`/update mass assignment, migration quality: FKs, indexes, NULLs, N+1) and per-stack checks for mass assignment, CSRF, file upload (exact MIME allowlist, storage path), route inventory, API versioning and response constants
- `secure-review`: secrets in test code and fixtures; `diff` mode now also scans every commit since the base branch for secrets

### Changed
- `secure-review` stack checklists narrowed to the stacks the skill covers (Laravel for PHP, no Koa/Hono)

## [1.2.0] - 2026-10-29

### Added
- `secure-review` skill: a standalone security review (never chained into `/feature` and never started by Claude on its own). Detects the stack (Next.js, React, Node APIs, Python with Django/Flask/FastAPI, PHP, Capacitor, Electron, React Native, Docker), installs pinned scanners on first use (web-secure-verification, semgrep, gitleaks, bandit, pip-audit, osv-scanner), adds an AI review of what scanners miss, verifies every finding, and writes a self-contained, OWASP-mapped HTML report for clients with secret values redacted
- `npm run secure-review:test` and a CI step running the skill's self-check on Python 3.10
- MIT license, CI workflow, PR and issue templates, `CONTRIBUTING.md`, `SECURITY.md` and this changelog
- Animated pipeline overview and social preview image

### Changed
- README: consistent 9-stage wording, badges and a quick-start block

### Removed
- Unused Next.js starter assets from `public/`

## [1.1.0] - 2026-10-08

### Added
- Four model-routed subagents: `lead`, `scout`, `reviewer`, `reviewer-deep`
- Size and Risk routing, and "Done-when" criteria
- Opt-in push gate that blocks direct pushes to protected branches (`.claude/push-gate.conf`)

### Changed
- `lead` drafts the plan; "change impact" renamed

### Fixed
- Stale root-cause-analysis wording; marketplace version aligned; missing Copilot prompts flagged in the README

## [1.0.0] - 2026-09-28

### Added
- Claude Code plugin marketplace with the `dev-workflow` skills (debug, feature, implement, intake, plan, refactor, research, review, ship, test)
- README steps for installing and updating the plugin

## [0.1.0] - 2026-06-05

### Added
- Initial Jira automation flow and the Next.js sandbox app

[Unreleased]: https://github.com/pruthvidarji1993/ai-automation-jira/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/pruthvidarji1993/ai-automation-jira/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/pruthvidarji1993/ai-automation-jira/releases/tag/v1.2.0
[1.1.0]: https://github.com/pruthvidarji1993/ai-automation-jira/releases/tag/v1.1.0
