# backend/app/main.py
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import time

from app.routers import auth, students, attendance, classes, teachers
from app.database import init_db, close_db

# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting QR Attendance System...")
    await init_db()
    print("✅ Database initialized successfully")
    yield
    # Shutdown
    print("🛑 Shutting down...")
    await close_db()
    print("✅ Cleanup complete")

# Create FastAPI app
app = FastAPI(
    title="QR Attendance System API",
    description="Industry-level attendance management system with QR code scanning",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "https://yourdomain.com"  # Add your production domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "message": "Validation error"
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "message": "Internal server error",
            "detail": str(exc) if app.debug else "An error occurred"
        }
    )

# Include routers
app.include_router(auth.router)
app.include_router(teachers.router)
app.include_router(students.router)
app.include_router(attendance.router)
app.include_router(classes.router)

# Health check endpoint
@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "QR Attendance System API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/api/docs"
    }

@app.get("/api/health", tags=["Health"])
async def health_check():
    from app.database import pool
    
    try:
        if pool:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_status = "healthy"
        else:
            db_status = "disconnected"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "timestamp": time.time()
    }

# API Information
@app.get("/api/info", tags=["Information"])
async def api_info():
    return {
        "name": "QR Attendance System",
        "version": "2.0.0",
        "features": [
            "Multi-user authentication (Admin, Teacher, Student)",
            "QR code-based attendance marking",
            "Role-based access control",
            "Attendance reports and analytics",
            "Email notifications (OTP, alerts)",
            "Audit logging",
            "Password reset via email OTP",
            "Attendance percentage tracking",
            "Low attendance alerts"
        ],
        "endpoints": {
            "authentication": "/api/auth",
            "teachers": "/api/teachers",
            "students": "/api/students",
            "attendance": "/api/attendance",
            "classes": "/api/classes"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )