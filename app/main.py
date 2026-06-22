from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import bcrypt
import os

from app.database import database
from app.routes import admin, student

app = FastAPI(title="LMS System")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "change-this-secret-key-in-production"),
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def startup():
    await database.connect()


@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/login")


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
async def register(request: Request):
    form = await request.form()
    name = form.get("name", "").strip()
    email = form.get("email", "").strip().lower()
    password = form.get("password", "")
    confirm = form.get("confirm", "")

    if not name or not email or not password:
        return templates.TemplateResponse(
            "register.html", {"request": request, "error": "All fields are required."}
        )
    if password != confirm:
        return templates.TemplateResponse(
            "register.html", {"request": request, "error": "Passwords do not match."}
        )
    if len(password) < 4:
        return templates.TemplateResponse(
            "register.html", {"request": request, "error": "Password must be at least 4 characters."}
        )

    existing = await database.db.students.find_one({"email": email})
    if existing:
        return templates.TemplateResponse(
            "register.html", {"request": request, "error": "Email already registered."}
        )

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    await database.db.students.insert_one({
        "name": name, "email": email, "password": hashed,
    })

    return templates.TemplateResponse(
        "register.html",
        {"request": request, "success": "Registration successful! You can now sign in."},
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request):
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")

    admin_user = await database.db.admins.find_one({"username": username})
    if admin_user and bcrypt.checkpw(
        password.encode(), admin_user["password"].encode()
    ):
        request.session["user"] = {"username": username, "role": "admin"}
        return RedirectResponse(url="/admin/dashboard", status_code=303)

    student_user = await database.db.students.find_one({"email": username})
    if student_user and bcrypt.checkpw(
        password.encode(), student_user["password"].encode()
    ):
        request.session["user"] = {
            "id": str(student_user["_id"]),
            "name": student_user["name"],
            "role": "student",
        }
        return RedirectResponse(url="/student/dashboard", status_code=303)

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid credentials"},
    )


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")


app.include_router(admin.router)
app.include_router(student.router)
