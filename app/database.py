from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt

class Database:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        self.client = AsyncIOMotorClient("mongodb://localhost:27017")
        self.db = self.client.lms_db
        await self._seed()

    async def _seed(self):
        if await self.db.admins.find_one({"username": "admin"}) is None:
            hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
            await self.db.admins.insert_one({"username": "admin", "password": hashed})

        if await self.db.courses.count_documents({}) == 0:
            await self.db.courses.insert_many([
                {"title": "Python Basics", "description": "Introduction to Python programming"},
                {"title": "Linux Fundamentals", "description": "Basic Linux commands and concepts"},
                {"title": "Web Security", "description": "Web application security fundamentals"},
            ])

        if await self.db.students.count_documents({}) == 0:
            hashed = bcrypt.hashpw(b"student123", bcrypt.gensalt()).decode()
            student = await self.db.students.insert_one({
                "name": "John", "email": "john@example.com", "password": hashed,
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
                    "course_id": courses[0]["_id"],
                    "title": "Python Quiz",
                    "exam_date": "2026-06-25",
                })

database = Database()
