---
name: test
description: Run the project's test suite, add coverage for new behavior, and (for bugfixes) add a regression test that fails pre-fix and passes post-fix. Use after implement, or as step 6 of /feature.
---

# test

Verify behavior. Add tests where they're missing. Make failures actionable.

## Inputs

- The working branch.
- Task type (drives policy — bugfix requires a regression test).
- Optional: reproduction steps from the `debug` skill (bugfix only).

## Procedure

1. **Detect the test runner.** Inspect `package.json`, `pyproject.toml`,
   `Gemfile`, `go.mod`, etc.

2. **Run the existing suite.** Capture pass/fail counts and the first 10
   failures with `file:line`.

3. **For bugfixes only:**
   - Convert the reproduction into a failing test in the canonical test
     location for that file.
   - Confirm the test fails on the pre-fix tree (compare against `main`).
   - Confirm the test passes on the current branch.
   - Commit as `test(<scope>): regression test for <ticket>`.

4. **For features and refactors:**
   - Add new tests for any new public surface.
   - Don't duplicate existing coverage.

5. **For UI changes (if a browser MCP is available):** smoke-test the changed
   screen and capture a screenshot.

## Output

```
## Test results
- Suite: <runner>, <N> passed, <M> failed (<duration>)
- New tests: <count> (<files>)
- Regression test: <path> ✔  (bugfix only)
- UI smoke: <passed|n/a>
- all_green: <true|false>
```

## Verification

- `all_green` matches the reported counts.
- For bugfixes: a regression test file exists at the reported path.
- Pre-existing failures unrelated to this change are called out separately.

## Failure modes

- **No test runner detected:** report a blocker and stop.
- **Regression test passes pre-fix:** the test isn't actually catching the
  bug — strengthen it before claiming coverage.
