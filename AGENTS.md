# LMS — AGENTS.md

## Run

```bash
# MongoDB must be running on localhost:27017
cd /home/akira/projects/lms
env/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Critical gotchas

- **motor version**: `requirements.txt` pins `motor==3.3.1` but this is incompatible with installed `pymongo==4.17` (`_QUERY_OPTIONS` removed). Always install `motor>=3.7` instead. The `env/` venv already has `motor==3.7.1`.
- **No tests**: zero test files, no test framework. Do not assume pytest or any test runner exists.
- **`static/` directory must exist** — `main.py:19` mounts it and crashes if absent. Keep an empty `static/` dir.
- **Auth redirects**: `auth.py` raises `HTTPException(status_code=303, headers={"Location": "/login"})`. Not a `RedirectResponse`. Login POST also uses `status_code=303`.
- **Login flow**: single field `username` — checks `admins` by `username`, then `students` by `email`. No separate role/type selector.
- **Session shape**: `request.session["user"]` is `{"username", "role": "admin"}` or `{"id", "name", "role": "student"}`.
- **Pydantic models unused**: `models.py` schemas exist but are not used for DB I/O. All DB ops use raw dicts via Motor.

## Architecture

- **Singleton DB**: `database.py:45` creates a module-level `Database()` instance imported by routes. Call `database.connect()` once on startup.
- **Auto-seed**: On first startup, `_seed()` inserts admin (`admin/admin123`), 3 courses, 1 student (`john@example.com`/`student123`), 3 enrollments, 1 exam.
- **Raw Motor queries**: No ODM. `find()`, `find_one()`, `insert_one()`, `count_documents()`. Pydantic not used for I/O.
- **`venv at `env/`**: gitignored, already has all deps. Not in requirements.txt.
- **`opencode.json`** at root references `.opencode/codebase-index.md` via `instructions`.
- **Collections**: `assessments` and `projects` — each has `student_id`, `course_id`, `heading`, `description`, `total_marks`, `marks_obtained`.
- **Exams**: `exams` collection has `title`, `description`, `questions` (array of `{q, options[4], correct}`), and `assigned_students` (array of ObjectId). `exam_results` stores `exam_id`, `student_id`, `score`, `total`.
- **Student ID**: sequential `S0001`, `S0002`, ... generated in `admin.py:_next_student_id()`.
- **Delete cascades**: Deleting a student also removes their enrollments, assessments, and projects.
- **Never drop the database**: The seed function only writes on empty collections, so data survives restarts. Do not call `dropDatabase()` in tests — it destroys user data.
