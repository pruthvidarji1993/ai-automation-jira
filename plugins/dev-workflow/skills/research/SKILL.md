---
name: research
description: Codebase exploration and hypothesis validation. Auto-detect project conventions, trace lifecycles (sync + async), produce evidence-backed findings before planning. Use as step 2 of /feature, between intake and plan.
---

# research

Read the code before writing the plan. Evidence over conclusions.

## Inputs

- Intake output: `task_type`, `size`, `summary`, `acceptance_criteria`.
- Optional: explicit hypotheses to validate.
- Optional: `prefetched_conventions` — a `## Project conventions` block from the orchestrator's background scan. When present, skip Step 3 and only spot-check one citation. If the orchestrator says the scan is still running, don't spawn track B or do Step 3 yet. Wait for the scan before Step 5 (Verify). If it failed, do Step 3 inline then.

## Depth by size

| Size      | Steps run                                                | Execution                         |
|-----------|----------------------------------------------------------|-----------------------------------|
| `trivial` | skipped (orchestrator routes around this stage)          | —                                 |
| `small`   | Steps 1–3 + Step 5 happy-path only                       | Inline                            |
| `medium`  | All steps; full verification                             | Inline, unless complexity is high and ≥ 2 tracks apply |
| `large`   | All steps; full verification; cross-repo if applicable   | Inline, unless complexity is high and ≥ 2 tracks apply |

## Parallel tracks (high complexity only)

Steps 2–4 are independent reads, so they *can* run as concurrent `Explore`
agents. First decide whether they should (the Fan-out decision in `feature/parallelism.md`):

- **Low/medium complexity** → run Steps 2–4 inline. No agents.
- **High complexity:** pick the tracks whose "Spawn when" condition is true for **this** task.
- **Only 1 track applies, or the area is small** (single module, ≤ ~5 files to read) → run Steps 2–4 inline. No agents.
- **Only one track is substantial** → do it inline with parallel `Read`/`Grep`/`Bash` calls in one message. Never spawn one foreground agent and wait on it.
- **≥ 2 substantial tracks apply** → spawn just those tracks (`subagent_type: "Explore"`, thoroughness "very thorough") in **one message**.
- Record the decision, e.g. `research fan-out: A+C (async job) — B prefetched, D n/a`.

| Track | Covers               | Agent asks                                                                                       | Spawn when                         |
|-------|----------------------|--------------------------------------------------------------------------------------------------|------------------------------------|
| A     | Locate + impact      | Module dir, key components, every caller/consumer and importer of what's changing (3+ synonyms) | Always (inline if the area is small) |
| B     | Conventions + tests  | Step 3 conventions + existing tests for the affected module and how they're run                  | No `prefetched_conventions`, or tests are spread across many dirs |
| C     | Async lifecycle      | Step 4 trace: handler → service → hooks → jobs → push → client, with UX signals                  | Operation could be async           |
| D     | Cross-repo contract  | The other side of any API/schema/event contract the change touches                               | Large, or intake flags cross-team  |

Each agent prompt must include: the intake summary and AC verbatim, the
track's scope, the 3+ synonym search rule, "read-only — do not edit files or
run git commands", and the required return format:

```
### Track <X> findings
- <path:line> — <fact>   (every bullet cited)
### Open questions
- <…>
```

**Merge (inline, after all tracks return):**
1. Union the findings and dedupe by `path:line`.
2. Spot-check at least one citation per track by opening the cited line. If a citation is wrong, drop that finding and re-check the track's other claims.
3. Resolve conflicts between tracks by reading the code yourself. Don't pick a side without evidence.
4. Then run Step 5 (Verify) and Step 6 (Hypotheses) **inline**. Verification runs real commands and stays with the parent.

If a track agent fails or returns uncited claims, retry it once, then do that track inline.

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

### Independence hints (for the plan's parallel lanes)
- <file group> ↔ <file group>: <independent | coupled via path:line>

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
