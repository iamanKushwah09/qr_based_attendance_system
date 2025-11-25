from fastapi import APIRouter, HTTPException, Depends, status, Body
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import hashlib
from datetime import datetime, timedelta
import secrets

from app.database import connect
from app.utils.jwt_handler import create_access_token
from app.models.login import LoginRequest
from app.models.register import RegisterRequest
from app import config

router = APIRouter(prefix="/auth", tags=["Auth"])

# Simple Bearer token scheme (Swagger me "Value" box ke liye)
bearer_scheme = HTTPBearer(auto_error=True)

# ---------- PASSWORD STRENGTH CHECK ----------
def validate_password_strength(password: str):
    """
    Strong password rules:
    - kam se kam 8 characters
    - letters + numbers dono hone chahiye
    - space allowed nahi
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long",
        )

    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)

    if not (has_letter and has_digit):
        raise HTTPException(
            status_code=400,
            detail="Password must contain both letters and numbers",
        )

    if " " in password:
        raise HTTPException(
            status_code=400,
            detail="Password must not contain spaces",
        )


# ---------- REGISTER (create admin/teacher/student user) ----------
@router.post("/register")
async def register(data: RegisterRequest):
    db = await connect()

    # check if username already exists
    existing = await db.fetchrow(
        "SELECT * FROM users WHERE username=$1", data.username
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="User already exists"
        )

    if data.role not in ("admin", "teacher", "student"):
        raise HTTPException(
            status_code=400, detail="Invalid role"
        )

    # strong password rule
    validate_password_strength(data.password)

    hashed = hashlib.sha256(data.password.encode()).hexdigest()

    await db.execute(
        """
        INSERT INTO users (username, password_hash, role)
        VALUES ($1, $2, $3)
        """,
        data.username,
        hashed,
        data.role,
    )

    return {"msg": "User registered successfully"}


# ---------- LOGIN ----------
@router.post("/login")
async def login(data: LoginRequest):
    db = await connect()
    hashed = hashlib.sha256(data.password.encode()).hexdigest()

    # generic message (user / pass dono ke liye same) -> security best practice
    invalid_exc = HTTPException(
        status_code=401,
        detail="Invalid username or password",
    )

    user = await db.fetchrow(
        "SELECT * FROM users WHERE username=$1 AND password_hash=$2",
        data.username,
        hashed,
    )

    if not user:
        raise invalid_exc

    token = create_access_token(
        {"sub": user["username"], "role": user["role"]}
    )
    return {"token": token}


# ---------- CURRENT USER & ROLE HELPERS ----------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    raw_token = credentials.credentials  # "Bearer <token>" me se sirf token part

    try:
        payload = jwt.decode(
            raw_token,
            config.SECRET_KEY,
            algorithms=[config.ALGORITHM],
        )
        username = payload.get("sub")

        if username is None:
            raise credentials_exception 

    except JWTError:
        raise credentials_exception

    db = await connect()
    user = await db.fetchrow(
        "SELECT username, role, assigned_class FROM users WHERE username=$1",
        username,
    )
    if not user:
        raise credentials_exception

    return {
        "username": user["username"],
        "role": user["role"],
        "assigned_class": user["assigned_class"],
    }

# async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    if token is None:
        raise credentials_exception

    try:
        payload = jwt.decode(
            token,
            config.SECRET_KEY,
            algorithms=[config.ALGORITHM],
        )
        username = payload.get("sub")

        if username is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # DB se latest role + assigned_class le aate hain
    db = await connect()
    user = await db.fetchrow(
        "SELECT username, role, assigned_class FROM users WHERE username=$1",
        username,
    )
    if not user:
        raise credentials_exception

    return {
        "username": user["username"],
        "role": user["role"],
        "assigned_class": user["assigned_class"],
    }


async def admin_required(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def staff_required(current_user: dict = Depends(get_current_user)):
    # staff = admin or teacher
    if current_user["role"] not in ("admin", "teacher"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher or admin access required",
        )
    return current_user


# ---------- CHANGE OWN PASSWORD (Admin + Teacher + Student) ----------
@router.post("/change-password")
async def change_own_password(
    old_password: str = Body(...),
    new_password: str = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Logged-in user (admin / teacher / student) apna password change karega.
    - old password verify hoga
    - new password strong hona chahiye
    """

    db = await connect()

    user = await db.fetchrow(
        "SELECT * FROM users WHERE username=$1",
        current_user["username"],
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_hash = hashlib.sha256(old_password.encode()).hexdigest()
    if old_hash != user["password_hash"]:
        raise HTTPException(status_code=400, detail="Old password is incorrect")

    # strong password check
    validate_password_strength(new_password)
    new_hash = hashlib.sha256(new_password.encode()).hexdigest()

    await db.execute(
        "UPDATE users SET password_hash=$1 WHERE username=$2",
        new_hash,
        current_user["username"],
    )

    return {"msg": "Password updated successfully"}


# ---------- ADMIN: RESET ANY USER PASSWORD ----------
@router.post("/admin-reset-password")
async def admin_reset_password(
    username: str = Body(...),
    new_password: str = Body(...),
    admin: dict = Depends(admin_required),
):
    """
    Sirf ADMIN:
    Kisi bhi user (admin/teacher/student) ka password reset kar sakta hai.
    """

    db = await connect()

    user = await db.fetchrow(
        "SELECT * FROM users WHERE username=$1",
        username,
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # strong password check
    validate_password_strength(new_password)
    hashed = hashlib.sha256(new_password.encode()).hexdigest()

    await db.execute(
        "UPDATE users SET password_hash=$1 WHERE username=$2",
        hashed,
        username,
    )

    return {"msg": f"Password reset successfully for user '{username}'"}


# ---------- FORGOT PASSWORD: REQUEST RESET TOKEN ----------
@router.post("/forgot-password/request")
async def forgot_password_request(username: str = Body(..., embed=True)):
    """
    Public endpoint:
    - User username dega (admin / teacher / student)
    - Agar user exist karta hai to reset_token + expiry set hoga
    - Response me bhi token bhej rahe hain (demo/test purpose)
      Production me ise email/SMS se bhejna chahiye.
    """

    db = await connect()

    user = await db.fetchrow(
        "SELECT username FROM users WHERE username=$1",
        username,
    )

    # Security ke liye: user exist ho ya na ho,
    # same message return karte hain (username guessing avoid)
    if not user:
        return {
            "msg": "If this username exists, a reset token has been generated."
        }

    # Random secure token generate
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=15)  # 15 minutes valid

    await db.execute(
        """
        UPDATE users
        SET reset_token=$1, reset_token_expires=$2
        WHERE username=$3
        """,
        token,
        expires_at,
        username,
    )

    # DEMO: token response me de rahe hain, taaki aap Swagger se test kar sako
    return {
        "msg": "Reset token generated. Use this token to reset your password (demo mode).",
        "username": username,
        "reset_token": token,
        "expires_at_utc": expires_at.isoformat(),
    }
# ---------- FORGOT PASSWORD: CONFIRM RESET ----------
@router.post("/forgot-password/confirm")
async def forgot_password_confirm(
    username: str = Body(...),
    reset_token: str = Body(...),
    new_password: str = Body(...),
):
    """
    Public endpoint:
    - username + reset_token + new_password
    - Token + expiry check hoga
    - Password strong hona chahiye
    """

    db = await connect()

    user = await db.fetchrow(
        """
        SELECT username, reset_token, reset_token_expires
        FROM users
        WHERE username=$1
        """,
        username,
    )

    if not user or not user["reset_token"]:
        raise HTTPException(status_code=400, detail="Invalid reset token or username")

    # Expiry check
    if not user["reset_token_expires"] or user["reset_token_expires"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset token has expired. Request a new one.")

    # Token match?
    if reset_token != user["reset_token"]:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    # Strong password rule
    validate_password_strength(new_password)
    new_hash = hashlib.sha256(new_password.encode()).hexdigest()

    # Update password + clear token
    await db.execute(
        """
        UPDATE users
        SET password_hash=$1,
            reset_token=NULL,
            reset_token_expires=NULL
        WHERE username=$2
        """,
        new_hash,
        username,
    )

    return {"msg": "Password has been reset successfully"}
