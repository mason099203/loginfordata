from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["user", "advanced_user", "admin"]


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: Role
    created_at: datetime
    is_active: bool
    email_verified: bool


class RegisterForm(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)
    display_name: str = Field(min_length=1, max_length=50)


class LoginForm(BaseModel):
    email: str
    password: str
