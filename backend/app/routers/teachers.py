from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import connect
from app.routers.auth import admin_required, get_current_user
import hashlib

router = APIRouter(prefix="/teachers", tags=["Teachers"])


class TeacherUpdate(BaseModel):
    username: str
    password: str | None = None   # optional
    class_name: str | None = None # optional


# ---------- GET ALL TEACHERS (Admin Only) ----------
@router.get("/list")
async def list_teachers(admin: dict = Depends(admin_required)):
    db = await connect()
    rows = await db.fetch(
        """
        SELECT id, username, role, assigned_class
        FROM users
        WHERE role='teacher'
        ORDER BY username
        """
    )
    return rows


# ---------- GET SINGLE TEACHER BY USERNAME ----------
@router.get("/{username}")
async def get_teacher(username: str, admin: dict = Depends(admin_required)):
    db = await connect()
    row = await db.fetchrow(
        """
        SELECT id, username, role, assigned_class
        FROM users
        WHERE username=$1 AND role='teacher'
        """,
        username,
    )
    if not row:
        raise HTTPException(404, "Teacher not found")
    return row


# ---------- UPDATE TEACHER ----------
@router.put("/update")
async def update_teacher(data: TeacherUpdate, admin: dict = Depends(admin_required)):
    db = await connect()

    teacher = await db.fetchrow(
        "SELECT * FROM users WHERE username=$1 AND role='teacher'",
        data.username,
    )
    if not teacher:
        raise HTTPException(404, "Teacher not found")

    # Update password if provided
    if data.password:
        hashed = hashlib.sha256(data.password.encode()).hexdigest()
        await db.execute(
            "UPDATE users SET password_hash=$1 WHERE username=$2",
            hashed,
            data.username,
        )

    # Update class if provided
    if data.class_name:
        cls = await db.fetchrow(
            "SELECT * FROM classes WHERE name=$1",
            data.class_name,
        )
        if not cls:
            raise HTTPException(400, "Class does not exist")

        await db.execute(
            "UPDATE users SET assigned_class=$1 WHERE username=$2",
            data.class_name,
            data.username,
        )

    return {"msg": "Teacher updated successfully"}


# ---------- DELETE TEACHER ----------
@router.delete("/delete/{username}")
async def delete_teacher(username: str, admin: dict = Depends(admin_required)):
    db = await connect()

    teacher = await db.fetchrow(
        "SELECT * FROM users WHERE username=$1 AND role='teacher'",
        username,
    )
    if not teacher:
        raise HTTPException(404, "Teacher not found")

    await db.execute("DELETE FROM users WHERE username=$1", username)

    return {"msg": "Teacher deleted successfully"}
