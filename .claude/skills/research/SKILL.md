---
name: research
description: Codebase exploration and hypothesis validation. Auto-detect project conventions, trace lifecycles (sync + async), produce evidence-backed findings before planning. Use as step 2 of /feature, between intake and plan.
---

# research

Read the code before writing the plan. Evidence over conclusions.

## Inputs

- Intake output: `task_type`, `size`, `risk`, `summary`, `acceptance_criteria`. A missing `risk` means `high` - score up, never down.
- Optional: explicit hypotheses to validate.

## Depth by size

| Size      | Steps run                                                |
|-----------|----------------------------------------------------------|
| `trivial` | skipped (orchestrator routes around this stage)          |
| `small`   | Steps 1–3 + Step 5 happy-path only                       |
| `medium`  | All steps; full verification                             |
| `large`   | All steps; full verification; cross-repo if applicable   |

## Parallel lookups

Step 2 is serial because each search depends on the last. The cross-cutting checks below do not depend on each other, so dispatch them together in **one message, one `Agent` call per layer** (`subagent_type: "scout"`, read-only, `omitClaudeMd`). Paste any project rules that matter into each prompt; scouts do not load `CLAUDE.md`. Every lookup returns 10 lines or fewer with `file:line` evidence.

Agent names are written bare (`scout`). Installed as a plugin they appear as `dev-workflow:scout`; pass whichever name your agent list shows.

| Size      | Dispatch                                                              |
|-----------|-----------------------------------------------------------------------|
| `trivial` | none                                                                  |
| `small`   | none - search inline                                                  |
| `medium`  | only the 1-3 layers the task plausibly touches                        |
| `large`   | every layer below, plus the contract check when an endpoint is in play |

`risk: high` always adds the **auth / permissions** lookup, whatever the size.

Layers: **data fetching and cache** (how data is loaded, cached, invalidated) · **auth / permissions** (who may do this, where it is enforced) · **config and flags** (env, feature flags, defaults) · **shared components and utilities** (what already exists to reuse) · **API contract** (the other side of the call: request shape, errors, status codes).

Root-cause judgment is not delegated to a scout. You make the call from their evidence.

## Procedure

### Step 1 — Preflight

- List relevant skills/tools available for the task.
- If the operation could be async (request → service → callbacks → background jobs → push/broadcast → client), plan to trace the full lifecycle.
- Check `CLAUDE.md`, `AGENTS.md`, and any `.github/instructions/` for constraints. Heed deprecation notices.

### Step 2 — Explore

1. Search the codebase with **3+ synonym terms** — never rely on one search term.
2. Identify the module directory, key components, callers, and consumers.
3. Trace imports for impact analysis: what depends on what is changing.
4. Find related tests.
5. Cross-repo: if the task touches API contracts, check the other side.

### Step 3 — Auto-detect conventions

Use `Glob` and `Grep` to detect: language, framework, styling approach, state management, test runner, package manager. Record as `## Project Conventions`. Do not hardcode assumptions — read the repo.

### Step 4 — Async lifecycle tracing (when applicable)

Trace: handler → service → callbacks/hooks → background jobs → push/broadcast → client. Do NOT conclude "synchronous" because the handler returns a response; check for post-commit side effects.

UX signal checklist: existing toast messages, loading states, polling patterns, retry/timeout handling.

### Step 5 — Verify (mandatory medium/large; happy-path only small)

- **Run it, don't just read it.** Execute the operation locally; capture real output. No "the code looks like it should work."
- **Verify happy path with real output.** Error path for medium/large.
- **Extract every requirement.** Quote specs/AC directly — do not interpolate.
- **Map integration points.** Inputs, outputs, reusable code, feature flags or gating.
- **Cite every claim.** Each claim has a `file:line` reference or the command that produced it.

### Step 6 — Hypotheses

State 2–3 hypotheses about the approach. Mark each `validated | refuted | open` with the evidence.

## Output

```
## Research findings

### Project conventions
<language, framework, styling, test runner, package manager>

### Files to change
- <path:line> — <current behavior; what is wrong or missing>

### Async concerns
<lifecycle trace; "n/a" if synchronous>

### Hypotheses
| # | Hypothesis | Status                  | Evidence       |
|---|------------|-------------------------|----------------|
| 1 | …          | validated/refuted/open  | <file:line>    |

### Open questions
- <anything that requires user input before planning>
```

## Verification

- At least one `file:line` reference per "Files to change" entry.
- Every claim has a citation (`file:line` OR command output).
- If the operation is async-capable: a lifecycle trace exists.
- Project conventions block is filled (not "tbd").

## Rules

| Rule                       | Detail                                                |
|----------------------------|-------------------------------------------------------|
| 3+ synonym searches        | Never trust one search term                           |
| Evidence over conclusions  | Paste output; do not say "should work"                |
| Quote specs directly       | No interpolation                                      |
| Trace full lifecycle       | Do not stop at the controller for async ops           |
| No fabricated detail       | If you do not know, write "unknown" + plan to verify  |

## Failure modes

- **Search returns nothing on the first term:** widen with 2+ more synonyms before concluding "feature doesn't exist."
- **Convention auto-detect picks up legacy files:** check `package.json` / config files for the project's *target* conventions, not just neighboring code.
- **Async operation looks synchronous:** verify by reading post-response code paths (callbacks, jobs, hooks). Reading only the handler is insufficient.
