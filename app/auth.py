from fastapi import Request, HTTPException, Depends


async def get_admin_user(request: Request):
    user = request.session.get("user")
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


async def get_student_user(request: Request):
    user = request.session.get("user")
    if not user or user.get("role") != "student":
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


async def get_authenticated_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user
