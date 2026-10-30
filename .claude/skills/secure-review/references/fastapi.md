# FastAPI checklist (loaded together with python.md)

- Routes missing the auth dependency (`Depends(get_current_user)`), or a router
  included without it; read every `APIRouter` / `include_router` for leftover
  debug/admin routes and `/api/v1` vs `/api/v2` differences.
- Pydantic models reused for input and output exposing internal fields or
  letting the client set `is_admin`; missing `response_model` filtering. Use
  separate input and output schemas.
- `CORSMiddleware(allow_origins=["*"], allow_credentials=True)`.
- JWT decode without `algorithms=[...]` or with
  `options={"verify_signature": False}`.
- Cookie auth without an `Origin` / CSRF check on state-changing routes.
- `UploadFile` read fully into memory with no size cap; client file name used as
  the storage path; no content-type allowlist by content.
- `/docs`, `/redoc` and `/openapi.json` open in production when the API is
  private.
- Status codes as `status.HTTP_*` and shared constants; exception text returned
  to the client; no `200` with an error body.
- Per-row queries in a loop (SQLAlchemy without `joinedload` / `selectinload`).
