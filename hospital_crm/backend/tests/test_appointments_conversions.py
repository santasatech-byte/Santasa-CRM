"""
Module 18, 19 & 20: Appointments, Consultation Outcomes & Conversions Test Suite
"""
from datetime import datetime, timedelta, timezone
import pytest
from app.core.security import hash_password, create_access_token
from app.modules.administration.models import User, UserRole
from app.modules.leads.models import Lead


@pytest.fixture
def exec_user(db_session):
    u = User(
        email="exec.appt@santasa.com",
        full_name="Appt Executive",
        hashed_password=hash_password("ValidPass123!"),
        role=UserRole.CRM_EXECUTIVE.value,
        is_active=True
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    token = create_access_token(data={"sub": u.id, "email": u.email, "role": u.role})
    return {"Authorization": f"Bearer {token}"}, u


@pytest.fixture
def doctor_user(db_session):
    u = User(
        email="dr.soumya@santasa.com",
        full_name="Dr. Soumya",
        hashed_password=hash_password("DoctorPass123!"),
        role=UserRole.DOCTOR.value,
        is_active=True
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    token = create_access_token(data={"sub": u.id, "email": u.email, "role": u.role})
    return {"Authorization": f"Bearer {token}"}, u


def test_book_appointment_lifecycle(client, exec_user, doctor_user, db_session):
    """Test booking an appointment transitions lead status and creates timeline log."""
    exec_headers, _ = exec_user
    _, doctor = doctor_user

    # 1. Create Lead
    lead = client.post("/api/v1/leads", headers=exec_headers, json={
        "patient_name": "Appointment Test Patient",
        "primary_phone": "9876500661"
    }).json()

    appt_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

    # 2. Book Appointment
    book_resp = client.post("/api/v1/appointments", headers=exec_headers, json={
        "lead_id": lead["id"],
        "doctor_id": doctor.id,
        "appointment_at": appt_time,
        "service_type": "Initial Fertility Consultation",
        "notes": "Patient seeking consultation for primary infertility."
    })
    assert book_resp.status_code == 201
    appt_data = book_resp.json()
    assert appt_data["status"] == "Booked"
    assert appt_data["doctor_id"] == doctor.id

    # Verify Lead Status Transitioned to 'Appointment Booked'
    updated_lead = client.get(f"/api/v1/leads/{lead['id']}", headers=exec_headers).json()
    assert updated_lead["lead_status"] == "Appointment Booked"


def test_record_consultation_outcome(client, exec_user, doctor_user):
    """Test doctor records consultation outcome and lead status transitions to 'Consultation Done'."""
    exec_headers, _ = exec_user
    doc_headers, doctor = doctor_user

    lead = client.post("/api/v1/leads", headers=exec_headers, json={
        "patient_name": "Consultation Patient",
        "primary_phone": "9876500662"
    }).json()

    appt_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    appt = client.post("/api/v1/appointments", headers=exec_headers, json={
        "lead_id": lead["id"],
        "doctor_id": doctor.id,
        "appointment_at": appt_time
    }).json()

    # Record Outcome
    outcome_resp = client.post(f"/api/v1/appointments/{appt['id']}/outcome", headers=doc_headers, json={
        "outcome_status": "Recommended Treatment",
        "recommended_service": "IVF with ICSI Package",
        "estimated_value": 175000.0,
        "clinical_summary": "Patient advised for ICSI cycle in upcoming cycle."
    })
    assert outcome_resp.status_code == 201
    outcome_data = outcome_resp.json()
    assert outcome_data["outcome_status"] == "Recommended Treatment"
    assert outcome_data["estimated_value"] == 175000.0

    # Verify Lead Status is 'Consultation Done'
    updated_lead = client.get(f"/api/v1/leads/{lead['id']}", headers=exec_headers).json()
    assert updated_lead["lead_status"] == "Consultation Done"


def test_record_conversion_and_revenue(client, exec_user):
    """Test recording patient conversion transitions lead to 'Converted' and captures revenue."""
    exec_headers, _ = exec_user
    lead = client.post("/api/v1/leads", headers=exec_headers, json={
        "patient_name": "Conversion Patient",
        "primary_phone": "9876500663"
    }).json()

    # Record Conversion
    conv_resp = client.post("/api/v1/conversions", headers=exec_headers, json={
        "lead_id": lead["id"],
        "converted_service": "Complete IVF Package Cycle 1",
        "conversion_value": 185000.0,
        "notes": "Patient paid initial deposit and registered for cycle."
    })
    assert conv_resp.status_code == 201
    conv_data = conv_resp.json()
    assert conv_data["conversion_value"] == 185000.0
    assert conv_data["converted_service"] == "Complete IVF Package Cycle 1"

    # Verify Lead Status is 'Converted'
    updated_lead = client.get(f"/api/v1/leads/{lead['id']}", headers=exec_headers).json()
    assert updated_lead["lead_status"] == "Converted"
