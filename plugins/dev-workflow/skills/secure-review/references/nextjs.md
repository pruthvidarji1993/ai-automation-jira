# Next.js checklist (loaded together with react.md)

## Secrets in the bundle (A02, A05)

- `NEXT_PUBLIC_*` variables holding secrets (server API keys, service-role
  keys, signing secrets). Anything with that prefix ships to every visitor.
- Server-only modules imported into a `'use client'` file; secrets passed as
  props from a server component into a client component.
- Source maps published in production (`productionBrowserSourceMaps`, `.map`
  files under `public/`).

## Server surface

- Server Actions: every exported action is a public POST endpoint. Each must
  authenticate, authorize the specific record, and validate input (e.g. zod) -
  a check in the calling component does not protect it.
- Route handlers (`app/**/route.ts`, `pages/api/**`) without auth, or trusting
  ids from the body/query without ownership checks.
- `middleware.ts` used as the only auth layer: `matcher` gaps leave routes
  unprotected, and middleware-only auth has been bypassable before - the
  handler must check too.
- `redirect()` / `NextResponse.redirect()` with a user-supplied target.
- `next.config` `images.remotePatterns` / `domains` set to `**` or any host
  (the image optimizer becomes an open proxy).
- Security headers missing from `headers()` in `next.config` or middleware.
- `fetch` in server code to a URL built from user input (SSRF).
- Data returned from server components or actions that includes fields the
  user may not see (whole DB rows serialised to the client).

## CSRF, uploads, routes and N+1

- Server actions and route handlers that mutate with cookie auth: confirm the
  `Origin` check applies (`serverActions.allowedOrigins` too wide) and custom
  `POST` route handlers verify `Origin` or a token; `GET` handlers that change
  state.
- Uploads: never store under `public/` (Next serves it) or use the client file
  name as the path; presigned URLs with content-type and size conditions.
- Route inventory: list every `app/**/route.ts`, `page.tsx` data fetch and
  `middleware`/`proxy` `matcher`; the matcher must cover `/api` and every
  private segment, and each handler still checks auth itself (middleware is
  not the only guard).
- N+1 in server components: `await` inside `map`/loops that call the DB or an
  internal API per item (use one batched query or `Promise.all` with a limit).
