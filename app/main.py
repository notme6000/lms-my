import logging
import os
import time
from collections import defaultdict
from dotenv import load_dotenv

from bson.objectid import ObjectId
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import bcrypt

from app.database import database
from app.auth import get_authenticated_user
from app.routes import admin, student

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("lms")

app = FastAPI(title="LMS System")

secret_key = os.getenv("SECRET_KEY")
if not secret_key or secret_key == "change-this-secret-key-in-production":
    logger.warning(
        "SECRET_KEY not set or using default. Session security is compromised. "
        "Set SECRET_KEY environment variable to a secure random value."
    )
    secret_key = secret_key or "insecure-fallback-do-not-use"

app.add_middleware(
    SessionMiddleware,
    secret_key=secret_key,
    session_cookie="lms_session",
    same_site="lax",
    https_only=True,
    max_age=86400,
)

allowed_hosts = os.getenv("ALLOWED_HOSTS", "lms-my.onrender.com")
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[h.strip() for h in allowed_hosts.split(",")],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

app.add_middleware(SecurityHeadersMiddleware)


class LoginRateLimiter(BaseHTTPMiddleware):
    def __init__(self, app, max_attempts: int = 5, window_seconds: int = 60):
        super().__init__(app)
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/login" and request.method == "POST":
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            self.attempts[client_ip] = [t for t in self.attempts[client_ip] if now - t < self.window_seconds]
            if len(self.attempts[client_ip]) >= self.max_attempts:
                logger.warning("Rate limit hit for IP: %s", client_ip)
                return HTMLResponse(
                    "<h3>Too many login attempts. Please try again later.</h3>",
                    status_code=429,
                )
            self.attempts[client_ip].append(now)
        return await call_next(request)

app.add_middleware(LoginRateLimiter)


app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.exception_handler(400)
async def bad_request_handler(request, exc):
    logger.error("400 error: %s", exc)
    return PlainTextResponse("Bad Request", status_code=400)


@app.exception_handler(403)
async def forbidden_handler(request, exc):
    logger.error("403 error: %s", exc)
    return PlainTextResponse("Forbidden", status_code=403)


@app.exception_handler(404)
async def not_found_handler(request, exc):
    logger.error("404 error: %s", exc)
    return PlainTextResponse("Not Found", status_code=404)


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.exception("500 Internal Server Error")
    return PlainTextResponse("Internal Server Error", status_code=500)


@app.on_event("startup")
async def startup():
    logger.info("Connecting to MongoDB...")
    await database.connect()
    logger.info("Connected to MongoDB successfully.")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down - closing MongoDB connection...")
    await database.close()
    logger.info("MongoDB connection closed.")


@app.get("/health")
async def health():
    db_ok = database.db is not None
    return {"status": "ok" if db_ok else "degraded", "database": "connected" if db_ok else "disconnected"}


@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/login")


@app.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, user: dict = Depends(get_authenticated_user)):
    return templates.TemplateResponse("change_password.html", {"request": request, "user": user})


@app.post("/change-password")
async def change_password(request: Request, user: dict = Depends(get_authenticated_user)):
    form = await request.form()
    current = form.get("current_password", "")
    new_pass = form.get("new_password", "")
    confirm = form.get("confirm", "")

    errors = []
    if len(new_pass) < 8:
        errors.append("Password must be at least 8 characters.")
    if not any(c.isupper() for c in new_pass):
        errors.append("Password must contain an uppercase letter.")
    if not any(c.isdigit() for c in new_pass):
        errors.append("Password must contain a digit.")
    if new_pass != confirm:
        errors.append("Passwords do not match.")
    if new_pass == current:
        errors.append("New password must differ from current password.")
    if errors:
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "user": user, "error": " ".join(errors)},
        )

    if user["role"] == "admin":
        dbuser = await database.db.admins.find_one({"username": user["username"]})
    else:
        dbuser = await database.db.students.find_one({"_id": ObjectId(user["id"])})

    if not dbuser or not bcrypt.checkpw(current.encode(), dbuser["password"].encode()):
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "user": user, "error": "Current password is incorrect."},
        )

    hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
    if user["role"] == "admin":
        await database.db.admins.update_one({"username": user["username"]}, {"$set": {"password": hashed}})
    else:
        await database.db.students.update_one({"_id": ObjectId(user["id"])}, {"$set": {"password": hashed, "must_change_password": False}})
        request.session["user"]["must_change_password"] = False

    return RedirectResponse(
        url="/admin/dashboard" if user["role"] == "admin" else "/student/dashboard",
        status_code=303,
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request):
    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")

    if not username or not password:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Username and password are required."},
        )

    admin_user = await database.db.admins.find_one({"username": username})
    if admin_user and bcrypt.checkpw(
        password.encode(), admin_user["password"].encode()
    ):
        request.session["user"] = {"username": username, "role": "admin"}
        logger.info("Admin login: %s", username)
        return RedirectResponse(url="/admin/dashboard", status_code=303)

    student_user = await database.db.students.find_one({"email": username})
    if student_user and bcrypt.checkpw(
        password.encode(), student_user["password"].encode()
    ):
        must_change = student_user.get("must_change_password", False)
        request.session["user"] = {
            "id": str(student_user["_id"]),
            "name": student_user["name"],
            "role": "student",
            "must_change_password": must_change,
        }
        logger.info("Student login: %s", student_user["email"])
        if must_change:
            return RedirectResponse(url="/change-password", status_code=303)
        return RedirectResponse(url="/student/dashboard", status_code=303)

    logger.warning("Failed login attempt for: %s", username)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid credentials"},
    )


@app.get("/logout")
async def logout(request: Request):
    logger.info("Logout: %s", request.session.get("user", {}).get("username", "unknown"))
    request.session.clear()
    return RedirectResponse(url="/login")


app.include_router(admin.router)
app.include_router(student.router)
