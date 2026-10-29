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

## Mass assignment and wildcard queries

- `Model(**request.data)`, `Model.objects.filter(...).update(**request.POST)`,
  `setattr` loops over request keys, `ModelForm`/`ModelSerializer` with
  `fields = '__all__'` or `exclude = [...]`; Pydantic/FastAPI models that
  reuse the DB model so the client can set `is_admin`. Use explicit field
  lists and separate input/output schemas.
- `.objects.all()` / `session.query(Model)` returned whole to the client; use
  `.only()`/`.values()`/response models. See `database.md`.

## CSRF

- Django `@csrf_exempt`, `CsrfViewMiddleware` removed, DRF
  `SessionAuthentication` with exempted views, `CSRF_TRUSTED_ORIGINS` too wide.
  Flask/FastAPI cookie auth without Flask-WTF `CSRFProtect` or an `Origin`
  check.

## File upload

- Django `FileField`/`ImageField` without validators; trusting
  `UploadedFile.content_type` or the extension (sniff the content, e.g.
  `python-magic`, and allowlist exact types, never `*/*`). `MEDIA_ROOT` inside
  or served from the static path; `upload_to` using the client file name
  (use `uuid` names); no `DATA_UPLOAD_MAX_MEMORY_SIZE`/`FILE_UPLOAD_MAX_MEMORY_SIZE`.
- Flask `request.files[...].save(os.path.join(dir, file.filename))` without
  `secure_filename` and a type check; FastAPI `UploadFile` read fully into
  memory with no size cap.

## Routes, versioning and responses

- Route inventory: read every `urls.py` / `include()` / Flask blueprint /
  FastAPI `APIRouter`; each has auth and permission dependencies; no leftover
  debug/admin routes (`/admin` exposed, `django-debug-toolbar`, `/docs` and
  `/openapi.json` open in production when the API is private).
- API versioning: unversioned or several versions mounted with different
  security (`/api/v1` lacking the permission class `/api/v2` has).
- Response contract: status codes/messages as scattered literals instead of
  `status.HTTP_*` and shared constants; error shape differing per view;
  `200` with an error body; exception text returned to the client.

## N+1

- Related objects accessed in a loop or serializer without
  `select_related`/`prefetch_related` (Django), `joinedload`/`selectinload`
  (SQLAlchemy); a `SerializerMethodField` that queries per row. See
  `database.md`.
