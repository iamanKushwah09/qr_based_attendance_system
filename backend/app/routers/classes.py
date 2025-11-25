from fastapi import APIRouter, HTTPException, Depends
from app.database import connect
from app.routers.auth import admin_required

router = APIRouter(prefix="/classes", tags=["Classes"])


@router.post("/add")
async def add_class(name: str, admin: dict = Depends(admin_required)):
    db = await connect()

    exists = await db.fetchrow(
        "SELECT * FROM classes WHERE name=$1",
        name
    )
    if exists:
        raise HTTPException(400, "Class already exists")

    await db.execute(
        "INSERT INTO classes (name) VALUES ($1)",
        name
    )

    return {"msg": "Class added successfully"}


@router.get("/list")
async def list_classes(admin: dict = Depends(admin_required)):
    db = await connect()
    return await db.fetch("SELECT * FROM classes ORDER BY name")


@router.delete("/delete/{name}")
async def delete_class(name: str, admin: dict = Depends(admin_required)):
    db = await connect()

    exists = await db.fetchrow(
        "SELECT * FROM classes WHERE name=$1",
        name
    )
    if not exists:
        raise HTTPException(404, "Class not found")

    # Check if students exist
    used = await db.fetchrow(
        "SELECT * FROM students WHERE class=$1",
        name
    )
    if used:
        raise HTTPException(400, "Cannot delete class — students assigned")

    await db.execute("DELETE FROM classes WHERE name=$1", name)

    return {"msg": "Class deleted successfully"}
