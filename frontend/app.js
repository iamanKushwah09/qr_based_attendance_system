// ====== CONFIG ======
const API_BASE = "http://localhost:8000";

// ====== JWT HELPERS ======
function parseJwt(token) {
  try {
    const base64Url = token.split(".")[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
}

function getToken() {
  return localStorage.getItem("token");
}

function saveToken(token) {
  localStorage.setItem("token", token);
}

function logout() {
  localStorage.removeItem("token");
  window.location.href = "index.html";
}

// ====== GENERIC API WRAPPER ======
async function apiRequest(method, path, { query = {}, body = null } = {}) {
  const token = getToken();
  const url = new URL(API_BASE + path);

  Object.entries(query).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") {
      url.searchParams.append(k, v);
    }
  });

  const headers = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = "Bearer " + token;
  }

  const res = await fetch(url.toString(), {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });

  if (!res.ok) {
    let msg = "Error " + res.status;
    try {
      const data = await res.json();
      if (data.detail) msg = data.detail;
    } catch {}
    throw new Error(msg);
  }

  try {
    return await res.json();
  } catch {
    return null;
  }
}

// ====== LOGIN PAGE LOGIC ======
document.addEventListener("DOMContentLoaded", () => {
  const path = window.location.pathname;

  if (path.endsWith("index.html") || path.endsWith("/frontend/") || path.endsWith("/")) {
    const loginForm = document.getElementById("loginForm");
    if (loginForm) {
      loginForm.addEventListener("submit", handleLogin);
    }
    return;
  }

  const token = getToken();
  if (!token) {
    window.location.href = "index.html";
    return;
  }
  const payload = parseJwt(token);
  if (!payload || !payload.role) {
    logout();
    return;
  }

  const role = payload.role;
  if (path.endsWith("admin.html") && role !== "admin") {
    redirectByRole(role);
    return;
  }
  if (path.endsWith("teacher.html") && role !== "teacher") {
    redirectByRole(role);
    return;
  }
  if (path.endsWith("student.html") && role !== "student") {
    redirectByRole(role);
    return;
  }

  if (path.endsWith("admin.html")) {
    initAdmin(payload);
  } else if (path.endsWith("teacher.html")) {
    initTeacher(payload);
  } else if (path.endsWith("student.html")) {
    initStudent(payload);
  }
});

async function handleLogin(e) {
  e.preventDefault();
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();
  const errorEl = document.getElementById("loginError");
  errorEl.textContent = "";

  try {
    const data = await apiRequest("POST", "/auth/login", {
      body: { username, password },
    });
    const token = data.token;
    saveToken(token);

    const payload = parseJwt(token);
    if (!payload || !payload.role) {
      throw new Error("Invalid token");
    }
    redirectByRole(payload.role);
  } catch (err) {
    errorEl.textContent = err.message || "Login failed";
  }
}

function redirectByRole(role) {
  if (role === "admin") {
    window.location.href = "admin.html";
  } else if (role === "teacher") {
    window.location.href = "teacher.html";
  } else if (role === "student") {
    window.location.href = "student.html";
  } else {
    window.location.href = "index.html";
  }
}

// ====== ADMIN PAGE FUNCTIONS ======
function initAdmin(payload) {
  const info = document.getElementById("adminUserInfo");
  if (info) {
    info.textContent = `Logged in as ${payload.sub} (admin)`;
  }
  adminLoadStudents();
}

async function adminCreateClass() {
  const name = document.getElementById("classNameInput").value.trim();
  const msg = document.getElementById("classMsg");
  msg.textContent = "";

  if (!name) {
    msg.textContent = "Class name required.";
    return;
  }

  try {
    await apiRequest("POST", "/classes/add", {
      query: { name },
    });
    msg.textContent = "Class created successfully.";
  } catch (err) {
    msg.textContent = err.message;
  }
}

async function adminCreateTeacher() {
  const username = document.getElementById("teacherUsername").value.trim();
  const password = document.getElementById("teacherPassword").value.trim();
  const msg = document.getElementById("teacherMsg");
  msg.textContent = "";

  if (!username || !password) {
    msg.textContent = "Username & Password required.";
    return;
  }

  try {
    await apiRequest("POST", "/auth/register", {
      body: {
        username,
        password,
        role: "teacher",
      },
    });
    msg.textContent = "Teacher user created successfully.";
  } catch (err) {
    msg.textContent = err.message;
  }
}

async function adminCreateStudent() {
  const name = document.getElementById("studentName").value.trim();
  const roll = document.getElementById("studentRoll").value.trim();
  const cls = document.getElementById("studentClass").value.trim();
  const password = document.getElementById("studentPassword").value.trim();
  const msg = document.getElementById("studentMsg");
  msg.textContent = "";

  if (!name || !roll || !cls || !password) {
    msg.textContent = "All fields required.";
    return;
  }

  try {
    await apiRequest("POST", "/students/add", {
      query: {
        name,
        roll_no: roll,
        class_name: cls,
        password,
      },
    });
    msg.textContent = "Student + login created successfully.";
    adminLoadStudents();
  } catch (err) {
    msg.textContent = err.message;
  }
}

async function adminLoadStudents() {
  const container = document.getElementById("studentsList");
  if (!container) return;
  container.innerHTML = "Loading...";

  try {
    const data = await apiRequest("GET", "/students/list");
    if (!Array.isArray(data) || data.length === 0) {
      container.innerHTML = "<p class='muted'>No students found.</p>";
      return;
    }
    container.innerHTML = data
      .map(
        (s) =>
          `<div class="list-item">${s.class} - ${s.roll_no} — ${s.name}</div>`
      )
      .join("");
  } catch (err) {
    container.innerHTML = `<p class="error-msg">${err.message}</p>`;
  }
}

function openAllQrPreview() {
  // Will open an HTML page from backend which renders all QR images
  const token = getToken();
  const url = API_BASE + "/students/all-qr-preview";
  window.open(url, "_blank");
}

// ====== TEACHER PAGE FUNCTIONS ======
function initTeacher(payload) {
  const info = document.getElementById("teacherUserInfo");
  if (info) {
    info.textContent = `Logged in as ${payload.sub} (teacher)`;
  }
  teacherLoadStudents();
}

async function teacherLoadStudents() {
  const container = document.getElementById("teacherStudentsList");
  if (!container) return;
  container.innerHTML = "Loading...";

  try {
    const data = await apiRequest("GET", "/students/list");
    if (!Array.isArray(data) || data.length === 0) {
      container.innerHTML = "<p class='muted'>No students found.</p>";
      return;
    }
    container.innerHTML = data
      .map(
        (s) =>
          `<div class="list-item">${s.roll_no} — ${s.name}</div>`
      )
      .join("");
  } catch (err) {
    container.innerHTML = `<p class="error-msg">${err.message}</p>`;
  }
}

function openClassQrView() {
  const url = API_BASE + "/students/class-qr-view";
  window.open(url, "_blank");
}

async function teacherMarkAttendance() {
  const uuid = document.getElementById("markUuidInput").value.trim();
  const msg = document.getElementById("markMsg");
  msg.textContent = "";

  if (!uuid) {
    msg.textContent = "UUID required.";
    return;
  }

  try {
    const data = await apiRequest("GET", `/attendance/mark/${uuid}`);
    msg.textContent = data.msg || "Marked.";
  } catch (err) {
    msg.textContent = err.message;
  }
}

async function teacherLoadTodayAttendance() {
  const container = document.getElementById("teacherAttendanceList");
  if (!container) return;
  container.innerHTML = "Loading...";

  const today = new Date().toISOString().split("T")[0];

  try {
    const data = await apiRequest("GET", "/attendance/list", {
      query: { date_filter: today },
    });
    if (!Array.isArray(data) || data.length === 0) {
      container.innerHTML = "<p class='muted'>No attendance records for today.</p>";
      return;
    }
    container.innerHTML = data
      .map(
        (a) =>
          `<div class="list-item">${a.roll_no} — ${a.student_name || ""} (${a.date})</div>`
      )
      .join("");
  } catch (err) {
    container.innerHTML = `<p class="error-msg">${err.message}</p>`;
  }
}

// ====== STUDENT PAGE FUNCTIONS ======
function initStudent(payload) {
  const info = document.getElementById("studentUserInfo");
  if (info) {
    info.textContent = `Logged in as ${payload.sub} (student)`;
  }
  loadStudentProfile();
  loadMyAttendance();
}

async function loadStudentProfile() {
  const box = document.getElementById("studentProfile");
  if (!box) return;
  box.innerHTML = "Loading...";

  try {
    const s = await apiRequest("GET", "/students/me");
    box.innerHTML = `
      <p><strong>Name:</strong> ${s.name}</p>
      <p><strong>Roll No:</strong> ${s.roll_no}</p>
      <p><strong>Class:</strong> ${s.class}</p>
    `;
  } catch (err) {
    box.innerHTML = `<p class="error-msg">${err.message}</p>`;
  }
}

function openMyQrView() {
  const url = API_BASE + "/students/my-qr-view";
  window.open(url, "_blank");
}

async function loadMyQrBase64() {
  const box = document.getElementById("studentQrBox");
  if (!box) return;
  box.innerHTML = "Loading QR...";

  try {
    const data = await apiRequest("GET", "/students/my-qr-base64");
    if (!data.qr_image) {
      box.innerHTML = "<p class='muted'>QR image not found.</p>";
      return;
    }
    box.innerHTML = `<img src="${data.qr_image}" alt="My QR">`;
  } catch (err) {
    box.innerHTML = `<p class="error-msg">${err.message}</p>`;
  }
}

async function loadMyAttendance() {
  const container = document.getElementById("studentAttendance");
  if (!container) return;
  container.innerHTML = "Loading...";

  try {
    const data = await apiRequest("GET", "/attendance/me");
    if (!Array.isArray(data) || data.length === 0) {
      container.innerHTML = "<p class='muted'>No attendance records found.</p>";
      return;
    }
    container.innerHTML = data
      .map(
        (a) =>
          `<div class="list-item">${a.date} — ${a.class_name}</div>`
      )
      .join("");
  } catch (err) {
    container.innerHTML = `<p class="error-msg">${err.message}</p>`;
  }
}
