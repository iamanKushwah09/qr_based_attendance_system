// app.js - Modern QR Attendance System Frontend (Final Fixed Version)

// ==================== CONFIGURATION ====================
const API_URL = 'http://localhost:8000/api';
const BACKEND_URL = 'http://localhost:8000'; // QR images ke liye

let authToken = null;
let currentUser = null;
let html5QrCode = null;

// ==================== STYLE INJECTION FOR TOASTS ====================
// CSS for Floating Toast Notifications (Sabse Upar Dikhen)
const styleSheet = document.createElement("style");
styleSheet.textContent = `
    #toast-container {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999999; /* Modal se bhi upar */
        display: flex;
        flex-direction: column;
        gap: 10px;
        pointer-events: none;
    }
    .toast-alert {
        background: white;
        padding: 16px 20px;
        border-radius: 8px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        display: flex;
        align-items: flex-start;
        gap: 12px;
        min-width: 320px;
        max-width: 450px;
        animation: slideInRight 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        border-left: 5px solid #ccc;
        pointer-events: auto;
        font-family: system-ui, -apple-system, sans-serif;
    }
    .toast-content { display: flex; flex-direction: column; gap: 4px; }
    .toast-title { font-weight: 700; font-size: 14px; text-transform: uppercase; }
    .toast-msg { font-size: 14px; color: #4b5563; line-height: 1.4; }
    
    .toast-alert.success { border-left-color: #10b981; }
    .toast-alert.success i { color: #10b981; }
    
    .toast-alert.error { border-left-color: #ef4444; }
    .toast-alert.error i { color: #ef4444; }
    .toast-alert.error .toast-title { color: #dc2626; }
    
    .toast-alert.warning { border-left-color: #f59e0b; }
    .toast-alert.warning i { color: #f59e0b; }

    @keyframes slideInRight {
        from { transform: translateX(120%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes fadeOut {
        to { opacity: 0; transform: translateY(-20px); }
    }
`;
document.head.appendChild(styleSheet);

// ==================== UTILITY FUNCTIONS ====================
// ==================== UTILITY FUNCTIONS ====================

// ... (showLoading, hideLoading, showAlert pehle se hain) ...

// NEW: Force Download Function
const downloadImage = async (url, filename) => {
    try {
        showLoading();
        const response = await fetch(url);
        const blob = await response.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        
        document.body.removeChild(link);
        window.URL.revokeObjectURL(blobUrl);
    } catch (error) {
        console.error('Download failed:', error);
        window.open(url, '_blank'); // Fallback
    } finally {
        hideLoading();
    }
};
const showLoading = () => {
    const loader = document.getElementById('loadingScreen');
    if(loader) loader.classList.remove('hidden');
};

const hideLoading = () => {
    const loader = document.getElementById('loadingScreen');
    if(loader) loader.classList.add('hidden');
};

// IMPROVED SHOW ALERT (Toast Notification)
const showAlert = (message, type = 'success') => {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }

    // Handle Objects gracefully
    let displayMsg = message;
    if (typeof message === 'object') {
        displayMsg = JSON.stringify(message);
    }

    const alertDiv = document.createElement('div');
    alertDiv.className = `toast-alert ${type}`;
    
    let icon = 'info-circle';
    let title = 'Info';
    if (type === 'success') { icon = 'check-circle'; title = 'Success'; }
    if (type === 'error') { icon = 'times-circle'; title = 'Error'; }
    if (type === 'warning') { icon = 'exclamation-triangle'; title = 'Warning'; }

    alertDiv.innerHTML = `
        <i class="fas fa-${icon}" style="font-size: 20px; margin-top: 2px;"></i>
        <div class="toast-content">
            <span class="toast-title">${title}</span>
            <span class="toast-msg">${displayMsg}</span>
        </div>
    `;
    
    container.appendChild(alertDiv);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        alertDiv.style.animation = 'fadeOut 0.5s forwards';
        setTimeout(() => alertDiv.remove(), 500);
    }, 5000);
};

// IMPROVED API REQUEST (Error Parsing Logic)
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
            // === SMART ERROR PARSER ===
            // Ye [object Object] ko human-readable text mein badlega
            let errorMsg = 'Something went wrong';

            if (data.detail) {
                if (typeof data.detail === 'string') {
                    errorMsg = data.detail;
                } else if (Array.isArray(data.detail)) {
                    // FastAPI Validation Errors list
                    errorMsg = data.detail.map(err => {
                        const field = err.loc ? err.loc[err.loc.length - 1] : 'Field';
                        return `${field}: ${err.msg}`;
                    }).join('\n');
                } else {
                    errorMsg = JSON.stringify(data.detail);
                }
            } else if (data.message) {
                errorMsg = data.message;
            }

            throw new Error(errorMsg);
        }

        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error; // Caller catch block will handle alert
    }
};

// ==================== ADVANCED POPUP (MODAL) ====================
const openModal = (title, bodyHtml, footerHtml = '') => {
    let modal = document.getElementById('dynamicModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'dynamicModal';
        modal.className = 'modal';
        document.body.appendChild(modal);
    }

    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3 class="modal-title">${title}</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">${bodyHtml}</div>
            <div class="modal-footer">${footerHtml}</div>
        </div>
    `;
    
    setTimeout(() => modal.classList.add('active'), 10);
};

const closeModal = () => {
    const modal = document.getElementById('dynamicModal');
    if (modal) {
        modal.classList.remove('active');
        setTimeout(() => modal.innerHTML = '', 300);
    }
};

window.onclick = function(event) {
    const modal = document.getElementById('dynamicModal');
    if (event.target == modal) {
        closeModal();
    }
}

// ==================== AUTHENTICATION ====================
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

// ==================== DASHBOARD & NAVIGATION ====================
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

    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            navigateToSection(item.dataset.section);
        });
    });
};

const navigateToSection = (section) => {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.getElementById(`${section}Section`)?.classList.add('active');
    
    const titles = {
        dashboard: 'Dashboard', qrScanner: 'Scan QR Code', teachers: 'Teachers Management',
        students: 'Students Management', classes: 'Classes Management', attendance: 'Attendance Records',
        reports: 'Reports & Analytics', profile: 'My Profile'
    };
    document.getElementById('pageTitle').textContent = titles[section] || 'Dashboard';
    loadSectionData(section);
};

const loadSectionData = async (section) => {
    const loaders = {
        dashboard: loadDashboardData, qrScanner: loadQRScanner, teachers: loadTeachers,
        students: loadStudents, classes: loadClasses, attendance: loadAttendance,
        reports: loadReports, profile: loadProfile
    };
    if (loaders[section]) {
        showLoading();
        try { await loaders[section](); } 
        catch (e) { showAlert('Failed to load: ' + e.message, 'error'); } 
        finally { hideLoading(); }
    }
};

// ==================== DASHBOARD & SECTIONS ====================

const loadDashboardData = async () => {
    const statsGrid = document.getElementById('statsGrid');
    const role = currentUser.role;

    if (role === 'admin') {
        const [teachers, students, classes] = await Promise.all([
            apiRequest('/teachers/list'), apiRequest('/students/list'), apiRequest('/classes/list')
        ]);
        statsGrid.innerHTML = `
            <div class="stat-card primary">
                <div class="stat-icon"><i class="fas fa-chalkboard-teacher"></i></div>
                <div class="stat-value">${teachers.total || teachers.length || 0}</div>
                <div class="stat-label">Total Teachers</div>
            </div>
            <div class="stat-card success">
                <div class="stat-icon"><i class="fas fa-user-graduate"></i></div>
                <div class="stat-value">${students.total || students.length || 0}</div>
                <div class="stat-label">Total Students</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-icon"><i class="fas fa-school"></i></div>
                <div class="stat-value">${classes.length || 0}</div>
                <div class="stat-label">Total Classes</div>
            </div>
            <div class="stat-card danger">
                <div class="stat-icon"><i class="fas fa-clipboard-check"></i></div>
                <div class="stat-value" id="todayAttendance">0</div>
                <div class="stat-label">Today's Attendance</div>
            </div>
        `;
    } else if (role === 'teacher') {
        try {
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
            `;
        } catch(e) { statsGrid.innerHTML = `<div class="alert error">Error loading dashboard</div>`; }
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
        `;
    }
};

const loadQRScanner = () => {
    const section = document.getElementById('qrScannerSection');
    section.innerHTML = `
        <div class="card">
            <div class="card-header"><h2 class="card-title">Scan Student QR Code</h2></div>
            <div class="qr-scanner-container"><div id="qr-reader"></div></div>
            <div id="scanResult"></div>
        </div>
    `;
    if (!html5QrCode) html5QrCode = new Html5Qrcode("qr-reader");
    
    html5QrCode.start({ facingMode: "environment" }, { fps: 10, qrbox: { width: 250, height: 250 } },
        async (decodedText) => {
            html5QrCode.stop();
            try {
                showLoading();
                const result = await apiRequest(`/attendance/mark/${decodedText}`);
                document.getElementById('scanResult').innerHTML = `
                    <div class="alert success"><i class="fas fa-check-circle"></i>
                    <div><strong>${result.msg}</strong><br><small>${result.student.name} (${result.student.roll_no})</small></div></div>
                `;
                showAlert('Attendance marked!', 'success');
            } catch (error) {
                document.getElementById('scanResult').innerHTML = `<div class="alert error"><i class="fas fa-exclamation-circle"></i><span>${error.message}</span></div>`;
                showAlert(error.message, 'error');
            } finally {
                hideLoading();
                setTimeout(() => { document.getElementById('scanResult').innerHTML = ''; loadQRScanner(); }, 3000);
            }
        }
    ).catch(err => section.innerHTML += `<div class="alert error">Camera error: ${err}</div>`);
};

// ==================== LISTING FUNCTIONS ====================

const loadStudents = async () => {
    const section = document.getElementById('studentsSection');
    let endpoint = currentUser.role === 'teacher' ? '/teachers/me/students' : '/students/list';
    const data = await apiRequest(endpoint);
    const students = data.students || [];

    section.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Students</h2>
                ${currentUser.role !== 'student' ? `<button class="btn btn-primary btn-sm" onclick="showAddStudentModal()"><i class="fas fa-plus"></i> Add Student</button>` : ''}
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Roll No</th><th>Name</th><th>Class</th><th>Email</th><th>Status</th>
                            ${currentUser.role !== 'student' ? '<th>Actions</th>' : ''}
                        </tr>
                    </thead>
                    <tbody>
                        ${students.map(s => `
                            <tr>
                                <td><strong>${s.roll_no}</strong></td>
                                <td>${s.name}</td>
                                <td><span class="badge primary">${s.class}</span></td>
                                <td>${s.email || '-'}</td>
                                <td><span class="badge ${s.is_active ? 'success' : 'danger'}">${s.is_active ? 'Active' : 'Inactive'}</span></td>
                                ${currentUser.role !== 'student' ? `
                                    <td>
                                        <button class="btn btn-sm btn-secondary" onclick="viewStudent(${s.id})"><i class="fas fa-eye"></i></button>
                                        <button class="btn btn-sm btn-primary" onclick="editStudent(${s.id})"><i class="fas fa-edit"></i></button>
                                        <button class="btn btn-sm btn-danger" onclick="deleteStudent(${s.id})"><i class="fas fa-trash"></i></button>
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

const loadTeachers = async () => {
    if (currentUser.role !== 'admin') return;
    const section = document.getElementById('teachersSection');
    const data = await apiRequest('/teachers/list');
    const teachers = data.teachers || [];

    section.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Teachers</h2>
                <button class="btn btn-primary btn-sm" onclick="showAddTeacherModal()"><i class="fas fa-plus"></i> Add Teacher</button>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr><th>Username</th><th>Email</th><th>Class</th><th>Status</th><th>Actions</th></tr>
                    </thead>
                    <tbody>
                        ${teachers.map(t => `
                            <tr>
                                <td><strong>${t.username}</strong></td>
                                <td>${t.email}</td>
                                <td><span class="badge primary">${t.assigned_class || 'N/A'}</span></td>
                                <td><span class="badge ${t.is_active ? 'success' : 'danger'}">${t.is_active ? 'Active' : 'Inactive'}</span></td>
                                <td>
                                    <button class="btn btn-sm btn-primary" onclick="editTeacher('${t.username}')"><i class="fas fa-edit"></i></button>
                                    <button class="btn btn-sm btn-danger" onclick="deleteTeacher('${t.username}')"><i class="fas fa-trash"></i></button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
};

const loadClasses = async () => {
    if (currentUser.role !== 'admin') return;
    const section = document.getElementById('classesSection');
    const classes = await apiRequest('/classes/list');

    section.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Classes</h2>
                <button class="btn btn-primary btn-sm" onclick="showAddClassModal()"><i class="fas fa-plus"></i> Add Class</button>
            </div>
            <div class="table-responsive">
                <table>
                    <thead><tr><th>Name</th><th>Section</th><th>Req %</th><th>Status</th><th>Actions</th></tr></thead>
                    <tbody>
                        ${classes.map(c => `
                            <tr>
                                <td><strong>${c.name}</strong></td>
                                <td>${c.section || '-'}</td>
                                <td><span class="badge warning">${c.required_attendance_percentage}%</span></td>
                                <td><span class="badge ${c.is_active ? 'success' : 'danger'}">${c.is_active ? 'Active' : 'Inactive'}</span></td>
                                <td>
                                    <button class="btn btn-sm btn-primary" onclick="editClass('${c.name}')"><i class="fas fa-edit"></i></button>
                                    <button class="btn btn-sm btn-danger" onclick="deleteClass('${c.name}')"><i class="fas fa-trash"></i></button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
};

const loadAttendance = async () => {
    const section = document.getElementById('attendanceSection');
    const today = new Date().toISOString().split('T')[0];
    let endpoint = currentUser.role === 'student' ? `/attendance/me?period=month` : `/attendance/list?date_filter=${today}`;
    const data = await apiRequest(endpoint);
    const records = data.records || [];

    section.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Attendance Records</h2>
                <div style="display: flex; gap: 12px;">
                    <input type="date" class="form-control" id="attendanceDate" value="${today}" style="width:auto;padding:8px 16px;">
                    <button class="btn btn-primary btn-sm" onclick="filterAttendance()"><i class="fas fa-filter"></i> Filter</button>
                </div>
            </div>
            <div class="table-responsive">
                <table>
                    <thead><tr><th>Date</th><th>Student</th><th>Roll No</th><th>Time</th><th>Status</th></tr></thead>
                    <tbody>
                        ${records.length ? records.map(r => `
                            <tr>
                                <td>${r.date}</td><td>${r.student_name}</td><td><strong>${r.roll_no}</strong></td>
                                <td>${r.time}</td><td><span class="badge success">Present</span></td>
                            </tr>
                        `).join('') : '<tr><td colspan="5" style="text-align:center">No records found</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
    `;
};

// ==================== REPORTS SECTION ====================

const loadReports = async () => {
    const section = document.getElementById('reportsSection');
    const today = new Date().toISOString().split('T')[0];
    
    let classOptions = '';
    try {
        const classes = await apiRequest('/classes/list?is_active=true');
        classOptions = classes.map(c => `<option value="${c.name}">${c.name}</option>`).join('');
    } catch(e) { console.error("Error loading classes for reports"); }

    section.innerHTML = `
        <div class="card">
            <div class="card-header"><h2 class="card-title">Attendance Reports</h2></div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Report Type</label>
                    <select class="form-control" id="reportType" onchange="toggleReportInputs()">
                        <option value="daily">Daily Summary</option>
                        <option value="student">Student Percentage</option>
                        <option value="class">Class Percentage</option>
                        <option value="absent">Absent List</option>
                    </select>
                </div>
                
                <div id="classInputGroup" class="form-group">
                    <label>Select Class</label>
                    <select class="form-control" id="reportClass">
                        <option value="">-- Select Class --</option>
                        ${classOptions}
                    </select>
                </div>

                <div id="studentInputGroup" class="form-group" style="display:none;">
                    <label>Student Roll No</label>
                    <input type="text" class="form-control" id="reportRollNo" placeholder="Enter Roll Number">
                </div>

                <div class="form-group">
                    <label>Date / Start Date</label>
                    <input type="date" class="form-control" id="reportStartDate" value="${today}">
                </div>
                
                <div id="endDateGroup" class="form-group" style="display:none;">
                    <label>End Date</label>
                    <input type="date" class="form-control" id="reportEndDate" value="${today}">
                </div>

                <button class="btn btn-primary" onclick="generateReport()">
                    <i class="fas fa-chart-line"></i> Generate Report
                </button>
            </div>
            <div id="reportResults" style="margin-top:20px;"></div>
        </div>
    `;
};

window.toggleReportInputs = () => {
    const type = document.getElementById('reportType').value;
    const classGroup = document.getElementById('classInputGroup');
    const studentGroup = document.getElementById('studentInputGroup');
    const endDateGroup = document.getElementById('endDateGroup');

    classGroup.style.display = 'none';
    studentGroup.style.display = 'none';
    endDateGroup.style.display = 'none';

    if (type === 'daily' || type === 'absent') {
        classGroup.style.display = 'block';
    } else if (type === 'student') {
        studentGroup.style.display = 'block';
        endDateGroup.style.display = 'block';
    } else if (type === 'class') {
        classGroup.style.display = 'block';
        endDateGroup.style.display = 'block';
    }
};

window.generateReport = async () => {
    const type = document.getElementById('reportType').value;
    const startDate = document.getElementById('reportStartDate').value;
    const endDate = document.getElementById('reportEndDate').value;
    const className = document.getElementById('reportClass').value;
    const rollNo = document.getElementById('reportRollNo').value;
    const resultDiv = document.getElementById('reportResults');

    if (!startDate) { showAlert('Please select a date', 'error'); return; }

    try {
        showLoading();
        let data, html = '';

        if (type === 'daily') {
            if (!className) throw new Error("Please select a class");
            data = await apiRequest(`/attendance/report/daily-summary?class_name=${className}&target_date=${startDate}`);
            html = `
                <div class="alert info">
                    <h4>Daily Summary: ${data.class_name} (${data.date})</h4>
                    <p>Total Students: <strong>${data.total_students}</strong></p>
                    <p>Present: <strong style="color:green">${data.present}</strong></p>
                    <p>Absent: <strong style="color:red">${data.absent}</strong></p>
                    <p>Attendance: <strong>${data.attendance_percentage}%</strong></p>
                </div>`;
        } else if (type === 'absent') {
            if (!className) throw new Error("Please select a class");
            data = await apiRequest(`/attendance/absent/${className}?target_date=${startDate}`);
            html = `<h3>Absent Students (${data.date})</h3>`;
            if (data.absent_students.length === 0) {
                html += `<p class="alert success">No students absent today!</p>`;
            } else {
                html += `<ul class="list-group">`;
                data.absent_students.forEach(s => {
                    html += `<li style="padding:10px; border-bottom:1px solid #eee;">
                        <strong>${s.roll_no}</strong> - ${s.name} <span class="badge danger">Absent</span>
                    </li>`;
                });
                html += `</ul>`;
            }
        } else if (type === 'student') {
            if (!rollNo) throw new Error("Please enter roll number");
            data = await apiRequest(`/attendance/report/student-percentage/${rollNo}?start_date=${startDate}&end_date=${endDate}`);
            html = `
                <div class="card">
                    <h4>Report: ${data.student.name} (${data.student.roll_no})</h4>
                    <p>Period: ${data.period.start_date} to ${data.period.end_date}</p>
                    <hr>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                        <div>Working Days: <strong>${data.statistics.total_working_days}</strong></div>
                        <div>Present: <strong>${data.statistics.present_days}</strong></div>
                        <div>Percentage: <strong class="${data.statistics.attendance_percentage >= 75 ? 'text-success' : 'text-danger'}">${data.statistics.attendance_percentage}%</strong></div>
                    </div>
                </div>`;
        } else if (type === 'class') {
            if (!className) throw new Error("Please select a class");
            data = await apiRequest(`/attendance/report/class-percentage/${className}?start_date=${startDate}&end_date=${endDate}`);
            html = `<h4>Class Report: ${className} (Avg: ${data.statistics.average_percentage}%)</h4>
                    <div class="table-responsive"><table><thead><tr><th>Roll</th><th>Name</th><th>Present</th><th>%</th></tr></thead><tbody>`;
            data.students.forEach(s => {
                html += `<tr>
                    <td>${s.roll_no}</td>
                    <td>${s.name}</td>
                    <td>${s.present_days}/${data.statistics.total_working_days}</td>
                    <td><span class="badge ${s.percentage >= 75 ? 'success' : 'warning'}">${s.percentage}%</span></td>
                </tr>`;
            });
            html += `</tbody></table></div>`;
        }
        resultDiv.innerHTML = html;
    } catch (error) {
        // Error alert is already shown by apiRequest
        resultDiv.innerHTML = `<div class="alert error">${error.message}</div>`;
    } finally {
        hideLoading();
    }
};

// ==================== PROFILE & SETTINGS ====================

const loadProfile = async () => { 
    document.getElementById('profileSection').innerHTML = `
        <div class="card">
            <div class="card-header"><h2>My Profile</h2></div>
            <div class="modal-body">
                <div style="text-align:center; margin-bottom:20px;">
                    <div class="user-avatar" style="width:80px;height:80px;font-size:32px;margin:0 auto;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);color:white;border-radius:50%;">${currentUser.username[0].toUpperCase()}</div>
                </div>
                <h3 style="text-align:center; margin-bottom:10px;">${currentUser.username}</h3>
                <div style="padding: 0 20px;">
                    <p><strong>Email:</strong> ${currentUser.email || '-'}</p>
                    <p><strong>Role:</strong> <span class="badge primary">${currentUser.role}</span></p>
                    ${currentUser.assigned_class ? `<p><strong>Class:</strong> <span class="badge success">${currentUser.assigned_class}</span></p>` : ''}
                </div>
            </div>
        </div>

        <div class="card" style="margin-top: 20px;">
            <div class="card-header"><h2>Account Settings</h2></div>
            <div class="modal-body">
                <h3>Change Password</h3>
                <form id="changePasswordForm" style="margin-top: 15px;">
                    <div class="form-group">
                        <label>Current Password</label>
                        <input type="password" id="currentPassword" class="form-control" placeholder="Enter current password" required>
                    </div>
                    <div class="form-group">
                        <label>New Password</label>
                        <input type="password" id="newPassword" class="form-control" placeholder="Enter new password" required>
                    </div>
                    <div class="form-group">
                        <label>Confirm New Password</label>
                        <input type="password" id="confirmPassword" class="form-control" placeholder="Confirm new password" required>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:20px;">
                        <button type="submit" class="btn btn-primary">
                            <i class="fas fa-key"></i> Update Password
                        </button>
                        <a href="forgot-password.html" class="text-primary" style="font-size:14px; text-decoration:none;">Forgot Password?</a>
                    </div>
                </form>
            </div>
        </div>
    `;

    document.getElementById('changePasswordForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const currentPass = document.getElementById('currentPassword').value;
        const newPass = document.getElementById('newPassword').value;
        const confirmPass = document.getElementById('confirmPassword').value;

        if (newPass !== confirmPass) {
            showAlert('New passwords do not match!', 'error');
            return;
        }

        try {
            showLoading();
            await apiRequest('/auth/change-password', {
                method: 'POST',
                body: JSON.stringify({ old_password: currentPass, new_password: newPass })
            });
            showAlert('Password changed successfully!', 'success');
            document.getElementById('changePasswordForm').reset();
        } catch (error) {
            showAlert(error.message, 'error');
        } finally {
            hideLoading();
        }
    });
};

// ==================== CRUD OPERATIONS ====================

// --- STUDENT CRUD ---

window.showAddStudentModal = async () => {
    try {
        const classes = await apiRequest('/classes/list?is_active=true');
        const options = classes.map(c => `<option value="${c.name}">${c.name}</option>`).join('');
        const form = `
            <form id="addStudentForm">
                <div class="form-group"><label>Full Name</label><input type="text" name="name" class="form-control" required></div>
                <div class="form-group"><label>Roll No</label><input type="text" name="roll_no" class="form-control" required></div>
                <div class="form-group"><label>Class</label><select name="class_name" class="form-control" required><option value="">Select</option>${options}</select></div>
                <div class="form-group"><label>Father's Name</label><input type="text" name="father_name" class="form-control"></div>
                <div class="form-group"><label>Mother's Name</label><input type="text" name="mother_name" class="form-control"></div>
                <div class="form-group"><label>DOB</label><input type="date" name="date_of_birth" class="form-control"></div>
                <div class="form-group"><label>Email</label><input type="email" name="email" class="form-control"></div>
                <div class="form-group"><label>Mobile</label><input type="text" name="mobile" class="form-control"></div>
                <div class="form-group" style="display:flex;gap:10px;align-items:center;">
                    <input type="checkbox" id="createLoginChk" name="create_login"> <label for="createLoginChk" style="margin:0">Create Login?</label>
                </div>
                <div id="passwordField" class="form-group" style="display:none;"><label>Password</label><input type="password" name="password" class="form-control"></div>
            </form>
        `;
        openModal('Add Student', form, `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="submitAddStudent()">Save</button>`);
        document.getElementById('createLoginChk').addEventListener('change', e => document.getElementById('passwordField').style.display = e.target.checked ? 'block' : 'none');
    } catch (e) { showAlert(e.message, 'error'); }
};

window.submitAddStudent = async () => {
    const data = Object.fromEntries(new FormData(document.getElementById('addStudentForm')).entries());
    data.create_login = document.getElementById('createLoginChk').checked;
    try {
        showLoading();
        await apiRequest('/students/add', { method: 'POST', body: JSON.stringify(data) });
        showAlert('Student added!', 'success');
        closeModal();
        loadStudents();
    } catch (e) { 
        showAlert(e.message, 'error'); // Fixed: Show alert explicitly
    } finally { hideLoading(); }
};

// REPLACE THIS FUNCTION
window.viewStudent = async (id) => {
    try {
        const s = await apiRequest(`/students/${id}`);
        const qrImgSrc = s.qr_uuid ? `${BACKEND_URL}/qrcodes/${s.qr_uuid}.png` : '';
        const fileName = `${s.roll_no}_QR.png`;
        
        const body = `
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px; margin-bottom: 20px;">
                <div><strong>Name:</strong> ${s.name}</div>
                <div><strong>Roll No:</strong> ${s.roll_no}</div>
                <div><strong>Class:</strong> ${s.class}</div>
                <div><strong>Father:</strong> ${s.father_name || '-'}</div>
                <div><strong>Mobile:</strong> ${s.mobile || '-'}</div>
                <div><strong>Email:</strong> ${s.email || '-'}</div>
            </div>
            
            <div style="text-align:center; padding: 20px; background: #f8f9fa; border-radius: 12px; border: 2px dashed #e5e7eb;">
                <h4 style="margin-bottom: 15px; color: #4b5563;">Student QR Code</h4>
                
                ${s.qr_uuid ? `
                    <img src="${qrImgSrc}" 
                         style="width: 200px; height: 200px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); background: white; padding: 10px;" 
                         alt="QR Code"
                         onerror="this.onerror=null; this.src=''; this.parentElement.innerHTML='<p style=\'color:red\'>QR Image Not Found on Server</p>'">
                    <br>
                    <div style="margin-top: 10px; font-family: monospace; font-size: 12px; color: #666;">
                        ID: ${s.qr_uuid}
                    </div>
                    <br>
                    <button onclick="downloadImage('${qrImgSrc}', '${fileName}')" class="btn btn-primary" style="margin-top: 10px; display: inline-flex; align-items: center; gap: 8px;">
                        <i class="fas fa-download"></i> Download QR
                    </button>
                ` : '<p class="alert warning">No QR Code Generated</p>'}
            </div>
        `;
        openModal('Student Details', body, `<button class="btn btn-secondary" onclick="closeModal()">Close</button>`);
    } catch (e) { showAlert(e.message, 'error'); }
};

window.editStudent = async (id) => {
    try {
        const s = await apiRequest(`/students/${id}`);
        const form = `
            <form id="editStudentForm">
                <div class="form-group"><label>Full Name</label><input type="text" name="name" value="${s.name}" class="form-control" required></div>
                <div class="form-group"><label>Father's Name</label><input type="text" name="father_name" value="${s.father_name||''}" class="form-control"></div>
                <div class="form-group"><label>Mother's Name</label><input type="text" name="mother_name" value="${s.mother_name||''}" class="form-control"></div>
                <div class="form-group"><label>Date of Birth</label><input type="date" name="date_of_birth" value="${s.date_of_birth||''}" class="form-control"></div>
                <div class="form-group"><label>Email</label><input type="email" name="email" value="${s.email||''}" class="form-control"></div>
                <div class="form-group"><label>Mobile</label><input type="text" name="mobile" value="${s.mobile||''}" class="form-control"></div>
                <div class="form-group"><label>Address</label><textarea name="address" class="form-control" rows="2">${s.address||''}</textarea></div>
                <div class="form-group"><label>Status</label>
                    <select name="is_active" class="form-control">
                        <option value="true" ${s.is_active?'selected':''}>Active</option>
                        <option value="false" ${!s.is_active?'selected':''}>Inactive</option>
                    </select>
                </div>
            </form>
        `;
        openModal('Edit Student', form, `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="submitEditStudent(${id})">Update</button>`);
    } catch (e) { showAlert(e.message, 'error'); }
};

window.submitEditStudent = async (id) => {
    const data = Object.fromEntries(new FormData(document.getElementById('editStudentForm')).entries());
    if(data.is_active) data.is_active = data.is_active === 'true';
    try {
        showLoading();
        await apiRequest(`/students/update/${id}`, { method: 'PUT', body: JSON.stringify(data) });
        showAlert('Student Updated!', 'success');
        closeModal();
        loadStudents();
    } catch (e) { 
        showAlert(e.message, 'error'); // Fixed: Show alert explicitly
    } finally { hideLoading(); }
};

window.deleteStudent = async (id) => {
    if(!confirm('Delete this student?')) return;
    try {
        showLoading();
        await apiRequest(`/students/delete/${id}`, { method: 'DELETE' });
        showAlert('Deleted!', 'success');
        loadStudents();
    } catch (e) { showAlert(e.message, 'error'); } finally { hideLoading(); }
};

// --- TEACHER CRUD ---

window.showAddTeacherModal = async () => {
    try {
        const classes = await apiRequest('/classes/list?is_active=true');
        const options = classes.map(c => `<option value="${c.name}">${c.name}</option>`).join('');
        const form = `
            <form id="addTeacherForm">
                <div class="form-group"><label>Name</label><input type="text" name="name" class="form-control" required></div>
                <div class="form-group"><label>Username</label><input type="text" name="username" class="form-control" required></div>
                <div class="form-group"><label>Email</label><input type="email" name="email" class="form-control" required></div>
                <div class="form-group"><label>Mobile</label><input type="text" name="mobile" class="form-control"></div>
                <div class="form-group"><label>Password</label><input type="password" name="password" class="form-control" required></div>
                <div class="form-group"><label>Class</label><select name="assigned_class" class="form-control"><option value="">Select</option>${options}</select></div>
            </form>
        `;
        openModal('Add Teacher', form, `<button class="btn btn-primary" onclick="submitAddTeacher()">Save</button>`);
    } catch(e) { showAlert(e.message, 'error'); }
};

window.submitAddTeacher = async () => {
    const data = Object.fromEntries(new FormData(document.getElementById('addTeacherForm')).entries());
    try {
        showLoading();
        await apiRequest('/teachers/create', { method: 'POST', body: JSON.stringify(data) });
        showAlert('Teacher Added!', 'success');
        closeModal();
        loadTeachers();
    } catch(e) { 
        showAlert(e.message, 'error'); // Fixed: Show alert explicitly
    } finally { hideLoading(); }
};

window.editTeacher = async (username) => {
    try {
        const t = await apiRequest(`/teachers/${username}`);
        const classes = await apiRequest('/classes/list?is_active=true');
        const options = classes.map(c => `<option value="${c.name}" ${t.assigned_class==c.name?'selected':''}>${c.name}</option>`).join('');
        const form = `
            <form id="editTeacherForm">
                <div class="form-group"><label>Name</label><input type="text" name="name" value="${t.name||''}" class="form-control"></div>
                <div class="form-group"><label>Email</label><input type="email" name="email" value="${t.email}" class="form-control"></div>
                <div class="form-group"><label>Mobile</label><input type="text" name="mobile" value="${t.mobile||''}" class="form-control"></div>
                <div class="form-group"><label>Class</label><select name="assigned_class" class="form-control"><option value="">Select</option>${options}</select></div>
                <div class="form-group"><label>Status</label>
                    <select name="is_active" class="form-control">
                        <option value="true" ${t.is_active?'selected':''}>Active</option>
                        <option value="false" ${!t.is_active?'selected':''}>Inactive</option>
                    </select>
                </div>
            </form>
        `;
        openModal('Edit Teacher', form, `<button class="btn btn-primary" onclick="submitEditTeacher('${username}')">Update</button>`);
    } catch(e) { showAlert(e.message, 'error'); }
};

window.submitEditTeacher = async (username) => {
    const data = Object.fromEntries(new FormData(document.getElementById('editTeacherForm')).entries());
    if(data.is_active) data.is_active = data.is_active === 'true';
    try {
        showLoading();
        await apiRequest(`/teachers/update/${username}`, { method: 'PUT', body: JSON.stringify(data) });
        showAlert('Teacher Updated!', 'success');
        closeModal();
        loadTeachers();
    } catch(e) { 
        showAlert(e.message, 'error'); // Fixed: Show alert explicitly
    } finally { hideLoading(); }
};

window.deleteTeacher = async (username) => {
    if(!confirm('Delete this teacher?')) return;
    try {
        showLoading();
        await apiRequest(`/teachers/delete/${username}`, { method: 'DELETE' });
        showAlert('Deleted!', 'success');
        loadTeachers();
    } catch(e) { showAlert(e.message, 'error'); } finally { hideLoading(); }
};

// --- CLASS CRUD ---

window.showAddClassModal = () => {
    const form = `
        <form id="addClassForm">
            <div class="form-group"><label>Name</label><input type="text" name="name" class="form-control" required></div>
            <div class="form-group"><label>Section</label><input type="text" name="section" class="form-control"></div>
            <div class="form-group"><label>Year</label><input type="text" name="academic_year" value="${new Date().getFullYear()}" class="form-control"></div>
            <div class="form-group"><label>Req %</label><input type="number" name="required_attendance_percentage" value="75" class="form-control"></div>
        </form>
    `;
    openModal('Add Class', form, `<button class="btn btn-primary" onclick="submitAddClass()">Save</button>`);
};

window.submitAddClass = async () => {
    const data = Object.fromEntries(new FormData(document.getElementById('addClassForm')).entries());
    data.required_attendance_percentage = parseFloat(data.required_attendance_percentage);
    try {
        showLoading();
        await apiRequest('/classes/create', { method: 'POST', body: JSON.stringify(data) });
        showAlert('Class Added!', 'success');
        closeModal();
        loadClasses();
    } catch(e) { 
        showAlert(e.message, 'error'); // Fixed: Show alert explicitly
    } finally { hideLoading(); }
};

window.editClass = async (name) => {
    try {
        const c = await apiRequest(`/classes/${name}`);
        const form = `
            <form id="editClassForm">
                <div class="form-group"><label>Section</label><input type="text" name="section" value="${c.section||''}" class="form-control"></div>
                <div class="form-group"><label>Academic Year</label><input type="text" name="academic_year" value="${c.academic_year||''}" class="form-control"></div>
                <div class="form-group"><label>Req %</label><input type="number" name="required_attendance_percentage" value="${c.required_attendance_percentage}" class="form-control"></div>
                <div class="form-group"><label>Status</label>
                    <select name="is_active" class="form-control">
                        <option value="true" ${c.is_active?'selected':''}>Active</option>
                        <option value="false" ${!c.is_active?'selected':''}>Inactive</option>
                    </select>
                </div>
            </form>
        `;
        openModal('Edit Class', form, `<button class="btn btn-primary" onclick="submitEditClass('${name}')">Update</button>`);
    } catch(e) { showAlert(e.message, 'error'); }
};

window.submitEditClass = async (name) => {
    const data = Object.fromEntries(new FormData(document.getElementById('editClassForm')).entries());
    data.required_attendance_percentage = parseFloat(data.required_attendance_percentage);
    if(data.is_active) data.is_active = data.is_active === 'true';
    try {
        showLoading();
        await apiRequest(`/classes/update/${name}`, { method: 'PUT', body: JSON.stringify(data) });
        showAlert('Class Updated!', 'success');
        closeModal();
        loadClasses();
    } catch(e) { 
        showAlert(e.message, 'error'); // Fixed: Show alert explicitly
    } finally { hideLoading(); }
};

window.deleteClass = async (name) => {
    if(!confirm('Delete this class?')) return;
    try {
        showLoading();
        await apiRequest(`/classes/delete/${name}`, { method: 'DELETE' });
        showAlert('Deleted!', 'success');
        loadClasses();
    } catch(e) { showAlert(e.message, 'error'); } finally { hideLoading(); }
};

window.filterAttendance = () => {
    const date = document.getElementById('attendanceDate').value;
    loadAttendance();
};

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    document.getElementById('loginForm')?.addEventListener('submit', async e => {
        e.preventDefault(); await login(document.getElementById('username').value, document.getElementById('password').value);
    });
    document.getElementById('logoutBtn')?.addEventListener('click', logout);
    document.getElementById('refreshBtn')?.addEventListener('click', () => {
        const active = document.querySelector('.nav-item.active');
        if(active) loadSectionData(active.dataset.section);
    });
    document.getElementById('mobileMenuBtn')?.addEventListener('click', () => document.getElementById('sidebar').classList.toggle('active'));
});