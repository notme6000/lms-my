# LMS Codebase Index

## Tech Stack
- **Language**: Python 3.14
- **Framework**: FastAPI 0.104.1
- **Server**: Uvicorn 0.24.0
- **Templating**: Jinja2 3.1.2
- **Database**: MongoDB (local) with Motor 3.3.1 (async driver)
- **Auth**: Session-based (starlette.middleware.sessions), bcrypt 4.1.2
- **Frontend**: Tailwind CSS (CDN), no build step

## Project Structure
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
├── static/                # Static files (empty)
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation
└── instruction.md         # Original project specification
```

## App Entry Point
`app/main.py` — FastAPI app creation, session middleware, Jinja2 setup, startup event (DB connect + seed), global routes.

## Database
`app/database.py` — `Database` class with singleton pattern. Connects to `mongodb://localhost:27017`, uses `lms_db`. Auto-seeds on first startup:
- 1 admin (admin/admin123)
- 3 courses (Python Basics, Linux Fundamentals, Web Security)
- 1 student (john@example.com/student123)
- 3 enrollments (60%, 40%, 0% progress)
- 1 exam (Python Quiz, 2026-06-25)

## Auth Flow
`app/auth.py` — `get_admin_user` and `get_student_user` dependencies check `request.session["user"]["role"]`. Raise 303 redirect to `/login` on failure.

## Routes

### Global (`app/main.py`)
| Route | Method | Description |
|---|---|---|
| `/` | GET | Redirect to `/login` |
| `/login` | GET/POST | Login page + credential check |
| `/register` | GET/POST | Register page + student creation |
| `/logout` | GET | Clear session, redirect to `/login` |

### Admin (`app/routes/admin.py`)
| Route | Method | Description |
|---|---|---|
| `/admin/dashboard` | GET | Stats + upcoming exams table |

### Student (`app/routes/student.py`)
| Route | Method | Description |
|---|---|---|
| `/student/dashboard` | GET | Courses, progress bars, exams, notifications |

## Database Collections
| Collection | Key Fields |
|---|---|
| `admins` | `username`, `password` (bcrypt) |
| `students` | `name`, `email`, `password` (bcrypt) |
| `courses` | `title`, `description` |
| `enrollments` | `student_id` (ObjectId), `course_id` (ObjectId), `progress` (int) |
| `exams` | `course_id` (ObjectId), `title`, `exam_date` |

## How to Run
```bash
# Ensure MongoDB is running on localhost:27017
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Demo Credentials
- **Admin**: username `admin`, password `admin123`
- **Student**: email `john@example.com`, password `student123`
