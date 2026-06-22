from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from bson.objectid import ObjectId

from app.database import database
from app.auth import get_student_user

router = APIRouter(prefix="/student")
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    student_user: dict = Depends(get_student_user),
):
    student_id = student_user["id"]

    enrollments = await database.db.enrollments.find(
        {"student_id": ObjectId(student_id)}
    ).to_list(length=100)

    courses = []
    enrolled_course_ids = []
    for enrollment in enrollments:
        course = await database.db.courses.find_one({"_id": enrollment["course_id"]})
        if course:
            enrolled_course_ids.append(course["_id"])
            courses.append({
                "title": course["title"],
                "progress": enrollment.get("progress", 0),
            })

    upcoming_exams = []
    if enrolled_course_ids:
        exams = await database.db.exams.find(
            {"course_id": {"$in": enrolled_course_ids}}
        ).to_list(length=10)
        for exam in exams:
            upcoming_exams.append({
                "title": exam["title"],
                "date": exam.get("exam_date", ""),
            })

    return templates.TemplateResponse("student/dashboard.html", {
        "request": request,
        "student": student_user,
        "courses": courses,
        "upcoming_exams": upcoming_exams,
        "notifications": [
            "New lesson uploaded",
            "Exam scheduled",
        ],
    })
