#!/usr/bin/env python3
"""Simple script to test MongoDB Atlas connection."""
import asyncio
import os
import sys
from pathlib import Path

# Load .env from project root
from dotenv import load_dotenv
dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path)

from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB_NAME", "lms_db")

    if not uri:
        print("ERROR: MONGODB_URI not found in .env")
        sys.exit(1)

    print(f"Connecting to: {uri.split('@')[1] if '@' in uri else uri}")
    print(f"Database: {db_name}")

    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    try:
        info = await client.server_info()
        print(f"\nConnected! MongoDB version: {info['version']}")
        print(f"Server type: {info.get('msg', 'unknown')}")
        dbs = await client.list_database_names()
        print(f"Databases: {dbs}")
    except Exception as e:
        print(f"\nConnection FAILED: {e}")
        sys.exit(1)
    finally:
        client.close()

asyncio.run(main())
