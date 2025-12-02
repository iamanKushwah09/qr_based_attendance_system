# backend/app/routers/classes.py
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, validator
from datetime import datetime
from decimal import Decimal

from app.database import connect
from app.routers.auth import admin_required, get_current_user, log_action
from app import config

router = APIRouter(prefix="/classes", tags=["Classes"])

class ClassCreate(BaseModel):
    name: str
    section: str | None = None
    academic_year: str | None = None
    required_attendance_percentage: float = config.DEFAULT_ATTENDANCE_PERCENTAGE
    
    @validator('required_attendance_percentage')
    def validate_percentage(cls, v):
        if not 0 <= v <= 100:
            raise ValueError('Percentage must be between 0 and 100')
        return v

class ClassUpdate(BaseModel):
    section: str | None = None
    academic_year: str | None = None
    required_attendance_percentage: float | None = None
    is_active: bool | None = None
    
    @validator('required_attendance_percentage')
    def validate_percentage(cls, v):
        if v is not None and not 0 <= v <= 100:
            raise ValueError('Percentage must be between 0 and 100')
        return v

# ==================== CREATE CLASS ====================
@router.post("/create", status_code=201)
async def create_class(
    data: ClassCreate,
    admin: dict = Depends(admin_required),
    request: Request = None
):
    """Admin: Create new class"""
    db = await connect()
    
    try:
        # Check duplicate
        existing = await db.fetchrow(
            "SELECT id FROM classes WHERE name=$1", data.name
        )
        if existing:
            raise HTTPException(400, "Class already exists")
        
        # Create class
        class_id = await db.fetchval("""
            INSERT INTO classes 
            (name, section, academic_year, required_attendance_percentage, is_active)
            VALUES ($1, $2, $3, $4, TRUE)
            RETURNING id
        """, data.name, data.section, data.academic_year, 
            data.required_attendance_percentage)
        
        # Log action
        await log_action(db, admin['id'], "CLASS_CREATED", "classes", class_id,
                        {"name": data.name},
                        request.client.host if request else None)
        
        return {
            "msg": "Class created successfully",
            "class_id": class_id,
            "name": data.name
        }
    
    finally:
        await db.close()

# ==================== LIST CLASSES ====================
@router.get("/list")
async def list_classes(
    is_active: bool | None = None,
    current_user: dict = Depends(get_current_user)
):
    """List all classes"""
    db = await connect()
    
    try:
        where_clause = ""
        params = []
        
        if is_active is not None:
            where_clause = "WHERE is_active=$1"
            params.append(is_active)
        
        query = f"""
            SELECT id, name, section, academic_year, 
                   required_attendance_percentage, is_active, created_at
            FROM classes
            {where_clause}
            ORDER BY name
        """
        
        classes = await db.fetch(query, *params)
        
        # Get student counts for each class
        classes_data = []
        for cls in classes:
            student_count = await db.fetchval("""
                SELECT COUNT(*) FROM students 
                WHERE class=$1 AND is_active=TRUE
            """, cls['name'])
            
            teacher_count = await db.fetchval("""
                SELECT COUNT(*) FROM users 
                WHERE assigned_class=$1 AND role='teacher' AND is_active=TRUE
            """, cls['name'])
            
            classes_data.append({
                **dict(cls),
                "student_count": student_count,
                "teacher_count": teacher_count
            })
        
        return classes_data
    
    finally:
        await db.close()

# ==================== GET CLASS ====================
@router.get("/{class_name}")
async def get_class(
    class_name: str,
    current_user: dict = Depends(get_current_user)
):
    """Get class details"""
    db = await connect()
    
    try:
        cls = await db.fetchrow("""
            SELECT * FROM classes WHERE name=$1
        """, class_name)
        
        if not cls:
            raise HTTPException(404, "Class not found")
        
        # Permission check for teacher
        if current_user["role"] == "teacher":
            if current_user["assigned_class"] != class_name:
                raise HTTPException(403, "Cannot view other classes")
        
        # Get counts
        student_count = await db.fetchval("""
            SELECT COUNT(*) FROM students 
            WHERE class=$1 AND is_active=TRUE
        """, class_name)
        
        teacher_count = await db.fetchval("""
            SELECT COUNT(*) FROM users 
            WHERE assigned_class=$1 AND role='teacher' AND is_active=TRUE
        """, class_name)
        
        return {
            **dict(cls),
            "student_count": student_count,
            "teacher_count": teacher_count
        }
    
    finally:
        await db.close()

# ==================== UPDATE CLASS ====================
@router.put("/update/{class_name}")
async def update_class(
    class_name: str,
    data: ClassUpdate,
    admin: dict = Depends(admin_required),
    request: Request = None
):
    """Admin: Update class details"""
    db = await connect()
    
    try:
        # Check exists
        cls = await db.fetchrow(
            "SELECT id FROM classes WHERE name=$1", class_name
        )
        if not cls:
            raise HTTPException(404, "Class not found")
        
        # Build update query
        updates = []
        params = []
        param_count = 0
        
        for field in ['section', 'academic_year', 'required_attendance_percentage', 'is_active']:
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
        
        # Add class_name for WHERE
        param_count += 1
        params.append(class_name)
        
        query = f"""
            UPDATE classes 
            SET {', '.join(updates)}
            WHERE name = ${param_count}
        """
        
        await db.execute(query, *params)
        
        # Log action
        await log_action(db, admin['id'], "CLASS_UPDATED", "classes", cls['id'],
                        {"name": class_name},
                        request.client.host if request else None)
        
        return {"msg": "Class updated successfully"}
    
    finally:
        await db.close()

# ==================== DELETE CLASS ====================
@router.delete("/delete/{class_name}")
async def delete_class(
    class_name: str,
    admin: dict = Depends(admin_required),
    request: Request = None
):
    """Admin: Delete class (soft delete)"""
    db = await connect()
    
    try:
        cls = await db.fetchrow(
            "SELECT id FROM classes WHERE name=$1", class_name
        )
        if not cls:
            raise HTTPException(404, "Class not found")
        
        # Check if students exist
        student_count = await db.fetchval("""
            SELECT COUNT(*) FROM students 
            WHERE class=$1 AND is_active=TRUE
        """, class_name)
        
        if student_count > 0:
            raise HTTPException(400, 
                f"Cannot delete class. {student_count} active students assigned to this class.")
        
        # Soft delete
        await db.execute("""
            UPDATE classes 
            SET is_active=FALSE, updated_at=$1
            WHERE name=$2
        """, datetime.utcnow(), class_name)
        
        # Log action
        await log_action(db, admin['id'], "CLASS_DELETED", "classes", cls['id'],
                        {"name": class_name},
                        request.client.host if request else None)
        
        return {"msg": "Class deleted successfully"}
    
    finally:
        await db.close()

# ==================== GET CLASS STATISTICS ====================
@router.get("/{class_name}/statistics")
async def get_class_statistics(
    class_name: str,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed statistics for a class"""
    db = await connect()
    
    try:
        # Permission check
        if current_user["role"] == "teacher":
            if current_user["assigned_class"] != class_name:
                raise HTTPException(403, "Cannot view other classes")
        elif current_user["role"] not in ("admin", "teacher"):
            raise HTTPException(403, "Access denied")
        
        # Get class info
        cls = await db.fetchrow(
            "SELECT * FROM classes WHERE name=$1", class_name
        )
        if not cls:
            raise HTTPException(404, "Class not found")
        
        # Total students
        total_students = await db.fetchval("""
            SELECT COUNT(*) FROM students 
            WHERE class=$1 AND is_active=TRUE
        """, class_name)
        
        # Today's attendance
        today_present = await db.fetchval("""
            SELECT COUNT(DISTINCT student_id)
            FROM attendance
            WHERE class_name=$1 AND date=CURRENT_DATE
        """, class_name)
        
        # Average attendance (last 30 days)
        from datetime import date, timedelta
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        working_days = await db.fetchval("""
            SELECT COUNT(DISTINCT date)
            FROM attendance
            WHERE class_name=$1 AND date BETWEEN $2 AND $3
        """, class_name, start_date, end_date)
        
        if working_days > 0:
            total_attendance = await db.fetchval("""
                SELECT COUNT(*)
                FROM attendance
                WHERE class_name=$1 AND date BETWEEN $2 AND $3
            """, class_name, start_date, end_date)
            
            avg_percentage = (total_attendance * 100.0 / (total_students * working_days)) if total_students > 0 else 0
        else:
            avg_percentage = 0
        
        return {
            "class_name": class_name,
            "section": cls['section'],
            "academic_year": cls['academic_year'],
            "required_percentage": float(cls['required_attendance_percentage']),
            "total_students": total_students,
            "today_present": today_present,
            "today_absent": total_students - today_present,
            "today_percentage": (today_present * 100.0 / total_students) if total_students > 0 else 0,
            "last_30_days": {
                "working_days": working_days,
                "average_percentage": round(avg_percentage, 2)
            }
        }
    
    finally:
        await db.close()