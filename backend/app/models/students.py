CREATE_STUDENTS_TABLE = """
CREATE TABLE IF NOT EXISTS students (
    id SERIAL PRIMARY KEY,
    name TEXT,
    roll_no TEXT,
    class TEXT,
    qr_uuid TEXT UNIQUE
);
"""
