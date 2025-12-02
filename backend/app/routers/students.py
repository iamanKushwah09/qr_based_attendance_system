# backend/app/routers/students.py
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, EmailStr, validator
from datetime import date, datetime
import hashlib
import re

from app.database import connect
from app.utils.qr_generator import generate_uuid_qr
from app.routers.auth import staff_required, get_current_user, admin_required, log_action
from app.utils.email_service import EmailService

router = APIRouter(prefix="/students", tags=["Students"])

class StudentCreate(BaseModel):
    name: str
    roll_no: str
    class_name: str
    father_name: str | None = None
    mother_name: str | None = None
    date_of_birth: date | None = None
    address: str | None = None
    email: EmailStr | None = None
    mobile: str | None = None
    create_login: bool = False
    password: str | None = None
    
    @validator('mobile')
    def validate_mobile(cls, v):
        if v and not re.match(r'^\+?[0-9]{10,15}$', v):
            raise ValueError('Invalid mobile number')
        return v

class StudentUpdate(BaseModel):
    name: str | None = None
    father_name: str | None = None
    mother_name: str | None = None
    date_of_birth: date | None = None
    address: str | None = None
    email: EmailStr | None = None
    mobile: str | None = None
    is_active: bool | None = None

# ==================== ADD STUDENT ====================
@router.post("/add", status_code=201)
async def add_student(
    data: StudentCreate,
    current_user: dict = Depends(staff_required),
    request: Request = None
):
    """Add new student (Admin/Teacher)"""
    db = await connect()
    
    try:
        # Validate class exists
        cls = await db.fetchrow("SELECT * FROM classes WHERE name=$1", data.class_name)
        if not cls:
            raise HTTPException(400, "Class does not exist")
        
        # Teacher can only add to their class
        if current_user["role"] == "teacher":
            if current_user["assigned_class"] != data.class_name:
                raise HTTPException(403, "You can only add students to your assigned class")
        
        # Check duplicate roll number
        existing = await db.fetchrow("SELECT id FROM students WHERE roll_no=$1", data.roll_no)
        if existing:
            raise HTTPException(400, "Student with this roll number already exists")
        
        # Check duplicate email
        if data.email:
            existing_email = await db.fetchrow("SELECT id FROM students WHERE email=$1", data.email)
            if existing_email:
                raise HTTPException(400, "Email already registered")
        
        user_id = None
        temp_password = None
        
        # Create login user if requested
        if data.create_login:
            if not data.password:
                # Generate temporary password
                import secrets
                temp_password = f"Student@{secrets.token_hex(4)}"
                password = temp_password
            else:
                password = data.password
            
            # Check if username exists
            existing_user = await db.fetchrow("SELECT id FROM users WHERE username=$1", data.roll_no)
            if existing_user:
                raise HTTPException(400, "Username already exists")
            
            # Validate password strength
            from app.routers.auth import validate_password_strength
            validate_password_strength(password)
            
            # Create user account
            hashed = hashlib.sha256(password.encode()).hexdigest()
            user_id = await db.fetchval("""
                INSERT INTO users (username, email, mobile, password_hash, role, is_verified)
                VALUES ($1, $2, $3, $4, 'student', TRUE)
                RETURNING id
            """, data.roll_no, data.email, data.mobile, hashed)
        
        # Generate QR code
        unique_id, qr_path = generate_uuid_qr(data.roll_no)
        
        # Insert student
        student_id = await db.fetchval("""
            INSERT INTO students 
            (user_id, name, roll_no, class, father_name, mother_name, date_of_birth, 
             address, qr_uuid, is_active)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, TRUE)
            RETURNING id
        """, user_id, data.name, data.roll_no, data.class_name, data.father_name,
            data.mother_name, data.date_of_birth, data.address, unique_id)
        
        # Log action
        await log_action(db, current_user['id'], "STUDENT_ADDED", "students", 
                        student_id, {"roll_no": data.roll_no, "class": data.class_name},
                        request.client.host if request else None)
        
        # Send welcome email
        if data.email and data.create_login:
            await EmailService.send_welcome_email(
                data.email, data.roll_no, "student", temp_password
            )
        
        return {
            "msg": "Student added successfully",
            "student_id": student_id,
            "roll_no": data.roll_no,
            "qr_uuid": unique_id,
            "qr_path": qr_path,
            "login_created": data.create_login,
            "temporary_password": temp_password if temp_password else None
        }
    
    finally:
        await db.close()

# ==================== LIST STUDENTS ====================
@router.get("/list")
async def list_students(
    class_name: str | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """List students with pagination and filters"""
    db = await connect()
    
    try:
        offset = (page - 1) * page_size
        
        # Build query based on role
        if current_user["role"] == "admin":
            where_clause = "WHERE 1=1"
            params = []
        elif current_user["role"] == "teacher":
            where_clause = "WHERE s.class = $1"
            params = [current_user["assigned_class"]]
        else:  # student
            where_clause = "WHERE s.roll_no = $1"
            params = [current_user["username"]]
        
        # Add filters
        param_count = len(params)
        if class_name and current_user["role"] == "admin":
            param_count += 1
            where_clause += f" AND s.class = ${param_count}"
            params.append(class_name)
        
        if is_active is not None:
            param_count += 1
            where_clause += f" AND s.is_active = ${param_count}"
            params.append(is_active)
        
        # Count total
        count_query = f"SELECT COUNT(*) FROM students s {where_clause}"
        total = await db.fetchval(count_query, *params)
        
        # Fetch students
        query = f"""
            SELECT s.id, s.name, s.roll_no, s.class, s.father_name, s.mother_name,
                   s.date_of_birth, s.address, s.qr_uuid, s.is_active, s.created_at,
                   u.email, u.mobile
            FROM students s
            LEFT JOIN users u ON s.user_id = u.id
            {where_clause}
            ORDER BY s.class, s.roll_no
            LIMIT ${param_count + 1} OFFSET ${param_count + 2}
        """
        params.extend([page_size, offset])
        
        students = await db.fetch(query, *params)
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "students": [dict(s) for s in students]
        }
    
    finally:
        await db.close()

# ==================== GET STUDENT ====================
@router.get("/{student_id}")
async def get_student(
    student_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get single student details"""
    db = await connect()
    
    try:
        student = await db.fetchrow("""
            SELECT s.*, u.email, u.mobile, u.is_active as user_active
            FROM students s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.id = $1
        """, student_id)
        
        if not student:
            raise HTTPException(404, "Student not found")
        
        # Permission check
        if current_user["role"] == "teacher":
            if student["class"] != current_user["assigned_class"]:
                raise HTTPException(403, "Not your class")
        elif current_user["role"] == "student":
            if student["roll_no"] != current_user["username"]:
                raise HTTPException(403, "Access denied")
        
        return dict(student)
    
    finally:
        await db.close()

# ==================== UPDATE STUDENT ====================
@router.put("/update/{student_id}")
async def update_student(
    student_id: int,
    data: StudentUpdate,
    current_user: dict = Depends(staff_required),
    request: Request = None
):
    """Update student details"""
    db = await connect()
    
    try:
        student = await db.fetchrow(
            "SELECT * FROM students WHERE id=$1", student_id
        )
        if not student:
            raise HTTPException(404, "Student not found")
        
        # Teacher can only update their class students
        if current_user["role"] == "teacher":
            if student["class"] != current_user["assigned_class"]:
                raise HTTPException(403, "Cannot update students of another class")
        
        # Build update query
        updates = []
        params = []
        param_count = 0
        
        for field in ['name', 'father_name', 'mother_name', 'date_of_birth', 
                     'address', 'is_active']:
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
        
        # Add student_id for WHERE clause
        param_count += 1
        params.append(student_id)
        
        query = f"""
            UPDATE students 
            SET {', '.join(updates)}
            WHERE id = ${param_count}
        """
        
        await db.execute(query, *params)
        
        # Update user table if email/mobile provided
        if student['user_id'] and (data.email or data.mobile):
            user_updates = []
            user_params = []
            user_param_count = 0
            
            if data.email:
                user_param_count += 1
                user_updates.append(f"email = ${user_param_count}")
                user_params.append(data.email)
            
            if data.mobile:
                user_param_count += 1
                user_updates.append(f"mobile = ${user_param_count}")
                user_params.append(data.mobile)
            
            if user_updates:
                user_param_count += 1
                user_params.append(student['user_id'])
                
                await db.execute(
                    f"UPDATE users SET {', '.join(user_updates)} WHERE id = ${user_param_count}",
                    *user_params
                )
        
        # Log action
        await log_action(db, current_user['id'], "STUDENT_UPDATED", "students",
                        student_id, {"roll_no": student["roll_no"]},
                        request.client.host if request else None)
        
        return {"msg": "Student updated successfully"}
    
    finally:
        await db.close()

# ==================== DELETE STUDENT ====================
@router.delete("/delete/{student_id}")
async def delete_student(
    student_id: int,
    current_user: dict = Depends(staff_required),
    request: Request = None
):
    """Delete student (soft delete by setting is_active=false)"""
    db = await connect()
    
    try:
        student = await db.fetchrow(
            "SELECT * FROM students WHERE id=$1", student_id
        )
        if not student:
            raise HTTPException(404, "Student not found")
        
        # Teacher can only delete their class students
        if current_user["role"] == "teacher":
            if student["class"] != current_user["assigned_class"]:
                raise HTTPException(403, "Cannot delete students of another class")
        
        # Soft delete
        await db.execute(
            "UPDATE students SET is_active=FALSE, updated_at=$1 WHERE id=$2",
            datetime.utcnow(), student_id
        )
        
        # Deactivate user account if exists
        if student['user_id']:
            await db.execute(
                "UPDATE users SET is_active=FALSE WHERE id=$1",
                student['user_id']
            )
        
        # Log action
        await log_action(db, current_user['id'], "STUDENT_DELETED", "students",
                        student_id, {"roll_no": student["roll_no"]},
                        request.client.host if request else None)
        
        return {"msg": "Student deleted successfully"}
    
    finally:
        await db.close()

# ==================== STUDENT: GET OWN PROFILE ====================
@router.get("/me/profile")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """Student: Get own profile"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Only students can access this endpoint")
    
    db = await connect()
    try:
        student = await db.fetchrow("""
            SELECT s.*, u.email, u.mobile
            FROM students s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.roll_no = $1
        """, current_user["username"])
        
        if not student:
            raise HTTPException(404, "Student record not found")
        
        return dict(student)
    
    finally:
        await db.close()

# ==================== BULK IMPORT STUDENTS ====================
@router.post("/bulk-import")
async def bulk_import_students(
    students_data: list[StudentCreate],
    current_user: dict = Depends(admin_required),
    request: Request = None
):
    """Bulk import students (Admin only)"""
    db = await connect()
    
    try:
        results = {
            "success": 0,
            "failed": 0,
            "errors": []
        }
        
        for idx, student_data in enumerate(students_data):
            try:
                # Validate class
                cls = await db.fetchrow(
                    "SELECT id FROM classes WHERE name=$1", student_data.class_name
                )
                if not cls:
                    results["errors"].append({
                        "row": idx + 1,
                        "roll_no": student_data.roll_no,
                        "error": "Class does not exist"
                    })
                    results["failed"] += 1
                    continue
                
                # Check duplicate
                existing = await db.fetchrow(
                    "SELECT id FROM students WHERE roll_no=$1", student_data.roll_no
                )
                if existing:
                    results["errors"].append({
                        "row": idx + 1,
                        "roll_no": student_data.roll_no,
                        "error": "Duplicate roll number"
                    })
                    results["failed"] += 1
                    continue
                
                # Generate QR
                unique_id, _ = generate_uuid_qr(student_data.roll_no)
                
                # Insert student
                await db.execute("""
                    INSERT INTO students 
                    (name, roll_no, class, father_name, mother_name, qr_uuid, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                """, student_data.name, student_data.roll_no, student_data.class_name,
                    student_data.father_name, student_data.mother_name, unique_id)
                
                results["success"] += 1
                
            except Exception as e:
                results["errors"].append({
                    "row": idx + 1,
                    "roll_no": student_data.roll_no,
                    "error": str(e)
                })
                results["failed"] += 1
        
        return results
    
    finally:
        await db.close()