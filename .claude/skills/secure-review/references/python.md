# Python checklist (plain Python, scripts, any framework)

Framework-specific checks live in `django.md`, `flask.md` and `fastapi.md`.

## Injection and unsafe execution (A03, A08)

- `subprocess.*(..., shell=True)`, `os.system`, `os.popen` with user input.
- `eval`, `exec`, `compile` on non-constant input.
- `pickle`, `dill`, `shelve`, `marshal`, `joblib.load` on untrusted data;
  `yaml.load` without `SafeLoader` (use `yaml.safe_load`).
- Raw SQL with f-strings or `%` formatting: `cursor.execute(f"...")`,
  Django `.raw()`, `.extra()`, `RawSQL`; SQLAlchemy `text()` with interpolation.
- `open()` / `send_file` / `FileResponse` with user-controlled paths (no
  `safe_join` / resolve-and-check).
- Jinja2 `Template(user_input)` or `render_template_string` with user input
  (SSTI); `autoescape=False`; `|safe` / `mark_safe` on user data.
- `xml.etree`/`lxml` parsing untrusted XML (use `defusedxml`).
- `requests` with `verify=False`; `requests.get(user_url)` without an allowlist
  (SSRF).

## General Python

- `assert` used for security checks (stripped with `-O`).
- `random` used for tokens, OTPs or passwords (use `secrets`).
- `hashlib.md5`/`sha1` for passwords (use argon2/bcrypt via passlib or
  Django's hashers).
- `tempfile.mktemp`, world-writable files, predictable temp paths.
- Logging of request bodies, headers (`Authorization`) or personal data.

## Mass assignment, uploads and routes (any framework)

- `setattr` loops or `Model(**data)` over request keys; reusing the DB model as
  the input schema so the client can set `is_admin`. Use explicit field lists.
  See `database.md`.
- Uploads: trust neither the client content type nor the file name; allowlist
  exact types by content (e.g. `python-magic`), cap the size, store outside the
  served path under generated names.
- Route inventory: every route has auth; no leftover debug/admin routes; the
  response contract uses shared constants, no `200` with an error body, no
  exception text returned to the client.
- N+1: related rows fetched inside a loop; use eager loading
  (`joinedload`/`selectinload`). See `database.md`.
