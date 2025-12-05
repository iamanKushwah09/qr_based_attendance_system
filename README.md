# 🎓 QR Attendance System - Industry-Level

**Production-ready attendance management system with QR code scanning, multi-user authentication, and comprehensive reporting.**

---

## 🌟 Features

### Core Features
- ✅ **Multi-User System**: Admin, Teacher, and Student roles with proper access control
- 🔐 **Strong Authentication**: JWT-based auth with password strength validation
- 📧 **Email Integration**: OTP-based password reset via SMTP (Free Gmail)
- 📱 **QR Code Scanning**: Unique QR codes for each student
- 📊 **Comprehensive Reports**: Daily, weekly, monthly, and custom date range reports
- 🔔 **Automated Alerts**: Low attendance email notifications
- 📈 **Attendance Analytics**: Percentage tracking, summaries, and statistics
- 🔍 **Audit Logging**: Complete action tracking for security
- 💾 **Pagination**: Efficient data retrieval for large datasets
- 🗃️ **Data Export**: Bulk import/export capabilities

### Security Features
- Password hashing with SHA-256
- JWT tokens with expiration
- Role-based access control (RBAC)
- OTP verification for password reset
- Rate limiting on sensitive operations
- Audit trail for all critical actions

---

## 🏗️ Architecture

```
qr-attendance-system/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application
│   │   ├── config.py               # Configuration
│   │   ├── database.py             # Database connection
│   │   ├── models/                 # Pydantic models
│   │   ├── routers/                # API endpoints
│   │   │   ├── auth.py            # Authentication
│   │   │   ├── students.py        # Student management
│   │   │   ├── teachers.py        # Teacher management
│   │   │   ├── classes.py         # Class management
│   │   │   └── attendance.py      # Attendance tracking
│   │   └── utils/                  # Utilities
│   │       ├── jwt_handler.py     # JWT operations
│   │       ├── email_service.py   # Email sender
│   │       └── qr_generator.py    # QR code generation
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env
├── QR/qrcodes/                     # Generated QR codes
├── docker-compose.yml
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Gmail account (for email features)

### Option 1: Local Setup

```bash
# 1. Clone repository
git clone <repository-url>
cd qr-attendance-system

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
cd backend
pip install -r requirements.txt

# 4. Setup PostgreSQL database
createdb claude_db

# 5. Configure environment
cp .env.example .env
# Edit .env with your settings

# 6. Run application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 2: Docker Setup

```bash
# 1. Clone repository
git clone <repository-url>
cd qr-attendance-system

# 2. Configure environment
cp backend/.env.example backend/.env
# Edit .env with your settings

# 3. Start services
docker-compose up -d

# 4. Check health
curl http://localhost:8000/api/health
```

---

## 📧 Email Setup (Gmail - Free)

### Get Gmail App Password:

1. Go to [Google Account Settings](https://myaccount.google.com/)
2. **Security** → Enable **2-Step Verification**
3. **Security** → **App Passwords**
4. Generate app password for "Mail"
5. Copy the 16-character password

### Update .env file:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
```

---

## 👥 User Roles & Workflow

### 1. Admin (Super User)
**Default Credentials:**
- Username: `admin`
- Password: `Admin@123` (⚠️ Change immediately!)

**Capabilities:**
- Create/manage teachers and assign classes
- Create/manage classes with attendance requirements
- View all students, teachers, and attendance records
- Access comprehensive reports
- Reset any user's password
- View audit logs
- Bulk import students

### 2. Teacher
**Created by:** Admin

**Capabilities:**
- Add/update/delete students in assigned class only
- Mark attendance for assigned class
- View attendance reports for assigned class
- View absent student lists
- Generate class-wise reports
- Change own password

### 3. Student
**Created by:** Teacher or Admin

**Capabilities:**
- View own profile
- View own attendance records
- View attendance percentage
- See attendance statistics (weekly/monthly/yearly)
- Change own password

---

## 📋 API Endpoints

### Authentication (`/api/auth`)
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/register` | Register new user | Public |
| POST | `/login` | User login | Public |
| POST | `/refresh` | Refresh access token | Authenticated |
| POST | `/change-password` | Change own password | Authenticated |
| POST | `/forgot-password/request` | Request OTP | Public |
| POST | `/forgot-password/verify-otp` | Verify OTP | Public |
| POST | `/forgot-password/reset` | Reset password | Public |
| POST | `/admin/reset-password` | Admin reset password | Admin |
| POST | `/logout` | Logout | Authenticated |

### Teachers (`/api/teachers`)
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/create` | Create teacher | Admin |
| GET | `/list` | List all teachers | Admin |
| GET | `/{username}` | Get teacher details | Admin |
| PUT | `/update/{username}` | Update teacher | Admin |
| DELETE | `/delete/{username}` | Delete teacher | Admin |
| GET | `/me/profile` | Get own profile | Teacher |
| GET | `/me/students` | Get assigned students | Teacher |

### Students (`/api/students`)
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/add` | Add student | Admin/Teacher |
| GET | `/list` | List students | All (filtered by role) |
| GET | `/{student_id}` | Get student details | All (filtered by role) |
| PUT | `/update/{student_id}` | Update student | Admin/Teacher |
| DELETE | `/delete/{student_id}` | Delete student | Admin/Teacher |
| GET | `/me/profile` | Get own profile | Student |
| POST | `/bulk-import` | Bulk import students | Admin |

### Classes (`/api/classes`)
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/create` | Create class | Admin |
| GET | `/list` | List all classes | All |
| GET | `/{class_name}` | Get class details | All (filtered by role) |
| PUT | `/update/{class_name}` | Update class | Admin |
| DELETE | `/delete/{class_name}` | Delete class | Admin |
| GET | `/{class_name}/statistics` | Class statistics | Admin/Teacher |

### Attendance (`/api/attendance`)
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/mark/{uuid}` | Mark attendance via QR | Admin/Teacher |
| GET | `/list` | List attendance records | All (filtered by role) |
| GET | `/me` | Student's own attendance | Student |
| DELETE | `/delete/{id}` | Delete record | Admin |
| GET | `/report/daily-summary` | Daily class summary | Admin/Teacher |
| GET | `/absent/{class_name}` | Absent students list | Admin/Teacher |
| GET | `/report/student-percentage/{roll_no}` | Student percentage | All (filtered by role) |
| GET | `/report/class-percentage/{class_name}` | Class percentage | Admin/Teacher |

---

## 🔄 Complete Workflow Example

### Step 1: Admin Setup

```bash
# Login as admin
POST /api/auth/login
{
  "username": "admin",
  "password": "Admin@123"
}

# Change admin password
POST /api/auth/change-password
{
  "old_password": "Admin@123",
  "new_password": "NewSecure@Pass123"
}

# Create classes
POST /api/classes/create
{
  "name": "10-A",
  "section": "A",
  "academic_year": "2024-2025",
  "required_attendance_percentage": 75
}
```

### Step 2: Create Teachers

```bash
# Create teacher
POST /api/teachers/create
{
  "username": "teacher1",
  "email": "teacher1@school.com",
  "mobile": "+911234567890",
  "password": "Teacher@123",
  "name": "John Doe",
  "assigned_class": "10-A"
}
```

### Step 3: Teacher Creates Students

```bash
# Teacher login
POST /api/auth/login
{
  "username": "teacher1",
  "password": "Teacher@123"
}

# Add student with login credentials
POST /api/students/add
{
  "name": "Alice Smith",
  "roll_no": "10A001",
  "class_name": "10-A",
  "father_name": "Robert Smith",
  "email": "alice@example.com",
  "mobile": "+919876543210",
  "create_login": true,
  "password": "Student@123"
}

# Response includes QR code path
{
  "msg": "Student added successfully",
  "student_id": 1,
  "roll_no": "10A001",
  "qr_uuid": "a1b2c3d4-...",
  "qr_path": "/path/to/QR/qrcodes/10A001.png",
  "login_created": true
}
```

### Step 4: Mark Attendance

```bash
# Scan QR code and mark attendance
GET /api/attendance/mark/{qr_uuid}

# Response
{
  "msg": "Attendance marked successfully",
  "student": {
    "name": "Alice Smith",
    "roll_no": "10A001",
    "class": "10-A"
  },
  "marked_at": "2024-12-01 09:30:00"
}
```

### Step 5: View Reports

```bash
# Student views own attendance
GET /api/attendance/me?period=month

# Teacher views class report
GET /api/attendance/report/class-percentage/10-A?start_date=2024-11-01&end_date=2024-11-30

# Admin views all classes
GET /api/classes/list
```

---

## 🔒 Password Requirements

All passwords must meet these criteria:
- Minimum 8 characters
- At least 1 uppercase letter (A-Z)
- At least 1 lowercase letter (a-z)
- At least 1 number (0-9)
- At least 1 special character (!@#$%^&*(),.?":{}|<>)
- No spaces allowed

**Examples:**
- ✅ `Admin@123`
- ✅ `MyPass@2024`
- ❌ `password` (no uppercase, number, or special char)
- ❌ `Admin123` (no special character)

---

## 📊 Database Schema

### Tables

1. **users** - All user accounts (admin/teacher/student)
2. **students** - Student details with QR UUID
3. **classes** - Class information with attendance requirements
4. **attendance** - Daily attendance records
5. **attendance_summary** - Monthly attendance cache
6. **notifications** - User notifications
7. **audit_logs** - Action tracking

---

## 🛡️ Security Best Practices

1. **Change default admin password immediately**
2. **Use environment variables for secrets**
3. **Enable HTTPS in production**
4. **Regular database backups**
5. **Monitor audit logs**
6. **Implement rate limiting**
7. **Keep dependencies updated**
8. **Use strong JWT secret key (min 32 characters)**

---

## 📱 Mobile App Integration

The API supports mobile app integration:

```javascript
// Example: React Native / Flutter
const response = await fetch('http://your-server:8000/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'user',
    password: 'pass'
  })
});

const { access_token } = await response.json();

// Use token for authenticated requests
fetch('http://your-server:8000/api/students/list', {
  headers: { 'Authorization': `Bearer ${access_token}` }
});
```

---

## 🐛 Troubleshooting

### Database Connection Failed
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection
psql -U postgres -d ttendance_db
```

### Email Not Sending
1. Verify Gmail App Password is correct
2. Check 2-Step Verification is enabled
3. Test SMTP connection:
```python
python -c "import smtplib; smtplib.SMTP('smtp.gmail.com', 587).starttls()"
```

### QR Codes Not Generating
```bash
# Check QR directory exists and is writable
mkdir -p QR/qrcodes
chmod 755 QR/qrcodes
```

---

## 📈 Performance Optimization

- Database indexes on frequently queried columns
- Connection pooling (asyncpg)
- Pagination for large datasets
- Caching with attendance_summary table
- Efficient SQL queries with proper JOINs

---

## 🔄 Backup & Restore

### Backup Database
```bash
pg_dump -U postgres dance_db > backup_$(date +%Y%m%d).sql
```

### Restore Database
```bash
psql -U postgres claude_db < backup_20241201.sql
```

---

## 📝 API Documentation

Once running, access:
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

---

## 📄 License

This project is licensed under the MIT License.

---

## 💬 Support

For issues and questions:
- Open an issue on GitHub
- Email: support@example.com

---

## 🎯 Roadmap

- [ ] SMS notifications (Twilio integration)
- [ ] Face recognition attendance
- [ ] Mobile apps (iOS/Android)
- [ ] Biometric integration
- [ ] Parent portal
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Excel/PDF export

---

**Built with ❤️ for educational institutions**