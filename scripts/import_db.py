#!/usr/bin/env python3
"""Import JSON files from db_export/ into lms_db."""
import json, os, asyncio, bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId

SRC = os.path.join(os.path.dirname(__file__), "..", "db_export")
COLLECTIONS = ["admins", "students", "courses", "enrollments", "exams"]


def restore_objid(obj):
    if isinstance(obj, dict):
        return {k: restore_objid(v) for k, v in obj.items()}
    if isinstance(obj, str) and ObjectId.is_valid(obj):
        return ObjectId(obj)
    return obj


async def restore():
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "lms_db")
    client = AsyncIOMotorClient(uri)
    db = client[db_name]

    for name in COLLECTIONS:
        path = os.path.join(SRC, f"{name}.json")
        if not os.path.exists(path):
            print(f"  Skipping {name} (file not found)")
            continue
        with open(path) as f:
            docs = json.load(f)
        docs = [restore_objid(d) for d in docs]

        await db[name].drop()
        if docs:
            await db[name].insert_many(docs)
        print(f"  {name}: {len(docs)} documents restored")

    client.close()
    print("\nImport complete. Start the app and login with existing credentials.")


if __name__ == "__main__":
    asyncio.run(restore())
