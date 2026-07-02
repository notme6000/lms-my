# LMS Production Deployment Guide

This document describes every change made to make the LMS application **production-ready** with **security hardening**, **deployment automation**, and **operational best practices**.

---

## 1. Secrets Management

### `app/database.py`
- **Changed**: MongoDB connection string from hardcoded `mongodb://localhost:27017` to env var `MONGODB_URI`.
- **Changed**: Database name from hardcoded `lms_db` to env var `MONGODB_DB_NAME` (defaults to `lms_db`).
- **Added**: `close()` method for graceful shutdown.
- **Added**: `import os` at top.

### `.env.example`
- **Created**: Template showing all required env vars (no real secrets).

### `render.yaml`
- **Created**: Render Blueprint file so deployment config lives in the repo.
- `MONGODB_URI` is marked `sync: false` (set manually in Render dashboard).
- `SECRET_KEY` uses `generateValue: true` (Render auto-generates on first deploy).

---

## 2. Session Security

### `app/main.py`
- **Changed**: `SessionMiddleware` config:
  | Setting | Value | Purpose |
  |---|---|---|
  | `session_cookie` | `lms_session` | Custom cookie name (not default `session`) |
  | `same_site` | `lax` | Prevents CSRF from external origins |
  | `https_only` | `True` | Cookie only sent over HTTPS |
  | `max_age` | `86400` | Session expires after 24 hours |
- **Changed**: No weak fallback for `SECRET_KEY`. Logs a warning if not set.
- **Added**: Runtime check — if key is the default string, logs a security warning.

---

## 3. Security Headers

### `app/main.py` — `SecurityHeadersMiddleware`
All HTTP responses now include:

| Header | Value | Why |
|---|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Forces HTTPS for 1 year |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME sniffing |
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `X-XSS-Protection` | `1; mode=block` | XSS filter (legacy browsers) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Controls referrer leakage |

---

## 4. Host Header Validation

### `app/main.py` — `TrustedHostMiddleware`
- **Added**: Validates the `Host` header against `ALLOWED_HOSTS` env var.
- Format: comma-separated list (e.g., `.onrender.com,localhost,127.0.0.1`).
- Prevents Host header injection attacks.

---

## 5. Login Rate Limiting

### `app/main.py` — `LoginRateLimiter` middleware
- **Added**: In-memory rate limiter on `POST /login`.
- Configuration: **5 attempts per IP per 60 seconds**.
- Returns HTTP **429 Too Many Requests** when exceeded.
- Logs a warning for each rate-limit hit.

---

## 6. Error Handling (No Stack Traces)

### `app/main.py` — Exception handlers
- **Added**: Custom handlers for HTTP 400, 403, 404, 500.
- All return generic `PlainTextResponse` messages — **no stack traces, no internal paths**.
- Errors are logged to server logs for debugging.

---

## 7. Health Check Endpoint

### `app/main.py` — `GET /health`
- **Added**: Returns JSON `{"status": "ok", "database": "connected"}`.
- Render uses this to monitor service health (`healthCheckPath` in `render.yaml`).

---

## 8. Graceful Shutdown

### `app/main.py` — `@app.on_event("shutdown")`
- **Added**: Closes MongoDB client connection on graceful shutdown.

---

## 9. Logging

### `app/main.py`
- **Added**: Structured logging via Python's `logging` module with timestamp, level, and module name.
- **Added**: Log lines for logins (admin/student), failed attempts, rate limits, and unauthorized access attempts.

### `app/auth.py`
- **Added**: Logging for unauthorized access attempts.

---

## 10. Input Validation

### `app/routes/admin.py`

| Route | Validation Added |
|---|---|
| `POST /students/create` | Email regex validation, name length (2-100), ObjectId validation on course_ids |
| `POST /students/{sid}/delete` | ObjectId validation on `sid` |
| `POST /students/{sid}/assessments` | Numeric validation: `total_marks` > 0, `marks_obtained` >= 0, marks <= total |
| `POST /students/{sid}/projects` | Same numeric validation |
| `POST /students/{sid}/reset-password` | ObjectId validation |
| `POST /batches/create` | Name max length 200 |
| `POST /courses/create` | Title length 2-200 |
| `POST /courses/{cid}/edit` | Title length 2-200 |
| `POST /exams/create` | Title max 200, at least 1 question, ObjectId validation on assigned_students |
| `POST /exams/{eid}/edit` | Same |

### `app/routes/student.py`

| Route | Validation Added |
|---|---|
| `GET /exams/{eid}` | ObjectId validation |
| `POST /exams/{eid}` | ObjectId validation, `answer` must be digit |
| `GET /exams/{eid}/result` | ObjectId validation |

### `app/main.py`

| Route | Validation Added |
|---|---|
| `POST /change-password` | Min 8 chars, requires uppercase + digit, confirm match, must differ from current |
| `POST /login` | Non-empty username and password |

---

## 11. Dependency Fix

### `requirements.txt`
- **Changed**: `motor==3.3.1` → `motor>=3.7,<4` (3.3.1 is incompatible with `pymongo>=4.17`).
- **Added**: `python-dotenv>=1.0.0` for local `.env` file support.

---

## 12. Scripts Fix

### `scripts/export_db.py` and `scripts/import_db.py`
- **Changed**: Both now read `MONGODB_URI` and `MONGODB_DB_NAME` from env vars instead of hardcoded `mongodb://localhost:27017`.

---

## 13. `.gitignore` Update

### `.gitignore`
- **Added**: `.env` (secrets file).
- **Added**: `db_export/` (data snapshots).
- **Added**: `__pycache__/`, `*.pyc`.

---

## 14. Seed Credentials — No More Hardcoded Defaults

### `app/database.py` — `_seed()` method

**Before**: Admin (`admin`/`admin123`) and student (`john@example.com`/`student123`) credentials were hardcoded in source code. Deploying to production with an empty Atlas database would seed these weak credentials.

**After**: The seed now reads credentials from **environment variables**:

| Env Var | Purpose | Required for seed? |
|---|---|---|
| `ADMIN_USERNAME` | Initial admin username | If set (with `ADMIN_PASSWORD`), creates admin |
| `ADMIN_PASSWORD` | Initial admin password | Required alongside `ADMIN_USERNAME` |
| `SEED_STUDENT_EMAIL` | Demo student email | If set (with `SEED_STUDENT_PASSWORD`), creates student + enrollments + exam |
| `SEED_STUDENT_PASSWORD` | Demo student password | Required alongside `SEED_STUDENT_EMAIL` |

**Behavior**:
- If `ADMIN_USERNAME` and `ADMIN_PASSWORD` are **not set**, the seed **skips** admin creation (logs a warning).
- If `SEED_STUDENT_EMAIL` and `SEED_STUDENT_PASSWORD` are **not set**, the seed **skips** student creation.
- In production, you can set these env vars temporarily on first deploy, then remove them. Data persists.
- Courses are still seeded (non-sensitive) when the courses collection is empty.

---

## Deployment Steps on Render

### 1. Push code to GitHub

```bash
git add .
git commit -m "Production hardening: security headers, rate limiting, input validation, env vars"
git push origin main
```

### 2. Create a Web Service on Render

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New Web Service**.
2. Connect your GitHub repo.
3. Or use the Blueprint: **New** → **Blueprint** → select `render.yaml`.

### 3. Set Environment Variables

| Variable | Value | Notes |
|---|---|---|
| `MONGODB_URI` | `mongodb+srv://user:pass@cluster.xxxxx.mongodb.net/lms_db?retryWrites=true&w=majority` | From MongoDB Atlas |
| `MONGODB_DB_NAME` | `lms_db` | Must match the db in the URI |
| `SECRET_KEY` | Auto-generated (or paste a 64-char hex string) | Render can auto-generate |
| `ALLOWED_HOSTS` | `.onrender.com` | Or your custom domain |
| `PYTHON_VERSION` | `3.14` | Must match your runtime |
| `ADMIN_USERNAME` | `admin` | (Optional) Set on first deploy only — initial admin |
| `ADMIN_PASSWORD` | `your-strong-admin-password` | (Optional) Set on first deploy only — then remove |

**Important**: After the first deploy, `ADMIN_USERNAME`/`ADMIN_PASSWORD` can be **removed** from env vars. The admin account persists in Atlas.

### 4. MongoDB Atlas Network Access

In Atlas → **Network Access** → **Add IP Address** → `0.0.0.0/0` (Render has dynamic IPs).

### 5. Verify Deployment

- Visit `https://your-app.onrender.com/health` — should return `{"status": "ok", "database": "connected"}`
- Test login at `/login`
- Check Render logs for any startup errors

---

## Pre-Deployment Checklist

- [ ] `MONGODB_URI` set in Render env vars
- [ ] `SECRET_KEY` set (auto-generated or custom)
- [ ] `ALLOWED_HOSTS` includes `.onrender.com`
- [ ] Atlas whitelist allows `0.0.0.0/0`
- [ ] `static/` directory exists in repo
- [ ] `.env` is NOT committed
- [ ] `ADMIN_USERNAME`/`ADMIN_PASSWORD` set on first deploy (or admin created another way)
- [ ] Remove seed env vars after first deploy to prevent re-seed confusion
