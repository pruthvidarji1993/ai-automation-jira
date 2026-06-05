---
name: review
description: Structured review of a diff or PR. Produces findings categorized as critical / warning / info with a GO / NO-GO verdict. For medium/large diffs, spawn a fresh-context reviewer agent — the implementer must not review its own code. Use to review a PR, audit a local diff, or as step 7 of /feature.
---

# review

Sharp, actionable review without writing code. Evidence-based: every finding includes a `file:line` AND a one-line quote of the offending code.

## Inputs

- A review target:
  - `HEAD` — uncommitted + last commit (local diff)
  - `<branch>` — diff against `main` (or configured base)
  - `<PR#>` — fetched via `gh pr view <#> --json files,additions,deletions` + `gh pr diff <#>`
- Optional: `task_type` (tunes severity — bugfixes get harsher review of regression coverage).
- Optional: `size` (drives reviewer isolation, below).

## Reviewer isolation

| Size      | Who reviews                                                                      |
|-----------|----------------------------------------------------------------------------------|
| trivial   | Inline (the orchestrator)                                                        |
| small     | Inline                                                                           |
| medium    | **Fresh-context Agent.** Spawn with `subagent_type: "general-purpose"` and pass the diff + this skill's procedure. The implementer must NOT review its own code. |
| large     | Same as medium                                                                   |

For agent-spawned reviews, the prompt must include: the full diff, the AC from intake, the plan, the file:line evidence requirement, and a strict instruction "do not write code — produce findings only."

## Procedure

1. **Load the diff.** Use `git diff <base>...<branch>` or `gh pr diff <#>`.

2. **Apply the four quality pillars:**
   - **Validation:** are inputs checked at every external boundary?
   - **Global impact:** does this change ripple in non-obvious ways?
   - **Pattern consistency:** does the change follow the codebase's idioms?
   - **Logic vs syntax:** is the code doing the right thing, not just compiling?

3. **Categorize findings:**
   - **critical** — must fix before merge (bug, security, data loss, contract break, missing rescue on a user-facing failure path).
   - **warning** — should fix before merge (perf, ergonomics, missing tests).
   - **info** — noted, not blocking (style, opportunistic cleanup).

4. **Each finding includes:**
   - `file:line` reference
   - one-line quote of the offending code
   - one-sentence issue
   - one-sentence fix

5. **Cross-check against the plan's failure-mode table.** Any row marked `Rescued = NO + User sees = Silent` that wasn't addressed in the diff → automatic critical.

6. **Pick a verdict:**
   - `GO` if zero critical findings.
   - `NO-GO` otherwise.

## Output

```
## Review findings — <GO|NO-GO>  (<critical> critical / <warning> warning / <info> info)

### Critical
- <file:line>
  `<one-line quote>`
  Issue: <one sentence>
  Fix: <one sentence>

### Warning
- <file:line>
  `<one-line quote>`
  Issue: <one sentence>
  Fix: <one sentence>

### Info
- <file:line>
  `<one-line quote>`
  Issue: <one sentence>
  Fix: <one sentence>
```

## Verification

- Every finding has `file:line`, a quoted line, an issue, and a fix.
- The verdict matches the critical count (`GO` iff zero criticals).
- Plan's failure-mode table cross-check has been performed (note "none applicable" if no failure-mode table existed).

## Failure modes

- **Diff too large for a meaningful single pass:** split the review into chunks by file group; don't produce a shallow review. For PRs >1000 LOC, push back to the implementer to split.
- **Duplicates the test stage's reports:** dedupe; defer to whichever stage saw it first.
- **Reviewer is also the implementer (medium+):** stop and spawn a fresh-context Agent. Self-review on medium+ is not allowed.
