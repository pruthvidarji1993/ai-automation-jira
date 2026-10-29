# PHP checklist (Laravel)

Scanners here: semgrep `p/php` and osv-scanner for `composer.lock`. Apply
`general.md` first; these are the PHP-specific red flags.

- Raw queries with interpolation (`DB::raw`, `whereRaw("... $x")`,
  `DB::select("..." . $input)`, `mysqli_query` with concatenation).
- `eval`, `assert` with strings, `preg_replace` with `/e`, `include`/`require`
  of user-controlled paths (LFI/RFI), `unserialize` on user input.
- `shell_exec`, `exec`, `system`, `passthru`, backticks with input.
- File uploads stored under `public/` with the original extension (PHP
  execution); downloads served from user-supplied paths.
- `md5`/`sha1` for passwords instead of `password_hash`; `rand`/`mt_rand` for
  tokens instead of `random_bytes`.

## Laravel

- `$guarded = []` or missing `$fillable`, with `update($request->all())` (mass
  assignment).
- `APP_DEBUG=true` for production, `APP_KEY` committed.
- Routes without the `auth` middleware, or controllers that load models by id
  without a policy/ownership check (`Invoice::find($id)`).
- `{!! $var !!}` unescaped Blade output of user content.
- CSRF middleware exceptions (`$except`) covering state-changing routes.

## WordPress

- AJAX/REST handlers missing `current_user_can` and nonce checks.
- `$wpdb->query` / `get_results` without `$wpdb->prepare`.
- Output without `esc_html` / `esc_attr` / `wp_kses`.

## Mass assignment and wildcard queries

- `Model::create($request->all())`, `->update($request->all())`,
  `fill($request->input())`, `forceFill`, `unguard()`; use `validated()` /
  `only([...])` with an explicit `$fillable`.
- `$hidden` missing for password/token columns, so `toArray()`/`response()->json($model)`
  leaks them; `Model::all()` / `select *` returned to the client. Use an API
  Resource with named fields. See `database.md`.

## CSRF

- `VerifyCsrfToken::$except` / `validateCsrfTokens(except: [...])` covering
  state-changing routes that use the session; `@csrf` missing in Blade forms;
  routes put in `api.php` (no CSRF, no session) while still reading `auth()`
  cookies. Sanctum SPA routes need the CSRF cookie flow.

## File upload

- Validation without `mimes:`/`mimetypes:`/`image` and `max:`; `*` or the
  client `getClientOriginalExtension()`/`getClientMimeType()` trusted. Use
  `$file->extension()` (content-sniffed) with an exact allowlist.
- Stored with `move()` into `public/` or `storage/app/public` served by the
  web server (`.php`/`.html`/`.svg` execution or XSS). Use `Storage::putFile`
  on a private disk with a generated name; serve via signed/authorized
  controller; check the `filesystems.php` disk `visibility`.

## Routes, versioning and responses

- Route inventory: read `routes/web.php`, `routes/api.php`, `routes/*.php` and
  `RouteServiceProvider`/`bootstrap/app.php`: each route group has `auth`,
  `throttle` and a policy; no leftover test/debug routes
  (`Route::get('/test')`, Telescope/Horizon/Debugbar exposed in production).
- API versioning: `/api/v1` vs unversioned routes both mounted; old version
  missing middleware added to the new one.
- Response contract: hard-coded status codes and message strings in many
  controllers instead of a shared response helper/`Response::HTTP_*` constants
  and API Resources; `200` with `success: false`; exceptions rendered with
  `getMessage()`/trace.

## N+1

- Relation accessed in a loop or Blade/Resource without `with()`/`load()`;
  `Model::preventLazyLoading()` not enabled in non-production. See `database.md`.
