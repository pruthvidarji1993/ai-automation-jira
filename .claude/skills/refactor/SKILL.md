---
name: refactor
description: Execute behavior-preserving structural changes. Tests stay green at every commit; one concern per commit; no drive-by changes. Use when restructuring code without changing observable behavior.
---

# refactor

Refactors are easy to do badly. This skill enforces the discipline that makes
them safe.

## Inputs

- An approved refactor plan.
- Optional: user feedback on rerun.

## Procedure

1. **Pre-flight.** Run the existing test suite. If it isn't green before you
   start, stop — refactoring on a red suite is fishing in the dark.

2. **Snapshot before-state.** One paragraph describing the subsystem's current
   shape and behavior.

3. **For each plan step:**
   1. Make the change.
   2. Run tests — they must stay green.
   3. Commit. One concern per commit. Subject: `refactor(<scope>): <what>`.

4. **No drive-by changes.** If you spot a bug or want to delete unused code,
   write it down as a follow-up and keep going. Mixing concerns makes the
   refactor unreviewable.

5. **Snapshot after-state.** One paragraph on the new shape and what behavior
   is now easier / cheaper / clearer.

## Output

```
Branch:  <branch>
Commits: <list>

## Before
<paragraph>

## After
<paragraph>

Follow-ups noticed (not addressed):
- <item>
```

## Verification

- Test suite green at every commit.
- No commit mixes refactor with behavior change.
- Before/After sections present.

## Failure modes

- **Tests red before starting:** stop, refuse to refactor.
- **Tests go red mid-stream:** stop, revert the offending commit, re-plan.
