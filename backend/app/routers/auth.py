# backend/app/routers/auth.py
from fastapi import APIRouter, HTTPException, Depends, status, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import hashlib
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr, validator
import re

from app.database import connect
from app.utils.jwt_handler import create_access_token, create_refresh_token
from app.utils.email_service import EmailService
from app import config

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer(auto_error=True)

# Pydantic Models
class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    mobile: str | None = None
    password: str
    role: str = "admin"
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username can only contain letters, numbers, and underscores')
        return v
    
    @validator('mobile')
    def validate_mobile(cls, v):
        if v and not re.match(r'^\+?[0-9]{10,15}$', v):
            raise ValueError('Invalid mobile number format')
        return v
    
    @validator('role')
    def validate_role(cls, v):
        if v not in ('admin', 'teacher', 'student'):
            raise ValueError('Invalid role')
        return v

class LoginRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

# Password validation
def validate_password_strength(password: str):
    """Strong password validation"""
    if len(password) < config.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {config.PASSWORD_MIN_LENGTH} characters long"
        )
    
    if not re.search(r'[A-Z]', password):
        raise HTTPException(400, "Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        raise HTTPException(400, "Password must contain at least one lowercase letter")
    
    if not re.search(r'[0-9]', password):
        raise HTTPException(400, "Password must contain at least one number")
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise HTTPException(400, "Password must contain at least one special character")
    
    if " " in password:
        raise HTTPException(400, "Password must not contain spaces")

# Audit logging
async def log_action(db, user_id: int, action: str, entity_type: str = None, 
                     entity_id: int = None, details: dict = None, ip: str = None):
    """Log user actions for audit trail"""
    await db.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
        VALUES ($1, $2, $3, $4, $5, $6)
    """, user_id, action, entity_type, entity_id, details, ip)

# ==================== REGISTRATION ====================
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, request: Request):
    """Register new user (admin/teacher/student)"""
    db = await connect()
    
    try:
        # Check existing username
        existing = await db.fetchrow("SELECT id FROM users WHERE username=$1", data.username)
        if existing:
            raise HTTPException(400, "Username already exists")
        
        # Check existing email
        if data.email:
            existing_email = await db.fetchrow("SELECT id FROM users WHERE email=$1", data.email)
            if existing_email:
                raise HTTPException(400, "Email already registered")
        
        # Check existing mobile
        if data.mobile:
            existing_mobile = await db.fetchrow("SELECT id FROM users WHERE mobile=$1", data.mobile)
            if existing_mobile:
                raise HTTPException(400, "Mobile number already registered")
        
        # Validate password
        validate_password_strength(data.password)
        
        # Hash password
        hashed = hashlib.sha256(data.password.encode()).hexdigest()
        
        # Insert user
        user_id = await db.fetchval("""
            INSERT INTO users (username, email, mobile, password_hash, role, is_verified)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """, data.username, data.email, data.mobile, hashed, data.role, True)
        
        # Log action
        await log_action(db, user_id, "USER_REGISTERED", "users", user_id, 
                        {"role": data.role}, request.client.host)
        
        # Send welcome email
        if data.email:
            await EmailService.send_welcome_email(data.email, data.username, data.role)
        
        return {
            "msg": "User registered successfully",
            "user_id": user_id,
            "username": data.username,
            "role": data.role
        }
    
    finally:
        await db.close()

# ==================== LOGIN ====================
@router.post("/login")
async def login(data: LoginRequest, request: Request):
    """User login with JWT token"""
    db = await connect()
    
    try:
        hashed = hashlib.sha256(data.password.encode()).hexdigest()
        
        user = await db.fetchrow("""
            SELECT id, username, email, role, assigned_class, is_active, is_verified
            FROM users 
            WHERE username=$1 AND password_hash=$2
        """, data.username, hashed)
        
        if not user:
            raise HTTPException(401, "Invalid username or password")
        
        if not user['is_active']:
            raise HTTPException(403, "Account is deactivated. Contact administrator.")
        
        # Update last login
        await db.execute("UPDATE users SET last_login=$1 WHERE id=$2", 
                        datetime.utcnow(), user['id'])
        
        # Create tokens
        access_token = create_access_token({
            "sub": user["username"],
            "role": user["role"],
            "user_id": user["id"]
        })
        
        refresh_token = create_refresh_token({
            "sub": user["username"]
        })
        
        # Log action
        await log_action(db, user['id'], "USER_LOGIN", "users", user['id'], 
                        None, request.client.host)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user['id'],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"],
                "assigned_class": user["assigned_class"]
            }
        }
    
    finally:
        await db.close()

# ==================== GET CURRENT USER ====================
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            credentials.credentials,
            config.SECRET_KEY,
            algorithms=[config.ALGORITHM]
        )
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    db = await connect()
    try:
        user = await db.fetchrow("""
            SELECT id, username, email, mobile, role, assigned_class, is_active
            FROM users WHERE username=$1
        """, username)
        
        if not user:
            raise credentials_exception
        
        if not user['is_active']:
            raise HTTPException(403, "Account is deactivated")
        
        return dict(user)
    finally:
        await db.close()

# Role-based dependencies
async def admin_required(current_user: dict = Depends(get_current_user)):
    """Admin role required"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user

async def staff_required(current_user: dict = Depends(get_current_user)):
    """Admin or Teacher role required"""
    if current_user["role"] not in ("admin", "teacher"):
        raise HTTPException(403, "Staff access required")
    return current_user

# ==================== CHANGE PASSWORD ====================
@router.post("/change-password")
async def change_password(
    request: Request,
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    
):
    """Change own password"""
    db = await connect()
    
    try:
        # Verify old password
        old_hash = hashlib.sha256(data.old_password.encode()).hexdigest()
        user = await db.fetchrow(
            "SELECT id FROM users WHERE username=$1 AND password_hash=$2",
            current_user["username"], old_hash
        )
        
        if not user:
            raise HTTPException(400, "Current password is incorrect")
        
        # Validate new password
        validate_password_strength(data.new_password)
        
        # Update password
        new_hash = hashlib.sha256(data.new_password.encode()).hexdigest()
        await db.execute(
            "UPDATE users SET password_hash=$1, updated_at=$2 WHERE username=$3",
            new_hash, datetime.utcnow(), current_user["username"]
        )
        
        # Log action
        await log_action(db, current_user['id'], "PASSWORD_CHANGED", "users", 
                        current_user['id'], None, request.client.host)
        
        return {"msg": "Password changed successfully"}
    
    finally:
        await db.close()

# ==================== FORGOT PASSWORD - REQUEST OTP ====================
@router.post("/forgot-password/request")
async def forgot_password_request(data: ForgotPasswordRequest):
    """Request OTP for password reset"""
    db = await connect()
    
    try:
        user = await db.fetchrow(
            "SELECT id, username, email, otp_attempts FROM users WHERE email=$1",
            data.email
        )
        
        if not user:
            # Don't reveal if email exists
            return {"msg": "If email exists, OTP has been sent"}
        
        # Check OTP attempts
        if user['otp_attempts'] >= config.MAX_OTP_ATTEMPTS:
            raise HTTPException(429, "Maximum OTP attempts reached. Try again after 1 hour.")
        
        # Generate OTP
        otp = EmailService.generate_otp()
        otp_expires = datetime.utcnow() + timedelta(minutes=config.OTP_EXPIRE_MINUTES)
        
        # Save OTP
        await db.execute("""
            UPDATE users 
            SET otp=$1, otp_expires=$2, otp_attempts=otp_attempts+1, updated_at=$3
            WHERE email=$4
        """, otp, otp_expires, datetime.utcnow(), data.email)
        
        # Send OTP email
        email_sent = await EmailService.send_otp_email(data.email, otp, user['username'])
        
        if not email_sent:
            raise HTTPException(500, "Failed to send OTP email. Please try again.")
        
        return {
            "msg": "OTP sent to your email",
            "expires_in_minutes": config.OTP_EXPIRE_MINUTES
        }
    
    finally:
        await db.close()

# ==================== VERIFY OTP ====================
@router.post("/forgot-password/verify-otp")
async def verify_otp(data: VerifyOTPRequest):
    """Verify OTP before password reset"""
    db = await connect()
    
    try:
        user = await db.fetchrow("""
            SELECT id, username, otp, otp_expires
            FROM users WHERE email=$1
        """, data.email)
        
        if not user or not user['otp']:
            raise HTTPException(400, "Invalid OTP or email")
        
        # Check expiry
        if user['otp_expires'] < datetime.utcnow():
            raise HTTPException(400, "OTP has expired. Request a new one.")
        
        # Verify OTP
        if user['otp'] != data.otp:
            raise HTTPException(400, "Invalid OTP")
        
        return {"msg": "OTP verified successfully. You can now reset password."}
    
    finally:
        await db.close()

# ==================== RESET PASSWORD ====================
@router.post("/forgot-password/reset")
async def reset_password(data: ResetPasswordRequest, request: Request):
    """Reset password using OTP"""
    db = await connect()
    
    try:
        user = await db.fetchrow("""
            SELECT id, username, otp, otp_expires
            FROM users WHERE email=$1
        """, data.email)
        
        if not user or not user['otp']:
            raise HTTPException(400, "Invalid request")
        
        # Check expiry
        if user['otp_expires'] < datetime.utcnow():
            raise HTTPException(400, "OTP has expired")
        
        # Verify OTP
        if user['otp'] != data.otp:
            raise HTTPException(400, "Invalid OTP")
        
        # Validate new password
        validate_password_strength(data.new_password)
        
        # Update password and clear OTP
        new_hash = hashlib.sha256(data.new_password.encode()).hexdigest()
        await db.execute("""
            UPDATE users 
            SET password_hash=$1, otp=NULL, otp_expires=NULL, otp_attempts=0, updated_at=$2
            WHERE email=$3
        """, new_hash, datetime.utcnow(), data.email)
        
        # Log action
        await log_action(db, user['id'], "PASSWORD_RESET", "users", user['id'], 
                        None, request.client.host)
        
        return {"msg": "Password reset successfully"}
    
    finally:
        await db.close()

# ==================== ADMIN: RESET USER PASSWORD ====================
@router.post("/admin/reset-password")
async def admin_reset_password(
    username: str = Body(...),
    new_password: str = Body(...),
    admin: dict = Depends(admin_required),
    request: Request = None
):
    """Admin: Reset any user's password"""
    db = await connect()
    
    try:
        user = await db.fetchrow("SELECT id, email FROM users WHERE username=$1", username)
        if not user:
            raise HTTPException(404, "User not found")
        
        # Validate password
        validate_password_strength(new_password)
        
        # Update password
        new_hash = hashlib.sha256(new_password.encode()).hexdigest()
        await db.execute(
            "UPDATE users SET password_hash=$1, updated_at=$2 WHERE username=$3",
            new_hash, datetime.utcnow(), username
        )
        
        # Log action
        await log_action(db, admin['id'], "ADMIN_PASSWORD_RESET", "users", 
                        user['id'], {"target_user": username}, 
                        request.client.host if request else None)
        
        return {"msg": f"Password reset for user '{username}'"}
    
    finally:
        await db.close()

# ==================== REFRESH TOKEN ====================
@router.post("/refresh")
async def refresh_token(refresh_token: str = Body(..., embed=True)):
    """Get new access token using refresh token"""
    try:
        payload = jwt.decode(
            refresh_token,
            config.SECRET_KEY,
            algorithms=[config.ALGORITHM]
        )
        username = payload.get("sub")
        
        if username is None:
            raise HTTPException(401, "Invalid refresh token")
        
        db = await connect()
        try:
            user = await db.fetchrow("""
                SELECT id, username, role FROM users WHERE username=$1 AND is_active=TRUE
            """, username)
            
            if not user:
                raise HTTPException(401, "User not found or inactive")
            
            # Create new access token
            new_access_token = create_access_token({
                "sub": user["username"],
                "role": user["role"],
                "user_id": user["id"]
            })
            
            return {
                "access_token": new_access_token,
                "token_type": "bearer"
            }
        finally:
            await db.close()
            
    except JWTError:
        raise HTTPException(401, "Invalid refresh token")

# ==================== LOGOUT ====================
@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
    request: Request = None
):
    """Logout user (client should delete token)"""
    db = await connect()
    try:
        await log_action(db, current_user['id'], "USER_LOGOUT", "users", 
                        current_user['id'], None, 
                        request.client.host if request else None)
        return {"msg": "Logged out successfully"}
    finally:
        await db.close()