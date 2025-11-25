from fastapi import APIRouter, HTTPException, Depends, Query
from app.database import connect
from app.utils.qr_generator import generate_uuid_qr
from app.routers.auth import staff_required, get_current_user, admin_required
import hashlib  # <-- added for password hashing
from fastapi.responses import HTMLResponse, JSONResponse
import base64
router = APIRouter(prefix="/students", tags=["Students"])


# ---------- ADD STUDENT (Admin + Teacher: class restricted + OPTIONAL login create) ----------
@router.post("/add")
async def add_student(
    name: str = Query(...),
    roll_no: str = Query(...),
    class_name: str = Query(...),
    password: str | None = Query(  # NEW: optional password for student login
        default=None,
        description="Optional password to create a login user for this student",
    ),
    current_user: dict = Depends(staff_required),
):
    db = await connect()

    # 1) Validate class exists
    cls = await db.fetchrow(
        "SELECT * FROM classes WHERE name=$1",
        class_name
    )
    if not cls:
        raise HTTPException(400, "Class does not exist. Add it first.")

    # 2) Teacher → only their own class
    if current_user["role"] == "teacher":
        if current_user["assigned_class"] != class_name:
            raise HTTPException(
                403, "You can only add students to your assigned class"
            )

    # 3) Check duplicate student roll_no
    existing = await db.fetchrow(
        "SELECT * FROM students WHERE roll_no=$1",
        roll_no,
    )
    if existing:
        raise HTTPException(400, "Student with this roll number already exists")

    # 4) OPTIONAL: create login user in `users` table IF password given
    if password:
        existing_user = await db.fetchrow(
            "SELECT * FROM users WHERE username=$1",
            roll_no,
        )
        if existing_user:
            raise HTTPException(
                400,
                "A user with this roll number already exists in login system",
            )

        hashed = hashlib.sha256(password.encode()).hexdigest()

        # NOTE: users table assumed as (username, password_hash, role)
        await db.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES ($1, $2, $3)
            """,
            roll_no,
            hashed,
            "student",
        )

    # 5) Generate QR UUID for this student
    unique_id, qr_path = generate_uuid_qr(roll_no)

    # 6) Insert into students table
    await db.execute(
        """
        INSERT INTO students (name, roll_no, class, qr_uuid)
        VALUES ($1, $2, $3, $4)
        """,
        name, roll_no, class_name, unique_id
    )

    return {
        "msg": "Student created successfully",
        "qr_uuid": unique_id,
        "qr_path": qr_path,
        "login_created": bool(password),
    }


# ---------- LIST STUDENTS (Role-based) ----------
@router.get("/list")
async def list_students(current_user: dict = Depends(get_current_user)):
    db = await connect()

    # ADMIN → All students
    if current_user["role"] == "admin":
        rows = await db.fetch(
            """
            SELECT id, name, roll_no, class, qr_uuid
            FROM students
            ORDER BY class, roll_no
            """
        )
        return rows

    # TEACHER → Only own class students
    if current_user["role"] == "teacher":
        rows = await db.fetch(
            """
            SELECT id, name, roll_no, class, qr_uuid
            FROM students
            WHERE class = $1
            ORDER BY roll_no
            """,
            current_user["assigned_class"],
        )
        return rows

    # STUDENT → Only self
    if current_user["role"] == "student":
        rows = await db.fetch(
            """
            SELECT id, name, roll_no, class, qr_uuid
            FROM students
            WHERE roll_no=$1
            """,
            current_user["username"],
        )
        return rows


# ---------- GET SINGLE STUDENT ----------
@router.get("/{student_id}")
async def get_student(student_id: int, current_user: dict = Depends(get_current_user)):
    db = await connect()

    student = await db.fetchrow(
        "SELECT id, name, roll_no, class, qr_uuid FROM students WHERE id=$1",
        student_id,
    )

    if not student:
        raise HTTPException(404, "Student not found")

    # ADMIN → allowed
    if current_user["role"] == "admin":
        return student

    # TEACHER → only own class
    if current_user["role"] == "teacher":
        if student["class"] != current_user["assigned_class"]:
            raise HTTPException(403, "Not your class")
        return student

    # STUDENT → Only themselves
    if current_user["role"] == "student":
        if student["roll_no"] != current_user["username"]:
            raise HTTPException(403, "Not your data")
        return student


# ---------- UPDATE STUDENT (Admin + Teacher) ----------
@router.put("/update/{student_id}")
async def update_student(
    student_id: int,
    name: str = Query(...),
    roll_no: str = Query(...),
    class_name: str = Query(...),
    current_user: dict = Depends(staff_required),
):
    db = await connect()

    student = await db.fetchrow("SELECT * FROM students WHERE id=$1", student_id)
    if not student:
        raise HTTPException(404, "Student not found")

    # Validate class exists
    cls = await db.fetchrow(
        "SELECT * FROM classes WHERE name=$1",
        class_name
    )
    if not cls:
        raise HTTPException(400, "Class does not exist")

    # TEACHER → only own class
    if current_user["role"] == "teacher":
        if student["class"] != current_user["assigned_class"]:
            raise HTTPException(403, "You cannot update students of another class")
        if class_name != current_user["assigned_class"]:
            raise HTTPException(403, "You cannot move students to another class")

    await db.execute(
        """
        UPDATE students
        SET name=$1, roll_no=$2, class=$3
        WHERE id=$4
        """,
        name, roll_no, class_name, student_id
    )

    return {"msg": "Student updated successfully"}


# ---------- DELETE STUDENT (Admin + Teacher) ----------
@router.delete("/delete/{student_id}")
async def delete_student(student_id: int, current_user: dict = Depends(staff_required)):
    db = await connect()

    student = await db.fetchrow("SELECT * FROM students WHERE id=$1", student_id)
    if not student:
        raise HTTPException(404, "Student not found")

    # TEACHER → only their own class
    if current_user["role"] == "teacher":
        if student["class"] != current_user["assigned_class"]:
            raise HTTPException(403, "You cannot delete students of another class")

    await db.execute("DELETE FROM students WHERE id=$1", student_id)

    return {"msg": "Student deleted successfully"}


# ---------- STUDENT: GET OWN PROFILE ----------
@router.get("/me")
async def get_my_student_profile(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "student":
        raise HTTPException(403, "Only students can access this endpoint")

    db = await connect()

    student = await db.fetchrow(
        """
        SELECT id, name, roll_no, class, qr_uuid
        FROM students
        WHERE roll_no = $1
        """,
        current_user["username"],
    )

    if not student:
        raise HTTPException(404, "No student record found for this user")

    return student


