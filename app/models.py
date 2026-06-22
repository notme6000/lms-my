from pydantic import BaseModel
from typing import Optional


class Admin(BaseModel):
    username: str
    password: str


class Student(BaseModel):
    name: str
    email: str
    password: str
    course_ids: list = []


class Course(BaseModel):
    title: str
    description: str


class Enrollment(BaseModel):
    student_id: str
    course_id: str
    progress: int = 0


class Exam(BaseModel):
    course_id: str
    title: str
    exam_date: str
