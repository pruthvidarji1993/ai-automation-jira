---
name: review
description: Structured review of a diff or PR. Produces findings categorized as critical / warning / info with a GO / NO-GO verdict. For medium/large diffs, a fresh-context reviewer (one combined agent, or parallel lens agents for high-complexity work) — the implementer must not review its own code. Use to review a PR, audit a local diff, or as step 7 of /feature.
---

# review

Sharp, actionable review without writing code. Evidence-based: every finding includes a `file:line` AND a one-line quote of the offending code.

## Inputs

- A review target:
  - `HEAD` — uncommitted + last commit (local diff)
  - `<branch>` — diff against `main` (or configured base)
  - `<PR#>` — fetched via `gh pr view <#> --json files,additions,deletions` + `gh pr diff <#>`
- Optional: `task_type` (tunes severity — bugfixes get harsher review of regression coverage).
- Optional: `size` and `complexity` (low/medium/high, from `/feature`). Together they drive reviewer isolation, below.
- Optional mode (from `/feature` Test ∥ Review): `collect <diff> findings=<…>`. The orchestrator already ran the fresh-context reviewer in the background, so don't spawn another one. Run 8.1, take the given findings into 8.2 step 3 (merge and severity mapping), hand criticals back to the orchestrator's consolidated fix pass (don't fix them here), then run 8.3–8.7. Without a mode, run the whole procedure in one go.

## Reviewer isolation

| Size      | Who reviews                                                                      |
|-----------|----------------------------------------------------------------------------------|
| trivial   | Inline (the orchestrator)                                                        |
| small     | Inline                                                                           |
| medium/large | **Fresh context required.** The implementer must NOT review its own code. 8.2's table decides one combined agent vs parallel lens agents. |

For agent-spawned reviews, the prompt must include: the full diff, the AC from intake, the plan, the file:line evidence requirement, and a strict instruction "do not write code — produce findings only."

## Procedure

### 8.1 Manual Code Review Checklist

Run these checks inline before spawning any agents:

- [ ] All changed files match the planned solution — no extra/missing changes
- [ ] No `any` types introduced — proper TypeScript types used throughout
- [ ] No leftover `console.log`, debug code, or commented-out code
- [ ] Follows existing codebase patterns (imports, naming, structure)
- [ ] No hardcoded values — uses env vars, constants, or config

### 8.2 Automated Review — lenses (parallel when it pays off)

The lenses are independent read-only analyses of the same diff. Reviewers
produce findings only. All fixes happen in **one consolidated pass**
afterwards, not one fix loop per tool.

**First decide how to run them** (see the Fan-out decision in `feature/parallelism.md`):

| Diff                                                        | Execution                                                         |
|-------------------------------------------------------------|-------------------------------------------------------------------|
| trivial/small                                               | **Inline:** one pass applying the applicable lens checklists yourself. No agents. |
| medium/large with low/medium complexity, or only 1–2 lenses apply | **One combined `Agent`** (`subagent_type: "general-purpose"`, `model: "opus"`) covering every applicable lens in a single fresh-context pass |
| High complexity with ≥ 3 applicable lenses                  | **Parallel:** one `Agent` per lens, spawned in a single message   |

Rows are checked top to bottom, and the first match wins.

Only spawn the lenses whose "Run when" condition is actually true for this
diff. Don't spawn a lens just to have it report "nothing applicable".

1. **Snapshot the diff** to a file (`git diff <base> > <scratchpad>/review.diff`,
   or reuse `impl.diff` from the orchestrator). Every lens reviews this one
   snapshot.
2. **Run the applicable lenses.** For agents, use `model: "opus"`. Use the
   `pr-review-toolkit` agent when it is installed. Otherwise use
   `general-purpose` with the lens checklist below.

   | Lens      | Agent (`subagent_type`)                         | Checks                                                                 | Run when                     |
   |-----------|-------------------------------------------------|------------------------------------------------------------------------|------------------------------|
   | code      | `pr-review-toolkit:code-reviewer`               | CLAUDE.md compliance, bugs, logic, null/undefined, races, security (confidence ≥ 80) | Always             |
   | errors    | `pr-review-toolkit:silent-failure-hunter`       | Empty catches, swallowed errors, missing user feedback, broad catches  | Diff adds/changes error handling, I/O, or async calls |
   | types     | `pr-review-toolkit:type-design-analyzer`        | Encapsulation, invariant expression/usefulness/enforcement (score /10) | New types introduced         |
   | comments  | `pr-review-toolkit:comment-analyzer`            | Comment accuracy vs code, stale/misleading comments                    | Comments added/changed       |
   | simplify  | `pr-review-toolkit:code-simplifier`             | Needless complexity, nested ternaries, redundancy, naming              | > ~50 LOC of new logic       |
   | react     | `general-purpose` (or `/react-doctor` inline)   | Hook rules, stale closures, deps, re-renders, keys                     | React components changed     |
   | tests     | `pr-review-toolkit:pr-test-analyzer`            | Behavioral coverage, critical paths, edge cases (gaps rated /10)       | **After** `test` finishes (needs the new tests) |
   | impact    | `Explore`                                       | §8.5: every importer/consumer of changed exports still works           | Changed exports have > 3 consumers |

   Every lens prompt must say: **"Findings only — do not edit any file or run
   git commands."** It must also include the diff path, the intake AC, the
   plan, and this return format for each finding:
   `[lens] <critical|warning|info> <file:line> — "<quote>" — issue — fix`.
   The lens applies the severity mapping in step 3 itself, before returning.
   (`code-simplifier` normally edits code. Its prompt must say to report the
   simplifications as findings instead.)
3. **Merge:** dedupe findings that hit the same `file:line` (keep the highest
   severity and note which lenses agreed). Map lens severities onto
   critical / warning / info:
   - **critical:** code-reviewer bugs/security; CRITICAL/HIGH silent failures; test gaps rated 8–10; type dimensions < 5/10; factually wrong comments; React hook-rule violations.
   - **warning:** everything else that should be fixed before merge.
   - **info:** optional simplifications and style.
4. **One fix pass:** inside `/feature`, hand the merged **critical** list to
   `implement` as a single feedback input. Warnings and info go into the PR
   body as `Follow-ups` and aren't fixed in this run (fixing them changes code
   after review and forces a re-review). When `review` is run standalone, fix
   criticals inline and list the warnings for the user.
5. **Targeted re-check:** re-run only the lenses that reported critical
   findings, against the new diff. Don't repeat the whole set.

| Merged result                                  | Action                                        |
|------------------------------------------------|-----------------------------------------------|
| 0 critical (warnings → PR follow-ups)          | Proceed to 8.3                                |
| Findings found, all fixed, targeted re-check clean | Proceed to 8.3                            |
| Finding needs a scope change                   | Document as known limitation, ask user        |
| Same critical survives two fix passes          | Escalate to user                              |

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

(Inside `/feature`, the `test` stage already ran the suite. Reuse its result and don't re-run unless the fix pass changed code.)

- [ ] Find all related tests: `find . -name "*FeatureName*.test.*"` (adjust pattern to ticket name)
- [ ] Existing tests still pass: run `npm test` or project-specific test command
- [ ] New/updated tests cover the changes made
- [ ] If tests fail — fix the CODE, not the test (unless requirements changed)

### 8.5 Impact Verification

(If the `impact` lens ran in 8.2, confirm its findings here. Otherwise do this inline.)

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

1. Return to `implement` and fix the issues. Inside `/feature`, don't loop on your own: return the merged findings, and the orchestrator runs one consolidated fix pass.
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
- Automated review (8.2) ran only the applicable lenses, in the execution mode the size table picks (inline / one agent / parallel with `model: "opus"`). Every lens was findings-only.
- Every finding in 8.3 has `file:line`, a quoted line, an issue, and a fix.
- The verdict matches the critical count (`GO` iff zero criticals).
- Plan's failure-mode table cross-check has been performed (note "none applicable" if no failure-mode table existed).
- 8.7 Summary Report is present at the end of the review output.

## Failure modes

- **Diff too large for a meaningful single pass:** split the review into chunks by file group; don't produce a shallow review. For PRs >1000 LOC, push back to the implementer to split.
- **Duplicates the test stage's reports:** dedupe; defer to whichever stage saw it first.
- **Reviewer is also the implementer (medium+):** stop and spawn a fresh-context Agent. Self-review on medium+ is not allowed.
- **pr-review-toolkit not installed:** run the same lenses as `general-purpose` agents (or inline) with the lens checklist from the 8.2 table. Note "toolkit not available — generic lenses".
- **A lens agent fails or returns uncited findings:** retry it once, then run that lens inline.
- **A lens edited files despite instructions:** files outside the snapshot's list that the `test` stage didn't create get deleted or reverted with `git checkout -- <file>`. Restore only the non-test files from the snapshot's file list to their snapshot state (`git apply` the snapshot onto a clean copy, or hand-revert). Never touch files the `test` stage created or edited. Keep only the lens's findings.
- **react-doctor not installed:** use the `general-purpose` react lens.
