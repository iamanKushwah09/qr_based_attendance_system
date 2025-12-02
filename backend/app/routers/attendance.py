# backend/app/routers/attendance.py
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from datetime import date, datetime, timedelta
from typing import Literal

from app.database import connect
from app.routers.auth import get_current_user, staff_required, admin_required, log_action
from app.utils.email_service import EmailService
from app import config

router = APIRouter(prefix="/attendance", tags=["Attendance"])

# ==================== MARK ATTENDANCE ====================
@router.get("/mark/{uuid}")
async def mark_attendance(
    uuid: str,
    current_user: dict = Depends(staff_required),
    request: Request = None
):
    """Mark attendance using QR UUID"""
    db = await connect()
    
    try:
        # Get student by QR UUID
        student = await db.fetchrow("""
            SELECT s.id, s.name, s.roll_no, s.class, s.is_active, u.email
            FROM students s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.qr_uuid = $1
        """, uuid)
        
        if not student:
            raise HTTPException(404, "Invalid QR Code")
        
        if not student['is_active']:
            raise HTTPException(403, "Student account is inactive")
        
        # Teacher can only mark their class attendance
        if current_user["role"] == "teacher":
            if student["class"] != current_user["assigned_class"]:
                raise HTTPException(403, "Cannot mark attendance for another class")
        
        # Check duplicate attendance for today
        existing = await db.fetchrow("""
            SELECT id FROM attendance
            WHERE student_id = $1 AND date = CURRENT_DATE
        """, student["id"])
        
        if existing:
            return {
                "msg": "Attendance already marked for today",
                "student": {
                    "name": student["name"],
                    "roll_no": student["roll_no"],
                    "class": student["class"]
                },
                "already_marked": True
            }
        
        # Mark attendance
        attendance_id = await db.fetchval("""
            INSERT INTO attendance 
            (student_id, student_name, roll_no, class_name, date, time, marked_by)
            VALUES ($1, $2, $3, $4, CURRENT_DATE, CURRENT_TIME, $5)
            RETURNING id
        """, student["id"], student["name"], student["roll_no"], 
            student["class"], current_user["id"])
        
        # Log action
        await log_action(db, current_user['id'], "ATTENDANCE_MARKED", "attendance",
                        attendance_id, 
                        {"student_roll": student["roll_no"], "class": student["class"]},
                        request.client.host if request else None)
        
        # Update monthly summary
        await update_attendance_summary(db, student["id"])
        
        # Check attendance percentage and send alert if low
        await check_and_alert_low_attendance(db, student["id"], student["email"])
        
        return {
            "msg": "Attendance marked successfully",
            "student": {
                "name": student["name"],
                "roll_no": student["roll_no"],
                "class": student["class"]
            },
            "marked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    finally:
        await db.close()

# ==================== LIST ATTENDANCE ====================
@router.get("/list")
async def list_attendance(
    date_filter: date | None = Query(None),
    class_name: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """List attendance records with filters"""
    db = await connect()
    
    try:
        offset = (page - 1) * page_size
        where_clauses = []
        params = []
        param_count = 0
        
        # Role-based filtering
        if current_user["role"] == "teacher":
            param_count += 1
            where_clauses.append(f"class_name = ${param_count}")
            params.append(current_user["assigned_class"])
        elif current_user["role"] == "student":
            param_count += 1
            where_clauses.append(f"roll_no = ${param_count}")
            params.append(current_user["username"])
        
        # Date filters
        if date_filter:
            param_count += 1
            where_clauses.append(f"date = ${param_count}")
            params.append(date_filter)
        elif start_date and end_date:
            param_count += 1
            where_clauses.append(f"date >= ${param_count}")
            params.append(start_date)
            param_count += 1
            where_clauses.append(f"date <= ${param_count}")
            params.append(end_date)
        
        # Class filter (for admin)
        if class_name and current_user["role"] == "admin":
            param_count += 1
            where_clauses.append(f"class_name = ${param_count}")
            params.append(class_name)
        
        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Count total
        count_query = f"SELECT COUNT(*) FROM attendance {where_clause}"
        total = await db.fetchval(count_query, *params)
        
        # Fetch records
        param_count += 1
        param_count_limit = param_count
        param_count += 1
        param_count_offset = param_count
        
        query = f"""
            SELECT a.*, u.username as marked_by_username
            FROM attendance a
            LEFT JOIN users u ON a.marked_by = u.id
            {where_clause}
            ORDER BY a.date DESC, a.time DESC
            LIMIT ${param_count_limit} OFFSET ${param_count_offset}
        """
        params.extend([page_size, offset])
        
        records = await db.fetch(query, *params)
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "records": [dict(r) for r in records]
        }
    
    finally:
        await db.close()

# ==================== STUDENT: MY ATTENDANCE ====================
@router.get("/me")
async def my_attendance(
    period: Literal["week", "month", "year", "all"] = Query("month"),
    current_user: dict = Depends(get_current_user)
):
    """Student: Get own attendance with statistics"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Only students can access this endpoint")
    
    db = await connect()
    
    try:
        # Calculate date range
        end_date = date.today()
        if period == "week":
            start_date = end_date - timedelta(days=7)
        elif period == "month":
            start_date = end_date - timedelta(days=30)
        elif period == "year":
            start_date = end_date - timedelta(days=365)
        else:  # all
            start_date = date(2000, 1, 1)
        
        # Get attendance records
        records = await db.fetch("""
            SELECT id, student_name, roll_no, class_name, date, time, created_at
            FROM attendance
            WHERE roll_no = $1 AND date BETWEEN $2 AND $3
            ORDER BY date DESC, time DESC
        """, current_user["username"], start_date, end_date)
        
        # Get total working days (based on class attendance)
        student = await db.fetchrow("""
            SELECT class FROM students WHERE roll_no = $1
        """, current_user["username"])
        
        if student:
            total_days_row = await db.fetchrow("""
                SELECT COUNT(DISTINCT date) as total_days
                FROM attendance
                WHERE class_name = $1 AND date BETWEEN $2 AND $3
            """, student["class"], start_date, end_date)
            total_days = total_days_row["total_days"] if total_days_row else 0
        else:
            total_days = 0
        
        present_days = len(records)
        percentage = (present_days * 100.0 / total_days) if total_days > 0 else 0.0
        
        return {
            "period": period,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "statistics": {
                "total_working_days": total_days,
                "present_days": present_days,
                "absent_days": total_days - present_days,
                "attendance_percentage": round(percentage, 2)
            },
            "records": [dict(r) for r in records]
        }
    
    finally:
        await db.close()

# ==================== DELETE ATTENDANCE ====================
@router.delete("/delete/{attendance_id}")
async def delete_attendance(
    attendance_id: int,
    admin: dict = Depends(admin_required),
    request: Request = None
):
    """Delete attendance record (Admin only)"""
    db = await connect()
    
    try:
        record = await db.fetchrow(
            "SELECT * FROM attendance WHERE id=$1", attendance_id
        )
        if not record:
            raise HTTPException(404, "Attendance record not found")
        
        await db.execute("DELETE FROM attendance WHERE id=$1", attendance_id)
        
        # Update summary
        await update_attendance_summary(db, record["student_id"])
        
        # Log action
        await log_action(db, admin['id'], "ATTENDANCE_DELETED", "attendance",
                        attendance_id, {"student_roll": record["roll_no"]},
                        request.client.host if request else None)
        
        return {"msg": "Attendance record deleted successfully"}
    
    finally:
        await db.close()

# ==================== DAILY SUMMARY ====================
@router.get("/report/daily-summary")
async def daily_summary(
    class_name: str = Query(...),
    target_date: date = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Get daily attendance summary for a class"""
    db = await connect()
    
    try:
        # Permission check
        if current_user["role"] == "teacher":
            if current_user["assigned_class"] != class_name:
                raise HTTPException(403, "Can only view your own class")
        elif current_user["role"] not in ("admin", "teacher"):
            raise HTTPException(403, "Access denied")
        
        # Total students in class
        total = await db.fetchval(
            "SELECT COUNT(*) FROM students WHERE class=$1 AND is_active=TRUE",
            class_name
        )
        
        # Present students
        present = await db.fetchval("""
            SELECT COUNT(DISTINCT student_id)
            FROM attendance
            WHERE class_name=$1 AND date=$2
        """, class_name, target_date)
        
        absent = total - present
        percentage = (present * 100.0 / total) if total > 0 else 0.0
        
        return {
            "class_name": class_name,
            "date": str(target_date),
            "total_students": total,
            "present": present,
            "absent": absent,
            "attendance_percentage": round(percentage, 2)
        }
    
    finally:
        await db.close()

# ==================== ABSENT LIST ====================
@router.get("/absent/{class_name}")
async def absent_list(
    class_name: str,
    target_date: date = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Get list of absent students for a class on a date"""
    db = await connect()
    
    try:
        # Permission check
        if current_user["role"] == "teacher":
            if current_user["assigned_class"] != class_name:
                raise HTTPException(403, "Can only view your own class")
        elif current_user["role"] not in ("admin", "teacher"):
            raise HTTPException(403, "Access denied")
        
        # Get absent students
        students = await db.fetch("""
            SELECT s.id, s.name, s.roll_no, s.class, u.email, u.mobile
            FROM students s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.class = $1 AND s.is_active = TRUE
              AND s.id NOT IN (
                  SELECT student_id
                  FROM attendance
                  WHERE class_name=$1 AND date=$2
              )
            ORDER BY s.roll_no
        """, class_name, target_date)
        
        return {
            "class_name": class_name,
            "date": str(target_date),
            "total_absent": len(students),
            "absent_students": [dict(s) for s in students]
        }
    
    finally:
        await db.close()

# ==================== STUDENT PERCENTAGE ====================
@router.get("/report/student-percentage/{roll_no}")
async def student_percentage(
    roll_no: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Get attendance percentage for a student"""
    db = await connect()
    
    try:
        # Get student
        student = await db.fetchrow("""
            SELECT id, name, roll_no, class FROM students WHERE roll_no=$1
        """, roll_no)
        
        if not student:
            raise HTTPException(404, "Student not found")
        
        # Permission check
        if current_user["role"] == "teacher":
            if student["class"] != current_user["assigned_class"]:
                raise HTTPException(403, "Cannot view students of another class")
        elif current_user["role"] == "student":
            if student["roll_no"] != current_user["username"]:
                raise HTTPException(403, "Can only view your own attendance")
        elif current_user["role"] != "admin":
            raise HTTPException(403, "Access denied")
        
        # Total working days
        total_days = await db.fetchval("""
            SELECT COUNT(DISTINCT date)
            FROM attendance
            WHERE class_name=$1 AND date BETWEEN $2 AND $3
        """, student["class"], start_date, end_date)
        
        # Present days
        present_days = await db.fetchval("""
            SELECT COUNT(DISTINCT date)
            FROM attendance
            WHERE roll_no=$1 AND date BETWEEN $2 AND $3
        """, roll_no, start_date, end_date)
        
        percentage = (present_days * 100.0 / total_days) if total_days > 0 else 0.0
        
        # Get class required percentage
        required = await db.fetchval("""
            SELECT required_attendance_percentage
            FROM classes WHERE name=$1
        """, student["class"])
        
        if required is None:
            required = config.DEFAULT_ATTENDANCE_PERCENTAGE
        
        return {
            "student": {
                "roll_no": student["roll_no"],
                "name": student["name"],
                "class": student["class"]
            },
            "period": {
                "start_date": str(start_date),
                "end_date": str(end_date)
            },
            "statistics": {
                "total_working_days": total_days,
                "present_days": present_days,
                "absent_days": total_days - present_days,
                "attendance_percentage": round(percentage, 2),
                "required_percentage": float(required),
                "status": "Sufficient" if percentage >= float(required) else "Insufficient"
            }
        }
    
    finally:
        await db.close()

# ==================== CLASS PERCENTAGE ====================
@router.get("/report/class-percentage/{class_name}")
async def class_percentage(
    class_name: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Get attendance percentage for entire class"""
    db = await connect()
    
    try:
        # Permission check
        if current_user["role"] == "teacher":
            if current_user["assigned_class"] != class_name:
                raise HTTPException(403, "Can only view your own class")
        elif current_user["role"] != "admin":
            raise HTTPException(403, "Access denied")
        
        # Total working days
        total_days = await db.fetchval("""
            SELECT COUNT(DISTINCT date)
            FROM attendance
            WHERE class_name=$1 AND date BETWEEN $2 AND $3
        """, class_name, start_date, end_date)
        
        # Per-student statistics
        students = await db.fetch("""
            SELECT s.id, s.name, s.roll_no,
                   COUNT(DISTINCT a.date) as present_days
            FROM students s
            LEFT JOIN attendance a ON a.student_id = s.id
                AND a.date BETWEEN $2 AND $3
            WHERE s.class = $1 AND s.is_active = TRUE
            GROUP BY s.id, s.name, s.roll_no
            ORDER BY s.roll_no
        """, class_name, start_date, end_date)
        
        # Calculate percentages
        students_data = []
        total_percentage = 0.0
        
        for student in students:
            present = student["present_days"]
            perc = (present * 100.0 / total_days) if total_days > 0 else 0.0
            total_percentage += perc
            
            students_data.append({
                "id": student["id"],
                "name": student["name"],
                "roll_no": student["roll_no"],
                "present_days": present,
                "absent_days": total_days - present,
                "percentage": round(perc, 2)
            })
        
        avg_percentage = (total_percentage / len(students)) if students else 0.0
        
        return {
            "class_name": class_name,
            "period": {
                "start_date": str(start_date),
                "end_date": str(end_date)
            },
            "statistics": {
                "total_working_days": total_days,
                "total_students": len(students),
                "average_percentage": round(avg_percentage, 2)
            },
            "students": students_data
        }
    
    finally:
        await db.close()

# ==================== HELPER FUNCTIONS ====================
async def update_attendance_summary(db, student_id: int):
    """Update monthly attendance summary for student"""
    now = datetime.now()
    month = now.month
    year = now.year
    
    # Calculate stats for current month
    total_days = await db.fetchval("""
        SELECT COUNT(DISTINCT date)
        FROM attendance
        WHERE student_id IN (
            SELECT id FROM students WHERE class = (
                SELECT class FROM students WHERE id = $1
            )
        )
        AND EXTRACT(MONTH FROM date) = $2
        AND EXTRACT(YEAR FROM date) = $3
    """, student_id, month, year)
    
    present_days = await db.fetchval("""
        SELECT COUNT(DISTINCT date)
        FROM attendance
        WHERE student_id = $1
        AND EXTRACT(MONTH FROM date) = $2
        AND EXTRACT(YEAR FROM date) = $3
    """, student_id, month, year)
    
    percentage = (present_days * 100.0 / total_days) if total_days > 0 else 0.0
    
    # Upsert summary
    await db.execute("""
        INSERT INTO attendance_summary 
        (student_id, month, year, total_days, present_days, percentage, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (student_id, month, year)
        DO UPDATE SET
            total_days = $4,
            present_days = $5,
            percentage = $6,
            updated_at = $7
    """, student_id, month, year, total_days, present_days, 
        round(percentage, 2), datetime.utcnow())

async def check_and_alert_low_attendance(db, student_id: int, email: str):
    """Check attendance and send alert if below threshold"""
    if not email:
        return
    
    # Get student and class info
    student = await db.fetchrow("""
        SELECT s.name, s.roll_no, s.class, c.required_attendance_percentage
        FROM students s
        LEFT JOIN classes c ON s.class = c.name
        WHERE s.id = $1
    """, student_id)
    
    if not student:
        return
    
    required = student["required_attendance_percentage"] or config.DEFAULT_ATTENDANCE_PERCENTAGE
    
    # Get current month percentage
    now = datetime.now()
    summary = await db.fetchrow("""
        SELECT percentage FROM attendance_summary
        WHERE student_id = $1 AND month = $2 AND year = $3
    """, student_id, now.month, now.year)
    
    if summary and float(summary["percentage"]) < float(required):
        # Send low attendance alert
        await EmailService.send_low_attendance_alert(
            email,
            student["name"],
            float(summary["percentage"]),
            float(required)
        )