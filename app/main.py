import secrets
from bson.objectid import ObjectId
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import bcrypt
import os

from app.database import database
from app.auth import get_authenticated_user
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


@app.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, user: dict = Depends(get_authenticated_user)):
    return templates.TemplateResponse("change_password.html", {"request": request, "user": user})


@app.post("/change-password")
async def change_password(request: Request, user: dict = Depends(get_authenticated_user)):
    form = await request.form()
    current = form.get("current_password", "")
    new_pass = form.get("new_password", "")
    confirm = form.get("confirm", "")

    if len(new_pass) < 4:
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "user": user, "error": "Password must be at least 4 characters."},
        )
    if new_pass != confirm:
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "user": user, "error": "Passwords do not match."},
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
        must_change = student_user.get("must_change_password", False)
        request.session["user"] = {
            "id": str(student_user["_id"]),
            "name": student_user["name"],
            "role": "student",
            "must_change_password": must_change,
        }
        if must_change:
            return RedirectResponse(url="/change-password", status_code=303)
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
