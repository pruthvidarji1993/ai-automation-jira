#!/usr/bin/env node
/**
 * PreToolUse gate: only the emails listed in `.claude/push-gate.conf` may push
 * a protected branch (default: main, master, develop) directly from a Claude
 * Code session. Everyone else opens a PR.
 *
 * OPT-IN: the gate is inert unless the project has `.claude/push-gate.conf`.
 * Installing or updating the plugin never changes how a project pushes.
 *
 * It resolves where a push will really land - the current branch, the
 * configured upstream, `remote.*.push` and `push.default=matching` - and treats
 * anything it cannot parse (variables, globs, shell aliases) as a possible hit.
 * A feature branch cut from origin/develop tracks develop, so a bare
 * `git push` there would update develop; checking only the branch name misses it.
 *
 * Configure per project in `.claude/push-gate.conf` (plain KEY='a b c' lines):
 *
 *   PROTECTED_BRANCHES='main master develop'
 *   ALLOWED_PUSH_EMAILS='you@example.com'
 *
 * With the file present but a key missing, the default branches are protected
 * and nobody is allowlisted. There is deliberately no env-var escape hatch: a
 * session that can set env vars could switch the gate off.
 *
 * FAILURE MODEL - fail CLOSED for git pushes: if parsing or git lookups throw
 * on a command that looks like a push, it is blocked. Non-push commands are
 * never blocked by an internal error.
 *
 * Also guards against a session defeating the gate: setting user.email to an
 * allowlisted address, `push --no-verify`, `core.hooksPath` changes, writes to
 * a protected ref through `gh api`, and edits to `.claude/push-gate.conf`.
 *
 * SCOPE: a guardrail for the ordinary case, not a sandbox. A determined local
 * user can still bypass client-side hooks; only server-side branch protection
 * is a real boundary. Verify the parser with:
 *
 *   node restrict-protected-push.mjs --selftest
 */
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const PROJECT_ROOT = process.env.CLAUDE_PROJECT_DIR || process.cwd();

/** Read KEY='a b c' from the project conf; fall back to defaults if absent. */
function loadConf() {
  const defaults = {
    PROTECTED_BRANCHES: 'develop main master',
    ALLOWED_PUSH_EMAILS: '',
  };
  try {
    const text = readFileSync(
      join(PROJECT_ROOT, '.claude', 'push-gate.conf'),
      'utf8'
    );
    for (const key of Object.keys(defaults)) {
      const m = text.match(new RegExp(`^${key}='([^']*)'`, 'm'));
      if (m && m[1].trim()) defaults[key] = m[1];
    }
  } catch {
    // no conf (or unreadable): keep defaults - the gate must not silently open
  }
  return defaults;
}

const GATE_ENABLED = existsSync(join(PROJECT_ROOT, '.claude', 'push-gate.conf'));
const conf = loadConf();
const PROTECTED = new Set(conf.PROTECTED_BRANCHES.split(/\s+/).filter(Boolean));
const ALLOWED_EMAILS = new Set(
  conf.ALLOWED_PUSH_EMAILS.split(/\s+/).filter(Boolean)
);

// Files a non-allowlisted session must not edit: they are the gate itself.
const GATE_FILES = [/(^|\/)\.claude\/push-gate\.conf$/];

/** "+refs/heads/develop" -> "develop". */
const bareBranch = (s) => s.replace(/^\+/, '').replace(/^refs\/heads\//, '');

/** Variables, globs and substitutions cannot be resolved statically. */
const isUnresolvable = (s) => /[$*?[\]`]/.test(s);

const SEGMENT_SPLIT = /&&|\|\||;|\n|\||`|\$\(|\(|\)/;

/** Strip quotes so `git push origin "develop"` and `bash -c "git push ..."` tokenize. */
function tokenize(seg) {
  return seg.replace(/['"]/g, ' ').trim().split(/\s+/).filter(Boolean);
}

/** Global git options that consume the next token when not written as --opt=value. */
const GIT_GLOBAL_WITH_VALUE = new Set([
  '-C',
  '-c',
  '--git-dir',
  '--work-tree',
  '--namespace',
  '--exec-path',
  '--config-env',
]);

/**
 * Given tokens starting at the `git` word, return { sub, args, aliases } where
 * sub is the real subcommand, args what follows it, and aliases any
 * `-c alias.x=y` definitions passed inline.
 */
function parseGit(toks) {
  const aliases = {};
  let i = 1;
  while (i < toks.length && toks[i].startsWith('-')) {
    const t = toks[i];
    if (GIT_GLOBAL_WITH_VALUE.has(t)) {
      if (t === '-c' && toks[i + 1]) {
        const m = toks[i + 1].match(/^alias\.([^=]+)=(.*)$/);
        if (m) aliases[m[1]] = m[2];
      }
      i += 2;
    } else {
      i += 1;
    }
  }
  return { sub: toks[i] ?? '', args: toks.slice(i + 1), aliases };
}

/**
 * Remote branch names one `git push` argv (after "push") may update/delete.
 * `ctx` supplies lazy, git-backed lookups so tests can inject fakes.
 * Unparseable input is reported as every protected branch.
 */
function pushTargets(argv, ctx) {
  const all = () => new Set(PROTECTED);
  const flags = argv.filter((a) => a.startsWith('-'));
  const positional = argv.filter((a) => !a.startsWith('-'));

  if (flags.some((f) => f === '--all' || f === '--mirror')) return all();

  const out = new Set();

  // No explicit refspec (`git push`, `git push origin`): git decides.
  if (positional.length <= 1) {
    const cur = ctx.currentBranch();
    if (cur) out.add(cur);
    const up = ctx.upstreamBranch();
    if (up) out.add(up);
    for (const spec of ctx.configuredPushRefspecs()) {
      const dest = spec.includes(':') ? spec.split(':').pop() : spec;
      if (!dest || isUnresolvable(dest)) return all();
      out.add(bareBranch(dest));
    }
    if (ctx.pushDefault() === 'matching') return all();
  }

  for (const spec of positional) {
    if (isUnresolvable(spec)) return all();
    const body = spec.replace(/^\+/, '');
    const colon = body.indexOf(':');
    const dest =
      colon === -1 ? body : body.slice(colon + 1) || body.slice(0, colon);
    const name = bareBranch(dest);
    out.add(name === 'HEAD' || name === '@' ? ctx.currentBranch() : name);
  }
  out.delete('');
  return out;
}

/**
 * Every protected branch any `git push` in `cmd` could touch. Resolves
 * aliases (inline `-c alias.x=`, repo config) and treats shell aliases that
 * mention push as an unknown push to every protected branch.
 */
function protectedTargetsIn(cmd, ctx) {
  const hit = new Set();
  for (const seg of cmd.split(SEGMENT_SPLIT)) {
    const toks = tokenize(seg);
    const gitAt = toks.findIndex((t) => t.replace(/.*\//, '') === 'git');
    if (gitAt === -1) continue;

    const { sub, args, aliases } = parseGit(toks.slice(gitAt));
    let pushArgs = null;
    if (sub === 'push') {
      pushArgs = args;
    } else if (sub) {
      const alias = aliases[sub] ?? ctx.alias(sub);
      if (alias) {
        if (alias.startsWith('!')) {
          if (/\bpush\b/.test(alias)) PROTECTED.forEach((b) => hit.add(b));
        } else {
          const at = tokenize(alias);
          if (at[0] === 'push') pushArgs = [...at.slice(1), ...args];
        }
      }
    }
    if (!pushArgs) continue;
    for (const b of pushTargets(pushArgs, ctx)) {
      if (PROTECTED.has(b)) hit.add(b);
    }
  }
  return hit;
}

function git(cwd, args) {
  try {
    return execFileSync('git', args, {
      cwd,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return '';
  }
}

function realContext(cwd) {
  const current = () => git(cwd, ['rev-parse', '--abbrev-ref', 'HEAD']);
  return {
    currentBranch: current,
    upstreamBranch: () => {
      const cur = current();
      return cur
        ? bareBranch(git(cwd, ['config', '--get', `branch.${cur}.merge`]))
        : '';
    },
    configuredPushRefspecs: () =>
      git(cwd, ['config', '--get-regexp', '^remote\\..*\\.push$'])
        .split('\n')
        .map((l) => l.replace(/^\S+\s+/, ''))
        .filter(Boolean),
    pushDefault: () => git(cwd, ['config', '--get', 'push.default']),
    alias: (name) => git(cwd, ['config', '--get', `alias.${name}`]),
  };
}

// ---- self-test --------------------------------------------------------------
if (process.argv.includes('--selftest')) {
  const fake = (o = {}) => ({
    currentBranch: () => o.cur ?? 'feat/x',
    upstreamBranch: () => o.up ?? '',
    configuredPushRefspecs: () => o.pushSpecs ?? [],
    pushDefault: () => o.pushDefault ?? '',
    alias: (n) => (o.aliases ?? {})[n] ?? '',
  });
  const cases = [
    ['plain push to develop', 'git push origin develop', fake(), ['develop']],
    ['HEAD refspec', 'git push origin HEAD:develop', fake(), ['develop']],
    [
      'refs/heads form',
      'git push origin HEAD:refs/heads/main',
      fake(),
      ['main'],
    ],
    ['delete flag', 'git push origin --delete develop', fake(), ['develop']],
    ['colon delete form', 'git push origin :master', fake(), ['master']],
    ['force plus prefix', 'git push origin +develop', fake(), ['develop']],
    [
      'force-with-lease',
      'git push --force-with-lease origin HEAD:develop',
      fake(),
      ['develop'],
    ],
    [
      'bare push, current protected',
      'git push',
      fake({ cur: 'develop' }),
      ['develop'],
    ],
    ['bare push, safe branch', 'git push', fake(), []],
    [
      'bare push, upstream is develop (the incident)',
      'git push',
      fake({ up: 'develop' }),
      ['develop'],
    ],
    [
      'git push origin, upstream is develop',
      'git push origin',
      fake({ up: 'develop' }),
      ['develop'],
    ],
    [
      'push -u origin HEAD, upstream is develop',
      'git push -u origin HEAD',
      fake({ up: 'develop' }),
      [],
    ],
    [
      'remote.origin.push points at develop',
      'git push',
      fake({ pushSpecs: ['HEAD:refs/heads/develop'] }),
      ['develop'],
    ],
    [
      'push.default=matching',
      'git push',
      fake({ pushDefault: 'matching' }),
      ['develop', 'main', 'master'],
    ],
    ['feature branch explicit', 'git push origin feat/x', fake(), []],
    [
      'feature branch w/ main in name',
      'git push origin feat/maintenance',
      fake(),
      [],
    ],
    [
      'two refspecs, one protected',
      'git push origin feat/x develop',
      fake(),
      ['develop'],
    ],
    [
      '--all is conservative',
      'git push --all',
      fake(),
      ['develop', 'main', 'master'],
    ],
    [
      'chained after &&',
      'npm test && git push origin develop',
      fake(),
      ['develop'],
    ],
    [
      'git -C dir push',
      'git -C ../other push origin develop',
      fake(),
      ['develop'],
    ],
    [
      'git -c k=v push',
      'git -c push.default=upstream push origin develop',
      fake(),
      ['develop'],
    ],
    [
      'bash -c wrapper',
      'bash -c "git push origin develop"',
      fake(),
      ['develop'],
    ],
    [
      'command substitution',
      'echo $(git push origin develop)',
      fake(),
      ['develop'],
    ],
    [
      'absolute git path',
      '/usr/bin/git push origin develop',
      fake(),
      ['develop'],
    ],
    [
      'variable refspec',
      'git push origin $BR',
      fake(),
      ['develop', 'main', 'master'],
    ],
    [
      'glob refspec',
      'git push origin refs/heads/*:refs/heads/*',
      fake(),
      ['develop', 'main', 'master'],
    ],
    [
      'repo alias to push',
      'git pu origin develop',
      fake({ aliases: { pu: 'push' } }),
      ['develop'],
    ],
    [
      'inline -c alias',
      'git -c alias.pp=push pp origin develop',
      fake(),
      ['develop'],
    ],
    [
      'shell alias with push',
      'git ship',
      fake({ aliases: { ship: '!git push' } }),
      ['develop', 'main', 'master'],
    ],
    ['unrelated command', 'git status', fake(), []],
    ['push -u safe', 'git push -u origin feat/x', fake(), []],
  ];
  let bad = 0;
  for (const [name, cmd, ctx, want] of cases) {
    const got = [...protectedTargetsIn(cmd, ctx)].sort();
    const wantSorted = [...want].sort();
    if (JSON.stringify(got) !== JSON.stringify(wantSorted)) {
      bad++;
      console.error(
        `FAIL ${name}: got=${JSON.stringify(got)} want=${JSON.stringify(wantSorted)}`
      );
    }
  }
  console.log(
    bad
      ? `\n${bad} selftest failure(s) - the gate is NOT reliable`
      : `selftest: ${cases.length}/${cases.length} OK`
  );
  process.exit(bad ? 1 : 0);
}

// ---- main -------------------------------------------------------------------
const block = (title, detail) => {
  process.stderr.write(`BLOCKED: ${title}\n\n${detail}\n`);
  process.exit(2);
};

// Opt-in: no conf file means this project did not ask for a gate.
if (!GATE_ENABLED) process.exit(0);

let cmd = '';
try {
  const chunks = [];
  for await (const c of process.stdin) chunks.push(c);
  const raw = chunks.join('');
  if (!raw.trim()) process.exit(0);

  let payload;
  try {
    payload = JSON.parse(raw);
  } catch {
    process.exit(0);
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload))
    process.exit(0);

  const cwd = PROJECT_ROOT;
  const email = git(cwd, ['config', 'user.email']);
  const allowed = ALLOWED_EMAILS.has(email);

  // Edits to the gate files themselves.
  const filePath =
    payload.tool_input?.file_path ?? payload.tool_input?.notebook_path;
  if (typeof filePath === 'string' && payload.tool_name !== 'Bash') {
    if (!allowed && GATE_FILES.some((re) => re.test(filePath))) {
      block(
        `${filePath} is part of the protected-branch gate.`,
        `Only ${[...ALLOWED_EMAILS].join(', ') || '(nobody is allowlisted)'} may change it through Claude.\nEdit it yourself in a terminal.\ngit config user.email: ${email || '(not set)'}`
      );
    }
    process.exit(0);
  }

  if (payload.tool_name !== 'Bash') process.exit(0);
  cmd =
    payload.tool_input && typeof payload.tool_input.command === 'string'
      ? payload.tool_input.command
      : '';
  if (!cmd || !/\bgit\b|\bgh\b/.test(cmd)) process.exit(0);

  if (!allowed) {
    // Impersonating an allowlisted identity.
    const spoof =
      /user\.email|GIT_(AUTHOR|COMMITTER)_EMAIL|GIT_CONFIG_(COUNT|PARAMETERS|GLOBAL)/.test(
        cmd
      ) && [...ALLOWED_EMAILS].some((e) => cmd.includes(e));
    if (spoof) {
      block(
        'setting git identity to an allowlisted address.',
        `Attempted: ${cmd.slice(0, 300)}\nOnly the real owner of that identity may push protected branches.`
      );
    }
    // Disabling the client-side hooks.
    if (
      /\bgit\b[^;&|\n]*(core\.hooksPath|--no-verify[^;&|\n]*\bpush\b|\bpush\b[^;&|\n]*--no-verify)/.test(
        cmd
      )
    ) {
      block(
        'bypassing or relocating git hooks.',
        `Attempted: ${cmd.slice(0, 300)}\n'core.hooksPath' changes and 'git push --no-verify' are not allowed here.`
      );
    }
    // Moving a protected ref through the GitHub API.
    const names = [...PROTECTED].join('|');
    if (
      /\bgh\s+api\b/.test(cmd) &&
      new RegExp(
        `git/refs/heads/(${names})\\b|branches/(${names})/(merge|rename)`
      ).test(cmd) &&
      /(-X|--method)\s*(PATCH|PUT|POST|DELETE)|-f\s|-F\s|--field|--raw-field/i.test(
        cmd
      )
    ) {
      block(
        'writing a protected branch through `gh api`.',
        `Attempted: ${cmd.slice(0, 300)}\nOpen a PR instead.`
      );
    }
  }

  // No cheap pre-filter on "push": an alias can hide it.
  const ctx = realContext(cwd);
  const hits = protectedTargetsIn(cmd, ctx);
  if (hits.size === 0 || allowed) process.exit(0);

  const upstream = ctx.upstreamBranch();
  const hint =
    upstream && PROTECTED.has(upstream)
      ? `\nThis branch tracks '${upstream}', so a bare 'git push' lands there. Fix it:\n  git branch --unset-upstream\n  git push -u origin HEAD\n`
      : '';
  block(
    `direct push to protected branch(es) [${[...hits].join(', ')}] is restricted.`,
    `Attempted: ${cmd.slice(0, 300)}\ngit config user.email: ${email || '(not set)'}\nAllowed to push these directly: ${[...ALLOWED_EMAILS].join(', ') || '(nobody - no allowlist configured)'}\n${hint}\nOpen a PR into the target branch instead of pushing to it directly.\nTo let an owner push directly, list their email in .claude/push-gate.conf:\n  ALLOWED_PUSH_EMAILS='you@example.com'`
  );
} catch (err) {
  // Fail closed for anything that looks like a push; never brick other commands.
  if (/\bgit\b/.test(cmd) && /\bpush\b/.test(cmd)) {
    block(
      `could not verify this git push (${err?.message ?? err}).`,
      'Blocked to stay safe. Run: node <plugin>/hooks/restrict-protected-push.mjs --selftest'
    );
  }
  process.stderr.write(
    `[push-gate] internal error, allowing non-push call: ${err?.message ?? err}\n`
  );
  process.exit(0);
}
