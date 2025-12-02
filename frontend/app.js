// app.js - Modern QR Attendance System Frontend

// Configuration
const API_URL = 'http://localhost:8000/docs';
let authToken = null;
let currentUser = null;
let html5QrCode = null;

// Utility Functions
const showLoading = () => {
    document.getElementById('loadingScreen').classList.remove('hidden');
};

const hideLoading = () => {
    document.getElementById('loadingScreen').classList.add('hidden');
};

const showAlert = (message, type = 'success') => {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert ${type}`;
    alertDiv.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    const container = document.querySelector('.main-content') || document.body;
    container.insertBefore(alertDiv, container.firstChild);
    
    setTimeout(() => alertDiv.remove(), 5000);
};

const apiRequest = async (endpoint, options = {}) => {
    const headers = {
        'Content-Type': 'application/json',
        ...(authToken && { 'Authorization': `Bearer ${authToken}` })
    };

    try {
        const response = await fetch(`${API_URL}${endpoint}`, {
            ...options,
            headers: { ...headers, ...options.headers }
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || data.message || 'Request failed');
        }

        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
};

// Authentication
const login = async (username, password) => {
    try {
        showLoading();
        const data = await apiRequest('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });

        authToken = data.access_token;
        currentUser = data.user;
        localStorage.setItem('authToken', authToken);
        localStorage.setItem('currentUser', JSON.stringify(currentUser));

        showDashboard();
        showAlert('Login successful! Welcome back.', 'success');
    } catch (error) {
        showAlert(error.message, 'error');
    } finally {
        hideLoading();
    }
};

const logout = () => {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('authToken');
    localStorage.removeItem('currentUser');
    
    document.getElementById('loginPage').style.display = 'flex';
    document.getElementById('dashboard').classList.remove('active');
    showAlert('Logged out successfully', 'success');
};

const checkAuth = () => {
    const token = localStorage.getItem('authToken');
    const user = localStorage.getItem('currentUser');

    if (token && user) {
        authToken = token;
        currentUser = JSON.parse(user);
        showDashboard();
    } else {
        hideLoading();
    }
};

// Dashboard Setup
const showDashboard = () => {
    document.getElementById('loginPage').style.display = 'none';
    document.getElementById('dashboard').classList.add('active');
    
    setupUserInfo();
    setupNavigation();
    loadDashboardData();
    hideLoading();
};

const setupUserInfo = () => {
    const userAvatar = document.getElementById('userAvatar');
    const userName = document.getElementById('userName');
    const userRole = document.getElementById('userRole');

    userAvatar.textContent = currentUser.username[0].toUpperCase();
    userName.textContent = currentUser.username;
    userRole.textContent = currentUser.role.charAt(0).toUpperCase() + currentUser.role.slice(1);
};

const setupNavigation = () => {
    const nav = document.getElementById('sidebarNav');
    const role = currentUser.role;

    const navItems = {
        admin: [
            { icon: 'tachometer-alt', label: 'Dashboard', section: 'dashboard' },
            { icon: 'qrcode', label: 'Scan QR', section: 'qrScanner' },
            { icon: 'chalkboard-teacher', label: 'Teachers', section: 'teachers' },
            { icon: 'user-graduate', label: 'Students', section: 'students' },
            { icon: 'school', label: 'Classes', section: 'classes' },
            { icon: 'clipboard-check', label: 'Attendance', section: 'attendance' },
            { icon: 'chart-bar', label: 'Reports', section: 'reports' },
            { icon: 'user-circle', label: 'Profile', section: 'profile' }
        ],
        teacher: [
            { icon: 'tachometer-alt', label: 'Dashboard', section: 'dashboard' },
            { icon: 'qrcode', label: 'Scan QR', section: 'qrScanner' },
            { icon: 'user-graduate', label: 'My Students', section: 'students' },
            { icon: 'clipboard-check', label: 'Attendance', section: 'attendance' },
            { icon: 'chart-bar', label: 'Reports', section: 'reports' },
            { icon: 'user-circle', label: 'Profile', section: 'profile' }
        ],
        student: [
            { icon: 'tachometer-alt', label: 'Dashboard', section: 'dashboard' },
            { icon: 'clipboard-check', label: 'My Attendance', section: 'attendance' },
            { icon: 'chart-line', label: 'My Stats', section: 'reports' },
            { icon: 'user-circle', label: 'Profile', section: 'profile' }
        ]
    };

    nav.innerHTML = navItems[role].map(item => `
        <div class="nav-item ${item.section === 'dashboard' ? 'active' : ''}" data-section="${item.section}">
            <i class="fas fa-${item.icon}"></i>
            <span>${item.label}</span>
        </div>
    `).join('');

    // Add click listeners
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            
            const section = item.dataset.section;
            navigateToSection(section);
        });
    });
};

const navigateToSection = (section) => {
    // Hide all sections
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    
    // Show selected section
    const sectionElement = document.getElementById(`${section}Section`);
    sectionElement.classList.add('active');
    
    // Update page title
    const titles = {
        dashboard: 'Dashboard',
        qrScanner: 'Scan QR Code',
        teachers: 'Teachers Management',
        students: 'Students Management',
        classes: 'Classes Management',
        attendance: 'Attendance Records',
        reports: 'Reports & Analytics',
        profile: 'My Profile'
    };
    
    document.getElementById('pageTitle').textContent = titles[section];
    
    // Load section data
    loadSectionData(section);
};

const loadSectionData = async (section) => {
    const loaders = {
        dashboard: loadDashboardData,
        qrScanner: loadQRScanner,
        teachers: loadTeachers,
        students: loadStudents,
        classes: loadClasses,
        attendance: loadAttendance,
        reports: loadReports,
        profile: loadProfile
    };

    const loader = loaders[section];
    if (loader) {
        showLoading();
        try {
            await loader();
        } catch (error) {
            showAlert('Failed to load data: ' + error.message, 'error');
        } finally {
            hideLoading();
        }
    }
};

// Dashboard Data
const loadDashboardData = async () => {
    const statsGrid = document.getElementById('statsGrid');
    const role = currentUser.role;

    if (role === 'admin') {
        const [teachers, students, classes] = await Promise.all([
            apiRequest('/teachers/list'),
            apiRequest('/students/list'),
            apiRequest('/classes/list')
        ]);

        statsGrid.innerHTML = `
            <div class="stat-card primary">
                <div class="stat-icon"><i class="fas fa-chalkboard-teacher"></i></div>
                <div class="stat-value">${teachers.total || teachers.length}</div>
                <div class="stat-label">Total Teachers</div>
            </div>
            <div class="stat-card success">
                <div class="stat-icon"><i class="fas fa-user-graduate"></i></div>
                <div class="stat-value">${students.total || students.length}</div>
                <div class="stat-label">Total Students</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-icon"><i class="fas fa-school"></i></div>
                <div class="stat-value">${classes.length}</div>
                <div class="stat-label">Total Classes</div>
            </div>
            <div class="stat-card danger">
                <div class="stat-icon"><i class="fas fa-clipboard-check"></i></div>
                <div class="stat-value" id="todayAttendance">0</div>
                <div class="stat-label">Today's Attendance</div>
            </div>
        `;
    } else if (role === 'teacher') {
        const students = await apiRequest('/teachers/me/students');
        
        statsGrid.innerHTML = `
            <div class="stat-card primary">
                <div class="stat-icon"><i class="fas fa-school"></i></div>
                <div class="stat-value">${currentUser.assigned_class || 'N/A'}</div>
                <div class="stat-label">My Class</div>
            </div>
            <div class="stat-card success">
                <div class="stat-icon"><i class="fas fa-user-graduate"></i></div>
                <div class="stat-value">${students.total || 0}</div>
                <div class="stat-label">My Students</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-icon"><i class="fas fa-clipboard-check"></i></div>
                <div class="stat-value" id="todayPresent">0</div>
                <div class="stat-label">Present Today</div>
            </div>
            <div class="stat-card danger">
                <div class="stat-icon"><i class="fas fa-user-times"></i></div>
                <div class="stat-value" id="todayAbsent">0</div>
                <div class="stat-label">Absent Today</div>
            </div>
        `;
    } else {
        const attendance = await apiRequest('/attendance/me?period=month');
        const stats = attendance.statistics;
        
        statsGrid.innerHTML = `
            <div class="stat-card success">
                <div class="stat-icon"><i class="fas fa-calendar-check"></i></div>
                <div class="stat-value">${stats.present_days}</div>
                <div class="stat-label">Days Present</div>
            </div>
            <div class="stat-card danger">
                <div class="stat-icon"><i class="fas fa-calendar-times"></i></div>
                <div class="stat-value">${stats.absent_days}</div>
                <div class="stat-label">Days Absent</div>
            </div>
            <div class="stat-card ${stats.attendance_percentage >= 75 ? 'success' : 'warning'}">
                <div class="stat-icon"><i class="fas fa-percentage"></i></div>
                <div class="stat-value">${stats.attendance_percentage}%</div>
                <div class="stat-label">Attendance Rate</div>
            </div>
            <div class="stat-card primary">
                <div class="stat-icon"><i class="fas fa-calendar"></i></div>
                <div class="stat-value">${stats.total_working_days}</div>
                <div class="stat-label">Working Days</div>
            </div>
        `;
    }
};

// QR Scanner
const loadQRScanner = () => {
    const section = document.getElementById('qrScannerSection');
    
    section.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Scan Student QR Code</h2>
            </div>
            <div class="qr-scanner-container">
                <div id="qr-reader"></div>
            </div>
            <div id="scanResult"></div>
        </div>
    `;

    // Initialize scanner
    if (!html5QrCode) {
        html5QrCode = new Html5Qrcode("qr-reader");
    }

    const config = { fps: 10, qrbox: { width: 250, height: 250 } };

    html5QrCode.start(
        { facingMode: "environment" },
        config,
        async (decodedText) => {
            // Stop scanner
            html5QrCode.stop();

            // Mark attendance
            try {
                showLoading();
                const result = await apiRequest(`/attendance/mark/${decodedText}`);
                
                document.getElementById('scanResult').innerHTML = `
                    <div class="alert success">
                        <i class="fas fa-check-circle"></i>
                        <div>
                            <strong>${result.msg}</strong><br>
                            <small>${result.student.name} (${result.student.roll_no})</small>
                        </div>
                    </div>
                `;
                
                showAlert('Attendance marked successfully!', 'success');
                
                // Restart scanner after 3 seconds
                setTimeout(() => {
                    document.getElementById('scanResult').innerHTML = '';
                    html5QrCode.start({ facingMode: "environment" }, config, arguments.callee);
                }, 3000);
            } catch (error) {
                document.getElementById('scanResult').innerHTML = `
                    <div class="alert error">
                        <i class="fas fa-exclamation-circle"></i>
                        <span>${error.message}</span>
                    </div>
                `;
                
                // Restart scanner
                setTimeout(() => {
                    document.getElementById('scanResult').innerHTML = '';
                    html5QrCode.start({ facingMode: "environment" }, config, arguments.callee);
                }, 3000);
            } finally {
                hideLoading();
            }
        }
    ).catch(err => {
        console.error('Scanner error:', err);
        showAlert('Failed to start camera. Please check permissions.', 'error');
    });
};

// Students Management
const loadStudents = async () => {
    const section = document.getElementById('studentsSection');
    const students = await apiRequest('/students/list');
    
    section.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Students</h2>
                ${currentUser.role !== 'student' ? `
                    <button class="btn btn-primary btn-sm" onclick="showAddStudentModal()">
                        <i class="fas fa-plus"></i> Add Student
                    </button>
                ` : ''}
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Roll No</th>
                            <th>Name</th>
                            <th>Class</th>
                            <th>Email</th>
                            <th>Status</th>
                            ${currentUser.role !== 'student' ? '<th>Actions</th>' : ''}
                        </tr>
                    </thead>
                    <tbody>
                        ${(students.students || students).map(student => `
                            <tr>
                                <td><strong>${student.roll_no}</strong></td>
                                <td>${student.name}</td>
                                <td><span class="badge primary">${student.class}</span></td>
                                <td>${student.email || 'N/A'}</td>
                                <td>
                                    <span class="badge ${student.is_active ? 'success' : 'danger'}">
                                        ${student.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                </td>
                                ${currentUser.role !== 'student' ? `
                                    <td>
                                        <button class="btn btn-sm btn-secondary" onclick="viewStudent(${student.id})">
                                            <i class="fas fa-eye"></i>
                                        </button>
                                        <button class="btn btn-sm btn-primary" onclick="editStudent(${student.id})">
                                            <i class="fas fa-edit"></i>
                                        </button>
                                    </td>
                                ` : ''}
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
};

// Teachers Management (Admin only)
const loadTeachers = async () => {
    if (currentUser.role !== 'admin') return;
    
    const section = document.getElementById('teachersSection');
    const teachers = await apiRequest('/teachers/list');
    
    section.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Teachers</h2>
                <button class="btn btn-primary btn-sm" onclick="showAddTeacherModal()">
                    <i class="fas fa-plus"></i> Add Teacher
                </button>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Assigned Class</th>
                            <th>Students</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${teachers.teachers.map(teacher => `
                            <tr>
                                <td><strong>${teacher.username}</strong></td>
                                <td>${teacher.email}</td>
                                <td><span class="badge primary">${teacher.assigned_class || 'N/A'}</span></td>
                                <td>${teacher.student_count || 0}</td>
                                <td>
                                    <span class="badge ${teacher.is_active ? 'success' : 'danger'}">
                                        ${teacher.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                </td>
                                <td>
                                    <button class="btn btn-sm btn-primary" onclick="editTeacher('${teacher.username}')">
                                        <i class="fas fa-edit"></i>
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
};

// Classes Management
const loadClasses = async () => {
    if (currentUser.role !== 'admin') return;
    
    const section = document.getElementById('classesSection');
    const classes = await apiRequest('/classes/list');
    
    section.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Classes</h2>
                <button class="btn btn-primary btn-sm" onclick="showAddClassModal()">
                    <i class="fas fa-plus"></i> Add Class
                </button>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Class Name</th>
                            <th>Section</th>
                            <th>Academic Year</th>
                            <th>Required %</th>
                            <th>Students</th>
                            <th>Teachers</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${classes.map(cls => `
                            <tr>
                                <td><strong>${cls.name}</strong></td>
                                <td>${cls.section || 'N/A'}</td>
                                <td>${cls.academic_year || 'N/A'}</td>
                                <td><span class="badge warning">${cls.required_attendance_percentage}%</span></td>
                                <td>${cls.student_count}</td>
                                <td>${cls.teacher_count}</td>
                                <td>
                                    <span class="badge ${cls.is_active ? 'success' : 'danger'}">
                                        ${cls.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                </td>
                                <td>
                                    <button class="btn btn-sm btn-secondary" onclick="viewClassStats('${cls.name}')">
                                        <i class="fas fa-chart-bar"></i>
                                    </button>
                                    <button class="btn btn-sm btn-primary" onclick="editClass('${cls.name}')">
                                        <i class="fas fa-edit"></i>
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
};

// Attendance Records
const loadAttendance = async () => {
    const section = document.getElementById('attendanceSection');
    const today = new Date().toISOString().split('T')[0];
    
    const attendance = await apiRequest(`/attendance/list?date_filter=${today}`);
    
    section.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Attendance Records - Today</h2>
                <div style="display: flex; gap: 12px;">
                    <input type="date" class="form-control" id="attendanceDate" value="${today}" 
                           style="width: auto; padding: 8px 16px;">
                    <button class="btn btn-primary btn-sm" onclick="filterAttendance()">
                        <i class="fas fa-filter"></i> Filter
                    </button>
                </div>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Roll No</th>
                            <th>Student Name</th>
                            <th>Class</th>
                            <th>Date</th>
                            <th>Time</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${attendance.records.map(record => `
                            <tr>
                                <td><strong>${record.roll_no}</strong></td>
                                <td>${record.student_name}</td>
                                <td><span class="badge primary">${record.class_name}</span></td>
                                <td>${record.date}</td>
                                <td>${record.time}</td>
                                <td><span class="badge success">Present</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
};

// Reports
const loadReports = async () => {
    const section = document.getElementById('reportsSection');
    
    section.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Attendance Reports</h2>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Report Type</label>
                    <select class="form-control" id="reportType">
                        <option value="daily">Daily Summary</option>
                        <option value="student">Student Percentage</option>
                        <option value="class">Class Percentage</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Start Date</label>
                    <input type="date" class="form-control" id="reportStartDate">
                </div>
                <div class="form-group">
                    <label>End Date</label>
                    <input type="date" class="form-control" id="reportEndDate">
                </div>
                <button class="btn btn-primary" onclick="generateReport()">
                    <i class="fas fa-chart-line"></i> Generate Report
                </button>
            </div>
            <div id="reportResults"></div>
        </div>
    `;
};

// Profile
const loadProfile = async () => {
    const section = document.getElementById('profileSection');
    
    section.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">My Profile</h2>
            </div>
            <div class="modal-body">
                <div class="user-avatar" style="width: 80px; height: 80px; font-size: 32px; margin-bottom: 20px;">
                    ${currentUser.username[0].toUpperCase()}
                </div>
                <h3>${currentUser.username}</h3>
                <p>${currentUser.email || 'No email'}</p>
                <p>Role: <span class="badge primary">${currentUser.role}</span></p>
                ${currentUser.assigned_class ? `<p>Class: <span class="badge success">${currentUser.assigned_class}</span></p>` : ''}
                
                <hr style="margin: 30px 0;">
                
                <h3>Change Password</h3>
                <form id="changePasswordForm">
                    <div class="form-group">
                        <label>Current Password</label>
                        <input type="password" class="form-control" id="currentPassword" required>
                    </div>
                    <div class="form-group">
                        <label>New Password</label>
                        <input type="password" class="form-control" id="newPassword" required>
                    </div>
                    <div class="form-group">
                        <label>Confirm New Password</label>
                        <input type="password" class="form-control" id="confirmPassword" required>
                    </div>
                    <button type="submit" class="btn btn-primary">
                        <i class="fas fa-key"></i> Update Password
                    </button>
                </form>
            </div>
        </div>
    `;
    
    // Add form listener
    document.getElementById('changePasswordForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const current = document.getElementById('currentPassword').value;
        const newPass = document.getElementById('newPassword').value;
        const confirm = document.getElementById('confirmPassword').value;
        
        if (newPass !== confirm) {
            showAlert('New passwords do not match', 'error');
            return;
        }
        
        try {
            showLoading();
            await apiRequest('/auth/change-password', {
                method: 'POST',
                body: JSON.stringify({
                    old_password: current,
                    new_password: newPass
                })
            });
            showAlert('Password changed successfully', 'success');
            e.target.reset();
        } catch (error) {
            showAlert(error.message, 'error');
        } finally {
            hideLoading();
        }
    });
};

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Check authentication
    checkAuth();
    
    // Login form
    document.getElementById('loginForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        await login(username, password);
    });
    
    // Logout button
    document.getElementById('logoutBtn').addEventListener('click', logout);
    
    // Refresh button
    document.getElementById('refreshBtn').addEventListener('click', () => {
        const activeSection = document.querySelector('.nav-item.active');
        if (activeSection) {
            loadSectionData(activeSection.dataset.section);
        }
    });
    
    // Mobile menu
    document.getElementById('mobileMenuBtn').addEventListener('click', () => {
        document.getElementById('sidebar').classList.toggle('active');
    });
});

// Placeholder functions for modal operations
window.showAddStudentModal = () => showAlert('Add Student feature - Coming soon!', 'warning');
window.showAddTeacherModal = () => showAlert('Add Teacher feature - Coming soon!', 'warning');
window.showAddClassModal = () => showAlert('Add Class feature - Coming soon!', 'warning');
window.viewStudent = (id) => showAlert(`View Student ${id} - Coming soon!`, 'warning');
window.editStudent = (id) => showAlert(`Edit Student ${id} - Coming soon!`, 'warning');
window.editTeacher = (username) => showAlert(`Edit Teacher ${username} - Coming soon!`, 'warning');
window.editClass = (name) => showAlert(`Edit Class ${name} - Coming soon!`, 'warning');
window.viewClassStats = (name) => showAlert(`View ${name} stats - Coming soon!`, 'warning');
window.filterAttendance = () => {
    const date = document.getElementById('attendanceDate').value;
    loadAttendance();
};
window.generateReport = () => showAlert('Generate Report - Coming soon!', 'warning');