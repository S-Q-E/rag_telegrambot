from pydantic import BaseModel
from typing import Optional, Dict, Any

# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# --- User Schemas ---
class UserBase(BaseModel):
    email: str


class UserCreate(UserBase):
    password: str
    telegram_id: Optional[str] = None
    tariff: Optional[str] = 'default'
    limits: Optional[Dict[str, Any]] = None


class UserUpdate(BaseModel):
    email: Optional[str] = None
    telegram_id: Optional[str] = None
    tariff: Optional[str] = None
    limits: Optional[Dict[str, Any]] = None


class User(UserBase):
    id: int
    telegram_id: Optional[str] = None
    tariff: Optional[str] = None
    limits: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True
