# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the `dev-workflow` plugin uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.3.5] - 2026-10-30

### Changed
- `secure-review`: semgrep findings no longer carry the autofix snippet (e.g. `True`) as their `fix`; `database.md` and `node-api.md` load triggers worded precisely; `web-frontend.md` split into `react.md` and `nextjs.md`, and `python.md` split into `python.md`, `django.md`, `flask.md` and `fastapi.md`; a project loads only the checklists for the frameworks it uses (Next.js also loads React, any framework also loads Python)

## [1.3.4] - 2026-10-30

### Removed
- `secure-review`: Capacitor and Electron detection and checklists (not used in this organisation); React Native and native iOS checks stay

## [1.3.3] - 2026-10-30

### Fixed
- `secure-review`: an unexpected crash in one scanner (install failure, bad output, unreadable file) no longer aborts the run; it is recorded as `failed` and the other tools still run. A repo with no recognised stack gets a note and the language-agnostic tools only; osv-scanner with no lockfile is `skipped` with a hint instead of `failed`

## [1.3.2] - 2026-10-30

### Removed
- `secure-review`: the "Business logic (A04)" section from `references/general.md`; it is out of scope for the skill

## [1.3.1] - 2026-10-29

### Changed
- `secure-review`: a verdict in `review.json` can set a finding's `title` and `fix`, so raw scanner wording is readable in the report; `full` mode reviews small repos in one pass instead of fanning out subagents

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

[Unreleased]: https://github.com/pruthvidarji1993/ai-automation-jira/compare/v1.3.5...HEAD
[1.3.5]: https://github.com/pruthvidarji1993/ai-automation-jira/compare/v1.3.4...v1.3.5
[1.3.4]: https://github.com/pruthvidarji1993/ai-automation-jira/compare/v1.3.3...v1.3.4
[1.3.3]: https://github.com/pruthvidarji1993/ai-automation-jira/compare/v1.3.2...v1.3.3
[1.3.2]: https://github.com/pruthvidarji1993/ai-automation-jira/compare/v1.3.1...v1.3.2
[1.3.1]: https://github.com/pruthvidarji1993/ai-automation-jira/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/pruthvidarji1993/ai-automation-jira/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/pruthvidarji1993/ai-automation-jira/releases/tag/v1.2.0
[1.1.0]: https://github.com/pruthvidarji1993/ai-automation-jira/releases/tag/v1.1.0
