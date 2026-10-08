#!/usr/bin/env node
/**
 * The plugin is the source of truth. `.claude/skills` and `.claude/agents` are
 * mirrors so the workflow also works when this repo is opened without the
 * plugin installed. Edit under plugins/dev-workflow/, then:
 *
 *   node scripts/sync-workflow.mjs          copy plugin -> .claude
 *   node scripts/sync-workflow.mjs --check  exit 1 if the mirrors have drifted
 */
import { cpSync, existsSync, readdirSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const pairs = [
  ['plugins/dev-workflow/skills', '.claude/skills'],
  ['plugins/dev-workflow/agents', '.claude/agents'],
];
const check = process.argv.includes('--check');

const files = (dir) =>
  existsSync(dir)
    ? readdirSync(dir, { recursive: true, withFileTypes: true })
        .filter((e) => e.isFile())
        .map((e) => relative(dir, join(e.parentPath, e.name)))
        .sort()
    : [];

let drift = 0;
for (const [from, to] of pairs) {
  const src = join(root, from);
  const dst = join(root, to);
  const a = files(src);
  const b = files(dst);
  const problems = [
    ...a.filter((f) => !b.includes(f)).map((f) => `missing  ${to}/${f}`),
    ...b.filter((f) => !a.includes(f)).map((f) => `extra    ${to}/${f}`),
    ...a
      .filter(
        (f) =>
          b.includes(f) &&
          !readFileSync(join(src, f)).equals(readFileSync(join(dst, f)))
      )
      .map((f) => `differs  ${to}/${f}`),
  ];
  if (check) {
    problems.forEach((p) => console.error(p));
    drift += problems.length;
  } else {
    rmSync(dst, { recursive: true, force: true });
    cpSync(src, dst, { recursive: true });
    console.log(`synced ${from} -> ${to} (${a.length} files)`);
  }
}
if (check) {
  console.log(drift ? `${drift} drift problem(s)` : 'mirrors in sync');
  process.exit(drift ? 1 : 0);
}
