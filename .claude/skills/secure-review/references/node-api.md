# Node.js API checklist (Express, NestJS, Fastify, Next.js server code)

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

## Mass assignment and wildcard queries

- `Model.create(req.body)`, `prisma.x.update({ data: req.body })`,
  `{ ...req.body }` spread into an ORM call, Mongoose `findByIdAndUpdate(id,
  req.body)`: pick fields through a zod/class-validator DTO with
  `whitelist`/`forbidNonWhitelisted` (Nest) or `.strict()` (zod).
- `select *` / `findMany()` / `find()` without `select`/`projection` returned
  to the client; see `database.md` for query and migration checks.

## CSRF

- Cookie-authenticated, state-changing routes with no token, no `SameSite`
  and no `Origin`/`Referer` check. `csurf` is deprecated; use a maintained
  double-submit/token library or verify `Origin` plus `SameSite=Lax/Strict`.
- CSRF middleware skipped for a whole router or for `POST` webhooks that also
  accept browser sessions; token compared with `==` instead of constant time.
- Bearer-token APIs are not CSRF-prone, but the same route must not also
  accept the session cookie.

## File upload

- multer/busboy/formidable with no `fileFilter`, or a filter that trusts
  `file.mimetype` / extension from the client (check magic bytes, e.g.
  `file-type`). Allowlist exact types (`image/png`, `image/jpeg`,
  `application/pdf`), never `*/*`, `image/*` or a blank filter.
- No `limits` (`fileSize`, `files`); whole file buffered in memory.
- Stored under `public/` or a static-served folder; client file name or path
  used on disk (use a random name, resolve and check the path stays inside the
  upload root, store outside the web root or in object storage with private
  ACLs and signed URLs). HTML/SVG served inline from the upload path.

## Routes, versioning and responses

- Route inventory: list every route file/controller and check each has auth
  and authorization; look for routes registered outside the main router, old
  or commented-out routes still mounted, and wildcard/catch-all handlers.
- API versioning: unversioned public API (`/api/orders`) or an old `/v1`
  left mounted without the auth, validation and rate limits added to `/v2`.
- Response contract: status codes and error messages as scattered literals
  instead of shared constants/enums; handlers that return different shapes
  for success and failure, or `200` with an error body; error text that
  differs for "not found" vs "forbidden" (enumeration). Use one response
  helper and one constants file.

## N+1

- `await` inside `for`/`map` calling the DB; Prisma/TypeORM/Sequelize relation
  loaded per item instead of `include`/`relations`/`join`; GraphQL resolvers
  without DataLoader. See `database.md`.
