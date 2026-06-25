# LMS — Learning Management System (Phase 1 MVP)

A server-rendered Learning Management System built with **FastAPI + MongoDB + Jinja2 + Tailwind CSS**. Two dashboards (admin and student) with session-based authentication.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.14 |
| Web Framework | FastAPI 0.104.1 |
| ASGI Server | Uvicorn 0.24.0 |
| Templating | Jinja2 3.1.2 |
| Database | MongoDB (local) |
| MongoDB Driver | Motor 3.3.1 (async) |
| Auth | Session-based (`starlette.middleware.sessions`) |
| Password Hashing | bcrypt 4.1.2 |
| Session Signing | itsdangerous 2.1.2 |
| Frontend | Tailwind CSS (CDN), minimal JS |

---

## Directory Structure

```
lms/
├── app/
│   ├── main.py            # App entry point, routes (/, /login, /register, /logout)
│   ├── database.py        # MongoDB connection + auto-seed on startup
│   ├── models.py          # Pydantic models (Admin, Student, Course, Enrollment, Exam)
│   ├── auth.py            # FastAPI dependencies for role-based access control
│   └── routes/
│       ├── admin.py       # Admin router (GET /admin/dashboard)
│       └── student.py     # Student router (GET /student/dashboard)
├── templates/
│   ├── login.html         # Unified login page
│   ├── register.html      # Student registration page
│   ├── admin/
│   │   └── dashboard.html # Admin dashboard
│   └── student/
│       └── dashboard.html # Student dashboard
├── scripts/
│   ├── export_db.py       # Export all MongoDB collections to JSON
│   └── import_db.py       # Import JSON files back into MongoDB
├── db_export/             # MongoDB data snapshots (JSON)
├── instruction.md         # Original project specification
└── requirements.txt       # Python dependencies
```

---

## Architecture

```
Browser (HTML + Tailwind CSS)
       │
       ▼
Uvicorn ASGI Server (0.0.0.0:8000)
       │
       ▼
FastAPI Application
       │
       ├── main.py         (global routes, session middleware, template engine)
       ├── routes/admin.py (Depends: get_admin_user)
       ├── routes/student.py (Depends: get_student_user)
       ├── auth.py         (dependency guards for roles)
       └── database.py     (Motor async MongoDB client + auto-seeder)
       │
       ▼
MongoDB (local:27017 / lms_db)
       ├── admins
       ├── students
       ├── courses
       ├── enrollments
       └── exams
```

Key points:
- **Server-rendered**: All HTML is generated on the server via Jinja2. No SPA/frontend framework.
- **Async throughout**: FastAPI + Motor use Python async/await for all DB operations.
- **Session-based auth**: Sessions stored in a signed cookie (itsdangerous). No JWT.
- **Dependency injection**: FastAPI `Depends(get_admin_user)` / `Depends(get_student_user)` protects routes.
- **Auto-seeding**: On first startup, if collections are empty, the app inserts demo data (1 admin, 3 courses, 1 student, 3 enrollments, 1 exam).
- **Unified login**: A single `/login` endpoint checks admins collection first (by username), then students (by email).

---

## Database Collections

### `admins`
```json
{ "username": "admin", "password": "<bcrypt hash>" }
```

### `students`
```json
{ "name": "John", "email": "john@example.com", "password": "<bcrypt hash>" }
```

### `courses`
```json
{ "title": "Python Basics", "description": "..." }
```

### `enrollments`
```json
{ "student_id": "<ObjectId>", "course_id": "<ObjectId>", "progress": 60 }
```

### `exams`
```json
{ "course_id": "<ObjectId>", "title": "Python Quiz", "exam_date": "2026-06-25" }
```

---

## Data Flow

### Registration (`/register`)
1. `GET /register` → renders `register.html`
2. `POST /register` → validates fields (required, password match, min length, unique email) → bcrypt hash → insert into `students` → success message

### Login (`/login`)
1. `GET /login` → renders `login.html`
2. `POST /login` → check `admins` by username → bcrypt verify → session `{username, role:"admin"}` → redirect to `/admin/dashboard`
3. If no admin match → check `students` by email → bcrypt verify → session `{id, name, role:"student"}` → redirect to `/student/dashboard`
4. Neither matches → re-render login with error

### Admin Dashboard (`/admin/dashboard`)
1. `get_admin_user` dependency checks session for `role == "admin"` (else redirect to `/login`)
2. Query MongoDB: count students, count courses, find exams (limit 10)
3. Render `admin/dashboard.html` with stats + exam table

### Student Dashboard (`/student/dashboard`)
1. `get_student_user` dependency checks session for `role == "student"` (else redirect to `/login`)
2. Find enrollments by `student_id`
3. For each enrollment, look up course title and progress
4. Find exams matching enrolled courses
5. Render `student/dashboard.html` with courses, progress bars, exams, notifications

### Logout (`/logout`)
1. Clear session → redirect to `/login`

---

## Key Files Explained

| File | Purpose |
|---|---|
| `app/main.py` | FastAPI app creation, session middleware, Jinja2 setup, startup event (DB connect + seed), global routes |
| `app/database.py` | `Database` class: connects to MongoDB, auto-seeds demo data if empty; singleton instance |
| `app/models.py` | Pydantic schemas for type validation (not used for DB ops) |
| `app/auth.py` | `get_admin_user(request)` and `get_student_user(request)` — FastAPI dependencies that guard routes |
| `app/routes/admin.py` | `APIRouter(prefix="/admin")` — dashboard route that queries aggregate stats |
| `app/routes/student.py` | `APIRouter(prefix="/student")` — dashboard route that queries per-student data |
| `scripts/export_db.py` | Connects to MongoDB, serializes all collections to `db_export/*.json` |
| `scripts/import_db.py` | Reads JSON from `db_export/`, deserializes ObjectIds, drops and repopulates MongoDB |

---

## Notable Patterns

- **Blueprint/Router pattern**: FastAPI `APIRouter` splits admin and student routes; included in `main.py`.
- **Dependency injection for auth**: Route protection is handled via `Depends(get_admin_user)`, idiomatic FastAPI.
- **Singleton database**: `database.py` creates a module-level `Database()` instance, imported by routes.
- **No ORM/ODM**: Raw MongoDB queries via Motor (find, find_one, insert_one, count_documents). Pydantic models exist but are not used for DB I/O.
- **Minimal frontend**: Tailwind CSS via CDN, no build step, no JS framework. Progress bars use inline styles.
- **Environment config**: Only `SECRET_KEY` env var (session signing), with a hardcoded fallback. DB host/port hardcoded to `localhost:27017`.

---

## Running the App

```bash
pip install -r requirements.txt
# Ensure MongoDB is running on localhost:27017
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Demo credentials** (auto-seeded):
- **Admin**: username `admin`, password `admin123`
- **Student**: email `john@example.com`, password `student123`

---

## Phase 1 Scope

This is a Phase 1 MVP with the minimum feature set:
- Admin and student login/logout
- Student self-registration
- Admin dashboard (aggregate stats + upcoming exams)
- Student dashboard (enrolled courses, progress bars, upcoming exams, notifications)

Future phases would add CRUD for courses/exams, lesson content, grading, and more.
