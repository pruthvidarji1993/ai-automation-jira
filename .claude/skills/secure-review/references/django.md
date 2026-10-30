# Django checklist (loaded together with python.md)

## Settings and defaults

- `DEBUG = True`, `ALLOWED_HOSTS = ['*']`, or `SECRET_KEY` hardcoded in
  committed settings.
- `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`,
  `SECURE_HSTS_SECONDS` unset for production.
- `MEDIA_ROOT` inside or served from the static path; no
  `DATA_UPLOAD_MAX_MEMORY_SIZE` / `FILE_UPLOAD_MAX_MEMORY_SIZE`.

## Access control and CSRF

- Views missing `login_required` / permission classes; DRF
  `permission_classes = [AllowAny]` or a default of `AllowAny` in settings.
- `@csrf_exempt` on views that use cookie auth; `CsrfViewMiddleware` removed;
  DRF `SessionAuthentication` with exempted views; `CSRF_TRUSTED_ORIGINS` too
  wide.
- `get_object_or_404(Model, pk=pk)` without scoping to the user or tenant
  (IDOR) - prefer `request.user.things.get(pk=pk)`.

## Data exposure and mass assignment

- DRF serializers / `ModelForm` with `fields = '__all__'` or `exclude = [...]`
  on models with sensitive or privileged fields.
- `Model.objects.filter(...).update(**request.POST)`; `.objects.all()` returned
  whole to the client (use `.only()` / `.values()`). See `database.md`.

## Injection and uploads

- `.raw()`, `.extra()`, `RawSQL` with interpolated input; `mark_safe` / `|safe`
  on user data.
- `FileField` / `ImageField` without validators; trusting
  `UploadedFile.content_type` or the extension; `upload_to` using the client
  file name (use `uuid` names).

## Routes, versioning and N+1

- Read every `urls.py` / `include()`; no exposed `/admin` or
  `django-debug-toolbar` in production; `/api/v1` lacking the permission class
  `/api/v2` has.
- Status codes as `status.HTTP_*` and shared constants; one error shape.
- Related objects in a loop or serializer without `select_related` /
  `prefetch_related`; a `SerializerMethodField` that queries per row.
