Build a **server-rendered web application** first.

# Recommended Stack

## Backend

* Python
* **FastAPI**
* Jinja2 Templates
* Uvicorn

## Database

* MongoDB
* Motor (MongoDB Driver)

## Frontend

* HTML
* Tailwind CSS
* JavaScript (minimal)

## Authentication

* Session-based authentication
* Password hashing using `bcrypt`

---

# Project Structure

```text
lms/
│
├── app/
│   ├── main.py
│   ├── auth.py
│   ├── database.py
│   ├── models.py
│   └── routes/
│       ├── admin.py
│       └── student.py
│
├── templates/
│   ├── login.html
│   ├── admin/
│   │   └── dashboard.html
│   │
│   └── student/
│       └── dashboard.html
│
├── static/
│   ├── css/
│   └── js/
│
└── requirements.txt
```

---

# Phase 1 Features

## Admin Login

### Admin Table

```json
{
  "_id": "...",
  "username": "admin",
  "password": "hashed_password",
  "role": "admin"
}
```

### Admin Can

* Login
* Logout
* View Dashboard

Dashboard cards:

```text
Total Students
Total Courses
Upcoming Exams
Recent Logins
```

---

## Student Login

### Student Collection

```json
{
  "_id": "...",
  "name": "John",
  "email": "john@example.com",
  "password": "hashed_password",
  "course_ids": [],
  "role": "student"
}
```

### Student Can

* Login
* Logout
* View Dashboard

---

# Student Dashboard

Layout:

```text
----------------------------------
Welcome John
----------------------------------

My Courses
-----------------
Python Basics
Linux Fundamentals
Web Security

Upcoming Exams
-----------------
Python Quiz
Date: 25-Jun-2026

Progress
-----------------
Python Basics: 60%
Linux: 40%

Notifications
-----------------
New lesson uploaded
Exam scheduled
```

---

# MongoDB Collections

Initially you only need:

## admins

```json
{
  "username": "admin",
  "password": "hashed"
}
```

## students

```json
{
  "name": "John",
  "email": "john@example.com",
  "password": "hashed"
}
```

## courses

```json
{
  "title": "Python Basics",
  "description": "Introduction to Python"
}
```

## enrollments

```json
{
  "student_id": "...",
  "course_id": "...",
  "progress": 60
}
```

## exams

```json
{
  "course_id": "...",
  "title": "Python Quiz",
  "exam_date": "2026-06-25"
}
```

---

# Authentication Flow

```text
Login Page
      |
      |
Enter Credentials
      |
      |
Check MongoDB
      |
      |
Password Verify (bcrypt)
      |
      |
Create Session
      |
      |
Redirect Dashboard
```

---

# Pages To Build First

### Public

* `/login`

### Admin

* `/admin/dashboard`

### Student

* `/student/dashboard`

### Auth

* `/logout`

That's enough for Version 1.

---

