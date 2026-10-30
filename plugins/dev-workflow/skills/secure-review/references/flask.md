# Flask checklist (loaded together with python.md)

- `app.run(debug=True)` reachable in production (the debugger allows code
  execution).
- `SECRET_KEY` hardcoded or default; no CSRF protection (Flask-WTF
  `CSRFProtect`) on forms or cookie-session endpoints, or no `Origin` check.
- Routes without `@login_required` or an equivalent check; read every
  blueprint and `register_blueprint` for leftover debug/admin routes and
  inconsistent auth between `/api/v1` and `/api/v2`.
- `render_template_string` / `Template(user_input)` (SSTI); `|safe` on user data.
- `request.files[...].save(os.path.join(dir, file.filename))` without
  `secure_filename` and a content-type check; no `MAX_CONTENT_LENGTH`.
- `send_file` / `send_from_directory` with user-controlled paths.
- Exception text or stack traces returned to the client; one shared error shape
  and shared status constants.
- Per-row queries in a loop (SQLAlchemy without `joinedload` / `selectinload`).
