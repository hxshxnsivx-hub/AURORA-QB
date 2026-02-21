from pydantic import BaseModel, EmailStr
from typing import Optional
from models.user import UserRole


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "newemail@example.com",
                "password": "newsecurepassword123"
            }
        }


class UserRoleUpdate(BaseModel):
    """Schema for updating user role (admin only)"""
    role: UserRole
    
    class Config:
        json_schema_extra = {
            "example": {
                "role": "Faculty"
            }
        }
