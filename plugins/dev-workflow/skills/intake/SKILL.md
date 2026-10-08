---
name: intake
description: Resolve a task description (ticket ID, URL, or free-form prompt) into structured task_type, size, risk, summary, acceptance criteria, validated success criteria, and cross-team impact. Use first when starting any new development task, or as the first step of the /feature orchestrator.
---

# intake

Turn a fuzzy task description into a structured intake the rest of the workflow can rely on. Validate the success criteria explicitly — unvalidated assumptions are the #1 cause of wasted implementation.

## Input

A `task_description`: ticket ID like `ABC-123`, a URL to Jira/Linear/GitHub, or free-form text.

## Procedure

1. **Resolve the source.**
   - Ticket-key shape (`^[A-Z]+-\d+$`): if an Atlassian/JIRA MCP is available, fetch the issue.
     If no JIRA MCP is connected, **stop and ask the user** to either:
     (a) connect the JIRA MCP so the ticket can be fetched, or
     (b) paste the ticket details (title, description, AC) directly.
     A bare ticket key carries no information on its own — do **not** infer AC from the key alone. Only fall back to free-form inference if the user already provided a description alongside the key, or explicitly declines both options.
   - URL: detect Jira / Linear / GitHub Issues / GitHub PR; use the appropriate MCP or `gh issue view` / `gh pr view`. For a Jira URL with no JIRA MCP connected, apply the same ask-to-connect-or-paste rule above.
   - Free-form: the user *is* the source.

2. **Extract acceptance criteria.** Pull explicit AC if present. Otherwise infer 3–5 testable criteria from the description.

3. **Classify task type.** Pick one of: `feature`, `bug`, `refactor`, `release`, `review`. Default to `feature` if ambiguous.

4. **Size the task.** Estimate from description + linked code references:
   - `trivial`: <50 LOC, 1 file.
   - `small`: 50–200 LOC, ≤3 files.
   - `medium`: 200–500 LOC.
   - `large`: >500 LOC or cross-cutting.

   If unsure, default to `medium`. Don't guess `trivial`.

   Size counts the files and layers the change actually needs, not how hard the ticket sounds.

5. **Score risk.** Size sets how much fan-out the workflow buys (lookups, review dimensions). Risk sets which model reviews and how deep. They are independent: a one-line change to a permission check is `trivial` and `high`.
   - `normal`: UI, copy, layout, isolated logic.
   - `high`: needs a **named trigger the change itself performs** - permissions or auth, money or contracts, data writes or deletes, a migration, a public API or schema change, a production incident.

   Score on evidence. Name the trigger in one line (`Risk: high - writes to the orders table`); with no trigger it is `normal`. When the evidence is split between `normal` and `high`, take `high`. A `trivial` task that is `high` risk does **not** take the trivial shortcut - it goes through research, plan and review.

6. **Validate success criteria.** State your assumption about what "done" means in plain language, distinct from the AC list. Flag anything the description leaves implicit. The orchestrator (or user) confirms this before research begins.

   **Anti-rationalization:** "I can infer what done means from the ticket" → NO. Surface the assumption so it can be challenged.

7. **Note cross-team impact.** Name any other repos, services, teams, or external APIs the change touches. If none, write `Self-contained`.

## Output

Return a structured block to the caller:

```
Type:    <feature|bug|refactor|release|review>
Size:    <trivial|small|medium|large>
Risk:    <normal|high> - <one-line reason or named trigger>
Summary: <one paragraph>

Acceptance criteria:
  1. <criterion>
  2. <criterion>
  ...

Success criteria (validated definition of done):
  <one or two sentences — the version that must be confirmed>

Cross-team impact:
  <repos / teams / APIs affected, or "Self-contained">
```

## Verification

- Type is one of the allowed values.
- Size is one of the allowed values.
- Risk is `normal` or `high`, with a one-line reason; `high` names its trigger.
- At least one acceptance criterion is listed.
- Success criteria block is present (not "tbd").
- Cross-team impact block is present (may be `Self-contained`).

## Failure modes

- **No JIRA MCP connected (ticket key/URL given):** ask the user to connect the JIRA MCP or paste the ticket details. Do not infer AC from a bare key.
- **Ticket fetch failed (MCP connected but errored), or user declines to connect/paste:** fall back to free-form; flag that AC are inferred.
- **Ambiguous type:** default to `feature`; surface the ambiguity in the summary.
- **Success criteria can't be stated without guessing:** stop and ask the user; do not invent.
