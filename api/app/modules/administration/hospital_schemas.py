"""
Hospital CRM - Hospital & Branch Pydantic Schemas
"""
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class BranchSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    hospital_id: str
    name: str
    code: str
    city: str
    state: str
    country: str
    phone: Optional[str] = None
    ivr_number: Optional[str] = None
    timezone: str
    is_active: bool


class CreateBranchRequest(BaseModel):
    hospital_id: str
    name: str = Field(..., min_length=2)
    code: str = Field(..., min_length=2, max_length=20)
    address: Optional[str] = None
    city: str
    state: str = "Karnataka"
    country: str = "India"
    phone: Optional[str] = None
    ivr_number: Optional[str] = None
    timezone: str = "Asia/Kolkata"
    is_active: bool = True


class UpdateBranchRequest(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    ivr_number: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class HospitalSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    code: str
    city: str
    state: str
    country: str
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    is_active: bool
    branches: List[BranchSummary] = []


class CreateHospitalRequest(BaseModel):
    name: str = Field(..., min_length=2)
    code: str = Field(..., min_length=2, max_length=20)
    address: Optional[str] = None
    city: str
    state: str = "Karnataka"
    country: str = "India"
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    is_active: bool = True


class UpdateHospitalRequest(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    is_active: Optional[bool] = None
