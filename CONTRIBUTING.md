# Contributing

Thanks for helping improve the workflow.

1. Branch from `main` (`feat/...`, `fix/...`, `docs/...`).
2. The Claude and Copilot flows are kept in sync by a script. After editing workflow files run `npm run workflow:sync`, then verify with `npm run workflow:check` and `npm run workflow:test`.
3. Run `npm run lint` and `npm run build`.
4. If the `dev-workflow` plugin changed, bump the version in `plugins/dev-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
5. Open a PR; CI runs the same checks.

Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`).
