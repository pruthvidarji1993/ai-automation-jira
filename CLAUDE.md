# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.

# Next.js + Tailwind rules

Stack: **Next.js 16.2.6 · React 19.2.4 · Tailwind CSS v4 · TypeScript (strict)**.

> ⚠️ This Next.js build differs from training data (see the warning above). When an API is non-trivial, read the matching doc under `node_modules/next/dist/docs/` **before** writing code. Heed `version: draft`, `unstable_*`, and deprecation notes. Watch for `{/* AI agent hint: ... */}` comments in the docs — they flag non-obvious requirements.

## Routing & file structure (App Router)

- All routes live in `app/`. Use the file conventions: `page.tsx`, `layout.tsx`, `loading.tsx`, `error.tsx`, `route.ts`, `not-found.tsx`.
- Co-locate route-only helpers/components inside the route folder; share cross-route code under a top-level folder (e.g. `app/_components/`, `lib/`).
- Import with the `@/*` path alias (e.g. `@/lib/db`), not long relative chains. Configured in [tsconfig.json](tsconfig.json).
- There is no Pages Router here — don't add `pages/`, `_app`, or `getServerSideProps`/`getStaticProps`.

## Server vs Client Components

- **Server Components are the default.** Keep them server-side unless you need a client capability.
- Add `'use client'` only when the component needs: state, effects/lifecycle, event handlers (`onClick`/`onChange`), browser APIs (`window`, `localStorage`), or custom hooks.
- Push `'use client'` to the **leaves** — keep data fetching, secrets, and heavy logic in Server Components and pass results down as props. Don't make a whole page a Client Component to get one interactive button.
- Never expose secrets (API keys, tokens) in Client Components.
- Fetch data in Server Components close to the source; use Server Actions / Route Handlers (`route.ts`) for mutations.

## Navigation

- Navigate with `<Link>` from `next/link` (not `<a>`); it prefetches routes in the viewport automatically. Use `prefetch={false}` for large/infinite link lists.
- Add `loading.tsx` to dynamic routes to enable partial prefetching and an immediate loading UI.
- **Instant navigation:** Suspense alone is NOT enough to guarantee instant client-side navigations. To opt a route into instant-navigation validation, export `unstable_instant` from the `page.tsx`/`layout.tsx`:
  ```tsx
  export const unstable_instant = { prefetch: 'static' }
  ```
  Requires `cacheComponents` enabled in `next.config.ts`; cannot be used in Client Components. Read `node_modules/next/dist/docs/01-app/02-guides/instant-navigation.md` before relying on it.

## Tailwind CSS v4 (CSS-first config)

- **No `tailwind.config.js`.** Tailwind v4 is configured in CSS. Entry point is [app/globals.css](app/globals.css):
  ```css
  @import "tailwindcss";
  ```
- Define design tokens with `@theme inline { ... }` using CSS variables (`--color-*`, `--font-*`), not a JS config object. Reference existing tokens before inventing new ones.
- PostCSS uses `@tailwindcss/postcss` (see [postcss.config.mjs](postcss.config.mjs)) — don't add `autoprefixer`/`postcss-import`; v4 handles them.
- Style with utility classes in `className`. Reach for CSS Modules or plain CSS only when utilities genuinely can't express it.
- Support dark mode with the `dark:` variant (the app uses `prefers-color-scheme`).
- Keep class lists ordered consistently (layout → box → typography → color → state/responsive); group responsive (`sm:`/`md:`) and state (`hover:`/`focus:`) variants together.

## TypeScript & quality

- `strict` is on — no implicit `any`, handle `null`/`undefined`. Type props explicitly; type `metadata` with `Metadata` from `next`.
- Use `next/font` (e.g. `next/font/google`) for fonts and `next/image` for images — don't hand-roll `<img>` or raw `<link>` font tags.
- Run `npm run lint` (flat-config ESLint + `eslint-config-next`, core-web-vitals + TS rules) and ensure `npm run build` passes before shipping.

## Don't

- Don't trust memorized Next.js/Tailwind APIs for non-trivial features — confirm against the local docs.
- Don't reintroduce v3 Tailwind config or Pages Router patterns.
- Don't mark a component `'use client'` just to fetch data.
