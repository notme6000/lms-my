from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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
