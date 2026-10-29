# Node.js API checklist (Express, NestJS, Fastify, Koa, Hono, Next.js server code)

## Input and injection (A03)

- `child_process.exec`/`execSync` or `spawn` with `shell: true` on user input -
  use `execFile`/`spawn` with an argument array.
- Raw SQL with template strings (`query(\`... ${id}\`)`, `$queryRawUnsafe`,
  `sequelize.query` without replacements, knex `.raw` with interpolation).
- Mongo/Mongoose filters built straight from `req.body`/`req.query` (operator
  injection: `{"password": {"$ne": null}}`); `$where`.
- `path.join(base, userInput)` / `res.sendFile` / `fs.*` without resolving and
  checking the result stays under `base` (path traversal).
- Prototype pollution: deep-merge/`Object.assign` of request JSON into objects,
  `obj[userKey] = value` with keys like `__proto__`.
- `vm`, `eval`, template engines rendering user-supplied templates (SSTI).
- No schema validation at the boundary (zod/joi/class-validator/ajv) for bodies,
  params and query.

## Access control and auth (A01, A07)

- Routes registered before the auth middleware, or a router mounted without it.
- NestJS controllers/handlers missing guards; `@Public()` on the wrong route.
- Ownership not checked when loading by id; tenant id from the request instead
  of the session.
- `jsonwebtoken.decode` used where `verify` is needed; `algorithms` not pinned.
- Session cookies without `httpOnly`, `secure`, `sameSite`; default session
  secrets.

## Hardening (A05)

- No `helmet` (or equivalent headers); `x-powered-by` left on.
- `cors({ origin: true, credentials: true })` or reflecting any origin.
- No rate limiting on login, OTP, password reset, signup, expensive endpoints.
- No body size limit (`express.json()` without `limit`, multer without
  `limits`); uploads saved with client-supplied file names.
- Error handler returning `err.stack` or raw DB errors.
- `trust proxy` misconfigured so IP-based rate limits can be spoofed via
  `X-Forwarded-For`.

## Request forgery (A10)

- `axios`/`fetch`/`got` to user-supplied URLs (webhooks, previews, imports)
  without an allowlist and without blocking private/metadata IPs
  (`169.254.169.254`, `127.0.0.1`, `10.0.0.0/8`, ...).
- Redirects (`res.redirect(req.query.next)`) to arbitrary hosts.

## Data

- Responses returning whole ORM rows (password hashes, tokens, internal flags).
- Secrets read at import time and logged on startup.
- Webhook endpoints that do not verify the provider signature (Stripe, GitHub,
  Slack...) or that compare signatures without a constant-time compare.
