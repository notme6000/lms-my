#!/usr/bin/env python3
"""Export all collections from lms_db to JSON files."""
import json, os, asyncio
from motor.motor_asyncio import AsyncIOMotorClient

OUT = os.path.join(os.path.dirname(__file__), "..", "db_export")
COLLECTIONS = ["admins", "students", "courses", "enrollments", "exams"]


def serialize(doc):
    if isinstance(doc, dict):
        return {k: serialize(v) for k, v in doc.items()}
    if hasattr(doc, "__str__") and type(doc).__name__ == "ObjectId":
        return str(doc)
    return doc


async def export():
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "lms_db")
    client = AsyncIOMotorClient(uri)
    db = client[db_name]
    os.makedirs(OUT, exist_ok=True)
    for name in COLLECTIONS:
        docs = await db[name].find().to_list(length=None)
        docs = [serialize(d) for d in docs]
        path = os.path.join(OUT, f"{name}.json")
        with open(path, "w") as f:
            json.dump(docs, f, indent=2)
        print(f"  {name}: {len(docs)} documents -> {path}")
    client.close()
    print(f"\nDone. Copy the 'db_export/' folder to the target machine.")


if __name__ == "__main__":
    asyncio.run(export())
