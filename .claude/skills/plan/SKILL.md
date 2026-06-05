---
name: plan
description: Produce an implementation plan with file-level changes, quality analysis (security/perf/reusability/readability/testability/cross-team), failure-mode table, risk assessment, line estimate, and feature flag. Use after intake + research, or as step 3 of /feature.
---

# plan

Write the plan a human will approve. Vague plans produce vague implementations. Evidence first — every change references a real `file:line` from the research findings.

## Inputs

- Intake output: task type, size, summary, AC, validated success criteria, cross-team impact.
- Research output: project conventions, files to change, hypotheses, open questions.
- Optional: previous plan + user feedback (for reruns after a "Modify" gate decision). When present, treat feedback as override-priority guidance.

## Procedure

1. **Decompose into steps.** Each step gets:
   - one or two sentences describing the change,
   - the file(s) it touches (using `file:line` from research),
   - any new dependencies or APIs,
   - the verification (test, manual check, typecheck) that proves it works.

2. **Quality analysis.** Evaluate each dimension. Skip any that genuinely don't apply — but say so in one line; do not fabricate concerns.

   | Dimension          | What to assess                                                              |
   |--------------------|------------------------------------------------------------------------------|
   | Security           | Auth boundaries, injection surfaces, data exposure, secret handling          |
   | Performance        | Hot paths, N+1 queries, payload size, caching, pagination                    |
   | Reusability        | Existing patterns to follow, shared utilities to leverage                    |
   | Readability        | Naming clarity, structural complexity, separation of concerns                |
   | Testability        | What tests are needed, edge cases, test-pyramid level                        |
   | Cross-team impact  | Other repos, teams, APIs, or contracts affected                              |

3. **Failure-mode table.** For each method or endpoint being added/changed, enumerate failure modes:

   | Method/Endpoint | What can fail | Exception type | Rescued? | User sees |
   |-----------------|---------------|----------------|----------|-----------|

   **Any row with `Rescued = NO` AND `User sees = Silent` is a CRITICAL GAP.** Address it in the plan or surface it as an open question — do not ship past it.

   For trivial changes, skip with a brief justification.

4. **Line estimate.** Sum the per-step LOC. If the total is >500, propose a PR split with the math (e.g., "PR 1: storage + types ≈ 180 LOC; PR 2: UI + tests ≈ 340 LOC"). Don't just say "consider splitting".

5. **Feature flag.** Name the flag if the change is gated, or write `N/A` with a reason.

6. **Surface risk.** Call out data migrations, public-API shape changes, shared infra, cross-cutting refactors. Pick `low | medium | high` and justify in one sentence.

7. **Per-step failure modes.** For each implementation step, name at least one way it can go wrong and how the implementation should detect it.

8. **If `feedback` is set on rerun:**
   - Reproduce the previous plan in a collapsed `### Previous attempt` block.
   - Restate the user feedback verbatim under `### Feedback`.
   - Write the new plan under `### Revised plan`.

## Output

```
## Plan
1. <step> — files: <path:line> — verify: <how>
2. ...

### Quality analysis
- **Security:** <findings | "None identified — read-only client-side only">
- **Performance:** <findings | "None identified">
- **Reusability:** <patterns to follow>
- **Readability:** <concerns>
- **Testability:** <what to test, level>
- **Cross-team impact:** <repos/APIs | "Self-contained">

### Failure modes (per endpoint/method)
| Method/Endpoint | What can fail | Exception | Rescued? | User sees |
|-----------------|---------------|-----------|----------|-----------|

### Line estimate
- Total: <N> LOC across <M> files. PR split: <none | proposed split with math>.

### Feature flag
- <name | N/A — reason>

### Risks
- <risk> (low|medium|high) — <one-sentence justification>

### Per-step failure modes
- Step N: <symptom> → <detection>

---

## Stop — orchestrator fires GATE 1 next

Do not proceed to `implement` without explicit user approval. The orchestrator
must render the GATE 1 AskUserQuestion in the same turn that this plan is
delivered.
```

## Verification

- At least 3 numbered steps (1 step is OK for trivial tasks).
- Each step that touches existing code references a real `file:line`.
- Quality analysis covers all 6 dimensions (with "N/A — reason" if skipped).
- Failure-mode table is present (or `N/A — trivial change`).
- Line estimate is a number, not a guess.
- A `### Risks` and `### Per-step failure modes` subsection are present.
- No placeholder language: "TBD", "etc.", "handle error appropriately".
- The closing `## Stop — orchestrator fires GATE 1 next` block is present.

## Failure modes

- **Plan is too abstract:** rewrite, replacing every placeholder with the actual command, code, or test.
- **Plan disagrees with research findings:** if a referenced file doesn't exist or research said "don't change X", stop and surface to the user; do not silently re-draft.
- **Critical gap found in failure-mode table but no mitigation:** treat as a blocker; ask the user before proceeding to GATE 1.
