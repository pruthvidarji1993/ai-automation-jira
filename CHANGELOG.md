# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the `dev-workflow` plugin uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
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

[Unreleased]: https://github.com/pruthvidarji1993/ai-automation-jira/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/pruthvidarji1993/ai-automation-jira/releases/tag/v1.1.0
