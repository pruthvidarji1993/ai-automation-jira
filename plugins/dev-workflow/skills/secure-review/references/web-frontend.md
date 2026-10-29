# React and Next.js checklist

## XSS (A03)

- `dangerouslySetInnerHTML`, `innerHTML`, `outerHTML`, `insertAdjacentHTML`,
  `document.write` with any value that is not a constant - sanitize with
  DOMPurify (or the project's sanitizer) at the point of rendering.
- Markdown or rich-text renderers with raw HTML enabled (`rehype-raw`,
  `allowDangerousHtml`, `html: true`).
- `href`/`src` built from user data without blocking `javascript:` and `data:`
  URLs.
- `eval`, `new Function`, `setTimeout(string)` on non-constant input.
- `postMessage` listeners that do not check `event.origin`; `postMessage(...,
  '*')` carrying tokens or user data.
- `target="_blank"` to untrusted URLs without `rel="noopener noreferrer"`.
- Third-party scripts loaded without SRI or from user-configurable hosts.

## Secrets in the browser bundle (A02, A05)

- `NEXT_PUBLIC_*`, `VITE_*`, `REACT_APP_*` variables holding secrets (server API
  keys, service-role keys, signing secrets). Anything with those prefixes ships
  to every visitor.
- Server-only modules imported into a `'use client'` file; secrets passed as
  props from a server component into a client component.
- Source maps published in production (`productionBrowserSourceMaps`, `.map`
  files under `public/`).

## Next.js server surface

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

## Auth tokens on the client

- Access/refresh tokens in `localStorage`, `sessionStorage`, IndexedDB or
  non-`HttpOnly` cookies; tokens in URLs (leak through Referer and logs).
- Role or permission decided only on the client (cookie or JWT payload read
  in the browser) with no server check.
- Logout that clears client state but not the server session.
