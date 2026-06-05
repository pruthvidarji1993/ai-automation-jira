# Copilot prompts

Reusable prompt files for [GitHub Copilot Chat](https://docs.github.com/en/copilot) that drive an end-to-end development workflow — ticket in, reviewed PR out. Mirrors the Claude skills in [.claude/skills/](.claude/skills/).

## Usage

Invoke any prompt by typing its name as a slash command in Copilot Chat:

```
/feature ABC-123
/intake "add debounce to product search"
/review 42
```

Each `<name>.prompt.md` in [.github/prompts/](.github/prompts/) is self-contained — Copilot picks them up automatically when this folder is present.

> Requires VS Code with prompt files enabled (`chat.promptFiles: true` in settings), or a Copilot client that supports `.github/prompts/`.

## The orchestrator

**`/feature <task>`** describes the full pipeline:

```
intake → research → plan → [GATE 1: approve plan]
       → implement → [GATE 2: approve diff]
       → test → review → ship
```

Pass a ticket ID (`ABC-123`), a Jira/Linear/GitHub URL, or a free-form description.

> **Important — Copilot does not auto-chain prompts.** Unlike the Claude version, where `/feature` automatically invokes each sub-skill, Copilot's `.github/prompts/` only loads one prompt per slash command. `/feature` will produce the **intake output and stop** — you then manually run `/research`, `/plan`, etc. one after the other (in the same chat session, so prior context carries over). The gate steps (approve plan / approve diff) happen naturally between your manual invocations.
>
> If you want a single-command end-to-end flow, use the Claude version ([.claude/skills/](.claude/skills/)) — Copilot is best used here for individual stages.

## Individual prompts

Use these directly when you want a single stage instead of the full flow.

| Prompt | What it does |
|--------|--------------|
| [`/intake`](.github/prompts/intake.prompt.md) | Resolve a task into structured type, size, summary, AC, success criteria |
| [`/research`](.github/prompts/research.prompt.md) | Explore the codebase, validate hypotheses, gather `file:line` evidence |
| [`/plan`](.github/prompts/plan.prompt.md) | Produce an implementation plan with quality analysis + failure modes |
| [`/implement`](.github/prompts/implement.prompt.md) | Execute an approved plan as commits on a feature branch |
| [`/refactor`](.github/prompts/refactor.prompt.md) | Behavior-preserving structural changes, tests green every commit |
| [`/debug`](.github/prompts/debug.prompt.md) | Reproduce a bug deterministically, identify root cause |
| [`/test`](.github/prompts/test.prompt.md) | Add or strengthen tests around a change |
| [`/review`](.github/prompts/review.prompt.md) | Structured diff/PR review with critical / warning / info findings |
| [`/ship`](.github/prompts/ship.prompt.md) | Self-review → QA → PR open → address review comments |

## Suggested manual sequence

For a full feature in Copilot, run these in order within the same chat session — prior outputs stay in context, so you don't need to re-paste them:

```
/intake     ABC-123       → captures type, size, AC, success criteria
/research                 → file:line evidence + conventions
/plan                     → implementation plan
                          ── GATE 1: you approve or request changes ──
/implement                → edits in working tree (no commits yet)
                          ── GATE 2: you approve or request changes ──
/test                     → run suite, add coverage
/review                   → critical / warning / info findings
/ship                     → self-review, QA, commit, PR
```

Skip stages that don't apply (e.g. trivial change → `/intake` → `/implement` → `/ship`). If you start a fresh session mid-flow, re-share the prior outputs so context isn't lost.

## Conventions

- Prompts are independent — Copilot won't chain them. You drive the sequence.
- `/implement` leaves edits uncommitted. Only `/ship` runs `git commit`.
- Every plan or review finding cites `file:line` — no hand-wavy claims.

## Relation to the Claude skills

These prompts are a direct port of [.claude/skills/](.claude/skills/). Same procedures, same gates, same outputs. Key difference:

| | Claude (`.claude/skills/`) | Copilot (`.github/prompts/`) |
|---|---|---|
| Orchestration | `/feature` auto-chains all stages and fires gates inline | Each `/prompt` is a separate invocation — you chain them manually |
| Sub-invocation | Skill tool calls other skills | You paste prior output into the next prompt |
| Gates | `AskUserQuestion` rendered inline | Plain Q&A between your invocations |
| Fresh-context review | Spawned `Agent` worker | New Copilot Chat session |

Pick the Claude version when you want full automation; pick Copilot prompts when you want to drive each stage yourself.
