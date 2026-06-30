from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from bson.objectid import ObjectId
import datetime

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

    assessments = await database.db.assessments.find(
        {"student_id": ObjectId(student_id)}
    ).to_list(length=100)
    for a in assessments:
        course = await database.db.courses.find_one({"_id": a["course_id"]})
        a["course_title"] = course["title"] if course else ""

    projects = await database.db.projects.find(
        {"student_id": ObjectId(student_id)}
    ).to_list(length=100)
    for p in projects:
        course = await database.db.courses.find_one({"_id": p["course_id"]})
        p["course_title"] = course["title"] if course else ""

    return templates.TemplateResponse("student/dashboard.html", {
        "request": request,
        "student": student_user,
        "courses": courses,
        "assessments": assessments,
        "projects": projects,
    })


@router.get("/exams", response_class=HTMLResponse)
async def list_exams(
    request: Request,
    student_user: dict = Depends(get_student_user),
):
    oid = ObjectId(student_user["id"])
    exams = await database.db.exams.find(
        {"assigned_students": oid}
    ).to_list(length=50)

    taken = await database.db.exam_results.find(
        {"student_id": oid}
    ).to_list(length=100)
    taken_ids = {str(r["exam_id"]) for r in taken}
    taken_map = {str(r["exam_id"]): r for r in taken}

    exam_list = []
    for e in exams:
        eid = str(e["_id"])
        exam_list.append({
            "_id": eid,
            "title": e["title"],
            "description": e.get("description", ""),
            "question_count": len(e.get("questions", [])),
            "taken": eid in taken_ids,
            "score": taken_map[eid]["score"] if eid in taken_map else None,
            "total": taken_map[eid]["total"] if eid in taken_map else None,
        })

    return templates.TemplateResponse("student/exams.html", {
        "request": request,
        "student": student_user,
        "exams": exam_list,
    })


@router.get("/exams/{eid}", response_class=HTMLResponse)
async def take_exam(
    request: Request,
    eid: str,
    student_user: dict = Depends(get_student_user),
):
    oid = ObjectId(student_user["id"])
    exam = await database.db.exams.find_one({"_id": ObjectId(eid)})
    if not exam or oid not in exam.get("assigned_students", []):
        return RedirectResponse(url="/student/exams", status_code=303)

    already = await database.db.exam_results.find_one(
        {"exam_id": ObjectId(eid), "student_id": oid}
    )
    if already:
        return RedirectResponse(url=f"/student/exams/{eid}/result", status_code=303)

    for q in exam["questions"]:
        q.pop("correct", None)

    return templates.TemplateResponse("student/exam_take.html", {
        "request": request,
        "student": student_user,
        "exam": {"_id": eid, "title": exam["title"], "questions": exam["questions"]},
    })


@router.post("/exams/{eid}", response_class=HTMLResponse)
async def submit_exam(
    request: Request,
    eid: str,
    student_user: dict = Depends(get_student_user),
):
    form = await request.form()
    oid = ObjectId(student_user["id"])
    exam = await database.db.exams.find_one({"_id": ObjectId(eid)})
    if not exam or oid not in exam.get("assigned_students", []):
        return RedirectResponse(url="/student/exams", status_code=303)

    already = await database.db.exam_results.find_one(
        {"exam_id": ObjectId(eid), "student_id": oid}
    )
    if already:
        return RedirectResponse(url=f"/student/exams/{eid}/result", status_code=303)

    score = 0
    total = len(exam["questions"])
    for i, q in enumerate(exam["questions"]):
        answer = form.get(f"answer_{i}", "")
        if answer and int(answer) == q["correct"]:
            score += 1

    await database.db.exam_results.insert_one({
        "exam_id": ObjectId(eid),
        "student_id": oid,
        "score": score,
        "total": total,
        "submitted_at": datetime.datetime.utcnow().isoformat(),
    })
    return RedirectResponse(url=f"/student/exams/{eid}/result", status_code=303)


@router.get("/exams/{eid}/result", response_class=HTMLResponse)
async def exam_result(
    request: Request,
    eid: str,
    student_user: dict = Depends(get_student_user),
):
    oid = ObjectId(student_user["id"])
    exam = await database.db.exams.find_one({"_id": ObjectId(eid)})
    if not exam:
        return RedirectResponse(url="/student/exams", status_code=303)

    result = await database.db.exam_results.find_one(
        {"exam_id": ObjectId(eid), "student_id": oid}
    )
    if not result:
        return RedirectResponse(url=f"/student/exams/{eid}", status_code=303)

    return templates.TemplateResponse("student/exam_result.html", {
        "request": request,
        "student": student_user,
        "exam": {"title": exam["title"]},
        "score": result["score"],
        "total": result["total"],
        "percentage": round(result["score"] / result["total"] * 100, 1) if result["total"] else 0,
    })
