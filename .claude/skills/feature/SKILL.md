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

| Order | Skill       | Why                                                     |
|-------|-------------|---------------------------------------------------------|
| 1     | `intake`    | Resolve the task, extract AC, classify size, validate success criteria |
| 2     | `research`  | Map the codebase, detect conventions, validate hypotheses |
| 3     | `plan`      | Write the implementation plan with quality analysis     |
| 4     | `implement` | Execute the plan on a branch                            |
| 5     | `test`      | Run tests, add coverage                                 |
| 6     | `review`    | Structured review of the diff                           |
| 7     | `ship`      | Self-review, QA, AI approval, open PR                   |

Invoke each via the Skill tool with the skill name as the `skill` argument.
Pass concrete inputs in the `args` field — never say "use prior context".

## Size-based routing

`intake` classifies the task; use the size to decide which stages run.

| Size      | Stages run                                                          | Gates fired      |
|-----------|---------------------------------------------------------------------|------------------|
| trivial   | intake → implement → ship                                           | none             |
| small     | intake → research (light) → plan → implement → test → ship          | GATE 1, GATE 2   |
| medium    | All 7 stages                                                        | GATE 1, GATE 2   |
| large     | All 7 stages; plan must propose a PR split if >500 LOC              | GATE 1, GATE 2   |

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

### Stage 3 — Plan (skip if size = trivial)
Invoke the `plan` skill with the intake + research outputs.
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

- **Approve** → continue to Stage 4.
- **Modify** → ask the user for specific feedback, then re-invoke the `plan`
  skill with the previous plan AND the feedback as inputs. Re-render GATE 1.
- **Reject** → write a one-paragraph summary of where we stopped and why, then
  exit cleanly. Do not proceed.

### Stage 4 — Implement
Invoke the `implement` skill with the approved plan + research findings as input.
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

- **Continue** → go to Stage 5.
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

- **Pass** → go to Stage 5.
- **Fail — apply fixes** → ask the user for notes, then re-invoke `implement`
  with the notes. After re-implementation, re-render GATE 2 (not this sub-gate).

### Stage 5 — Test
Invoke the `test` skill. If it reports failures, route the run back to
`implement` with the test failures as feedback (same path as "Request changes"
above). Do not proceed to review on a red suite.

### Stage 6 — Review (skip if size = trivial)
Invoke the `review` skill against the working branch.
For `medium`/`large`, the `review` skill spawns its own fresh-context reviewer agent.
Capture findings.

If there are any **critical** findings, treat that as a "Request changes"
event: feed them to `implement` and re-run from Stage 4. Do not ship code with
known criticals.

### Stage 7 — Ship
Invoke the `ship` skill with `ticket`, `branch`, `task_type`, `size`.
Capture `pr_url` and the sub-stage status.

### Stage 8 — Report

Print a compact summary to the user:

```
Feature complete.
  intake     → {task_type}, {size}
  research   → {N} files mapped, {hypothesis_count} hypotheses
  plan       → {N} steps, risk={low|medium|high}, ~{LOC} LOC
  GATE 1     → {decision}
  implement  → {N} files changed on {branch} ({inline|worktree}, uncommitted)
  GATE 2     → {decision}{ → manual-test: {decision}}
  test       → {pass_count} passed
  review     → {critical} critical / {warning} warning / {info} info
  ship       → {pr_url} (template: {path|"minimal"})
```

## Hard rules

- **Never skip a gate.** GATE 1 and GATE 2 must fire on every non-trivial run.
- **Never invent a gate.** Only the two gates (and the manual-test sub-gate) defined above exist.
- **Fire the gate in the SAME turn as the sub-skill output.** This is the explicit fix for the gate-firing bug where the orchestrator ended the turn after delivering a plan/implement output and never fired the AskUserQuestion call. The post-stage protocol notes in GATE 1 and GATE 2 are not optional.
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
