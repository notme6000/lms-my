import secrets
from bson.objectid import ObjectId
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import bcrypt

from app.database import database
from app.auth import get_admin_user

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")


async def _next_student_id():
    last = await database.db.students.find_one({}, sort=[("student_id", -1)])
    if last and "student_id" in last:
        num = int(last["student_id"][1:]) + 1
    else:
        num = 1
    return f"S{num:04d}"


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
    q = request.query_params.get("q", "").strip()
    query = {}
    if q:
        query = {"$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"student_id": {"$regex": q, "$options": "i"}},
        ]}
    students = await database.db.students.find(query).to_list(length=100)
    for s in students:
        s["_id"] = str(s["_id"])
        s.pop("password", None)
    return templates.TemplateResponse("admin/students.html", {
        "request": request,
        "admin": admin_user,
        "students": students,
        "q": q,
    })


@router.get("/students/create", response_class=HTMLResponse)
async def create_student_page(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    courses = await database.db.courses.find().to_list(length=50)
    for c in courses:
        c["_id"] = str(c["_id"])
    return templates.TemplateResponse("admin/create_student.html", {
        "request": request,
        "admin": admin_user,
        "courses": courses,
    })


@router.post("/students/create", response_class=HTMLResponse)
async def create_student(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    form = await request.form()
    name = form.get("name", "").strip()
    email = form.get("email", "").strip().lower()
    course_ids = form.getlist("course_ids")

    courses = await database.db.courses.find().to_list(length=50)
    for c in courses:
        c["_id"] = str(c["_id"])

    if not name or not email:
        return templates.TemplateResponse(
            "admin/create_student.html",
            {"request": request, "admin": admin_user, "courses": courses, "error": "Name and email are required."},
        )

    existing = await database.db.students.find_one({"email": email})
    if existing:
        return templates.TemplateResponse(
            "admin/create_student.html",
            {"request": request, "admin": admin_user, "courses": courses, "error": "A student with this email already exists."},
        )

    student_id = await _next_student_id()
    password = secrets.token_urlsafe(12)
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    result = await database.db.students.insert_one({
        "student_id": student_id,
        "name": name,
        "email": email,
        "password": hashed,
        "must_change_password": True,
    })

    for cid in course_ids:
        await database.db.enrollments.insert_one({
            "student_id": result.inserted_id,
            "course_id": ObjectId(cid),
            "progress": 0,
        })

    return templates.TemplateResponse(
        "admin/create_student.html",
        {
            "request": request,
            "admin": admin_user,
            "courses": courses,
            "success": "Student created! Share these credentials:",
            "generated_student_id": student_id,
            "generated_email": email,
            "generated_password": password,
        },
    )


@router.post("/students/{sid}/delete", response_class=HTMLResponse)
async def delete_student(
    request: Request,
    sid: str,
    admin_user: dict = Depends(get_admin_user),
):
    oid = ObjectId(sid)
    await database.db.students.delete_one({"_id": oid})
    await database.db.enrollments.delete_many({"student_id": oid})
    await database.db.assessments.delete_many({"student_id": oid})
    await database.db.projects.delete_many({"student_id": oid})
    return RedirectResponse(url="/admin/students", status_code=303)


@router.post("/students/{sid}/reset-password", response_class=HTMLResponse)
async def reset_student_password(
    request: Request,
    sid: str,
    admin_user: dict = Depends(get_admin_user),
):
    oid = ObjectId(sid)
    student = await database.db.students.find_one({"_id": oid})
    if not student:
        return RedirectResponse(url="/admin/students", status_code=303)

    password = secrets.token_urlsafe(12)
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    await database.db.students.update_one(
        {"_id": oid},
        {"$set": {"password": hashed, "must_change_password": True}},
    )

    return templates.TemplateResponse("admin/reset_password.html", {
        "request": request,
        "admin": admin_user,
        "student": {"_id": sid, "name": student["name"], "email": student["email"], "student_id": student.get("student_id", "")},
        "generated_password": password,
    })


@router.get("/students/{sid}", response_class=HTMLResponse)
async def student_detail(
    request: Request,
    sid: str,
    admin_user: dict = Depends(get_admin_user),
):
    oid = ObjectId(sid)
    student = await database.db.students.find_one({"_id": oid})
    if not student:
        return RedirectResponse(url="/admin/students", status_code=303)

    student["_id"] = str(student["_id"])
    student.pop("password", None)

    enrollments = await database.db.enrollments.find({"student_id": oid}).to_list(length=50)
    courses = []
    for e in enrollments:
        course = await database.db.courses.find_one({"_id": e["course_id"]})
        if course:
            courses.append({"_id": str(course["_id"]), "title": course["title"], "progress": e.get("progress", 0)})

    assessments = await database.db.assessments.find({"student_id": oid}).to_list(length=100)
    for a in assessments:
        a["_id"] = str(a["_id"])
        course = await database.db.courses.find_one({"_id": a["course_id"]})
        a["course_title"] = course["title"] if course else "Unknown"

    projects = await database.db.projects.find({"student_id": oid}).to_list(length=100)
    for p in projects:
        p["_id"] = str(p["_id"])
        course = await database.db.courses.find_one({"_id": p["course_id"]})
        p["course_title"] = course["title"] if course else "Unknown"

    return templates.TemplateResponse("admin/student_detail.html", {
        "request": request,
        "admin": admin_user,
        "student": student,
        "courses": courses,
        "assessments": assessments,
        "projects": projects,
    })


@router.post("/students/{sid}/assessments", response_class=HTMLResponse)
async def add_assessment(
    request: Request,
    sid: str,
    admin_user: dict = Depends(get_admin_user),
):
    form = await request.form()
    oid = ObjectId(sid)
    heading = form.get("heading", "").strip()
    description = form.get("description", "").strip()
    course_id = form.get("course_id", "")
    total_marks = form.get("total_marks", "").strip()
    marks_obtained = form.get("marks_obtained", "").strip()

    if not heading or not course_id or not total_marks or not marks_obtained:
        return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)

    await database.db.assessments.insert_one({
        "student_id": oid,
        "course_id": ObjectId(course_id),
        "heading": heading,
        "description": description,
        "total_marks": int(total_marks),
        "marks_obtained": int(marks_obtained),
    })
    return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)


@router.post("/students/{sid}/assessments/{aid}/delete", response_class=HTMLResponse)
async def delete_assessment(
    request: Request,
    sid: str,
    aid: str,
    admin_user: dict = Depends(get_admin_user),
):
    await database.db.assessments.delete_one({"_id": ObjectId(aid)})
    return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)


@router.post("/students/{sid}/projects", response_class=HTMLResponse)
async def add_project(
    request: Request,
    sid: str,
    admin_user: dict = Depends(get_admin_user),
):
    form = await request.form()
    oid = ObjectId(sid)
    heading = form.get("heading", "").strip()
    description = form.get("description", "").strip()
    course_id = form.get("course_id", "")
    total_marks = form.get("total_marks", "").strip()
    marks_obtained = form.get("marks_obtained", "").strip()

    if not heading or not course_id or not total_marks or not marks_obtained:
        return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)

    await database.db.projects.insert_one({
        "student_id": oid,
        "course_id": ObjectId(course_id),
        "heading": heading,
        "description": description,
        "total_marks": int(total_marks),
        "marks_obtained": int(marks_obtained),
    })
    return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)


@router.post("/students/{sid}/projects/{pid}/delete", response_class=HTMLResponse)
async def delete_project(
    request: Request,
    sid: str,
    pid: str,
    admin_user: dict = Depends(get_admin_user),
):
    await database.db.projects.delete_one({"_id": ObjectId(pid)})
    return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)


@router.get("/courses", response_class=HTMLResponse)
async def list_courses(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    courses = await database.db.courses.find().to_list(length=50)
    for c in courses:
        c["_id"] = str(c["_id"])
    return templates.TemplateResponse("admin/courses.html", {
        "request": request,
        "admin": admin_user,
        "courses": courses,
    })


@router.get("/courses/create", response_class=HTMLResponse)
async def create_course_page(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    return templates.TemplateResponse("admin/course_form.html", {
        "request": request,
        "admin": admin_user,
        "course": None,
    })


@router.post("/courses/create", response_class=HTMLResponse)
async def create_course(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    form = await request.form()
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()

    if not title:
        return templates.TemplateResponse(
            "admin/course_form.html",
            {"request": request, "admin": admin_user, "course": None, "error": "Title is required."},
        )

    await database.db.courses.insert_one({"title": title, "description": description})
    return RedirectResponse(url="/admin/courses", status_code=303)


@router.get("/courses/{cid}/edit", response_class=HTMLResponse)
async def edit_course_page(
    request: Request,
    cid: str,
    admin_user: dict = Depends(get_admin_user),
):
    course = await database.db.courses.find_one({"_id": ObjectId(cid)})
    if not course:
        return RedirectResponse(url="/admin/courses", status_code=303)
    course["_id"] = str(course["_id"])
    return templates.TemplateResponse("admin/course_form.html", {
        "request": request,
        "admin": admin_user,
        "course": course,
    })


@router.post("/courses/{cid}/edit", response_class=HTMLResponse)
async def edit_course(
    request: Request,
    cid: str,
    admin_user: dict = Depends(get_admin_user),
):
    form = await request.form()
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()

    if not title:
        course = await database.db.courses.find_one({"_id": ObjectId(cid)})
        course["_id"] = str(course["_id"])
        return templates.TemplateResponse(
            "admin/course_form.html",
            {"request": request, "admin": admin_user, "course": course, "error": "Title is required."},
        )

    await database.db.courses.update_one(
        {"_id": ObjectId(cid)},
        {"$set": {"title": title, "description": description}},
    )
    return RedirectResponse(url="/admin/courses", status_code=303)


@router.post("/courses/{cid}/delete", response_class=HTMLResponse)
async def delete_course(
    request: Request,
    cid: str,
    admin_user: dict = Depends(get_admin_user),
):
    oid = ObjectId(cid)
    await database.db.enrollments.delete_many({"course_id": oid})
    await database.db.assessments.delete_many({"course_id": oid})
    await database.db.projects.delete_many({"course_id": oid})
    await database.db.exams.delete_many({"course_id": oid})
    await database.db.courses.delete_one({"_id": oid})
    return RedirectResponse(url="/admin/courses", status_code=303)
