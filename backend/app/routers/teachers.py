# backend/app/routers/teachers.py
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, EmailStr
from datetime import datetime
import hashlib

from app.database import connect
from app.routers.auth import admin_required, get_current_user, log_action, validate_password_strength
from app.utils.email_service import EmailService

router = APIRouter(prefix="/teachers", tags=["Teachers"])

class TeacherCreate(BaseModel):
    username: str
    email: EmailStr
    mobile: str | None = None
    password: str
    name: str
    assigned_class: str | None = None

class TeacherUpdate(BaseModel):
    email: EmailStr | None = None
    mobile: str | None = None
    name: str | None = None
    assigned_class: str | None = None
    is_active: bool | None = None

# ==================== CREATE TEACHER ====================
@router.post("/create", status_code=201)
async def create_teacher(
    data: TeacherCreate,
    admin: dict = Depends(admin_required),
    request: Request = None
):
    """Admin: Create new teacher account"""
    db = await connect()
    
    try:
        # Check existing username
        existing = await db.fetchrow(
            "SELECT id FROM users WHERE username=$1", data.username
        )
        if existing:
            raise HTTPException(400, "Username already exists")
        
        # Check existing email
        existing_email = await db.fetchrow(
            "SELECT id FROM users WHERE email=$1", data.email
        )
        if existing_email:
            raise HTTPException(400, "Email already registered")
        
        # Validate class if assigned
        if data.assigned_class:
            cls = await db.fetchrow(
                "SELECT id FROM classes WHERE name=$1", data.assigned_class
            )
            if not cls:
                raise HTTPException(400, "Assigned class does not exist")
        
        # Validate password
        validate_password_strength(data.password)
        
        # Hash password
        hashed = hashlib.sha256(data.password.encode()).hexdigest()
        
        # Create user
        user_id = await db.fetchval("""
            INSERT INTO users 
            (username, email, mobile, password_hash, role, assigned_class, is_verified)
            VALUES ($1, $2, $3, $4, 'teacher', $5, TRUE)
            RETURNING id
        """, data.username, data.email, data.mobile, hashed, data.assigned_class)
        
        # Log action
        await log_action(db, admin['id'], "TEACHER_CREATED", "users", user_id,
                        {"username": data.username, "class": data.assigned_class},
                        request.client.host if request else None)
        
        # Send welcome email
        await EmailService.send_welcome_email(
            data.email, data.username, "teacher", data.password
        )
        
        return {
            "msg": "Teacher created successfully",
            "user_id": user_id,
            "username": data.username,
            "assigned_class": data.assigned_class
        }
    
    finally:
        await db.close()

# ==================== LIST TEACHERS ====================
@router.get("/list")
async def list_teachers(
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: dict = Depends(admin_required)
):
    """Admin: List all teachers"""
    db = await connect()
    
    try:
        offset = (page - 1) * page_size
        where_clause = "WHERE role='teacher'"
        params = []
        
        if is_active is not None:
            where_clause += " AND is_active=$1"
            params.append(is_active)
        
        # Count total
        count_query = f"SELECT COUNT(*) FROM users {where_clause}"
        total = await db.fetchval(count_query, *params)
        
        # Fetch teachers
        query = f"""
            SELECT id, username, email, mobile, assigned_class, is_active,
                   last_login, created_at
            FROM users
            {where_clause}
            ORDER BY username
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """
        params.extend([page_size, offset])
        
        teachers = await db.fetch(query, *params)
        
        # Get student counts for each teacher
        teachers_data = []
        for teacher in teachers:
            if teacher['assigned_class']:
                student_count = await db.fetchval("""
                    SELECT COUNT(*) FROM students 
                    WHERE class=$1 AND is_active=TRUE
                """, teacher['assigned_class'])
            else:
                student_count = 0
            
            teachers_data.append({
                **dict(teacher),
                "student_count": student_count
            })
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "teachers": teachers_data
        }
    
    finally:
        await db.close()

# ==================== GET TEACHER ====================
@router.get("/{username}")
async def get_teacher(
    username: str,
    admin: dict = Depends(admin_required)
):
    """Admin: Get teacher details"""
    db = await connect()
    
    try:
        teacher = await db.fetchrow("""
            SELECT id, username, email, mobile, assigned_class, is_active,
                   last_login, created_at, updated_at
            FROM users
            WHERE username=$1 AND role='teacher'
        """, username)
        
        if not teacher:
            raise HTTPException(404, "Teacher not found")
        
        # Get student count
        if teacher['assigned_class']:
            student_count = await db.fetchval("""
                SELECT COUNT(*) FROM students 
                WHERE class=$1 AND is_active=TRUE
            """, teacher['assigned_class'])
        else:
            student_count = 0
        
        return {
            **dict(teacher),
            "student_count": student_count
        }
    
    finally:
        await db.close()

# ==================== UPDATE TEACHER ====================
@router.put("/update/{username}")
async def update_teacher(
    username: str,
    data: TeacherUpdate,
    admin: dict = Depends(admin_required),
    request: Request = None
):
    """Admin: Update teacher details"""
    db = await connect()
    
    try:
        # Check teacher exists
        teacher = await db.fetchrow("""
            SELECT id FROM users WHERE username=$1 AND role='teacher'
        """, username)
        
        if not teacher:
            raise HTTPException(404, "Teacher not found")
        
        # Validate class if being updated
        if data.assigned_class:
            cls = await db.fetchrow(
                "SELECT id FROM classes WHERE name=$1", data.assigned_class
            )
            if not cls:
                raise HTTPException(400, "Assigned class does not exist")
        
        # Build update query
        updates = []
        params = []
        param_count = 0
        
        for field in ['email', 'mobile', 'assigned_class', 'is_active']:
            value = getattr(data, field)
            if value is not None:
                param_count += 1
                updates.append(f"{field} = ${param_count}")
                params.append(value)
        
        if not updates:
            raise HTTPException(400, "No fields to update")
        
        # Add updated_at
        param_count += 1
        updates.append(f"updated_at = ${param_count}")
        params.append(datetime.utcnow())
        
        # Add username for WHERE
        param_count += 1
        params.append(username)
        
        query = f"""
            UPDATE users 
            SET {', '.join(updates)}
            WHERE username = ${param_count}
        """
        
        await db.execute(query, *params)
        
        # Log action
        await log_action(db, admin['id'], "TEACHER_UPDATED", "users",
                        teacher['id'], {"username": username},
                        request.client.host if request else None)
        
        return {"msg": "Teacher updated successfully"}
    
    finally:
        await db.close()

# ==================== DELETE TEACHER ====================
@router.delete("/delete/{username}")
async def delete_teacher(
    username: str,
    admin: dict = Depends(admin_required),
    request: Request = None
):
    """Admin: Delete teacher (soft delete)"""
    db = await connect()
    
    try:
        teacher = await db.fetchrow("""
            SELECT id FROM users WHERE username=$1 AND role='teacher'
        """, username)
        
        if not teacher:
            raise HTTPException(404, "Teacher not found")
        
        # Soft delete
        await db.execute("""
            UPDATE users 
            SET is_active=FALSE, updated_at=$1
            WHERE username=$2
        """, datetime.utcnow(), username)
        
        # Log action
        await log_action(db, admin['id'], "TEACHER_DELETED", "users",
                        teacher['id'], {"username": username},
                        request.client.host if request else None)
        
        return {"msg": "Teacher deleted successfully"}
    
    finally:
        await db.close()

# ==================== TEACHER: GET OWN PROFILE ====================
@router.get("/me/profile")
async def get_my_teacher_profile(
    current_user: dict = Depends(get_current_user)
):
    """Teacher: Get own profile"""
    if current_user["role"] != "teacher":
        raise HTTPException(403, "Only teachers can access this endpoint")
    
    db = await connect()
    
    try:
        teacher = await db.fetchrow("""
            SELECT id, username, email, mobile, assigned_class, last_login, created_at
            FROM users
            WHERE username=$1
        """, current_user["username"])
        
        if not teacher:
            raise HTTPException(404, "Profile not found")
        
        # Get student count
        if teacher['assigned_class']:
            student_count = await db.fetchval("""
                SELECT COUNT(*) FROM students 
                WHERE class=$1 AND is_active=TRUE
            """, teacher['assigned_class'])
        else:
            student_count = 0
        
        return {
            **dict(teacher),
            "student_count": student_count
        }
    
    finally:
        await db.close()

# ==================== TEACHER: GET MY STUDENTS ====================
@router.get("/me/students")
async def get_my_students(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Teacher: Get students of assigned class"""
    if current_user["role"] != "teacher":
        raise HTTPException(403, "Only teachers can access this endpoint")
    
    if not current_user.get("assigned_class"):
        raise HTTPException(400, "No class assigned to you")
    
    db = await connect()
    
    try:
        offset = (page - 1) * page_size
        
        # Count total
        total = await db.fetchval("""
            SELECT COUNT(*) FROM students 
            WHERE class=$1 AND is_active=TRUE
        """, current_user["assigned_class"])
        
        # Fetch students
        students = await db.fetch("""
            SELECT s.id, s.name, s.roll_no, s.class, s.father_name, 
                   s.qr_uuid, u.email, u.mobile
            FROM students s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.class=$1 AND s.is_active=TRUE
            ORDER BY s.roll_no
            LIMIT $2 OFFSET $3
        """, current_user["assigned_class"], page_size, offset)
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "students": [dict(s) for s in students]
        }
    
    finally:
        await db.close()