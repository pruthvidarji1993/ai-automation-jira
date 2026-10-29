# Python checklist (Django, Flask, FastAPI, scripts)

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

## Django

- `DEBUG = True`, `ALLOWED_HOSTS = ['*']`, or `SECRET_KEY` hardcoded in
  committed settings.
- `@csrf_exempt` on views that use cookie auth; `CSRF_COOKIE_SECURE`,
  `SESSION_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` unset
  for production.
- Views missing `login_required` / permission classes; DRF
  `permission_classes = [AllowAny]` or a default of `AllowAny` in settings.
- DRF serializers with `fields = '__all__'` on models with sensitive or
  privileged fields (mass assignment and data exposure).
- `get_object_or_404(Model, pk=pk)` without scoping to the user or tenant
  (IDOR) - prefer `request.user.things.get(pk=pk)`.

## Flask

- `app.run(debug=True)` reachable in production (the debugger allows code
  execution).
- `SECRET_KEY` hardcoded or default; no CSRF protection (Flask-WTF) on forms
  with cookie sessions.
- Routes without `@login_required` or an equivalent check.

## FastAPI

- Routes missing the auth dependency (`Depends(get_current_user)`), or a router
  included without it.
- Pydantic models used for both input and output exposing internal fields;
  missing `response_model` filtering.
- `CORSMiddleware(allow_origins=["*"], allow_credentials=True)`.
- JWT decode without `algorithms=[...]` or with `options={"verify_signature": False}`.

## General Python

- `assert` used for security checks (stripped with `-O`).
- `random` used for tokens, OTPs or passwords (use `secrets`).
- `hashlib.md5`/`sha1` for passwords (use argon2/bcrypt via passlib or
  Django's hashers).
- `tempfile.mktemp`, world-writable files, predictable temp paths.
- Logging of request bodies, headers (`Authorization`) or personal data.
