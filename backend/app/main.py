from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, students, attendance, classes, teachers

app = FastAPI()

# # CORS (for frontend)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # ya ["http://localhost:5500"]
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

app.include_router(auth.router)
app.include_router(teachers.router)
app.include_router(students.router)
app.include_router(attendance.router)
app.include_router(classes.router)
