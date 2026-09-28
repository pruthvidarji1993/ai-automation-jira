---
name: debug
description: Systematic root-cause analysis. Reproduce the failure deterministically, identify the cause, hand off a fix hypothesis. Use when triaging a bug before planning a fix.
---

# debug

Replace guessing with evidence. Bug fixes that skip this stage tend to ship
symptom patches that mask the real defect.

## Inputs

- The bug description (from intake or a free-form report).

## Procedure

1. **Get a deterministic reproduction.** A failing command, a failing test, a
   script that reliably triggers the bug. If you can't reproduce, that's the
   first problem to fix — say so and stop.

2. **Form 2–3 competing hypotheses.** Don't anchor on the first one. Each is
   one sentence: "X happens because Y."

3. **For each hypothesis, identify the cheapest disproof.** A log line, a
   `git blame`, a one-line code change, a query.

4. **Run the disproofs.** Keep the hypothesis that survives. Discard the
   others with a note.

5. **Name the root cause precisely.** Not "the listing breaks" but "sortKey
   defaults to null when the user has no saved preference, and the comparator
   throws on null".

6. **Hypothesize a fix.** Not the implementation — a one-paragraph approach
   with the file(s) likely to change.

## Output

```
## Reproduction
<steps + expected vs actual>

## Root cause
<precise statement with file:line evidence>

## Fix hypothesis
<one paragraph approach>
```

## Verification

- Reproduction is deterministic ("sometimes" fails this check).
- Root cause references at least one specific `file:line`.
- Fix hypothesis is concrete, not "TBD".

## Failure modes

- **Can't reproduce:** stop; report a blocker. Do not advance to plan.
- **Multiple surviving causes:** write up all of them and let the user pick.
