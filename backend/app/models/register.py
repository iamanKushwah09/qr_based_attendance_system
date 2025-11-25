from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "admin"   # default admin; teacher bhi bana sakte ho
