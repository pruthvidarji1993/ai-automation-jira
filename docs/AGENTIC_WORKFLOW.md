# Agentic workflow: models, subagents and the push gate

How the `dev-workflow` plugin decides which model runs which step, and what it
guards. Shipped in plugin v1.1.0. Everything here arrives with a plugin update;
a project that installed it needs no other change.

## Subagents

Four agents live in `plugins/dev-workflow/agents/`. Each holds its model choice
in one place, so a skill never names a model.

| Agent           | Model / effort  | Tools     | Job                                                          |
| --------------- | --------------- | --------- | ------------------------------------------------------------ |
| `lead`          | Opus / high     | all       | Root cause on a bug; verifies every review finding           |
| `scout`         | Sonnet / low    | read-only | One narrow lookup, 10 lines back, `file:line` evidence       |
| `reviewer`      | Sonnet / medium | read-only | One review dimension on `risk: normal`                       |
| `reviewer-deep` | Opus / high     | read-only | One review dimension on `risk: high`                         |

`scout` sets `omitClaudeMd`, so a lookup does not pay to load `CLAUDE.md`; the
calling skill pastes in any rule the lookup needs.

Installed as a plugin, agent names are namespaced: `dev-workflow:scout`. The
skills write the bare name and say so; Claude uses whichever name its agent
list shows.

## Size and Risk

`intake` scores both. They are independent.

- **Size** (`trivial` / `small` / `medium` / `large`) sets fan-out: how many
  scouts research dispatches, how many review dimensions run.
- **Risk** (`normal` / `high`) sets the model and depth. `high` needs a named
  trigger the change itself performs: auth or permissions, money or contracts,
  data writes or deletes, a migration, a public API or schema change, a
  production incident. No trigger means `normal`. When the evidence is split,
  take `high`.

A `trivial` change with `risk: high` does **not** take the trivial shortcut; it
goes through research, plan and review.

| Size      | Research lookups                          | Review                          |
| --------- | ----------------------------------------- | ------------------------------- |
| `trivial` | none                                      | none (`normal` risk only)       |
| `small`   | none, search inline                       | inline                          |
| `medium`  | 1-3 `scout` on the layers likely touched  | 3-5 reviewer dimensions         |
| `large`   | every layer, plus the API contract        | every dimension the diff touches |

`risk: high` adds the auth / permissions lookup at any size, and uses
`reviewer-deep` for every dimension.

## Model policy

- **Main-conversation skills are not model-pinned.** The prompt cache is per
  model; switching mid-conversation re-reads the whole context at full price.
  Only subagents, which start fresh, get their own model.
- **Aliases only.** Agents use `opus` / `sonnet`. Never write a full model id
  into a skill or agent; nothing needs editing when a model ships.
- **Recommended default: `opusplan`** (Opus in plan mode, Sonnet elsewhere). A
  plugin cannot set a user's default model, so set it per project:

  ```json
  { "model": "opusplan" }
  ```

  in `.claude/settings.json`. This repo does.

Non-negotiable, whatever the seat or token budget:

1. All gates stay.
2. The plan, a bug's root cause and the final check of every review finding run
   on Opus.
3. `risk: high` work never drops to a cheaper model.
4. The objective checks (typecheck, lint, tests, build) are model-independent.
5. A missing Size or Risk is scored up, never down.

### Usage limits

| Message                      | Do this                                                                                                    |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------- |
| "You've hit your Opus limit" | `/model sonnet`, and set `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` plus `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` in `.claude/settings.local.json` `env` until it resets |
| Session or weekly limit      | Covers all models, so switching does not help; wait for the reset                                          |
| Usage climbing               | `/clear` between tasks                                                                                     |

`/usage` shows what each skill and subagent cost.

### When a new model ships

Aliases move on their own. Keep three finished tasks (one `small`, `medium`,
`large`) with their approved plans and final diffs, re-run them on a scratch
branch after a release, and compare: checks pass, review catches the known
issues, `/usage` is similar or lower. If not, hold the old model with
`ANTHROPIC_DEFAULT_SONNET_MODEL` / `ANTHROPIC_DEFAULT_OPUS_MODEL` until the
prompts are adjusted.

## Done means

`plan` ends with a `Done when` checklist: each line one measurable end state
plus the command or check that proves it, covering every acceptance criterion.
A run is finished only when every box is ticked with output as evidence. Two
review rounds is the cap; after that, escalate rather than loop.

## Protected-branch push gate

A `PreToolUse` hook (`plugins/dev-workflow/hooks/restrict-protected-push.mjs`)
blocks `git push` to a protected branch before it runs. It resolves where a push
really lands (current branch, upstream, `remote.*.push`, `push.default`),
handles `+refspecs`, `git -C/-c`, `bash -c`, `$(...)` and aliases, and fails
closed on anything unparseable. It also blocks setting `user.email` to an
allowlisted address, `push --no-verify`, `core.hooksPath` changes, writes to a
protected ref through `gh api`, and edits to `.claude/push-gate.conf`.

**Default behaviour:** `main`, `master` and `develop` are protected and nobody is
allowlisted, so Claude opens a PR instead. Pushing a feature branch is never
affected.

To let an owner push directly, or change the branches, add
`.claude/push-gate.conf` to the project (create it yourself in a terminal; the
gate does not let a session edit it):

```
PROTECTED_BRANCHES='main master develop'
ALLOWED_PUSH_EMAILS='you@example.com'
```

It is a guardrail for the ordinary case, not a sandbox. Only server-side branch
protection is a real boundary.

Check the parser: `npm run workflow:test`.

## Maintaining this repo

The plugin is the source of truth. `.claude/skills` and `.claude/agents` mirror
it so the workflow also works when the repo is opened without the plugin.

```bash
npm run workflow:sync    # plugin -> .claude
npm run workflow:check   # exit 1 if the mirrors drifted
```

After a change, bump `version` in both `plugin.json` and `marketplace.json`;
installed copies only update when the version changes.
