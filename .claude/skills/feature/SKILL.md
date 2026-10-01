---
name: feature
description: Master orchestrator for end-to-end feature development. Takes a task description and runs intake → research → plan → [GATE 1] → implement → [GATE 2] → test → review → ship. Invoke when the user says "/feature", "run the feature flow", or asks to take a ticket from description to PR.
---

# /feature — Master Orchestrator Skill

You are the orchestrator. Your job is to drive a feature from a task
description to a reviewed PR by invoking the sub-skills in `.claude/skills/`
in the right order, pausing at the two human gates, and reporting at the end.

You do **not** write code yourself. You delegate to the sub-skills. You **do**
render the gate prompts and route the user's reply.

## Argument

- `$task_description` — required. Ticket ID (e.g. `ABC-123`), URL, or
  free-form description of what to build.

If the user invoked `/feature` with no argument, ask once for the task
description before starting.

## Sub-skills you will invoke

All live under `.claude/skills/`:

| Order | Skill / Step              | Why                                                                      |
|-------|---------------------------|--------------------------------------------------------------------------|
| 1     | `intake`                  | Resolve the task, extract AC, classify size, validate success criteria   |
| 2     | `research`                | Map the codebase, detect conventions, validate hypotheses                |
| 3     | **Root Cause Analysis**   | (Bugs only) Trace data flow, pinpoint exact failing lines, present RCA   |
| 4     | `plan`                    | Write the implementation plan with quality analysis                      |
| —     | **GATE 1**                | Human approves the plan                                                  |
| 5     | **Solution Options**      | Present 2–4 solution options with trade-offs; human selects one          |
| 6     | `implement`               | Execute the approved solution on a branch                                |
| —     | **GATE 2**                | Human reviews the diff                                                   |
| 7     | `test`                    | Run tests, add coverage                                                  |
| 8     | `review`                  | Structured review of the diff                                            |
| 9     | `ship`                    | Self-review, QA, AI approval, open PR                                    |

Invoke each via the Skill tool with the skill name as the `skill` argument.
Pass concrete inputs in the `args` field — never say "use prior context".

## Size-based routing

`intake` classifies the task; use the size to decide which stages run.

| Size      | Stages run                                                                             | Gates fired               |
|-----------|----------------------------------------------------------------------------------------|---------------------------|
| trivial   | intake → implement → ship                                                              | none                      |
| small     | intake → research → [RCA if bug] → plan → solutions → implement → test → ship         | GATE 1, GATE 2, solutions |
| medium    | All 10 stages                                                                          | GATE 1, GATE 2, solutions |
| large     | All 10 stages; plan must propose a PR split if >500 LOC                               | GATE 1, GATE 2, solutions |

For `trivial`, the orchestrator may inline the change rather than spawning the
`implement` skill — but only for changes that are clearly under 50 LOC, single
file, and have no external surface change.

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
| 3 | Is the parallel time saved larger than the merge cost (re-reading and reconciling the agent outputs)? | Inline          |

- **All three "yes"** → fan out, but spawn **only the chunks that apply** to this task (e.g. no async-lifecycle track for a pure UI change, no types lens if no types were added).
- **Any "no"** → do the work inline in the main context, or with one combined agent when a fresh context is required (the implementer must never review its own medium+ code).
- **Record the decision** in one line in working notes, e.g. `complexity: high — fan-out: research → 2 tracks (A, B); C/D n/a`, or `complexity: low — fan-out: none (2 files, ~40 LOC)`. The Stage 10 report shows these lines.

When unsure between two complexity levels, pick the lower one and stay inline.
Starting an agent later is cheap; tokens already spent are not.

### Rules for every fan-out

1. **Spawn in one message.** All agents in a fan-out are separate `Agent` tool
   calls inside a *single* assistant message so they actually run concurrently.
   Spawning them one per turn is sequential and defeats the purpose.
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
   that happens before the rating, and it has its own trigger rule (below).
9. **On agent failure, retry that one agent once, then do its work inline.**
   One failed agent never fails the stage.

## Procedure

### Stage 1 — Intake
Invoke the `intake` skill with `$task_description`.

**Optional parallel conventions scan.** Size is not known yet, so start this
only when the description already signals non-trivial work: a ticket ID/URL
whose resolution takes time, multiple features/modules named, or an API or
cross-team mention. A one-line copy/config fix doesn't get it. If you start
it, do so in the **same message** as intake: a background `Agent`
(`subagent_type: "Explore"`, `run_in_background: true`): "Detect language, framework, styling, state
  management, test runner, package manager, lint/typecheck/test commands, and
  constraints from CLAUDE.md / AGENTS.md. Cite the config file for each. Return
  a `## Project conventions` block only."

Capture into working notes: `task_type`, `size`, `summary`, `acceptance_criteria`, `success_criteria`, `cross_team_impact`.
If `size = trivial`, ignore the conventions scan result when it arrives. Otherwise pass it to `research` as `prefetched_conventions`. If research starts before the scan has returned, research does not spawn track B. It waits for the scan result before Step 5 (Verify), and if the scan failed, it does Step 3 inline.

### Stage 2 — Research (skip if size = trivial)
Invoke the `research` skill with the intake outputs (plus `prefetched_conventions`
if the Stage 1 scan has returned). `research` fans out parallel `Explore`
tracks only for high-complexity tasks (see the Fan-out decision). Otherwise it
runs inline.
Capture into working notes: project conventions, files to change, hypotheses, open questions.

### Stage 3 — Root Cause Analysis (skip if task_type ≠ Bug)

**When:** `task_type = Bug` (as set by `intake`). Skip entirely for tasks, features, chores.

Perform inline without spawning a sub-skill:

1. **Classify the ticket.** Re-read the intake output. If `task_type` is not `Bug`, print `[RCA skipped — task type: {task_type}]` and move to Stage 4.
2. **Trace the data flow** from API / state source → business logic → UI, using the file:line evidence from research. Identify the exact layer where the behaviour diverges from expected.
3. **Pinpoint the failing lines.** Quote the exact code fragment(s) and explain why they produce the bug.
4. **Present the RCA** in this format before proceeding:

```
Root cause:
1. [Component/File:line] does [X]
2. But [data/condition] is [Y] when [scenario]
3. So the result is [Z] instead of [expected]

Offending code:
  <file:line>
  `<quoted line(s)>`
```

Do not proceed to Stage 4 until the RCA is presented. If you cannot identify the root cause with the research evidence, surface a blocker and ask the user.

### Stage 4 — Plan (skip if size = trivial)
Invoke the `plan` skill with the intake + research outputs (and RCA output if a bug).
Capture into working notes: the implementation plan, quality analysis, failure-mode table, risk level, line estimate, feature flag, parallel lanes.

### GATE 1 — Plan approval (REQUIRED, never skip)

**Post-stage protocol:** the `plan` skill output ends with `## Stop — orchestrator fires GATE 1 next`. As soon as you have rendered the plan, your VERY NEXT action in the SAME turn is the AskUserQuestion call below. Do not end the turn between the plan output and the gate. If you ever find yourself about to end the turn after delivering a plan, stop — fire the gate first.

Render via AskUserQuestion:

```
question: "Plan ready for {ticket-or-summary}. Approve to proceed to implementation?"
header:   "Plan approval"
options:
  - label: "Approve"
    description: "Plan looks good — proceed to implementation."
  - label: "Modify"
    description: "Adjust the plan based on feedback."
  - label: "Reject"
    description: "Stop and rethink the approach."
```

Route the reply:

- **Approve** → continue to Stage 5 (Solution Options).
- **Modify** → ask the user for specific feedback, then re-invoke the `plan`
  skill with the previous plan AND the feedback as inputs. Re-render GATE 1.
- **Reject** → write a one-paragraph summary of where we stopped and why, then
  exit cleanly. Do not proceed.

### Stage 5 — Solution Options (skip if size = trivial)

After GATE 1 is approved, and **before** invoking `implement`, present 2–4 concrete solution options inline. Do not invoke any sub-skill for this step.

For **each** option use this structure:

```
### Solution N: [Name] [(Recommended)]

**Approach:** Brief description of the strategy

**Changes:**
- <File 1> — what changes
- <File 2> — what changes

**Pros:**
- Benefit 1
- Benefit 2

**Cons:**
- Drawback 1

**Risk:** Low | Medium | High
```

After presenting all options, render a comparison matrix:

```
| Criteria                   | Solution 1 | Solution 2 | Solution 3 |
|----------------------------|-----------|-----------|-----------|
| Effort                     |           |           |           |
| Risk                       |           |           |           |
| Completeness               |           |           |           |
| Shared component impact    |           |           |           |
| API changes needed         |           |           |           |
```

Then immediately (in the same turn) fire a gate:

```
question: "Which solution do you want to implement for {ticket-or-summary}?"
header:   "Solution selection"
options:
  - label: "Solution 1 — [Name]"
    description: "<one-line summary>"
  - label: "Solution 2 — [Name]"
    description: "<one-line summary>"
  - label: "Solution 3 — [Name]"   # omit if fewer options
    description: "<one-line summary>"
  - label: "Solution 4 — [Name]"   # omit if fewer options
    description: "<one-line summary>"
```

Capture the chosen solution into working notes. Pass the full solution detail (approach + file changes) as `selected_solution` to the `implement` skill.

### Stage 6 — Implement
Invoke the `implement` skill with the approved plan (including `### Parallel lanes`) + research findings + selected solution as input.
If the selected solution changes the file set, recompute the lanes before invoking (same rules as the `plan` skill) — never run lanes whose file sets are stale.
Capture into working notes: `branch`, files changed in the working tree (uncommitted — `ship` commits later), execution mode (inline | parallel: N lanes).

### GATE 2 — Execution review (REQUIRED, never skip)

**Post-stage protocol:** as with GATE 1, fire the AskUserQuestion in the SAME turn that delivers the implement output. Do not end the turn between implement output and the gate.

**Speculative QA (only when it pays off).** Run it only for high-complexity
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

Render via AskUserQuestion:

```
question: "Implementation complete on branch {branch}. Continue to test/review, or pause for manual review?"
header:   "Execution review"
options:
  - label: "Continue"
    description: "Code looks fine — proceed to automated test and review."
  - label: "Pause for manual test"
    description: "Pause so I can manually validate before continuing."
  - label: "Request changes"
    description: "Implementation needs revision before moving on."
```

Route the reply:

- **Continue** → go to Stage 7.
- **Pause for manual test** → fire the sub-gate below.
- **Request changes** → ask the user for specific feedback, then re-invoke
  the `implement` skill with the feedback as override-priority input. Re-render
  GATE 2.

#### Sub-gate — Manual test

```
question: "Run your manual tests now. Reply when you're done."
header:   "Manual test"
options:
  - label: "Pass"
    description: "Manual test passed — continue."
  - label: "Fail — apply fixes"
    description: "Found issues; loop back to implement with the notes."
```

Route:

- **Pass** → go to Stage 7.
- **Fail — apply fixes** → ask the user for notes, then re-invoke `implement`
  with the notes. After re-implementation, re-render GATE 2 (not this sub-gate).

### Stages 7 + 8 — Test ∥ Review (run concurrently)

Run them **concurrently** only for **high complexity**, and only when review
has ≥ 3 applicable lenses or the suite is known to be slow. In every other case
(small, routine medium), run Test then Review in order.

Skills run in the main context one at a time, so the overlap comes from the
review lenses running as **background agents** while `test` runs:

1. **Snapshot the implementation diff:** `git diff HEAD > <scratchpad>/impl.diff`,
   and save the list of files it covers. Reviewers review this snapshot, so
   tests added by `test` cannot race them.
2. **Invoke `review` in launch mode** (`args: "launch-lenses impl.diff"`). It
   runs 8.1 inline (quick), spawns its applicable lenses *except* `tests` with
   `run_in_background: true`, and returns right away with `lenses pending`.
3. **Invoke `test`.** If speculative QA results are valid (fingerprint
   matches), pass them as `baseline_results`, so `test` only adds and runs new
   tests.
4. When `test` finishes, **invoke `review` again in collect mode**
   (`args: "collect impl.diff"`). It spawns the `tests` lens (if applicable)
   against `git diff HEAD`, which now includes the new tests. It then waits for
   all lens results and runs 8.3–8.7.
5. **Merge** test failures and review findings into one deduplicated list,
   ranked critical → warning → info.
6. **One consolidated fix pass:** if there are any test failures or **critical**
   findings, treat it as a single "Request changes" event: feed the whole merged
   list to `implement` once (not one loop per finding) and re-render GATE 2.
   After the fix, re-run only the failed tests and the review lenses that
   reported something. Do not re-run the whole fan-out.

Do not proceed to ship on a red suite or with known criticals.

For `trivial`, Stages 7 and 8 are skipped, per the routing table. Ship's QA covers the change.

### Stage 9 — Ship
Invoke the `ship` skill with `ticket`, `branch`, `task_type`, `size`.
Capture `pr_url` and the sub-stage status.

### Stage 10 — Report

Print a compact summary to the user:

```
Feature complete.
  intake          → {task_type}, {size}
  research        → {N} files mapped, {hypothesis_count} hypotheses
  root cause      → {rca_summary | "N/A — not a bug"}
  plan            → {N} steps, risk={low|medium|high}, ~{LOC} LOC
  GATE 1          → {decision}
  solution chosen → Solution {N}: {name}
  implement       → {N} files changed on {branch} ({inline|parallel: N lanes}, uncommitted)
  GATE 2          → {decision}{ → manual-test: {decision}}{ · speculative QA: {reused|stale|n/a}}
  test            → {pass_count} passed
  review          → {critical} critical / {warning} warning / {info} info ({N} lenses in parallel)
  ship            → {pr_url} (template: {path|"minimal"})
  agents          → {total_spawned} spawned, {failed_fallbacks} fell back inline
  fan-out log     → {one line per decision, incl. "none — <reason>"}
```

## Hard rules

- **Never skip a gate.** GATE 1, GATE 2, and the Solution selection gate must fire on every non-trivial run.
- **Never invent a gate.** Only the two main gates, the solution-selection gate, and the manual-test sub-gate defined above exist.
- **Fire the gate in the SAME turn as the sub-skill output.** This is the explicit fix for the gate-firing bug where the orchestrator ended the turn after delivering a plan/implement output and never fired the AskUserQuestion call. The post-stage protocol notes in GATE 1, Solution Options, and GATE 2 are not optional.
- **RCA before plan for bugs.** If `task_type = Bug`, Stage 3 (RCA) must complete before Stage 4 (Plan) is invoked.
- **Stages are ordered; parallelism is only where the Parallelism model says.** Stage order and gate order never change. The only *stages* that overlap are Test ∥ Review (high complexity), plus background read-only work during Intake and GATE 2. Parallel work *inside* a stage (research tracks, implement lanes, review lenses, ship QA commands) follows that skill's own rules. Don't invent new overlaps.
- **Never let parallel writers share a file.** If two lanes or agents would edit the same file, run them in sequence.
- **Pass concrete inputs.** When invoking a sub-skill, restate the inputs in the prompt — don't rely on the sub-skill reading your memory.
- **Trust the sub-skill's procedure.** Don't inline its work.
- **On rerun, give override-priority to user feedback.** When a gate routes back to `plan` or `implement`, the user's notes outrank the prior output.

## Failure handling

- If a sub-skill reports a blocker it can't resolve, stop and surface the blocker to the user. Don't paper over it.
- If GATE 1 is rejected, exit cleanly with a summary.
- If GATE 2 → "Request changes" or sub-gate → "Fail" recurs more than 3 times in a row, pause and ask the user whether to keep iterating or stop.
- If `review` returns NO-GO twice in a row on the same critical, escalate to the user before another implement loop.

## Composition note

Each sub-skill is also directly invokable on its own (e.g. you can run `plan`
standalone after intake + research). `/feature` is just the wiring. If a user
wants only parts of the flow, they can invoke those sub-skills directly.
