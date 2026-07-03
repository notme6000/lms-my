import logging
import os
import secrets
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("lms.database")


class Database:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DB_NAME", "lms_db")
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
        await self._seed()

    async def close(self):
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    async def _seed(self):
        admin_username = os.getenv("ADMIN_USERNAME")
        admin_password = os.getenv("ADMIN_PASSWORD")

        if admin_username and admin_password:
            if await self.db.admins.find_one({"username": admin_username}) is None:
                hashed = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
                await self.db.admins.insert_one({"username": admin_username, "password": hashed})
                logger.info("Admin '%s' seeded from environment variables.", admin_username)
        elif await self.db.admins.count_documents({}) == 0:
            logger.warning(
                "No admins found in database and ADMIN_USERNAME/ADMIN_PASSWORD not set. "
                "Set these environment variables to create an initial admin account."
            )

        if await self.db.courses.count_documents({}) == 0:
            await self.db.courses.insert_many([
                {"title": "Python Basics", "description": "Introduction to Python programming"},
                {"title": "Linux Fundamentals", "description": "Basic Linux commands and concepts"},
                {"title": "Web Security", "description": "Web application security fundamentals"},
            ])
            logger.info("Default courses seeded.")

        if await self.db.students.count_documents({}) == 0:
            student_email = os.getenv("SEED_STUDENT_EMAIL")
            student_password = os.getenv("SEED_STUDENT_PASSWORD")
            if student_email and student_password:
                hashed = bcrypt.hashpw(student_password.encode(), bcrypt.gensalt()).decode()
                student = await self.db.students.insert_one({
                    "student_id": "S0001",
                    "name": student_email.split("@")[0].title(),
                    "email": student_email,
                    "password": hashed,
                })
                courses = await self.db.courses.find().to_list(length=None)
                for i, c in enumerate(courses):
                    await self.db.enrollments.insert_one({
                        "student_id": student.inserted_id,
                        "course_id": c["_id"],
                        "progress": 60 if i == 0 else 40 if i == 1 else 0,
                    })
                if courses:
                    await self.db.exams.insert_one({
                        "title": "Python Quiz",
                        "description": "Test your Python basics knowledge",
                        "questions": [
                            {"q": "What type of language is Python?", "options": ["Compiled", "Interpreted", "Both", "None"], "correct": 1},
                            {"q": "Which keyword defines a function?", "options": ["func", "define", "def", "lambda"], "correct": 2},
                            {"q": "What is the output of print(2**3)?", "options": ["6", "8", "9", "Error"], "correct": 1},
                        ],
                        "assigned_students": [student.inserted_id],
                    })
                logger.info("Student '%s' seeded from environment variables.", student_email)
            else:
                logger.info(
                    "No students found and SEED_STUDENT_EMAIL/SEED_STUDENT_PASSWORD not set. "
                    "Skipping student seed."
                )


database = Database()
