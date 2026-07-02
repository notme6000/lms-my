import logging

from fastapi import Request, HTTPException, Depends

logger = logging.getLogger("lms.auth")


async def get_admin_user(request: Request):
    user = request.session.get("user")
    if not user or user.get("role") != "admin":
        logger.warning("Unauthorized admin access attempt")
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


async def get_student_user(request: Request):
    user = request.session.get("user")
    if not user or user.get("role") != "student":
        logger.warning("Unauthorized student access attempt")
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


async def get_authenticated_user(request: Request):
    user = request.session.get("user")
    if not user:
        logger.warning("Unauthenticated access attempt")
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user
