import secrets
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import bcrypt

from app.database import database
from app.auth import get_admin_user

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    total_students = await database.db.students.count_documents({})
    total_courses = await database.db.courses.count_documents({})
    upcoming_exams = await database.db.exams.find().to_list(length=10)
    for exam in upcoming_exams:
        exam["_id"] = str(exam["_id"])

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "admin": admin_user,
        "total_students": total_students,
        "total_courses": total_courses,
        "upcoming_exams": upcoming_exams,
    })


@router.get("/students", response_class=HTMLResponse)
async def list_students(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    students = await database.db.students.find().to_list(length=100)
    for s in students:
        s["_id"] = str(s["_id"])
        s.pop("password", None)
    return templates.TemplateResponse("admin/students.html", {
        "request": request,
        "admin": admin_user,
        "students": students,
    })


@router.get("/students/create", response_class=HTMLResponse)
async def create_student_page(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    return templates.TemplateResponse("admin/create_student.html", {
        "request": request,
        "admin": admin_user,
    })


@router.post("/students/create", response_class=HTMLResponse)
async def create_student(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    form = await request.form()
    name = form.get("name", "").strip()
    email = form.get("email", "").strip().lower()

    if not name or not email:
        return templates.TemplateResponse(
            "admin/create_student.html",
            {"request": request, "admin": admin_user, "error": "Name and email are required."},
        )

    existing = await database.db.students.find_one({"email": email})
    if existing:
        return templates.TemplateResponse(
            "admin/create_student.html",
            {"request": request, "admin": admin_user, "error": "A student with this email already exists."},
        )

    password = secrets.token_urlsafe(12)
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    await database.db.students.insert_one({
        "name": name,
        "email": email,
        "password": hashed,
        "must_change_password": True,
    })

    return templates.TemplateResponse(
        "admin/create_student.html",
        {
            "request": request,
            "admin": admin_user,
            "success": f"Student created! Share these credentials:",
            "generated_email": email,
            "generated_password": password,
        },
    )
