from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import date
from app.database import connect
from app.routers.auth import get_current_user, staff_required, admin_required

router = APIRouter(prefix="/attendance", tags=["Attendance"])


# ---------- MARK ATTENDANCE USING UUID ----------
@router.get("/mark/{uuid}")
async def mark_attendance(uuid: str, current_user: dict = Depends(staff_required)):
    db = await connect()

    student = await db.fetchrow(
        "SELECT id, name, roll_no, class FROM students WHERE qr_uuid=$1",
        uuid,
    )

    if not student:
        raise HTTPException(404, "Invalid QR Code")

    # TEACHER cannot mark other class attendance
    if current_user["role"] == "teacher":
        if student["class"] != current_user["assigned_class"]:
            raise HTTPException(403, "Cannot mark another class attendance")

    # Check duplicate attendance for today
    already = await db.fetchrow(
        """
        SELECT * FROM attendance
        WHERE student_id=$1 AND date=CURRENT_DATE
        """,
        student["id"],
    )
    if already:
        return {"msg": "Attendance already marked"}

    # Insert attendance
    await db.execute(
        """
        INSERT INTO attendance (student_id, student_name, roll_no, class_name, date, time)
        VALUES ($1, $2, $3, $4, CURRENT_DATE, CURRENT_TIME)
        """,
        student["id"],
        student["name"],
        student["roll_no"],
        student["class"],
    )

    return {"msg": "Attendance marked successfully"}


# ---------- LIST ATTENDANCE (ROLE-BASED) ----------
@router.get("/list")
async def list_attendance(
    date_filter: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    db = await connect()

    # ADMIN → All attendance
    if current_user["role"] == "admin":
        if date_filter:
            return await db.fetch(
                """
                SELECT * FROM attendance
                WHERE date=$1
                ORDER BY class_name, roll_no
                """,
                date_filter,
            )
        return await db.fetch(
            "SELECT * FROM attendance ORDER BY date DESC, class_name, roll_no"
        )

    # TEACHER → Only own class
    if current_user["role"] == "teacher":
        if date_filter:
            return await db.fetch(
                """
                SELECT * FROM attendance
                WHERE class_name=$1 AND date=$2
                ORDER BY roll_no
                """,
                current_user["assigned_class"],
                date_filter,
            )
        return await db.fetch(
            """
            SELECT * FROM attendance
            WHERE class_name=$1
            ORDER BY date DESC, roll_no
            """,
            current_user["assigned_class"],
        )

    # STUDENT → Only self
    if current_user["role"] == "student":
        if date_filter:
            return await db.fetch(
                """
                SELECT * FROM attendance
                WHERE roll_no=$1 AND date=$2
                ORDER BY date DESC
                """,
                current_user["username"],
                date_filter,
            )
        return await db.fetch(
            """
            SELECT * FROM attendance
            WHERE roll_no=$1
            ORDER BY date DESC
            """,
            current_user["username"],
        )

    raise HTTPException(403, "Not allowed")


# ---------- STUDENT: ONLY THEIR ATTENDANCE ----------
@router.get("/me")
async def my_attendance(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "student":
        raise HTTPException(403, "Only students can access this endpoint")

    db = await connect()

    rows = await db.fetch(
        """
        SELECT id, student_name, roll_no, class_name, date, time
        FROM attendance
        WHERE roll_no=$1
        ORDER BY date DESC, time DESC
        """,
        current_user["username"],
    )

    return rows


# ---------- DELETE ATTENDANCE (ADMIN ONLY) ----------
@router.delete("/delete/{attendance_id}")
async def delete_attendance(attendance_id: int, admin: dict = Depends(admin_required)):
    db = await connect()

    exists = await db.fetchrow("SELECT * FROM attendance WHERE id=$1", attendance_id)
    if not exists:
        raise HTTPException(404, "Attendance entry not found")

    await db.execute("DELETE FROM attendance WHERE id=$1", attendance_id)

    return {"msg": "Attendance deleted successfully"}


# =====================================================================
#              ADVANCED REPORTING & ABSENT APIs (PHASE 2)
# =====================================================================

# ---------- CLASS DAILY SUMMARY (PRESENT/ABSENT COUNT) ----------
@router.get("/report/daily-summary/{class_name}")
async def daily_summary(
    class_name: str,
    target_date: date = Query(..., description="Date for summary (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user),
):
    db = await connect()

    # Permission
    if current_user["role"] == "teacher":
        if current_user["assigned_class"] != class_name:
            raise HTTPException(403, "You can only view your own class summary")
    elif current_user["role"] not in ("admin", "teacher"):
        raise HTTPException(403, "Only admin or teacher can view class summary")

    # Total students in this class
    total_row = await db.fetchrow(
        "SELECT COUNT(*) AS c FROM students WHERE class=$1",
        class_name,
    )
    total_students = total_row["c"]

    # Present count = distinct students marked present
    present_row = await db.fetchrow(
        """
        SELECT COUNT(DISTINCT student_id) AS c
        FROM attendance
        WHERE class_name=$1 AND date=$2
        """,
        class_name,
        target_date,
    )
    present_count = present_row["c"]
    absent_count = max(total_students - present_count, 0)

    return {
        "class_name": class_name,
        "date": str(target_date),
        "total_students": total_students,
        "present": present_count,
        "absent": absent_count,
    }


# ---------- ABSENT LIST FOR A CLASS ON A GIVEN DATE ----------
@router.get("/absent/{class_name}")
async def absent_list(
    class_name: str,
    target_date: date = Query(..., description="Date to check absentees"),
    current_user: dict = Depends(get_current_user),
):
    db = await connect()

    # Permission
    if current_user["role"] == "teacher":
        if current_user["assigned_class"] != class_name:
            raise HTTPException(403, "You can only view your own class absentees")
    elif current_user["role"] not in ("admin", "teacher"):
        raise HTTPException(403, "Only admin or teacher can view absentees")

    # Students who are NOT in attendance table for that date + class
    rows = await db.fetch(
        """
        SELECT s.id, s.name, s.roll_no, s.class
        FROM students s
        WHERE s.class = $1
          AND s.id NOT IN (
              SELECT student_id
              FROM attendance
              WHERE class_name=$1 AND date=$2
          )
        ORDER BY s.roll_no
        """,
        class_name,
        target_date,
    )

    return {
        "class_name": class_name,
        "date": str(target_date),
        "absent_students": rows,
    }


# ---------- STUDENT-WISE ATTENDANCE PERCENTAGE ----------
@router.get("/report/student-percentage/{roll_no}")
async def student_percentage(
    roll_no: str,
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user),
):
    db = await connect()

    # Fetch student
    student = await db.fetchrow(
        "SELECT id, name, roll_no, class FROM students WHERE roll_no=$1",
        roll_no,
    )
    if not student:
        raise HTTPException(404, "Student not found")

    # Permissions
    if current_user["role"] == "teacher":
        if student["class"] != current_user["assigned_class"]:
            raise HTTPException(403, "You cannot view students of another class")
    elif current_user["role"] == "student":
        if student["roll_no"] != current_user["username"]:
            raise HTTPException(403, "You can only view your own percentage")
    elif current_user["role"] != "admin":
        raise HTTPException(403, "Not allowed")

    # Total working days for this class in range
    total_days_row = await db.fetchrow(
        """
        SELECT COUNT(DISTINCT date) AS total_days
        FROM attendance
        WHERE class_name=$1
          AND date BETWEEN $2 AND $3
        """,
        student["class"],
        start_date,
        end_date,
    )
    total_days = total_days_row["total_days"]

    # Days student was present
    present_days_row = await db.fetchrow(
        """
        SELECT COUNT(DISTINCT date) AS present_days
        FROM attendance
        WHERE roll_no=$1
          AND date BETWEEN $2 AND $3
        """,
        student["roll_no"],
        start_date,
        end_date,
    )
    present_days = present_days_row["present_days"]

    percentage = float(present_days) * 100.0 / float(total_days) if total_days else 0.0

    return {
        "roll_no": student["roll_no"],
        "name": student["name"],
        "class_name": student["class"],
        "start_date": str(start_date),
        "end_date": str(end_date),
        "total_working_days": total_days,
        "present_days": present_days,
        "attendance_percentage": round(percentage, 2),
    }


# ---------- CLASS-WISE ATTENDANCE PERCENTAGE ----------
@router.get("/report/class-percentage/{class_name}")
async def class_percentage(
    class_name: str,
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user),
):
    db = await connect()

    # Permissions
    if current_user["role"] == "teacher":
        if current_user["assigned_class"] != class_name:
            raise HTTPException(403, "You can only view your own class report")
    elif current_user["role"] != "admin":
        raise HTTPException(403, "Only admin or class teacher can view this")

    # Total distinct working days for class in range
    total_days_row = await db.fetchrow(
        """
        SELECT COUNT(DISTINCT date) AS total_days
        FROM attendance
        WHERE class_name=$1
          AND date BETWEEN $2 AND $3
        """,
        class_name,
        start_date,
        end_date,
    )
    total_days = total_days_row["total_days"]

    # Per-student present days
    students_rows = await db.fetch(
        """
        SELECT s.id,
               s.name,
               s.roll_no,
               COUNT(DISTINCT a.date) AS present_days
        FROM students s
        LEFT JOIN attendance a
          ON a.student_id = s.id
         AND a.date BETWEEN $2 AND $3
         AND a.class_name = $1
        WHERE s.class = $1
        GROUP BY s.id, s.name, s.roll_no
        ORDER BY s.roll_no
        """,
        class_name,
        start_date,
        end_date,
    )

    # Build output with percentage
    students_data = []
    total_percentage_sum = 0.0
    count_for_avg = 0

    for row in students_rows:
        present_days = row["present_days"]
        if total_days:
            perc = float(present_days) * 100.0 / float(total_days)
        else:
            perc = 0.0

        students_data.append(
            {
                "id": row["id"],
                "name": row["name"],
                "roll_no": row["roll_no"],
                "present_days": present_days,
                "attendance_percentage": round(perc, 2),
            }
        )

        total_percentage_sum += perc
        count_for_avg += 1

    avg_percentage = (
        round(total_percentage_sum / count_for_avg, 2) if count_for_avg else 0.0
    )

    return {
        "class_name": class_name,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "total_working_days": total_days,
        "average_percentage": avg_percentage,
        "students": students_data,
    }
