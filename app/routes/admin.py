import csv
import io
import logging
import re
import secrets
import urllib.parse
from bson.objectid import ObjectId
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import bcrypt
import openpyxl

from app.database import database
from app.auth import get_admin_user

logger = logging.getLogger("lms.admin")

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")


async def _next_student_id():
    last = await database.db.students.find_one({}, sort=[("student_id", -1)])
    if last and "student_id" in last:
        num = int(last["student_id"][1:]) + 1
    else:
        num = 1
    return f"S{num:04d}"


async def _next_batch_id():
    last = await database.db.batches.find_one({}, sort=[("batch_id", -1)])
    if last and "batch_id" in last:
        num = int(last["batch_id"][1:]) + 1
    else:
        num = 1
    return f"B{num:04d}"


EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


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
    batches = await database.db.batches.find().to_list(length=50)
    for b in batches:
        b["_id"] = str(b["_id"])
    bulk_error = request.query_params.get("bulk_error", "")
    return templates.TemplateResponse("admin/create_student.html", {
        "request": request,
        "admin": admin_user,
        "courses": courses,
        "batches": batches,
        "bulk_error": bulk_error,
    })


@router.post("/students/create", response_class=HTMLResponse)
async def create_student(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    form = await request.form()
    name = form.get("name", "").strip()
    email = form.get("email", "").strip().lower()
    batch_id = form.get("batch_id", "").strip()
    course_ids = form.getlist("course_ids")

    courses = await database.db.courses.find().to_list(length=50)
    for c in courses:
        c["_id"] = str(c["_id"])
    batches = await database.db.batches.find().to_list(length=50)
    for b in batches:
        b["_id"] = str(b["_id"])

    errors = []
    if not name or len(name) < 2 or len(name) > 100:
        errors.append("Name must be between 2 and 100 characters.")
    if not EMAIL_RE.match(email):
        errors.append("Invalid email address.")
    if errors:
        return templates.TemplateResponse(
            "admin/create_student.html",
            {"request": request, "admin": admin_user, "courses": courses, "batches": batches, "error": " ".join(errors), "bulk_error": ""},
        )

    existing = await database.db.students.find_one({"email": email})
    if existing:
        return templates.TemplateResponse(
            "admin/create_student.html",
            {"request": request, "admin": admin_user, "courses": courses, "batches": batches, "error": "A student with this email already exists.", "bulk_error": ""},
        )

    student_id = await _next_student_id()
    password = secrets.token_urlsafe(12)
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    student_doc = {
        "student_id": student_id,
        "name": name,
        "email": email,
        "password": hashed,
        "must_change_password": True,
    }
    if batch_id:
        student_doc["batch_id"] = batch_id
    result = await database.db.students.insert_one(student_doc)

    for cid in course_ids:
        if ObjectId.is_valid(cid):
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
            "batches": batches,
            "success": "Student created! Share these credentials:",
            "generated_student_id": student_id,
            "generated_email": email,
            "generated_password": password,
            "bulk_error": "",
        },
    )


@router.post("/students/bulk-upload")
async def bulk_create_students(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    form = await request.form()
    upload = form.get("file")

    if not upload or not hasattr(upload, "filename") or not upload.filename:
        return RedirectResponse(url="/admin/students/create?bulk_error=No+file+uploaded", status_code=303)

    contents = await upload.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(contents))
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    except Exception:
        return RedirectResponse(url="/admin/students/create?bulk_error=Invalid+Excel+file", status_code=303)

    if len(rows) < 2:
        return RedirectResponse(url="/admin/students/create?bulk_error=Excel+file+is+empty", status_code=303)

    errors = []
    to_create = []

    for i, row in enumerate(rows[1:], start=2):
        name = str(row[0]).strip() if row[0] else ""
        email = str(row[1]).strip().lower() if row[1] else ""
        batch_id = str(row[2]).strip() if len(row) > 2 and row[2] else ""

        if not name or len(name) < 2 or len(name) > 100:
            errors.append(f"Row {i}: Name must be between 2 and 100 characters.")
            continue
        if not EMAIL_RE.match(email):
            errors.append(f"Row {i}: Invalid email '{email}'.")
            continue

        existing = await database.db.students.find_one({"email": email})
        if existing:
            errors.append(f"Row {i}: Email '{email}' already exists.")
            continue

        to_create.append((name, email, batch_id))

    if not to_create:
        msg = "No valid students to create."
        if errors:
            msg += " " + " | ".join(errors[:5])
            if len(errors) > 5:
                msg += f" (and {len(errors) - 5} more)"
        encoded = urllib.parse.quote(msg)
        return RedirectResponse(url=f"/admin/students/create?bulk_error={encoded}", status_code=303)

    last = await database.db.students.find_one({}, sort=[("student_id", -1)])
    last_num = int(last["student_id"][1:]) if last and "student_id" in last else 0

    created = []
    for idx, (name, email, batch_id) in enumerate(to_create):
        student_id = f"S{last_num + 1 + idx:04d}"
        password = secrets.token_urlsafe(12)
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        doc = {
            "student_id": student_id,
            "name": name,
            "email": email,
            "password": hashed,
            "must_change_password": True,
        }
        if batch_id:
            doc["batch_id"] = batch_id
        await database.db.students.insert_one(doc)
        created.append((name, email, password))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Email", "Password"])
    writer.writerows(created)

    if errors:
        output.write(f"# Skipped ({len(errors)}): ")
        for e in errors:
            output.write(f"{e} ")

    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=student_credentials_{len(created)}_created.csv"
    return response


@router.post("/students/{sid}/delete", response_class=HTMLResponse)
async def delete_student(
    request: Request,
    sid: str,
    admin_user: dict = Depends(get_admin_user),
):
    if not ObjectId.is_valid(sid):
        return RedirectResponse(url="/admin/students", status_code=303)
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
    if not ObjectId.is_valid(sid):
        return RedirectResponse(url="/admin/students", status_code=303)
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

    name = student["name"]
    email = student["email"]
    student_id = student.get("student_id", "")
    return templates.TemplateResponse("admin/reset_password.html", {
        "request": request,
        "admin": admin_user,
        "student": {"_id": sid, "name": name, "email": email, "student_id": student_id},
        "generated_password": password,
    })


@router.post("/students/{sid}/update-batch", response_class=HTMLResponse)
async def update_student_batch(
    request: Request,
    sid: str,
    admin_user: dict = Depends(get_admin_user),
):
    if not ObjectId.is_valid(sid):
        return RedirectResponse(url="/admin/students", status_code=303)
    form = await request.form()
    batch_id = form.get("batch_id", "").strip()
    if batch_id:
        await database.db.students.update_one({"_id": ObjectId(sid)}, {"$set": {"batch_id": batch_id}})
    else:
        await database.db.students.update_one({"_id": ObjectId(sid)}, {"$unset": {"batch_id": ""}})
    return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)


@router.get("/students/{sid}", response_class=HTMLResponse)
async def student_detail(
    request: Request,
    sid: str,
    admin_user: dict = Depends(get_admin_user),
):
    if not ObjectId.is_valid(sid):
        return RedirectResponse(url="/admin/students", status_code=303)
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

    batches = await database.db.batches.find().to_list(length=50)
    for b in batches:
        b["_id"] = str(b["_id"])

    return templates.TemplateResponse("admin/student_detail.html", {
        "request": request,
        "admin": admin_user,
        "student": student,
        "courses": courses,
        "assessments": assessments,
        "projects": projects,
        "batches": batches,
    })


@router.post("/students/{sid}/assessments", response_class=HTMLResponse)
async def add_assessment(
    request: Request,
    sid: str,
    admin_user: dict = Depends(get_admin_user),
):
    form = await request.form()
    if not ObjectId.is_valid(sid):
        return RedirectResponse(url="/admin/students", status_code=303)
    oid = ObjectId(sid)
    heading = form.get("heading", "").strip()
    description = form.get("description", "").strip()
    course_id = form.get("course_id", "")
    total_marks = form.get("total_marks", "").strip()
    marks_obtained = form.get("marks_obtained", "").strip()

    if not heading or not course_id or not total_marks or not marks_obtained:
        return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)

    try:
        tm = int(total_marks)
        mo = int(marks_obtained)
        if tm <= 0 or mo < 0 or mo > tm:
            return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)
    except (ValueError, TypeError):
        return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)

    if not ObjectId.is_valid(course_id):
        return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)

    await database.db.assessments.insert_one({
        "student_id": oid,
        "course_id": ObjectId(course_id),
        "heading": heading,
        "description": description,
        "total_marks": tm,
        "marks_obtained": mo,
    })
    return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)


@router.post("/students/{sid}/assessments/{aid}/delete", response_class=HTMLResponse)
async def delete_assessment(
    request: Request,
    sid: str,
    aid: str,
    admin_user: dict = Depends(get_admin_user),
):
    if ObjectId.is_valid(aid):
        await database.db.assessments.delete_one({"_id": ObjectId(aid)})
    return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)


@router.post("/students/{sid}/projects", response_class=HTMLResponse)
async def add_project(
    request: Request,
    sid: str,
    admin_user: dict = Depends(get_admin_user),
):
    form = await request.form()
    if not ObjectId.is_valid(sid):
        return RedirectResponse(url="/admin/students", status_code=303)
    oid = ObjectId(sid)
    heading = form.get("heading", "").strip()
    description = form.get("description", "").strip()
    course_id = form.get("course_id", "")
    total_marks = form.get("total_marks", "").strip()
    marks_obtained = form.get("marks_obtained", "").strip()

    if not heading or not course_id or not total_marks or not marks_obtained:
        return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)

    try:
        tm = int(total_marks)
        mo = int(marks_obtained)
        if tm <= 0 or mo < 0 or mo > tm:
            return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)
    except (ValueError, TypeError):
        return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)

    if not ObjectId.is_valid(course_id):
        return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)

    await database.db.projects.insert_one({
        "student_id": oid,
        "course_id": ObjectId(course_id),
        "heading": heading,
        "description": description,
        "total_marks": tm,
        "marks_obtained": mo,
    })
    return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)


@router.post("/students/{sid}/projects/{pid}/delete", response_class=HTMLResponse)
async def delete_project(
    request: Request,
    sid: str,
    pid: str,
    admin_user: dict = Depends(get_admin_user),
):
    if ObjectId.is_valid(pid):
        await database.db.projects.delete_one({"_id": ObjectId(pid)})
    return RedirectResponse(url=f"/admin/students/{sid}", status_code=303)


@router.get("/batches", response_class=HTMLResponse)
async def list_batches(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    batches = await database.db.batches.find().to_list(length=50)
    for b in batches:
        b["_id"] = str(b["_id"])
        b["student_count"] = await database.db.students.count_documents({"batch_id": b["batch_id"]})
    return templates.TemplateResponse("admin/batches.html", {
        "request": request,
        "admin": admin_user,
        "batches": batches,
    })


@router.get("/batches/create", response_class=HTMLResponse)
async def create_batch_page(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    return templates.TemplateResponse("admin/batch_form.html", {
        "request": request,
        "admin": admin_user,
        "batch": None,
    })


@router.post("/batches/create", response_class=HTMLResponse)
async def create_batch(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    form = await request.form()
    name = form.get("name", "").strip()
    if not name or len(name) > 200:
        return templates.TemplateResponse(
            "admin/batch_form.html",
            {"request": request, "admin": admin_user, "batch": None, "error": "Name is required (max 200 characters)."},
        )
    batch_id = await _next_batch_id()
    await database.db.batches.insert_one({"batch_id": batch_id, "name": name})
    return RedirectResponse(url="/admin/batches", status_code=303)


@router.get("/batches/{bid}/edit", response_class=HTMLResponse)
async def edit_batch_page(
    request: Request,
    bid: str,
    admin_user: dict = Depends(get_admin_user),
):
    if not ObjectId.is_valid(bid):
        return RedirectResponse(url="/admin/batches", status_code=303)
    batch = await database.db.batches.find_one({"_id": ObjectId(bid)})
    if not batch:
        return RedirectResponse(url="/admin/batches", status_code=303)
    batch["_id"] = str(batch["_id"])
    return templates.TemplateResponse("admin/batch_form.html", {
        "request": request,
        "admin": admin_user,
        "batch": batch,
    })


@router.post("/batches/{bid}/edit", response_class=HTMLResponse)
async def edit_batch(
    request: Request,
    bid: str,
    admin_user: dict = Depends(get_admin_user),
):
    form = await request.form()
    name = form.get("name", "").strip()
    if not name or len(name) > 200:
        batch = await database.db.batches.find_one({"_id": ObjectId(bid)})
        if batch:
            batch["_id"] = str(batch["_id"])
        return templates.TemplateResponse(
            "admin/batch_form.html",
            {"request": request, "admin": admin_user, "batch": batch, "error": "Name is required (max 200 characters)."},
        )
    await database.db.batches.update_one(
        {"_id": ObjectId(bid)},
        {"$set": {"name": name}},
    )
    return RedirectResponse(url="/admin/batches", status_code=303)


@router.post("/batches/{bid}/delete", response_class=HTMLResponse)
async def delete_batch(
    request: Request,
    bid: str,
    admin_user: dict = Depends(get_admin_user),
):
    if ObjectId.is_valid(bid):
        await database.db.batches.delete_one({"_id": ObjectId(bid)})
    return RedirectResponse(url="/admin/batches", status_code=303)


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

    if not title or len(title) < 2 or len(title) > 200:
        return templates.TemplateResponse(
            "admin/course_form.html",
            {"request": request, "admin": admin_user, "course": None, "error": "Title must be between 2 and 200 characters."},
        )

    await database.db.courses.insert_one({"title": title, "description": description})
    return RedirectResponse(url="/admin/courses", status_code=303)


@router.get("/courses/{cid}/edit", response_class=HTMLResponse)
async def edit_course_page(
    request: Request,
    cid: str,
    admin_user: dict = Depends(get_admin_user),
):
    if not ObjectId.is_valid(cid):
        return RedirectResponse(url="/admin/courses", status_code=303)
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

    if not title or len(title) < 2 or len(title) > 200:
        course = await database.db.courses.find_one({"_id": ObjectId(cid)})
        if course:
            course["_id"] = str(course["_id"])
        return templates.TemplateResponse(
            "admin/course_form.html",
            {"request": request, "admin": admin_user, "course": course, "error": "Title must be between 2 and 200 characters."},
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
    if not ObjectId.is_valid(cid):
        return RedirectResponse(url="/admin/courses", status_code=303)
    oid = ObjectId(cid)
    await database.db.enrollments.delete_many({"course_id": oid})
    await database.db.assessments.delete_many({"course_id": oid})
    await database.db.projects.delete_many({"course_id": oid})
    await database.db.courses.delete_one({"_id": oid})
    return RedirectResponse(url="/admin/courses", status_code=303)


@router.get("/exams", response_class=HTMLResponse)
async def list_exams(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    exams = await database.db.exams.find().to_list(length=50)
    for e in exams:
        e["_id"] = str(e["_id"])
        e["student_count"] = len(e.get("assigned_students", []))
        e["question_count"] = len(e.get("questions", []))
    return templates.TemplateResponse("admin/exams.html", {
        "request": request,
        "admin": admin_user,
        "exams": exams,
    })


@router.get("/exams/create", response_class=HTMLResponse)
async def create_exam_page(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    students = await database.db.students.find().to_list(length=100)
    for s in students:
        s["_id"] = str(s["_id"])
        s.pop("password", None)
    batches = await database.db.batches.find().to_list(length=50)
    for b in batches:
        b["_id"] = str(b["_id"])
    batch_map = {}
    for s in students:
        bid = s.get("batch_id")
        if bid:
            batch_map.setdefault(bid, []).append(s["_id"])
    return templates.TemplateResponse("admin/exam_form.html", {
        "request": request,
        "admin": admin_user,
        "exam": None,
        "students": students,
        "batches": batches,
        "batch_map": batch_map,
    })


@router.post("/exams/create", response_class=HTMLResponse)
async def create_exam(
    request: Request,
    admin_user: dict = Depends(get_admin_user),
):
    form = await request.form()
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    exam_date = form.get("exam_date", "").strip()
    exam_time = form.get("exam_time", "").strip()
    batch_id = form.get("batch_id", "").strip()
    assigned = form.getlist("assigned_students")

    questions = []
    i = 0
    while f"q_{i}" in form:
        q_text = form.get(f"q_{i}", "").strip()
        opts = [form.get(f"q_{i}_opt_{j}", "").strip() for j in range(4)]
        correct = form.get(f"q_{i}_correct", "")
        if q_text and all(opts) and correct:
            questions.append({"q": q_text, "options": opts, "correct": int(correct)})
        i += 1

    students = await database.db.students.find().to_list(length=100)
    for s in students:
        s["_id"] = str(s["_id"])
        s.pop("password", None)
    batches = await database.db.batches.find().to_list(length=50)
    for b in batches:
        b["_id"] = str(b["_id"])

    if not title or len(title) > 200:
        return templates.TemplateResponse(
            "admin/exam_form.html",
            {"request": request, "admin": admin_user, "exam": None, "students": students, "batches": batches, "error": "Title is required (max 200 characters)."},
        )

    if not questions:
        return templates.TemplateResponse(
            "admin/exam_form.html",
            {"request": request, "admin": admin_user, "exam": None, "students": students, "batches": batches, "error": "At least one question is required."},
        )

    if batch_id:
        batch_students = await database.db.students.find({"batch_id": batch_id}).to_list(length=200)
        for bs in batch_students:
            sid = str(bs["_id"])
            if sid not in assigned:
                assigned.append(sid)

    assigned_ids = []
    for s in assigned:
        if ObjectId.is_valid(s):
            assigned_ids.append(ObjectId(s))

    doc = {
        "title": title,
        "description": description,
        "exam_date": exam_date,
        "exam_time": exam_time,
        "questions": questions,
        "assigned_students": assigned_ids,
    }
    if not exam_date:
        doc.pop("exam_date")
    if not exam_time:
        doc.pop("exam_time")
    await database.db.exams.insert_one(doc)
    return RedirectResponse(url="/admin/exams", status_code=303)


@router.get("/exams/{eid}/edit", response_class=HTMLResponse)
async def edit_exam_page(
    request: Request,
    eid: str,
    admin_user: dict = Depends(get_admin_user),
):
    if not ObjectId.is_valid(eid):
        return RedirectResponse(url="/admin/exams", status_code=303)
    exam = await database.db.exams.find_one({"_id": ObjectId(eid)})
    if not exam:
        return RedirectResponse(url="/admin/exams", status_code=303)
    exam["_id"] = str(exam["_id"])
    assigned_ids = [str(s) for s in exam.get("assigned_students", [])]

    students = await database.db.students.find().to_list(length=100)
    for s in students:
        s["_id"] = str(s["_id"])
        s.pop("password", None)
        s["assigned"] = str(s["_id"]) in assigned_ids
    batches = await database.db.batches.find().to_list(length=50)
    for b in batches:
        b["_id"] = str(b["_id"])
    batch_map = {}
    for s in students:
        bid = s.get("batch_id")
        if bid:
            batch_map.setdefault(bid, []).append(s["_id"])

    return templates.TemplateResponse("admin/exam_form.html", {
        "request": request,
        "admin": admin_user,
        "exam": exam,
        "students": students,
        "batches": batches,
        "batch_map": batch_map,
    })


@router.post("/exams/{eid}/edit", response_class=HTMLResponse)
async def edit_exam(
    request: Request,
    eid: str,
    admin_user: dict = Depends(get_admin_user),
):
    form = await request.form()
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    exam_date = form.get("exam_date", "").strip()
    exam_time = form.get("exam_time", "").strip()
    batch_id = form.get("batch_id", "").strip()
    assigned = form.getlist("assigned_students")

    questions = []
    i = 0
    while f"q_{i}" in form:
        q_text = form.get(f"q_{i}", "").strip()
        opts = [form.get(f"q_{i}_opt_{j}", "").strip() for j in range(4)]
        correct = form.get(f"q_{i}_correct", "")
        if q_text and all(opts) and correct:
            questions.append({"q": q_text, "options": opts, "correct": int(correct)})
        i += 1

    students = await database.db.students.find().to_list(length=100)
    for s in students:
        s["_id"] = str(s["_id"])
        s.pop("password", None)
    batches = await database.db.batches.find().to_list(length=50)
    for b in batches:
        b["_id"] = str(b["_id"])

    if not title or len(title) > 200:
        exam = await database.db.exams.find_one({"_id": ObjectId(eid)})
        if exam:
            exam["_id"] = str(exam["_id"])
            assigned_ids = [str(s) for s in exam.get("assigned_students", [])]
            for s in students:
                s["assigned"] = str(s["_id"]) in assigned_ids
        return templates.TemplateResponse(
            "admin/exam_form.html",
            {"request": request, "admin": admin_user, "exam": exam, "students": students, "batches": batches, "error": "Title is required (max 200 characters)."},
        )

    if not questions:
        exam = await database.db.exams.find_one({"_id": ObjectId(eid)})
        if exam:
            exam["_id"] = str(exam["_id"])
            assigned_ids = [str(s) for s in exam.get("assigned_students", [])]
            for s in students:
                s["assigned"] = str(s["_id"]) in assigned_ids
        return templates.TemplateResponse(
            "admin/exam_form.html",
            {"request": request, "admin": admin_user, "exam": exam, "students": students, "batches": batches, "error": "At least one question is required."},
        )

    if batch_id:
        batch_students = await database.db.students.find({"batch_id": batch_id}).to_list(length=200)
        for bs in batch_students:
            sid = str(bs["_id"])
            if sid not in assigned:
                assigned.append(sid)

    assigned_ids = []
    for s in assigned:
        if ObjectId.is_valid(s):
            assigned_ids.append(ObjectId(s))

    update = {
        "title": title,
        "description": description,
        "exam_date": exam_date,
        "exam_time": exam_time,
        "questions": questions,
        "assigned_students": assigned_ids,
    }
    if not exam_date:
        update.pop("exam_date")
    if not exam_time:
        update.pop("exam_time")
    await database.db.exams.update_one(
        {"_id": ObjectId(eid)},
        {"$set": update},
    )
    return RedirectResponse(url="/admin/exams", status_code=303)


@router.post("/exams/{eid}/delete", response_class=HTMLResponse)
async def delete_exam(
    request: Request,
    eid: str,
    admin_user: dict = Depends(get_admin_user),
):
    if not ObjectId.is_valid(eid):
        return RedirectResponse(url="/admin/exams", status_code=303)
    oid = ObjectId(eid)
    await database.db.exam_results.delete_many({"exam_id": oid})
    await database.db.exams.delete_one({"_id": oid})
    return RedirectResponse(url="/admin/exams", status_code=303)


@router.get("/exams/{eid}/results", response_class=HTMLResponse)
async def exam_results(
    request: Request,
    eid: str,
    admin_user: dict = Depends(get_admin_user),
):
    if not ObjectId.is_valid(eid):
        return RedirectResponse(url="/admin/exams", status_code=303)
    exam = await database.db.exams.find_one({"_id": ObjectId(eid)})
    if not exam:
        return RedirectResponse(url="/admin/exams", status_code=303)

    results = await database.db.exam_results.find({"exam_id": ObjectId(eid)}).to_list(length=100)
    student_data = []
    for r in results:
        student = await database.db.students.find_one({"_id": r["student_id"]})
        student_data.append({
            "name": student["name"] if student else "Unknown",
            "email": student["email"] if student else "",
            "student_id": student.get("student_id", "") if student else "",
            "score": r["score"],
            "total": r["total"],
            "submitted_at": r.get("submitted_at", ""),
        })

    return templates.TemplateResponse("admin/exam_results.html", {
        "request": request,
        "admin": admin_user,
        "exam": {"_id": eid, "title": exam["title"]},
        "results": student_data,
        "question_count": len(exam.get("questions", [])),
    })
