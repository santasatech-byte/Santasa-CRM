"""
Hospital CRM - Hospital & Branch Entity Models
"""
from typing import Optional, List
from sqlalchemy import Boolean, Column, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import BaseModel


class Hospital(BaseModel):
    __tablename__ = "hospitals"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), default="Karnataka", nullable=False)
    country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    branches: Mapped[List["Branch"]] = relationship("Branch", back_populates="hospital", cascade="all, delete-orphan")


class Branch(BaseModel):
    __tablename__ = "branches"

    hospital_id: Mapped[str] = mapped_column(String(36), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), default="Karnataka", nullable=False)
    country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ivr_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="branches")
