# Claude skills

Custom skills for [Claude Code](https://claude.com/claude-code) that drive an end-to-end development workflow — ticket in, reviewed PR out.

## Usage

Invoke any skill by typing its name as a slash command in Claude Code:

```
/feature ABC-123
/intake "add debounce to product search"
/review 42
```

Skills live in [.claude/skills/](.claude/skills/). Each `SKILL.md` is self-contained — Claude loads it on invocation.

## The orchestrator

**`/feature <task>`** runs the full pipeline:

```
intake → research → plan → [GATE 1: approve plan]
       → implement → [GATE 2: approve diff]
       → test → review → ship
```

Pass a ticket ID (`ABC-123`), a Jira/Linear/GitHub URL, or a free-form description. The flow pauses at the two gates for your approval; everything else is automated.

## Individual skills

Use these directly when you want a single stage instead of the full flow.

| Skill | What it does |
|-------|--------------|
| [`/intake`](.claude/skills/intake/SKILL.md) | Resolve a task into structured type, size, summary, AC, success criteria |
| [`/research`](.claude/skills/research/SKILL.md) | Explore the codebase, validate hypotheses, gather `file:line` evidence |
| [`/plan`](.claude/skills/plan/SKILL.md) | Produce an implementation plan with quality analysis + failure modes |
| [`/implement`](.claude/skills/implement/SKILL.md) | Execute an approved plan as commits on a feature branch |
| [`/refactor`](.claude/skills/refactor/SKILL.md) | Behavior-preserving structural changes, tests green every commit |
| [`/debug`](.claude/skills/debug/SKILL.md) | Reproduce a bug deterministically, identify root cause |
| [`/test`](.claude/skills/test/SKILL.md) | Add or strengthen tests around a change |
| [`/review`](.claude/skills/review/SKILL.md) | Structured diff/PR review with critical / warning / info findings |
| [`/ship`](.claude/skills/ship/SKILL.md) | Self-review → QA → PR open → address review comments |

## Conventions

- Skills delegate; they don't duplicate work. `/feature` calls the others — don't reinvoke a stage it already ran.
- `/implement` leaves edits uncommitted. Only `/ship` runs `git commit`.
- Every plan or review finding cites `file:line` — no hand-wavy claims.
