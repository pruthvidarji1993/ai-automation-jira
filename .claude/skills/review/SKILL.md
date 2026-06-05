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

### 8.1 Manual Code Review Checklist

Run these checks inline before spawning any agents:

- [ ] All changed files match the planned solution — no extra/missing changes
- [ ] No `any` types introduced — proper TypeScript types used throughout
- [ ] No leftover `console.log`, debug code, or commented-out code
- [ ] Follows existing codebase patterns (imports, naming, structure)
- [ ] No hardcoded values — uses env vars, constants, or config

### 8.2 Automated Review Pipeline

**Run these review tools sequentially. Fix ALL issues from a tool before running the next.**

Spawn each agent with `model: "claude-opus-4-8"` explicitly — do not inherit the session model.

#### Step 1: General Code Review (`/pr-review-toolkit:review-pr code`)

Invoke the `pr-review-toolkit:review-pr` skill with arg `code`. This runs the `code-reviewer` agent (Opus, confidence ≥ 80). Checks: CLAUDE.md compliance, bug detection, logic errors, null/undefined risks, race conditions, security. **Fix all reported issues before Step 2.**

#### Step 2: Silent Failure Hunter (`/pr-review-toolkit:review-pr errors`)

Invoke the `pr-review-toolkit:review-pr` skill with arg `errors`. Checks: empty catch blocks, swallowed errors, missing user feedback, broad catches, unjustified fallbacks. **Zero tolerance for CRITICAL and HIGH silent failures — fix all before Step 3.**

#### Step 3: Test Coverage Analysis (`/pr-review-toolkit:review-pr tests`)

Invoke the `pr-review-toolkit:review-pr` skill with arg `tests`. Checks: behavioral coverage, critical code paths, edge cases, missing error handling tests. **Add any missing tests rated 8–10 (critical gaps) before Step 4.**

#### Step 4: Type Design Review (`/pr-review-toolkit:review-pr types`)

Invoke only if new types were introduced. Checks: encapsulation, invariant expression, invariant usefulness, invariant enforcement. **Fix any dimension rated below 5/10 before Step 5.**

#### Step 5: Comment Quality (`/pr-review-toolkit:review-pr comments`)

Invoke the `pr-review-toolkit:review-pr` skill with arg `comments`. Checks: factual accuracy of comments vs code, stale/misleading comments. **Fix any CRITICAL issues (factually incorrect comments) before Step 6.**

#### Step 6: Code Simplification (`/pr-review-toolkit:review-pr simplify`)

Invoke the `pr-review-toolkit:review-pr` skill with arg `simplify`. Checks: unnecessary complexity, nested ternaries, redundant code, unclear naming. **Apply simplifications that improve readability without changing behaviour.**

#### Step 7: React Doctor (`/react-doctor`)

Invoke only if React components were changed. Checks: hook rule violations, stale closures, missing deps, re-render issues, key prop issues. **Fix all React-specific issues before proceeding.**

#### Automated Review Decision Matrix

| Tool result | Action |
|---|---|
| 0 issues found | Proceed to next tool |
| Issues found, all fixed | Re-run the same tool to verify, then proceed |
| Issues found, can't fix without scope change | Document as known limitation, ask user |
| All 8.2 steps pass | Proceed to 8.3 |

### 8.3 Standard Review Pillars

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

### 8.4 Test Verification

- [ ] Find all related tests: `find . -name "*FeatureName*.test.*"` (adjust pattern to ticket name)
- [ ] Existing tests still pass: run `npm test` or project-specific test command
- [ ] New/updated tests cover the changes made
- [ ] If tests fail — fix the CODE, not the test (unless requirements changed)

### 8.5 Impact Verification

- [ ] Re-check all files that import/use the changed code
- [ ] No unintended side effects on other features
- [ ] Shared components still work for all consumers

### 8.6 Acceptance Criteria Check

- [ ] Go back to the Jira ticket requirements from intake
- [ ] Verify each acceptance criterion is met
- [ ] If Figma mocks exist — verify UI matches the design

### 8.7 Summary Report

Present this table before handing back to the orchestrator:

| Item | Status |
|---|---|
| **Files Changed** | List of modified files |
| **Tests** | Passing / Failing / New tests added |
| **Automated Reviews** | All passed / Issues remaining (list) |
| **Acceptance Criteria** | All met / Partially met (explain) |
| **Side Effects** | None / List any found |
| **Ready for PR** | Yes / No (what's blocking) |

### 8.8 Failure Loop

If any step in this procedure fails:

1. Return to `implement` and fix the issues.
2. Re-run the failed step (and all subsequent steps).
3. Only proceed to `ship` when ALL checks pass.
4. If blocked on a check that requires scope expansion — stop and ask the user before continuing.

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

- Manual checklist (8.1) completed before spawning any agents.
- Automated review pipeline (8.2) ran all applicable steps with Opus model.
- Every finding in 8.3 has `file:line`, a quoted line, an issue, and a fix.
- The verdict matches the critical count (`GO` iff zero criticals).
- Plan's failure-mode table cross-check has been performed (note "none applicable" if no failure-mode table existed).
- 8.7 Summary Report is present at the end of the review output.

## Failure modes

- **Diff too large for a meaningful single pass:** split the review into chunks by file group; don't produce a shallow review. For PRs >1000 LOC, push back to the implementer to split.
- **Duplicates the test stage's reports:** dedupe; defer to whichever stage saw it first.
- **Reviewer is also the implementer (medium+):** stop and spawn a fresh-context Agent. Self-review on medium+ is not allowed.
- **pr-review-toolkit not installed:** skip 8.2 steps that require it, note as "not available", and proceed with 8.3 manual review.
- **react-doctor not installed:** skip 8.2 Step 7, note as "not available".
