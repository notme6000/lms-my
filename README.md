# LMS — Learning Management System

A server-rendered Learning Management System built with **FastAPI + MongoDB + Jinja2 + Tailwind CSS**. Admin and student dashboards with session-based authentication.

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
│   ├── main.py            # App entry point, global routes (/, /login, /logout, /change-password)
│   ├── database.py        # MongoDB connection + auto-seed on startup
│   ├── models.py          # Pydantic models (Admin, Student, Course, Enrollment, Exam)
│   ├── auth.py            # FastAPI dependencies for role-based access control
│   └── routes/
│       ├── admin.py       # Admin router — students, courses, exams, assessments, projects
│       └── student.py     # Student router — dashboard, exams, assessments, projects
├── templates/
│   ├── login.html         # Unified login page
│   ├── change_password.html # Password change page (forced on first login)
│   ├── admin/
│   │   ├── dashboard.html
│   │   ├── students.html
│   │   ├── create_student.html
│   │   ├── student_detail.html  # Per-student management (assessments, projects)
│   │   ├── reset_password.html
│   │   ├── courses.html
│   │   ├── course_form.html
│   │   ├── exams.html
│   │   ├── exam_form.html
│   │   └── exam_results.html
│   └── student/
│       ├── dashboard.html
│       ├── exams.html
│       ├── exam_take.html
│       └── exam_result.html
├── scripts/
│   ├── export_db.py       # Export all MongoDB collections to JSON
│   └── import_db.py       # Import JSON files back into MongoDB
├── db_export/             # MongoDB data snapshots (JSON)
├── instruction.md         # Original project specification
└── requirements.txt       # Python dependencies (motor>=3.7, not 3.3.1)
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
       ├── exams
       ├── assessments
       ├── projects
       └── exam_results
```

Key points:
- **Server-rendered**: All HTML is generated on the server via Jinja2. No SPA/frontend framework.
- **Async throughout**: FastAPI + Motor use Python async/await for all DB operations.
- **Session-based auth**: Sessions stored in a signed cookie (itsdangerous). No JWT.
- **Dependency injection**: FastAPI `Depends(get_admin_user)` / `Depends(get_student_user)` protects routes.
- **Auto-seeding**: On first startup, if collections are empty, the app inserts demo data.
- **Unified login**: A single `/login` endpoint checks admins by username, then students by email.

---

## Database Collections

### `admins`
```json
{ "username": "admin", "password": "<bcrypt hash>" }
```

### `students`
```json
{ "student_id": "S0001", "name": "John", "email": "john@example.com", "password": "<bcrypt hash>", "must_change_password": false }
```

### `courses`
```json
{ "title": "Python Basics", "description": "Introduction to Python programming" }
```

### `enrollments`
```json
{ "student_id": "<ObjectId>", "course_id": "<ObjectId>", "progress": 60 }
```

### `exams`
```json
{ "title": "Python Quiz", "description": "...", "questions": [{"q": "2+2=?", "options": ["3","4","5","6"], "correct": 1}], "assigned_students": ["<ObjectId>"] }
```

### `assessments`
```json
{ "student_id": "<ObjectId>", "course_id": "<ObjectId>", "heading": "Midterm", "description": "...", "total_marks": 100, "marks_obtained": 85 }
```

### `projects`
```json
{ "student_id": "<ObjectId>", "course_id": "<ObjectId>", "heading": "Final Project", "description": "...", "total_marks": 50, "marks_obtained": 42 }
```

### `exam_results`
```json
{ "exam_id": "<ObjectId>", "student_id": "<ObjectId>", "score": 2, "total": 3 }
```

---

## Routes

### Global (`app/main.py`)
| Route | Method | Description |
|---|---|---|
| `/` | GET | Redirect to `/login` |
| `/login` | GET/POST | Login page + credential check (admin by username, student by email) |
| `/logout` | GET | Clear session, redirect to `/login` |
| `/change-password` | GET/POST | Change password (forced on first login for new students) |

### Admin (`app/routes/admin.py`) — prefix `/admin`
| Route | Method | Description |
|---|---|---|
| `/dashboard` | GET | Aggregate stats + links to management |
| `/students` | GET | List / search students |
| `/students/create` | GET/POST | Create student with auto-generated ID, password, course enrollment |
| `/students/{id}` | GET | Student detail — view/add assessments and projects, reset password |
| `/students/{id}/delete` | POST | Delete student + enrollments + assessments + projects |
| `/students/{id}/reset-password` | POST | Generate new password, force change on next login |
| `/students/{id}/assessments` | POST | Add assessment |
| `/students/{id}/assessments/{aid}/delete` | POST | Delete assessment |
| `/students/{id}/projects` | POST | Add project |
| `/students/{id}/projects/{pid}/delete` | POST | Delete project |
| `/courses` | GET | List courses |
| `/courses/create` | GET/POST | Add course |
| `/courses/{id}/edit` | GET/POST | Edit course |
| `/courses/{id}/delete` | POST | Delete course + associated records |
| `/exams` | GET | List exams |
| `/exams/create` | GET/POST | Create exam with dynamic questions + student assignment |
| `/exams/{id}/edit` | GET/POST | Edit exam |
| `/exams/{id}/delete` | POST | Delete exam + results |
| `/exams/{id}/results` | GET | View student results and scores |

### Student (`app/routes/student.py`) — prefix `/student`
| Route | Method | Description |
|---|---|---|
| `/dashboard` | GET | Courses, assessments, projects, progress bars, notifications |
| `/exams` | GET | List assigned exams with taken/not-taken status |
| `/exams/{id}` | GET/POST | Take exam (questions with 4 options) and submit auto-graded answers |
| `/exams/{id}/result` | GET | View score and percentage |

---

## Data Flow

### Login (`/login`)
1. `GET /login` → renders `login.html`
2. `POST /login` → check `admins` by username → bcrypt verify → session `{username, role:"admin"}` → redirect to `/admin/dashboard`
3. If no admin match → check `students` by email → bcrypt verify → session `{id, name, role:"student", must_change_password}` → if `must_change_password` is true, redirect to `/change-password`; otherwise `/student/dashboard`
4. Neither matches → re-render login with error

### Student Creation (admin)
1. Admin fills name, email, selects courses → submit
2. System generates sequential student ID (`S0001`, `S0002`, ...) + random password
3. Student doc created with `must_change_password: true` + enrollments inserted
4. Admin shares credentials with student

### Exam Flow
1. Admin creates exam with questions (4 options per question, marks correct answer)
2. Admin assigns exam to specific students
3. Student sees exam in `/student/exams`, clicks "Take Exam"
4. Student answers questions, submits
5. System auto-grades, stores result in `exam_results`
6. Student views score, admin views all results

---

## Running the App

```bash
# Ensure MongoDB is running on localhost:27017
cd /home/akira/projects/lms
env/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Demo credentials** (auto-seeded):
- **Admin**: username `admin`, password `admin123`
- **Student**: email `john@example.com`, password `student123`

---

## Notable Patterns

- **Blueprint/Router pattern**: FastAPI `APIRouter` splits admin and student routes; included in `main.py`.
- **Dependency injection for auth**: Route protection is handled via `Depends(get_admin_user)`, idiomatic FastAPI.
- **Singleton database**: `database.py` creates a module-level `Database()` instance, imported by routes.
- **No ORM/ODM**: Raw MongoDB queries via Motor (find, find_one, insert_one, count_documents). Pydantic models exist but are not used for DB I/O.
- **Minimal frontend**: Tailwind CSS via CDN, no build step, no JS framework.
- **Environment config**: Only `SECRET_KEY` env var (session signing), with a hardcoded fallback. DB host/port hardcoded to `localhost:27017`.
- **Student IDs**: Auto-generated sequential IDs (`S0001`, `S0002`, ...).
- **Delete cascades**: Deleting a student removes their enrollments, assessments, projects, and exam results.
- **No self-registration**: Only admins can create student accounts.
