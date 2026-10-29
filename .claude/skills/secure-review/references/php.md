# PHP checklist (Laravel, Symfony, WordPress)

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
