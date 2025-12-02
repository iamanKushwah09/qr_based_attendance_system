# backend/app/database.py
import asyncpg
from app import config

# Database connection pool
pool = None

async def init_db():
    """Initialize database connection pool"""
    global pool
    pool = await asyncpg.create_pool(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASS,
        database=config.DB_NAME,
        min_size=5,
        max_size=20,
    )
    await create_tables()

async def close_db():
    """Close database connection pool"""
    global pool
    if pool:
        await pool.close()

async def get_db():
    """Get database connection from pool"""
    global pool
    if not pool:
        await init_db()
    async with pool.acquire() as conn:
        return conn

async def connect():
    """Legacy function for compatibility"""
    global pool
    if not pool:
        await init_db()
    return await pool.acquire()

async def create_tables():
    """Create all database tables with proper constraints"""
    conn = await pool.acquire()
    try:
        # Users table with enhanced fields
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE,
                mobile VARCHAR(15) UNIQUE,
                password_hash TEXT NOT NULL,
                role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'teacher', 'student')),
                assigned_class VARCHAR(50),
                is_active BOOLEAN DEFAULT TRUE,
                is_verified BOOLEAN DEFAULT FALSE,
                reset_token TEXT,
                reset_token_expires TIMESTAMP,
                otp VARCHAR(6),
                otp_expires TIMESTAMP,
                otp_attempts INT DEFAULT 0,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Classes table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                section VARCHAR(10),
                required_attendance_percentage DECIMAL(5,2) DEFAULT 75.00,
                academic_year VARCHAR(20),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Students table with enhanced fields
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY,
                user_id INT REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                roll_no VARCHAR(50) UNIQUE NOT NULL,
                class VARCHAR(50) NOT NULL,
                father_name VARCHAR(255),
                mother_name VARCHAR(255),
                date_of_birth DATE,
                address TEXT,
                qr_uuid TEXT UNIQUE NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (class) REFERENCES classes(name) ON UPDATE CASCADE
            );
        """)

        # Attendance table with proper indexing
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY,
                student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                student_name VARCHAR(255) NOT NULL,
                roll_no VARCHAR(50) NOT NULL,
                class_name VARCHAR(50) NOT NULL,
                date DATE NOT NULL,
                time TIME NOT NULL,
                marked_by INT REFERENCES users(id),
                location VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, date)
            );
        """)

        # Create indexes for better performance
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);
            CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);
            CREATE INDEX IF NOT EXISTS idx_attendance_class ON attendance(class_name);
            CREATE INDEX IF NOT EXISTS idx_students_class ON students(class);
            CREATE INDEX IF NOT EXISTS idx_students_roll ON students(roll_no);
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_users_mobile ON users(mobile);
        """)

        # Attendance summary table (for caching)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance_summary (
                id SERIAL PRIMARY KEY,
                student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                month INT NOT NULL,
                year INT NOT NULL,
                total_days INT DEFAULT 0,
                present_days INT DEFAULT 0,
                percentage DECIMAL(5,2) DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, month, year)
            );
        """)

        # Notifications table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id INT REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                type VARCHAR(50) NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Audit log table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                user_id INT REFERENCES users(id),
                action VARCHAR(100) NOT NULL,
                entity_type VARCHAR(50),
                entity_id INT,
                details TEXT,
                ip_address VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create default admin if not exists
        admin_exists = await conn.fetchrow(
            "SELECT id FROM users WHERE role='admin' LIMIT 1"
        )
        
        if not admin_exists:
            import hashlib
            default_password = hashlib.sha256("Admin@123".encode()).hexdigest()
            await conn.execute("""
                INSERT INTO users (username, email, password_hash, role, is_verified)
                VALUES ($1, $2, $3, $4, $5)
            """, "admin", "admin@school.com", default_password, "admin", True)

    finally:
        await pool.release(conn)