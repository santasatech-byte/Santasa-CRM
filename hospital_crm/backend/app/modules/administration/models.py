"""
Hospital CRM - Administration & User Entity Models
Defines User, Role, and Authentication data structures.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum
from app.core.database import BaseModel


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "Super Admin"
    HOSPITAL_ADMIN = "Hospital Administrator"
    CRM_MANAGER = "CRM Manager"
    CRM_EXECUTIVE = "CRM Executive"
    DOCTOR = "Doctor"


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    
    role: Mapped[str] = mapped_column(
        String(50),
        default=UserRole.CRM_EXECUTIVE.value,
        nullable=False,
        index=True
    )
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    branch_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    password_reset_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_reset_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def is_locked(self) -> bool:
        if self.locked_until:
            now = datetime.now(timezone.utc)
            # handle timezone aware / naive
            locked_until_utc = self.locked_until
            if locked_until_utc.tzinfo is None:
                locked_until_utc = locked_until_utc.replace(tzinfo=timezone.utc)
            return now < locked_until_utc
        return False
