# General checklist - every stack

Red flags. Each needs a concrete exploit before it is a finding.

## Access control (A01)

- An endpoint, server action or resolver that reads or writes a record by id
  without checking the record belongs to the caller (IDOR / BOLA).
- Authorization only in the UI (hidden button, disabled route) with no check on
  the server that performs the action.
- Role or tenant taken from the request body, query or a client-set cookie
  instead of the verified session.
- List endpoints that filter by tenant/org in some queries but not others.
- Admin or internal routes reachable without a role check; debug endpoints left
  enabled.
- Mass assignment: request body spread into a create/update (`role`,
  `isAdmin`, `ownerId`, `price` settable by the client). Includes wildcard
  reads/writes (`SELECT *`, `update(body)`): see `database.md` and the stack file.

## Authentication and session (A07)

- Passwords hashed with anything other than bcrypt/scrypt/argon2; no rate limit
  or lockout on login, OTP, password reset.
- Reset or invite tokens that are guessable, long-lived, reusable or not bound
  to the user.
- JWT: `alg: none` accepted, signature not verified (`decode` instead of
  `verify`), no expiry, secret hardcoded or weak.
- Session not invalidated on logout or password change.
- Bearer tokens or refresh tokens in `localStorage` / `sessionStorage` (any XSS
  steals them); cookies missing `HttpOnly`, `Secure`, `SameSite`.

## Secrets and configuration (A02, A05)

- Credentials, API keys, private keys in source, fixtures that ship, Docker
  images, CI files, or committed `.env` files. A secret in git history is live
  until rotated.
- Git history: run the secret scan over every commit (`full`) or every commit
  on the branch (`diff`). A key added then deleted is still exposed; report it
  as "rotate", not "remove". Also check old commits for deleted `.env`, key
  files, dumps and `*.pem`.
- Test code: real keys, tokens, production URLs, customer data or DB dumps in
  tests, fixtures, snapshots, mocks, Postman collections, `.env.test` and CI
  variables. Tests should use obvious fakes (`test_key_123`) or env vars; a
  string that matches a live provider format is a finding until proven fake.
- Debug mode, verbose stack traces or framework error pages in production
  config.
- CORS `*` (or a reflected origin) together with credentials.
- Missing security headers: CSP, HSTS, `X-Content-Type-Options`,
  `frame-ancestors`/`X-Frame-Options`, `Referrer-Policy`.
- TLS verification disabled (`rejectUnauthorized: false`, `verify=False`).

## Injection and request forgery (A03, A10)

- User input concatenated into SQL, NoSQL filters (`$where`, operator objects
  from JSON bodies), shell commands, file paths, template strings, LDAP, XPath.
- Server-side fetch of a user-supplied URL without an allowlist (SSRF) -
  includes webhooks, link previews, image proxies, PDF renderers.
- Redirects to a user-supplied URL (open redirect), especially after login.
- State-changing requests authenticated by cookie with no CSRF defence
  (`SameSite=Lax/Strict` or a token); CSRF protection disabled globally or
  exempted per route. Stack files show where each framework configures it.
- Regexes with nested quantifiers on user input (ReDoS).

## Data protection and privacy

- Personal data (emails, phones, tokens, payment data, health data) written to
  logs, analytics, error trackers or URLs.
- Raw backend errors, SQL errors or stack traces returned to the client.
- File uploads: type not checked against an exact MIME allowlist (never `*/*`
  or `image/*`) and by content, not just the client header or extension; no size
  limit; client file name used; stored under a public or guessable path
  instead of private storage; served with a content type the browser will
  execute (HTML/SVG). Stack files list the framework specifics.
- Exports and reports that include more fields than the caller may see.

## Routes, API versioning and response contract

- Inventory every route file/controller and confirm each route has
  authentication and authorization; look for forgotten debug, test or admin
  routes and catch-all handlers.
- Versioning: public API with no version, or an old version still mounted
  without the fixes (auth, validation, rate limits) the new one has.
- Response contract: one shared shape and shared constants for status codes
  and messages; no `200` with an error body; no error text that reveals
  whether a record exists; no raw exceptions returned.

## Account security

- Login, signup or reset responses that differ for existing vs unknown
  accounts (user enumeration).
- No MFA option for admin roles; OTPs that never expire or allow unlimited
  attempts.
- OAuth/SSO: missing or unchecked `state`, `redirect_uri` not exactly matched,
  implicit flow, ID token not validated (issuer, audience, expiry, nonce),
  accounts linked by unverified email.
- Session fixation (session id not rotated at login); "remember me" tokens
  stored in plain text.

## Caching and data leakage between users

- Authenticated responses cacheable by CDNs or shared proxies (missing
  `Cache-Control: private, no-store`).
- Next.js `fetch` cache, `unstable_cache`, ISR or a server-side memo keyed
  without the user id, serving one user's data to another.
- Per-user data in a global in-memory cache or module-level variable on the
  server.

## APIs: GraphQL, WebSockets, file and bulk endpoints

- GraphQL: introspection enabled in production, no depth/complexity limits,
  resolvers that skip the authorization the REST equivalent has, batching
  that bypasses rate limits.
- WebSockets / Socket.IO / SSE: no auth on connect, no per-message
  authorization for rooms/channels, origin not checked.
- List and export endpoints without pagination or a max page size; search
  without limits (resource exhaustion, A04).
- CSV/Excel exports that write user text beginning with `=`, `+`, `-`, `@`
  (formula injection).
- Emails and notifications built with user input (header injection, HTML
  injection into email bodies, links pointing at user-controlled hosts).
- Insecure randomness for tokens, OTPs, invite codes: `Math.random`,
  `random`, `rand()` (use the platform CSPRNG).

## Logging and monitoring (A09)

- No audit trail for security events: login failures, permission denials,
  admin actions, data exports.

## Supply chain and integrity (A06, A08)

- Dependencies with known CVEs that are actually reachable (scanner output -
  verify the vulnerable function is used before calling it critical).
- Packages installed from git URLs, tarballs or unpinned versions; new
  dependencies with install scripts.
- CI: secrets exposed to pull requests from forks (`pull_request_target`),
  actions pinned to a branch instead of a commit SHA, untrusted input in `run:`.
- Deserialising untrusted data (see stack checklists).

## AI / LLM features

- User-controlled text placed in a prompt that can call tools, read other
  users' data or change state (prompt injection) without an authorization check
  on the tool itself.
- Model output rendered as HTML/Markdown without sanitising, or executed.
- API keys for model providers sent to the browser.

## Privacy and compliance (client perspective)

Report these with `"category": "compliance"` so they appear in the report's
compliance section, not as code defects.

- Personal data collected that the feature does not need; no way to delete or
  export a user's data (GDPR/DPDP-style rights) where the product stores it.
- Third-party trackers, analytics or session replay loaded before consent, or
  capturing form fields with personal data.
- Personal or payment data sent to third-party services (AI providers, error
  trackers, analytics) without masking.
- Card data handled directly instead of through the payment provider's hosted
  fields (PCI scope).
- Sensitive data stored without encryption where the platform offers it, or
  kept with no retention limit.
- Restrictive or missing licenses in dependencies (scanner output) that
  conflict with how the client distributes the product.

## Containers and infrastructure

- Dockerfile runs as root, copies `.env` or the whole repo including secrets,
  uses `latest` tags, or leaves build tools and credentials in the final stage.
- Infrastructure files exposing admin ports or databases publicly.
- Terraform/CloudFormation/Kubernetes: public storage buckets, security groups
  open to `0.0.0.0/0` on admin or database ports, containers running
  privileged, secrets in plain manifests instead of a secret store.
