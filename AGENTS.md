# LMS — AGENTS.md

## Run

```bash
# MongoDB must be running on localhost:27017
env/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Critical Gotchas
- **Motor Version**: Always use `motor>=3.7` (present in `env/`). `requirements.txt` may list an incompatible version.
- **No Tests**: Zero test files exist. Verification relies on running linters/typecheckers or manual inspection.
- **Static Directory**: `/static/` must exist (even if empty) or FastAPI crashes on startup (`main.py:19`).
- **Auth Redirects**: Use `HTTPException(status_code=303, headers={"Location": "/login"})`, not `RedirectResponse`.
- **Login Fields**: Single field `username` is used for both admin (username) and student (email) lookups.
- **Session Shape**: `request.session["user"]` is `{"username", "role": "admin"}` or `{"id", "name", "role": "student"}`.
- **DB I/O**: Pydantic models in `models.py` are not used for DB I/O; all operations use raw dicts via Motor.

## Architecture & Data Model
- **DB Singleton**: `database.py:45` provides a module-level singleton `Database()` instance. Call `database.connect()` on startup.
- **Seeding**: DB auto-seeds on first startup (`_seed()`). Data persists; **never drop the database**.
- **Motor Usage**: All DB ops use raw Motor methods (`find`, `insert_one`, etc.); no ODM layer.
- **Collections**: Key collections include `assessments` and `projects`, structured around `student_id`, `course_id`, `total_marks`, and `marks_obtained`.
- **Student IDs**: Sequential (`S0001`, ...) generated via `admin.py:_next_student_id()`. Deleting a student cascades to remove enrollments, assessments, and projects.

## Demo Credentials
- **Admin**: username `admin`, password `admin123`
- **Student**: email `john@example.com`, password `student123`
