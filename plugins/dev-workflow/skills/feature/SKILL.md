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

## Procedure

### Stage 1 — Intake
Invoke the `intake` skill with `$task_description`.
Capture into working notes: `task_type`, `size`, `summary`, `acceptance_criteria`, `success_criteria`, `cross_team_impact`.

### Stage 2 — Research (skip if size = trivial)
Invoke the `research` skill with the intake outputs.
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
Capture into working notes: the implementation plan, quality analysis, failure-mode table, risk level, line estimate, feature flag.

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
Invoke the `implement` skill with the approved plan + research findings + selected solution as input.
Capture into working notes: `branch`, files changed in the working tree (uncommitted — `ship` commits later), worker location (inline | worktree path).

### GATE 2 — Execution review (REQUIRED, never skip)

**Post-stage protocol:** as with GATE 1, fire the AskUserQuestion in the SAME turn that delivers the implement output. Do not end the turn between implement output and the gate.

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

### Stage 7 — Test
Invoke the `test` skill. If it reports failures, route the run back to
`implement` with the test failures as feedback (same path as "Request changes"
above). Do not proceed to review on a red suite.

### Stage 8 — Review (skip if size = trivial)
Invoke the `review` skill against the working branch.
For `medium`/`large`, the `review` skill spawns its own fresh-context reviewer agent.
Capture findings.

If there are any **critical** findings, treat that as a "Request changes"
event: feed them to `implement` and re-run from Stage 6. Do not ship code with
known criticals.

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
  implement       → {N} files changed on {branch} ({inline|worktree}, uncommitted)
  GATE 2          → {decision}{ → manual-test: {decision}}
  test            → {pass_count} passed
  review          → {critical} critical / {warning} warning / {info} info
  ship            → {pr_url} (template: {path|"minimal"})
```

## Hard rules

- **Never skip a gate.** GATE 1, GATE 2, and the Solution selection gate must fire on every non-trivial run.
- **Never invent a gate.** Only the two main gates, the solution-selection gate, and the manual-test sub-gate defined above exist.
- **Fire the gate in the SAME turn as the sub-skill output.** This is the explicit fix for the gate-firing bug where the orchestrator ended the turn after delivering a plan/implement output and never fired the AskUserQuestion call. The post-stage protocol notes in GATE 1, Solution Options, and GATE 2 are not optional.
- **RCA before plan for bugs.** If `task_type = Bug`, Stage 3 (RCA) must complete before Stage 4 (Plan) is invoked.
- **Invoke skills sequentially.** Don't parallelize stages.
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
