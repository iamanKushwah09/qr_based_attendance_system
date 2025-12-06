# backend/app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "claude_qr")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "1234")

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

# OTP & Password Reset Configuration
OTP_EXPIRE_MINUTES = 10
RESET_TOKEN_EXPIRE_MINUTES = 15
MAX_OTP_ATTEMPTS = 3

# Email Configuration (SMTP - Free Gmail)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")  # Your Gmail
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # App Password
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "QR Attendance System")

# Attendance Configuration
DEFAULT_ATTENDANCE_PERCENTAGE = 75.0
QR_CODE_FOLDER = "QR/qrcodes"
UPLOAD_FOLDER = "uploads"

# Security
BCRYPT_ROUNDS = 12
PASSWORD_MIN_LENGTH = 8

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100