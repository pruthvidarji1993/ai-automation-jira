# Parallelism reference for `/feature`

Read this file only when the task is **not** low complexity (see `SKILL.md` → Parallelism). Low-complexity runs never need it.

## Parallelism model

Stages stay in order and gates stay blocking. Work *inside* and *between*
stages **may** fan out to multiple agents, but only when the work is
independent **and** the Fan-out decision below says it's worth the tokens. The
table lists where fan-out is *allowed*, not where it's required. Inline is the
default.

| Where (allowed, not required) | What may run in parallel                                                               | Who writes?                     |
|-------------------------------|----------------------------------------------------------------------------------------|---------------------------------|
| Stage 1 (Intake)            | *Optional* background **conventions scan** agent while intake resolves the ticket     | Nobody (read-only)              |
| Stage 2 (Research)          | Up to 4 `Explore` agents, one per *applicable* research track (see `research` skill)                   | Nobody (read-only)              |
| Stage 6 (Implement)         | One agent per **lane** from the plan's `### Parallel lanes` (disjoint file sets)      | Each lane only its own files    |
| GATE 2 (while human reviews)| Background **speculative QA** as plain `Bash` commands (no agent): lint + typecheck + existing suite | Nobody (read-only) |
| Stages 7 + 8                | `test` and `review` run concurrently; review lenses run as parallel agents            | `test` only (review is findings-only) |
| Stage 9 (Ship)              | Lint / typecheck / tests run concurrently; self-review agent alongside QA             | Nobody until the fix pass       |

### Fan-out decision (run this BEFORE every spawn — default is inline)

Every sub-agent costs tokens: each one re-reads context, files, and
instructions from scratch. So sub-agents are for **complex, high-effort work
only**. Simple and routine tasks are always done inline, whatever the stage.
Models are never downgraded to save tokens. Each agent uses the model its skill already specifies (e.g. review lenses use `opus`), or the session model when none is specified.

Running shell commands in the background (`Bash` with `run_in_background`)
is **not** a sub-agent fan-out. It costs no extra tokens and is always allowed
when the commands are independent.

**Step 1: rate the task's complexity** from the intake/research/plan outputs:

| Complexity | Typical signals                                                                                   | Sub-agents?                         |
|------------|---------------------------------------------------------------------------------------------------|-------------------------------------|
| Low        | `trivial`/`small`; single module; ≤ 3 files; copy/config/doc/style change; RCA points at 1–2 lines | **Never.** Everything inline        |
| Medium     | `medium` size but routine: one feature area, known pattern, no async or cross-team surface         | **Rarely.** Only for a fresh-context reviewer, or a step that really is heavy |
| High       | `large`, or `medium` with high risk; many modules/repos; async/background flows; API contract with another team; > 300 LOC plan; data migration; slow test suite | **Yes**, where step 2 passes |

**Step 2 (High, or a heavy step in a Medium task):** before each fan-out, check:

| # | Question                                                                                   | If "no" →                    |
|---|--------------------------------------------------------------------------------------------|------------------------------|
| 1 | Is the work really split into **≥ 2 independent chunks** (separate tracks, disjoint files, separate lenses)? | Inline              |
| 2 | Is each chunk **substantial**: more than ~5 files to read, ~30 LOC to write, or a slow command (> ~60 s)? | Inline or merge chunks |
| 3 | Will each agent run for longer than ~2 minutes of real work (not just reading a few files)? | Inline           |

- **All three "yes"** → fan out, but spawn **only the chunks that apply** to this task (e.g. no async-lifecycle track for a pure UI change, no types lens if no types were added).
- **Any "no"** → do the work inline in the main context, or with one combined agent when a fresh context is required (the implementer must never review its own medium+ code).
- **Record the decision** in one line in working notes, e.g. `complexity: high — fan-out: research → 2 tracks (A, B); C/D n/a`, or `complexity: low — fan-out: none (2 files, ~40 LOC)`. The Stage 10 report shows these lines.

When unsure between two complexity levels, pick the lower one and stay inline.
Starting an agent later is cheap; tokens already spent are not.

### Where the speed actually comes from (benchmark-backed)

In a measured large run, **implement was ~60% of all orchestrator turns**.
Test, review and ship together were about 25%, and research and plan were
under 15%. So:

- **Parallel implement lanes are REQUIRED** when complexity is high, the plan
  is ≥ ~300 LOC, and it has ≥ 2 lanes of ≥ ~60 LOC each (after the
  contract-first lane 0, see the `plan` skill). Don't fall back to inline
  because the modules are "coupled": lane 0's contracts (types plus exported
  function signatures) remove that coupling. This is the single biggest
  time saving.
- **The reviewer always runs in the background while `test` runs** (see
  Test ∥ Review below). That costs no extra tokens, since the reviewer runs anyway.
- **Research and intake fan-out rarely pays** in small or medium repos.
  Parallel `Read`/`Grep`/`Bash` calls in one message are usually faster.
- **Don't add work the old flow didn't do.** Only criticals and test failures
  are fixed in the run. Warnings become PR follow-ups (see Test ∥ Review below).
  Fixing warnings changes code after review, which then forces a second review.

### Rules for every fan-out

1. **Spawn in one message.** All agents in a fan-out are separate `Agent` tool
   calls inside a *single* assistant message so they actually run concurrently.
   Spawning them one per turn is sequential and defeats the purpose.
1b. **Never use a lone foreground agent for speed.** One agent with nothing
   running beside it is slower than doing the work yourself. It adds startup
   time and re-reads context. If you split work between an agent and yourself,
   spawn the agent with `run_in_background: true`, do your share inline while it
   runs, then merge. A single foreground agent is only allowed when you need a
   *fresh context* (the medium+ reviewer), never to "parallelize".
1c. **Prefer parallel tool calls before agents.** Several independent
   `Read`/`Grep`/`Bash` calls in one message already run in parallel, at no
   extra agent cost. Reach for agents only when a track needs many rounds of
   searching (more than ~5 files to explore with follow-up searches).
2. **Read-only fans out freely; writers need disjoint files.** Any number of
   read-only agents may run at once. Agents that edit code may only run in
   parallel when their file sets do not overlap (enforced by the plan's lanes).
3. **No agent touches git state.** Sub-agents must not run `git checkout`,
   `stash`, `reset`, `commit`, `add`, or branch operations. Only the
   orchestrator (and `ship`) changes git state.
4. **Self-contained prompts.** Every agent prompt restates its inputs (paths,
   AC, plan excerpt, output format). Agents do not see your working notes.
5. **Structured returns.** Ask each agent for a fixed output block (findings
   with `file:line`, or a status line) so results merge without re-reading.
6. **Gates are never parallelized away.** Background work may run *while* a
   gate is open, but nothing that depends on the gate's answer starts before
   the human replies, and nothing writes to the working tree during a gate.
7. **Cap the fan-out at 4 writers / 6 readers**, and always use the *fewest*
   agents that cover the applicable chunks. More agents cost more in merging
   and tokens than they save in wall-clock.
8. **Low complexity never fans out.** Once the task is rated low, no
   stage spawns a sub-agent. The Stage 1 conventions scan is the only spawn
   that happens before the rating, and it has its own trigger rule (Conventions scan, below).
9. **On agent failure, retry that one agent once, then do its work inline.**
   One failed agent never fails the stage.

## Conventions scan (Stage 1)

Size is not known yet, so start this
only when the description already signals non-trivial work: a ticket ID/URL
whose resolution takes time, multiple features/modules named, or an API or
cross-team mention. A one-line copy/config fix doesn't get it. **And** the
repo must be large (more than ~200 tracked source files, or a monorepo:
check with `git ls-files | wc -l`). In a small repo, research reads
`package.json` and the configs in one parallel call, so the scan only
duplicates that work. If you start
it, do so in the **same message** as intake: a background `Agent`
(`subagent_type: "Explore"`, `run_in_background: true`): "Detect language, framework, styling, state
  management, test runner, package manager, lint/typecheck/test commands, and
  constraints from CLAUDE.md / AGENTS.md. Cite the config file for each. Return
  a `## Project conventions` block only."


## Speculative QA (GATE 2)

Run it only for high-complexity
tasks where the suite is **known** to be slow (more than ~60 s, from CI config,
docs, or an earlier run in this session). If the time is unknown, skip it. A
fast or unknown suite runs once in Stage 7.

How to run it:
1. **First** record the tree fingerprint: `git diff HEAD | shasum`, plus
   `git status --porcelain | shasum`, plus untracked file contents
   (`git ls-files -o --exclude-standard -z | xargs -0 shasum | shasum`).
2. In the same message that fires the gate, start lint, typecheck, and the
   **existing** test suite as background `Bash` commands
   (`run_in_background: true`). This is **not** an agent. Nothing edits files.
3. The gate's reply decides what happens next:
   - **Continue:** Stage 7 uses the results if they've finished and the
     fingerprint still matches. Otherwise it runs the suite normally and
     doesn't wait.
   - **Request changes / Fail:** discard the results. Implement must not edit
     files while QA commands are still running, so stop them first (`TaskStop`).


## Test ∥ Review (Stages 7 + 8)

**Whenever review will use an agent** (any `medium`/`large` task: one combined
reviewer, or parallel lenses for high complexity), run them concurrently. The
reviewer agent runs anyway, so starting it in the background before `test`
saves wall-clock at no extra token cost. For `small` (inline review), run Test
then Review in order.

Skills run in the main context one at a time, so the overlap comes from the
reviewer running as a **background agent** while you run the tests. Do it in
this order (this is the flow that was measured to work):

1. **Snapshot the implementation diff:** `git diff HEAD > <scratchpad>/impl.diff`.
2. **Spawn the reviewer yourself in the background:** `Agent`,
   `subagent_type: "general-purpose"`, `model: "opus"`, `run_in_background: true`.
   Its prompt is the `review` skill's requirements for a fresh-context review:
   the diff path, the intake AC, the plan and failure-mode table, the
   applicable lenses from `review` §8.2, the `file:line` + quote evidence
   rule, and "findings only — do not edit files or run git commands". For
   high complexity with ≥ 3 applicable lenses, spawn one background agent per
   lens instead, all in the same message.
3. **While it runs, invoke `test`.** If speculative QA results are valid, pass
   them as `baseline_results`. If the implement lanes already wrote co-located
   tests, `test` only fills real gaps; it doesn't duplicate them.
4. **When the reviewer's notification arrives,** invoke `review` with
   `args: "collect impl.diff findings=<the agent's findings>"`. It merges and
   maps severities (§8.2 step 3), then runs 8.3–8.7. It does not spawn
   another reviewer.
   - If test results finish first and nothing else is left to do, end your
     message with a one-line status (`waiting on background reviewer`). Don't
     claim the stage is done. The notification resumes you.
5. **Merge** test failures and review findings into one deduplicated list,
   ranked critical → warning → info.
6. **One consolidated fix pass:** if there are any test failures or **critical**
   findings, treat it as a single "Request changes" event: feed the failures and
   criticals to `implement` once (not one loop per finding) and re-render GATE 2.
   **Warnings and info are not fixed in this run.** They go into the PR body
   as `Follow-ups`. If the user wants them fixed, they say so at GATE 2.
   After the fix, re-run only the failed tests and the review lenses that
   reported something. Do not re-run the whole fan-out.
