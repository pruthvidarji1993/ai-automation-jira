---
name: ship
description: Self-review, QA, AI approval, PR open (with template discovery), and PR review-comment cycle. Idempotent — safe to re-invoke. Use as the final step of a development flow.
---

# ship

Hand the change off — self-review → QA → AI approval → PR → address comments. Highest-stakes stage. Every action is guarded by an idempotency check, and progress is recorded so a context loss is recoverable.

## Sub-stage tracking

Record the current sub-stage in your working notes after each transition: `SELF_REVIEW → QA → AI_APPROVAL → PR_OPEN → REVIEW_CYCLE`. On resume, pick up at the recorded stage.

## Inputs

- `ticket` (string, for the PR body and title)
- `branch` (string)
- `task_type` and `size` from intake

## Step 1 — Self-review (status: `SELF_REVIEW`)

> **Note:** at this point the change is **uncommitted** in the working tree (the `implement` skill does not commit). The diff command below covers both committed and working-tree changes against the target branch.

| Size      | Action                                                                          |
|-----------|---------------------------------------------------------------------------------|
| trivial   | Eyeball the diff (`git diff origin/<target>` — includes uncommitted changes)    |
| small     | Eyeball + invoke the `review` skill once on the local diff                      |
| medium    | Spawn an `Agent` (fresh context) with `subagent_type: "general-purpose"` to review the branch diff. The implementer must NOT review its own code. |
| large     | Same as medium, plus a `mosaic-local-review` or equivalent codegen-rules audit  |

Apply any blocking fixes from the review before continuing. Re-run tests if anything changed. Fixes stay in the working tree — they're committed in Step 4.

## Step 2 — QA (status: `QA`)

Run, in order:

1. **Install deps** if `package.json` / `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock` changed: project's package manager (`npm ci`, `pnpm install --frozen-lockfile`, etc.).
2. **Lint** (e.g., `npm run lint`).
3. **Typecheck** (e.g., `npm run build` when build implies typecheck, or `tsc --noEmit`).
4. **Tests** (e.g., `npm test`).

If anything fails: fix the code (not the test), re-run from step 1.

### Regression mode (`--regression`)

After addressing PR comments in REVIEW_CYCLE, re-run only checks that previously failed. Diff results against the last green run to confirm the fix didn't introduce new failures.

## Step 3 — AI approval (status: `AI_APPROVAL`)

Fill this checklist with **real evidence** — paste command output, list real file paths. All items must pass before opening a PR. Write the filled checklist to the PR body (or as a comment on update).

```
## AI Approval Checklist

### Plan compliance
- [ ] Every file in the plan was changed: <planned vs actual>
- [ ] No unplanned files were changed: <list extras with justification, or "None">
- [ ] Estimated vs actual LOC: <planned> → <actual>

### Convention compliance
- [ ] New files follow the project's target conventions (not just neighboring legacy)
- [ ] Styling/UI approach matches project direction
- [ ] Architecture patterns match project direction

### Quality evidence
- [ ] Tests pass: <command + summary>
- [ ] Typecheck/build passes: <command + summary>
- [ ] Lint passes: <command + summary>
- [ ] New code has test coverage: <list new functions + their tests>

### Completeness
- [ ] Feature flag added if planned: <name or N/A>
- [ ] All acceptance criteria met: <map each AC to the implementation>

### PR readiness
- [ ] Diff under 500 lines (otherwise split per plan): <actual count>
- [ ] No secrets / debug code in diff
- [ ] Commits are clean (no "fix typo" chains) and follow Conventional Commits v1.0.0
```

## Step 4 — Open PR (status: `PR_OPEN`)

### Commit logical units

The `implement` skill leaves all changes uncommitted in the working tree. After self-review, QA, and AI approval have all passed, commit the change here. All commits MUST follow [Conventional Commits v1.0.0](#commit-message-format-conventional-commits-v100).

- **Default:** one commit for the whole change is fine — most teams squash-merge anyway.
- **Medium / large:** split into 2–4 logical commits (e.g. module + its test, handler + schema). Each commit must independently compile.
- Stage with `git add <files>` (avoid `git add -A` — it can sweep in stray files). Commit with `git commit -m "<type>(<scope>): <description>"` (use repeated `-m` flags for body/footers).
- Do not bypass pre-commit hooks (no `--no-verify`). If a hook fails, fix the underlying issue and re-commit.
- Do not use `git rebase -i` or `git add -i` — the harness blocks interactive flags. To restructure already-made commits, use `git reset --soft <base>` and recommit.

### Commit message format (Conventional Commits v1.0.0)

Structure:

```
<type>[optional scope][optional !]: <description>

[optional body]

[optional footer(s)]
```

**Type** (required, lowercase):

| type       | meaning                                   | SemVer  |
|------------|-------------------------------------------|---------|
| `feat`     | a new feature                             | MINOR   |
| `fix`      | a bug fix                                 | PATCH   |
| `docs`     | documentation only                        | —       |
| `style`    | formatting, no code-meaning change        | —       |
| `refactor` | behavior-preserving restructuring         | —       |
| `perf`     | performance improvement                   | —       |
| `test`     | adding or fixing tests                     | —       |
| `build`    | build system / dependencies               | —       |
| `ci`       | CI configuration                          | —       |
| `chore`    | maintenance, no src/test change           | —       |

**Rules:**

- **Scope** (optional) gives context in parentheses, e.g. `feat(parser): ...`. Prefer a real module/area name.
- **Description** (required): short, imperative mood, lowercase, no trailing period. Keep the header ≤ ~72 chars.
- **Body** (optional): MUST be separated from the description by one blank line. Explain *what* and *why*, not *how*.
- **Footers** (optional): git-trailer format `Token: value` (hyphenate multi-word tokens, e.g. `Reviewed-by`). Reference the ticket here, e.g. `Refs: WEB-123` or `Closes: WEB-123`.
- **Breaking changes:** signal with EITHER a `!` before the colon (`feat(api)!: ...`) OR a `BREAKING CHANGE: <description>` footer (uppercase, mandatory). Either bumps the MAJOR version.

Examples:

```
feat(auth): add password reset flow

Refs: WEB-123
```

```
fix(api)!: drop support for legacy v1 tokens

BREAKING CHANGE: v1 bearer tokens are no longer accepted; clients must migrate to v2.

Closes: WEB-456
```

### Preflight

- [ ] `git log --oneline origin/<target>..HEAD` shows ONLY our new commit(s).
- [ ] `git status` is clean (no leftover uncommitted changes).
- [ ] If extra commits leaked in: `git rebase --onto origin/<target>` (non-interactive).
- [ ] Branch name matches the ticket / slug.
- [ ] PR base set to the correct target.

### Push

`git push -u origin <branch>`. Fast-forward only — never force-push.

### PR template discovery

Look for an existing template in this order. **Use the first one found.**

1. `.github/PULL_REQUEST_TEMPLATE.md`
2. `.github/pull_request_template.md`
3. `docs/pull_request_template.md`
4. `.github/PULL_REQUEST_TEMPLATE/` (directory of named templates — pick `default.md` if present, else the first `.md` alphabetically)
5. `PULL_REQUEST_TEMPLATE.md` at repo root

If a template is found:
- Fill the template's existing headings/checkboxes from intake + plan + AI approval content.
- Keep the template's structure intact (don't reorder sections; don't drop sections).
- For checkboxes the change doesn't address, leave them unchecked and add a one-line `_N/A — reason_` note beneath, rather than deleting them.

If no template is found, use a minimal body:

```
## Summary
<one-sentence what + why>

## Acceptance criteria
- [x] <each AC from intake>

## AI approval
<paste the filled checklist from Step 3>
```

### Idempotency: existing PR?

`gh pr list --head <branch> --json number,url`. 
- If a PR exists: update its body with the current run summary; do not create a duplicate.
- If not: `gh pr create --base <target> --head <branch> --title "<type>(<scope>): <description>" --body "<rendered body via HEREDOC>"`. The title MUST follow the same [Conventional Commits format](#commit-message-format-conventional-commits-v100).

Reference the ticket. Mark the PR ready for review (not draft) unless `size = large`, in which case draft is acceptable.

## Step 5 — Address review comments (status: `REVIEW_CYCLE`)

After the PR opens, check for existing reviews. If none yet: notify the user, proceed to report — don't block. The review cycle runs on the next invocation when comments exist.

If reviews exist, loop autonomously (**max 5 iterations**):

1. `gh api repos/<owner>/<repo>/pulls/<#>/comments` and `gh pr view <#> --json reviews` to fetch unresolved threads.
2. Classify each comment:
   - **Valid concern** → fix the code.
   - **Misunderstanding** → reply with evidence (file:line, commit sha, test output). Do NOT mark resolved.
   - **Style nit** → fix if low-effort; otherwise reply with reasoning.
3. Push fixes as one batch commit (`fix(<scope>): address review comments`).
4. Re-run QA in `--regression` mode.
5. Reply on each addressed thread citing the fix commit — **but do NOT resolve the thread**. Let the reviewer resolve their own.
6. `gh pr edit <#> --add-reviewer <reviewer>` to re-request review.

**Exit conditions:** PR approved, no new review after the iteration, max iterations reached, OR the same comment persists for 2 iterations (escalate to user).

## Output

```
Sub-stage:  <SELF_REVIEW|QA|AI_APPROVAL|PR_OPEN|REVIEW_CYCLE|DONE>
Self-review: <inline | agent-id>
QA:          <lint ✓, typecheck ✓, tests ✓>
AI approval: <PASS|FAIL — reasons>
Template:    <path used | "minimal — no template found">
Pushed:      <branch>
PR:          <url>
PR action:   <created|updated>
Review iter: <N (if applicable)>
```

**Always end the report with the PR URL on its own final line**, regardless of `PR action` (created OR updated) or whether this was a resume / idempotent re-invoke:

```
🔗 PR: <url>
```

If the PR already existed and was only updated, still emit this line — the URL is the one thing the caller always needs back.

- `gh pr view <pr_url>` succeeds.
- Branch is on the remote at the expected SHA.
- AI Approval checklist is in the PR body (under its own heading if a template was used).

## Hard rules

| Rule                          | Detail                                                             |
|-------------------------------|--------------------------------------------------------------------|
| Never skip self-review        | "I'm confident in the diff" is not a substitute                    |
| Never skip QA                 | "Already ran tests" is not a substitute                            |
| Implementer ≠ self-reviewer (medium+) | Spawn a fresh-context Agent                                  |
| Never approve own PR          | Only external reviewer or human approves                           |
| Never force-push              | Preserve review history                                            |
| Conventional Commits          | Every commit + PR title follows Conventional Commits v1.0.0        |
| Don't resolve reviewer threads | Reply with evidence; the reviewer resolves their own              |
| Never dismiss reviews         | Only address or reply                                              |
| Idempotent PR open            | Always check for existing PR first                                 |
| Always surface the PR URL last | End the report with `🔗 PR: <url>` on its own line — created or updated, fresh run or resume |

## Failure modes

- **Push rejected (non-fast-forward):** stop, surface the conflict, do not force-push.
- **`gh auth` missing:** surface the auth error; suggest `gh auth login`.
- **PR body too long for template fields:** truncate, link to the run summary or ticket for full detail.
- **No PR template found:** use the minimal body above; note "no template found" in output.
- **Review loop hits max iterations:** stop, surface unresolved comments to the user, do not silently force progression.