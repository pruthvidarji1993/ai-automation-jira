# React checklist (SPAs and any React app)

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

- `VITE_*`, `REACT_APP_*` (and any other build-time public prefix) variables
  holding secrets (server API keys, service-role keys, signing secrets).
  Anything with those prefixes ships to every visitor.
- Source maps published in production (`.map` files next to the bundle,
  `build.sourcemap` / `GENERATE_SOURCEMAP` on).

## Auth tokens on the client

- Access/refresh tokens in `localStorage`, `sessionStorage`, IndexedDB or
  non-`HttpOnly` cookies; tokens in URLs (leak through Referer and logs).
- Role or permission decided only on the client (cookie or JWT payload read
  in the browser) with no server check.
- Logout that clears client state but not the server session.

## Uploads, API versioning and responses

- Uploads: the `accept` attribute is UX only; the server must allowlist exact
  MIME types and check magic bytes and size. Prefer short-lived presigned URLs
  with content-type and size conditions.
- API versioning: the frontend calling unversioned or deprecated endpoints;
  client code assuming an old response shape.
- Response handling: trust no field from the response for authorization;
  status/error strings compared as literals instead of shared constants;
  errors shown to the user verbatim from the backend.
