
# 🎓 QR-Based Attendance System

A Full-Stack Attendance System using **FastAPI** for the backend and plain **HTML/CSS/JS** for the frontend.
This repository contains an attendance system built around QR codes and JWT-based authentication with role-based access:
**Admin**, **Teacher**, and **Student**.

Repository: https://github.com/iamanKushwah09/qr_based_attendance_system.git

---

## 🔑 Features

- JWT-based authentication and role management (Admin / Teacher / Student)
- QR code generation for students (one per student)
- Role-based permissions:
  - **Admin**: Full CRUD for classes, teachers, students. Reset passwords.
  - **Teacher**: Manage students for their assigned class only; mark attendance.
  - **Student**: View own profile and QR; view own attendance; change password.
- Password-strength validation
- Change password (self) and Admin-reset password
- Forgot-password flow (token-based) with secure expiry
- APIs to preview and download QR codes (base64, HTML gallery)
- Frontend: simple role-specific dashboards (HTML/CSS/JS) that call the backend APIs
- PostgreSQL (asyncpg) used as the primary datastore

---

## 📁 Project structure (recommended)

```
backend/
  app/
    main.py
    database.py
    config.py
    models/
      login.py
      register.py
    routers/
      auth.py
      students.py
      teachers.py
      classes.py
      attendance.py
    utils/
      qr_generator.py
      jwt_handler.py
frontend/
  index.html
  admin.html
  teacher.html
  student.html
  styles.css
  app.js
  qrcodes/         # generated QR images (frontend/qrcodes/*.png)
README.md
requirements.txt
```

---

## 🚀 Quick setup (local)

### 1. Clone
```bash
git clone https://github.com/iamanKushwah09/qr_based_attendance_system.git
cd qr_based_attendance_system
```

### 2. Backend env
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

**Recommended `requirements.txt`**
```
fastapi
uvicorn
asyncpg
python-jose[cryptography]
qrcode
Pillow
```

### 3. PostgreSQL
Create database (example names):

```sql
CREATE DATABASE attendance_db;
CREATE USER attendance_user WITH PASSWORD 'strongpassword';
GRANT ALL PRIVILEGES ON DATABASE attendance_db TO attendance_user;
```

Update `app/config.py` with DB credentials (or use environment variables).

### 4. Create tables (run once)
Example SQL (run in psql or a DB client):

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL,
    assigned_class VARCHAR(50),
    reset_token TEXT,
    reset_token_expires TIMESTAMPTZ
);

CREATE TABLE classes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    roll_no VARCHAR(50) UNIQUE NOT NULL,
    class VARCHAR(50) NOT NULL,
    qr_uuid VARCHAR(200) NOT NULL
);

CREATE TABLE attendance (
    id SERIAL PRIMARY KEY,
    student_roll VARCHAR(50) NOT NULL,
    date DATE NOT NULL,
    time TIME NOT NULL,
    status VARCHAR(10) NOT NULL
);
```

### 5. Run backend
```bash
uvicorn app.main:app --reload
```

Open Swagger UI: http://127.0.0.1:8000/docs

### 6. Serve frontend (optional)
You can serve the `frontend` folder using Python http.server for local testing:

```bash
cd frontend
python -m http.server 5500
# Open http://localhost:5500/index.html
```

---

## 🔧 Important API endpoints

### Auth
- `POST /auth/register` — register new user (admin/teacher/student)
- `POST /auth/login` — login, returns JWT token
- `POST /auth/change-password` — logged-in user changes password
- `POST /auth/admin-reset-password` — admin resets any user's password
- `POST /auth/forgot-password/request` — request reset token (demo: returns token)
- `POST /auth/forgot-password/confirm` — confirm reset using token

### Students
- `POST /students/add` — add student (admin or teacher). Teacher restricted to own class.
- `GET /students/list` — list students (role-based)
- `GET /students/me` — logged-in student profile
- `GET /students/all-qr-preview` — admin HTML gallery (open in new tab)
- `GET /students/all-qr-base64` — admin: base64 list (Swagger preview)
- `GET /students/my-qr-base64` — student: own QR base64
- `GET /students/class-qr-base64` — teacher: class QR base64

### Attendance
- `GET /attendance/mark/{uuid}` — mark attendance by scanning QR uuid
- `GET /attendance/list` — list attendance (with optional filters)
- `GET /attendance/me` — student: view own attendance

---

## 🔐 Security notes & best practices

- **Never** return reset tokens in production responses. Use email/SMS to deliver tokens/OTP.
- Use HTTPS in production.
- Store `SECRET_KEY` and DB credentials in environment variables.
- Rotate JWT secret periodically and set reasonable token expiry.
- Consider rate-limiting forgot-password requests to avoid abuse.

---

## 📦 Deployment pointers

- Use services like **Render**, **Railway**, **Heroku**, or **DigitalOcean App Platform**.
- Use DB managed services (Heroku Postgres, Railway Postgres, AWS RDS).
- Serve static frontend from S3/CloudFront or Netlify/Vercel and point to backend API.

---

## 🗒️ Next improvements (suggestions)

- Implement email/SMS gateway for token delivery
- Add audit logs for admin actions
- Add UI for teacher to scan QR via camera (client-side JS)
- Export attendance to CSV/PDF
- Add unit tests and CI pipeline

---

## ❤️ Credits
Built by **Aman Kushwah** with ChatGPT assistance.

---

