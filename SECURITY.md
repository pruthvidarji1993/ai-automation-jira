# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 1.1.x (latest `dev-workflow` plugin) | ✅ |
| Older | ❌ |

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report privately through GitHub: **Security tab → Report a vulnerability**
([direct link](https://github.com/pruthvidarji1993/ai-automation-jira/security/advisories/new)).

Include:
- the affected component (skill, agent, hook, prompt or config file) and version
- steps to reproduce
- the impact you expect

You can expect an acknowledgement within a few days. This is a solo-maintained project, so fix timelines depend on severity; confirmed issues are fixed in a patch release and credited unless you prefer otherwise.

## In scope

- The push gate (`plugins/dev-workflow/hooks/restrict-protected-push.mjs`) being bypassable
- Skills, agents or prompts that could leak secrets (for example Jira or API tokens) or run unintended commands
- Unsafe default permissions in `.claude/settings.json`

## Out of scope

- The sandbox Next.js app in `app/`
- Behavior of Claude Code, GitHub Copilot, Jira or other third-party tools themselves

## Using this safely

- Never commit Jira, GitHub or API tokens.
- Review `.claude/settings.json` and the plugin's hooks before enabling them in a project.
- Keep the push gate enabled (`.claude/push-gate.conf`) on repositories with protected branches.
