---
name: implement
description: Execute an approved plan as code changes on a feature branch. Verify each step before advancing; changes stay uncommitted for ship. For high-complexity plans with parallel lanes, runs one agent per lane concurrently on disjoint file sets. Use after plan approval, or as step 4 of /feature.
---

# implement

Turn the approved plan into reviewed-quality code on a feature branch.

## Inputs

- The approved plan from the `plan` skill (with quality analysis + failure-mode table).
- Research findings (file:line references + project conventions).
- Optional: user feedback (set on rerun after GATE 2 → "Request changes" or manual-test → "Fail — apply fixes"). Treat as override-priority guidance.

## Procedure

1. **Preflight.**
   - `git fetch origin`.
   - Determine the PR target branch. Default to `main` unless `gh repo view --json defaultBranchRef -q .defaultBranchRef.name` returns something else.
   - Derive the branch name using the [Branch naming](#branch-naming) convention below.
   - Check whether the branch already exists (local or remote): `git rev-parse --verify <branch>` or `git ls-remote --exit-code --heads origin <branch>`.
     - **If it does not exist:** create and check it out.
     - **If it already exists: STOP — do not check it out automatically.** This is the **Branch Gate**. Show the user the existing branch (last commit, ahead/behind vs. the target branch) and ask how to proceed:
       1. **Continue on the existing branch** — `git checkout <branch>` and resume (see resume handling in Failure modes).
       2. **Create a new branch** — propose a disambiguated name (e.g. append `-2` or a more specific slug) and create it from the target branch.

       Do not proceed past this gate without an explicit choice.

2. **Choose the execution mode** from the plan's `### Parallel lanes`:

   | Plan says                         | Mode                                                        |
   |-----------------------------------|-------------------------------------------------------------|
   | `single (sequential)`, or trivial/small | **Inline:** run step 3 for each plan step yourself    |
   | Lane 0 + 1 lane                   | **Inline:** one lane gains nothing from an agent            |
   | Task isn't high complexity, lanes are tiny, or the plan is < ~300 LOC | **Inline:** agents would cost more tokens than they save |
   | High complexity, plan ≥ ~300 LOC, lane 0 + ≥2 lanes of ≥ ~60 LOC each | **Parallel lanes: required** (below). Don't fall back to inline because of "coupling"; lane 0's contracts handle that |

   Rows are checked top to bottom, and the first match wins.

   The plan proposes lanes. Re-check them against the Fan-out decision in `feature/parallelism.md` before spawning, and record the choice (`implement fan-out: 3 lanes` or `none — ~80 LOC`).

   **Parallel lanes procedure:**
   1. **Validate the lanes first.** Confirm no file appears in two lanes, comparing the plan's lists with any new files a step creates. If they overlap, merge those lanes. Never run overlapping lanes concurrently.
   2. **Run lane 0 inline**, with full verification (typecheck must pass) so every lane starts from a compiling foundation. Lane 0 must contain a **typed stub for every export one lane uses from another** (e.g. `export function listIssues(f: ListFilters): ListResult { throw new Error('not implemented') }`). The owning lane replaces the stub body. If the plan's lane 0 lacks these stubs, add them now. That is what lets every lane start at once.
   2b. **Snapshot before spawning:** record `git status --porcelain` and copy every currently modified or untracked file to `<scratchpad>/pre-lanes/`, keeping their paths. This is the restore point for integration checks.
   3. **Spawn one `Agent` for every lane in a single message** (`subagent_type: "general-purpose"`). **Don't run lanes in waves** (e.g. lib lanes first, then routes/pages). Waves were measured to roughly halve the speed-up. A lane that calls another lane's code works against lane 0's stub signatures, and its tests mock or import the real module after integration.
      All lanes share the working tree on the feature branch. This is safe
      because their file sets are disjoint, and lane 0's uncommitted changes are
      visible to them. (Worktrees would not see uncommitted lane 0 changes.)
      Each lane prompt must include:
      - the lane's plan steps verbatim, the research `file:line` evidence for them, project conventions, and the selected solution;
      - **"You may only create or edit these files: <exclusive list>. If you need a change elsewhere, stop and report it. Do not make it."**
      - "Do not run any git command that changes state (checkout, stash, reset, add, commit, branch)."
      - **Scoped verification only:** lint/test only your own files (e.g. `npx eslint <files>`, `npx vitest run <your test files>`). Do not run full-project typecheck or build. Other lanes are mid-edit and will cause false failures.
      - If the scoped tests share external state with other lanes (a database, fixed ports, a shared build cache), **lint only, and do not run tests**. Those tests run once at integration.
      - "Report every file you created or edited" (the `files:` field must be complete).
      - the hard rules below (no type-safety bypasses, tests co-located, fix code not tests);
      - return format: `Lane <N>: <done|blocked> — files: <list> — verified: <commands + result> — needs-outside-lane: <none|description>`.
   4. **Integrate (inline, after all lanes return):**
      - Compare `git status --porcelain` with the snapshot:
        - a file changed that is in **no** lane's list → restore it from `pre-lanes/`, or with `git checkout -- <file>` if it wasn't in the snapshot (that is, it was clean), and redo that change inline;
        - a lane reporting a file outside **its own** list → check that file against its owning lane's intent and hand-fix it inline;
        - a file whose owner lane didn't report it → treat it as a cross-lane edit and review it by hand.
      - Apply any `needs-outside-lane` requests inline, one at a time.
      - Run **full** verification once: typecheck/build + the plan's verifications for every step.
      - If integration fails, fix it inline. Do not respawn lanes for integration bugs.
   5. A lane that returns `blocked` or fails: retry that one lane once with the error added to its prompt, then finish it inline.

3. **For each plan step (inline mode, lane 0, and integration fixes):**
   1. Re-read the step.
   2. Make the change. Edit existing files in preference to creating new ones.
   3. Run the verification declared in the plan (typecheck, unit test, command).
   4. If verification fails: fix the issue, don't bypass. If you can't fix in ≤3 attempts, stop and report a blocker — do not paper over.

   Do **not** commit during implement. All edits stay in the working tree; `ship` commits the change once the full diff has been self-reviewed and QA'd. This matches normal dev flow: code → verify → commit once when done.

4. **If `feedback` is set:**
   - Surface the feedback at the top of your working context.
   - Address each point explicitly with new edits in the working tree (still no commits — `ship` will commit).
   - When feedback is a merged list from Test ∥ Review, fix it in **one pass**. If the fixes fall into ≥2 disjoint file groups and there are more than ~5 of them, you may run them as parallel lanes using the same procedure. Otherwise fix inline.

5. **No drive-by changes.** If you spot an unrelated bug or want to clean up adjacent code, note it as a follow-up and keep going.

## Branch naming

Format: `<type>/<ticket-or-slug>`.

`<type>` must be a conventional branch type — map the intake `task_type` to one of:

| type       | use for                                  |
|------------|------------------------------------------|
| `feat`     | new feature / capability                 |
| `fix`      | bug fix                                   |
| `chore`    | maintenance, deps, config                 |
| `docs`     | documentation only                        |
| `refactor` | behavior-preserving restructuring         |
| `test`     | adding or fixing tests                     |
| `perf`     | performance improvement                   |
| `ci`       | CI / pipeline changes                     |
| `build`    | build system / tooling                    |

Rules:

1. **Ticket number provided** → `<type>/<ticket-number>`, e.g. `feat/WEB-123`, `fix/WEB-456`, `chore/OPS-12`.
2. **No ticket number** → `<type>/<slug>`, e.g. `feat/user-authentication`, `fix/login-validation`, `refactor/api-client`.
3. Slugs are lowercase with hyphens (`-`) instead of spaces.
4. Before creating a branch, check whether it already exists (see Preflight). If it exists, **stop at the Branch Gate** and ask the user whether to continue on it or create a new (disambiguated) branch — never check it out automatically.

## Hard rules

| Rule                              | Detail                                                                  |
|-----------------------------------|-------------------------------------------------------------------------|
| No type-safety bypasses           | No `@ts-ignore`, `as any`, `// eslint-disable-next-line`, or equivalent without an inline justification AND a follow-up issue noted. |
| Tests co-located with code        | Write tests alongside the code change in the same step. Never defer "for later"; they ship in the same PR. |
| Fix code, not tests               | Tests are the alarm, code is the fire. Only edit tests when the AC itself changed. |
| No commits in implement           | All edits stay uncommitted. `ship` is the only stage that runs `git commit`. |

## Output

Report to the caller:

```
Branch:        <branch>
Mode:          <inline | parallel: N lanes (lane 0 inline)>
Lanes:
  - lane <N>: <done|retried|inline-fallback> — <files>
Plan steps:
  - <step 1 subject> [verified ✓]
  - <step 2 subject> [verified ✓]
Files changed: <N> (uncommitted in working tree — ship will commit)
Blockers:      <none | description>
```

## Verification

- Branch exists and is checked out.
- Parallel mode: every changed file belongs to exactly one lane (or lane 0 / integration), and full typecheck ran after the lanes merged.
- `git diff` shows the planned changes in the working tree.
- Every plan step is either complete or has a reported blocker.
- No `WIP`, `fixup`, or unresolved merge markers in the diff.
- `git diff` shows no introduced `@ts-ignore`, `as any`, or `eslint-disable` without justification.

## Failure modes

- **Verification fails repeatedly:** stop and report a blocker.
- **Plan step is wrong:** stop, note the deviation, ask the orchestrator for guidance rather than silently re-planning.
- **Branch already exists at preflight:** stop at the **Branch Gate** — ask the user whether to continue on the existing branch or create a new disambiguated one. Never auto-checkout.
- **Resume sees existing branch + uncommitted diff:** (after the user chose "continue" at the Branch Gate) re-derive remaining work from the plan vs. the current working-tree diff. Don't re-apply edits already present. (Trade-off of no per-step commits: mid-run resume is less precise. If pausing for a long time, commit manually before stepping away.)
- **Lane agent edits outside its file list:** if the file belongs to no lane, restore it from the `pre-lanes/` snapshot and redo the change inline. If it belongs to another lane, don't restore it, because that would wipe the owner's work. Hand-fix it per the integration step. Note it in the output either way.
- **Integration typecheck fails after lanes merge:** usually a contract mismatch between lanes. Fix it inline against lane 0's types. Don't re-run the lanes.
- **Two lanes turn out to need the same file mid-run:** that lane reports `needs-outside-lane`. Apply the change inline after all lanes return. Never let two agents edit one file.