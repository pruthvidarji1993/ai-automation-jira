---
name: secure-review
description: Standalone security review for any repository. Detects the stack (Next.js, React, Node API, Python with Django/Flask/FastAPI, PHP, Capacitor, Electron, React Native, Docker), installs pinned scanners on first use, runs them, adds an AI review of what scanners cannot see (access control, IDOR, mass assignment, session, SSRF, CSRF, file upload, injection, migrations, N+1, API versioning, platform risks), verifies every finding, and writes a developer findings list plus a self-contained HTML client report mapped to OWASP Top 10. Run manually with /secure-review [diff|full|deps] [--base <ref>].
argument-hint: '[diff|full|deps] [--base <ref>]'
disable-model-invocation: true
---

# Secure Review

Standalone: not part of any other review or pipeline. Copy this folder into any
repo's `.claude/skills/` and run `/secure-review`.

Arguments: `$ARGUMENTS`

| Mode             | Scope                                          | Use                         |
| ---------------- | ---------------------------------------------- | --------------------------- |
| `diff` (default) | Files changed vs base + uncommitted, secrets in commits since base, deps if a manifest changed | Before opening a PR |
| `full`           | Whole repo, secrets across full git history    | Audit, client deliverable   |
| `deps`           | Dependencies, licenses, supply chain only      | After a dependency change   |

`--base <ref>` overrides the diff base; otherwise the closest of
`origin/develop`, `origin/main`, `origin/master` is used.

## Requirements

- `python3` 3.10+ and `git`. Node.js 18+ with `npx` for JS/TS projects.
- Network on first run. Tools install **once, outside the project**, into
  `~/.cache/secure-review` (override with `SECURE_REVIEW_HOME`):
  pip-audit, bandit and semgrep in a private venv; gitleaks from `PATH` if it
  is 8.19+, else the release binary (SHA-256 checked against the release
  checksums), else `brew install gitleaks` when GitHub downloads are blocked;
  osv-scanner the same way, only when a PHP (`composer.lock`) or iOS
  CocoaPods project is detected. `web-secure-verification`
  runs through `npx` at a pinned version. Nothing is added to the project's
  `package.json`, requirements or lockfiles.
- Reports go to `<repo>/.secure-review/<timestamp>/`, kept out of git through
  `.git/info/exclude` (local only - the project's `.gitignore` is not touched).

The runner is `scripts/secure_review.py` in this skill's base directory (shown
when the skill loads). Below it is written `$SR`.

## 1. Scan

```bash
python3 "$SR" scan --mode <mode> [--base <ref>]
```

Run it in the background for `full` on a large repo; the first run also
installs tools (a few minutes, mostly semgrep). It prints the output
directory, the detected stacks, each tool's status and raw counts. Read
`<out>/scan.json` only as needed - it can be large.

If a JS project shows `node_modules missing`, **do not install dependencies
yourself** - install scripts run arbitrary code. Tell the developer, continue
with the other tools, and list it under limitations.

## 2. AI review - what scanners miss

Load only the checklists for the detected stacks (`references/` next to this
file):

| Stack in `scan.json`                     | Checklist                        |
| ---------------------------------------- | -------------------------------- |
| always                                   | `references/general.md`          |
| the project has queries, models or migrations (any ORM or SQL) | `references/database.md` |
| `react`, `next`                          | `references/web-frontend.md`     |
| `node-api`, `next` (route handlers, server actions) | `references/node-api.md` |
| `python`, `django`, `flask`, `fastapi`   | `references/python.md`           |
| `capacitor`, `electron`, `react-native`, `ios` | `references/mobile-desktop.md` |
| `php`                                    | `references/php.md`              |

No stack detected, or a stack not listed: still apply `general.md` - semgrep's
OWASP rules and gitleaks run on any language. Say in `limitations` which
stack-specific checks were not available.

- Also read the project's route files, migrations and test/fixture folders
  (secrets in tests, route inventory, migration quality, N+1) - scanners do not
  cover them, and they are not always in the diff for `full`.
- **`diff`**: read every changed file in full (not just hunks), and follow
  changed server code to its callers and the data it touches. Apply the
  loaded checklists.
- **`full`**: fan out read-only subagents in parallel, one per loaded
  checklist (split `general.md` from the stack lists). Give each the checklist
  path, the project paths from `scan.json`, and this contract: return at most
  15 findings, each with `file:line`, the concrete input or state that exploits
  it, and severity. Read entry points first (routes, API handlers, middleware,
  auth, config) - do not read the whole repo.

## 3. Verify - every finding, before it is reported

A review that cries wolf gets ignored, and then the real finding gets ignored
with it.

- **Critical and high**: open the file, confirm the line, and construct the
  exploit - who sends what, and what they get. If you cannot, it is a
  `suspicion` or a `false-positive`, not `confirmed`.
- **Medium and low**: verify one instance per rule, then give the rule a
  verdict (`rules` below) instead of checking hundreds of identical hits.
- **Duplicates** (the same secret from gitleaks and web-secure-verification,
  or the same sink from semgrep and the AI review): keep one, mark the other
  `false-positive` with the note `duplicate of Fxxx`.
- **Recalibrate** scanner severity to real exposure: `eval` on a constant is
  not critical; an IDOR on invoices is. Test fixtures, mocks and example keys
  are false positives.
- **Never write a secret value** - in chat, in `review.json` notes, titles or
  fixes, or in the summary - even weak or placeholder ones like `secret123` or
  `dev`. Write "the hardcoded JWT secret in server.js:7", never the value.
  (The report step also redacts literals on flagged lines as a safety net.)
- Do not manufacture findings. "Nothing found in this area" is a valid result.

## 4. Write `<out>/review.json`

```json
{
  "summary": {
    "executive": "3-6 sentences for a non-technical client: overall posture, the most serious risks in business terms, what to do first. Blank line between paragraphs.",
    "scope": "What was reviewed: mode, stacks, projects.",
    "limitations": "Tools that did not run and why, areas not reviewed, anything assumed."
  },
  "verdicts": { "F003": { "status": "confirmed", "severity": "high", "note": "Reachable from POST /api/upload without auth" } },
  "rules": { "semgrep:<check_id>": { "status": "false-positive", "note": "Only used on constant strings" } },
  "added": [
    { "rule": "idor", "severity": "critical", "title": "Any user can read any order",
      "file": "src/app/api/orders/[id]/route.ts", "line": 12, "owasp": "A01", "cwe": "CWE-639",
      "detail": "GET loads the order by id without checking it belongs to the session user.",
      "fix": "Filter the query by session.userId and return 404 otherwise." }
  ]
}
```

`status` is `confirmed`, `suspicion` or `false-positive`; findings with no
verdict show as `unverified`. Rule keys are `<source>:<rule>` exactly as in
`scan.json`. `added` holds the AI review's verified findings; `owasp` is the
2021 id (`A01`-`A10`). Privacy, licensing and other client-facing compliance
observations (see `general.md`) go in `added` with `"category": "compliance"`;
the report lists them separately from code defects.

Write the executive summary for the client, not the developer: what could
happen to their users, data or money, how likely it is, and what to do first.
No tool names, no CWE numbers, no file paths.

## 5. Report

```bash
python3 "$SR" report --dir <out>
```

Writes `<out>/report.html` - one self-contained file (no external assets,
light and dark, prints cleanly to PDF) that can be emailed to a client - and
prints the developer list.

## 6. Reply

- Overall risk and counts by severity.
- The developer list: `[SEVERITY] file:line - issue - fix` for confirmed
  findings, then suspicions labelled as such. In `diff` mode note that
  pre-existing findings outside the diff are excluded and not blocking.
- Tools that were skipped or failed, with the reason.
- The report path.

Do not fix code, commit, or push unless asked. Never run
`web-secure-verify scan --fix` - it edits files interactively.
