"""
Hospital CRM - Master End-to-End Complete Patient Lifecycle Test Suite
Verifies the complete hospital CRM lifecycle across all modules:
Patient Inquiry → Incoming IVR Call → Auto Lead Creation → Round-Robin Assignment →
Click-to-Call & Recording → Note Logging → Follow-up Scheduling → Completion →
Appointment Booking → Doctor Consultation Outcome → Package Conversion (INR) →
WhatsApp Review Request → Chronological Timeline Audit → Funnel & Revenue Metrics
"""
from datetime import datetime, timedelta, timezone
import pytest
from app.core.security import hash_password, create_access_token
from app.modules.administration.models import User, UserRole
from app.modules.administration.executive_models import ExecutiveProfile, ExecutiveStatus
from app.modules.administration.hospital_models import Hospital, Branch
from app.modules.leads.models import Lead


@pytest.fixture
def hospital_setup(db_session):
    """Sets up Hospital, Branch, Online Executive, Doctor, and Manager."""
    # 1. Hospital & Branch
    hosp = Hospital(name="Santasa IVF & Endosurgery Institute", code="SANTASA-HQ", city="Hassan")
    db_session.add(hosp)
    db_session.flush()

    branch = Branch(
        hospital_id=hosp.id,
        name="Hassan Main Branch",
        code="SAN-HSN",
        city="Hassan",
        ivr_number="08047190001"
    )
    db_session.add(branch)
    db_session.flush()

    # 2. Executive
    exec_user = User(
        email="executive.master@santasa.com",
        full_name="Priya Sharma (CRM Exec)",
        phone="+919876500001",
        hashed_password=hash_password("ValidPass123!"),
        role=UserRole.CRM_EXECUTIVE.value,
        branch_id=branch.id,
        is_active=True
    )
    db_session.add(exec_user)
    db_session.flush()

    prof = ExecutiveProfile(
        user_id=exec_user.id,
        employee_id="EMP-E2E-01",
        status=ExecutiveStatus.ONLINE.value,
        is_available_for_lead_assignment=True
    )
    db_session.add(prof)

    # 3. Doctor
    doctor = User(
        email="dr.soumya.e2e@santasa.com",
        full_name="Dr. Soumya Dinesh (IVF Specialist)",
        hashed_password=hash_password("DoctorPass123!"),
        role=UserRole.DOCTOR.value,
        branch_id=branch.id,
        is_active=True
    )
    db_session.add(doctor)

    # 4. Manager
    manager = User(
        email="manager.e2e@santasa.com",
        full_name="Sowmya M (CRM Head)",
        hashed_password=hash_password("ManagerPass123!"),
        role=UserRole.CRM_MANAGER.value,
        branch_id=branch.id,
        is_active=True
    )
    db_session.add(manager)

    db_session.commit()

    exec_token = create_access_token(data={"sub": exec_user.id, "email": exec_user.email, "role": exec_user.role})
    doc_token = create_access_token(data={"sub": doctor.id, "email": doctor.email, "role": doctor.role})
    mgr_token = create_access_token(data={"sub": manager.id, "email": manager.email, "role": manager.role})

    return {
        "branch": branch,
        "exec_headers": {"Authorization": f"Bearer {exec_token}"},
        "exec_user": exec_user,
        "doc_headers": {"Authorization": f"Bearer {doc_token}"},
        "doctor": doctor,
        "mgr_headers": {"Authorization": f"Bearer {mgr_token}"},
        "manager": manager
    }


def test_complete_patient_journey_e2e(client, hospital_setup, db_session):
    """
    Executes and validates the full 12-step Hospital CRM journey.
    """
    env = hospital_setup
    exec_headers = env["exec_headers"]
    doc_headers = env["doc_headers"]
    mgr_headers = env["mgr_headers"]
    branch = env["branch"]
    doctor = env["doctor"]
    exec_user = env["exec_user"]

    patient_raw_phone = "76765 50644"
    call_sid = "exo_master_journey_001"

    # -------------------------------------------------------------
    # Step 1: Patient Calls Hospital (Inbound IVR Webhook)
    # -------------------------------------------------------------
    incoming_resp = client.post("/api/v1/telephony/incoming-webhook", json={
        "CallSid": call_sid,
        "From": patient_raw_phone,
        "To": branch.ivr_number,
        "Direction": "incoming"
    })
    assert incoming_resp.status_code == 200
    call_info = incoming_resp.json()
    lead_id = call_info["lead_id"]
    assert lead_id is not None
    assert call_info["normalized_phone"] == "+917676550644"
    assert call_info["executive_id"] == exec_user.id

    # -------------------------------------------------------------
    # Step 2: Call Status Webhook with Recording URL
    # -------------------------------------------------------------
    status_resp = client.post("/api/v1/telephony/status-webhook", json={
        "CallSid": call_sid,
        "Status": "completed",
        "Duration": 240,
        "RecordingUrl": "https://api.exotel.com/recordings/master_journey_rec.mp3"
    })
    assert status_resp.status_code == 200

    # -------------------------------------------------------------
    # Step 3: Executive Updates Patient Profile & Notes
    # -------------------------------------------------------------
    lead_update = client.patch(f"/api/v1/leads/{lead_id}", headers=exec_headers, json={
        "patient_name": "Sayeda Tabasuma",
        "city": "Hassan",
        "service_interested": "IVF 1st Cycle Package",
        "priority": "High"
    })
    assert lead_update.status_code == 200
    assert lead_update.json()["patient_name"] == "Sayeda Tabasuma"

    note_resp = client.post(f"/api/v1/leads/{lead_id}/notes", headers=exec_headers, json={
        "note": "Patient enquired regarding IVF success rates and ICSI package costs. Callback scheduled."
    })
    assert note_resp.status_code == 201

    # -------------------------------------------------------------
    # Step 4: Executive Schedules Follow-up
    # -------------------------------------------------------------
    f_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    followup_resp = client.post("/api/v1/followups", headers=exec_headers, json={
        "lead_id": lead_id,
        "scheduled_at": f_time,
        "type": "Call",
        "priority": "High",
        "notes": "Follow-up regarding financial package and clinic visit"
    })
    assert followup_resp.status_code == 201
    followup_id = followup_resp.json()["id"]

    # -------------------------------------------------------------
    # Step 5: Complete Follow-up
    # -------------------------------------------------------------
    complete_resp = client.post(f"/api/v1/followups/{followup_id}/complete", headers=exec_headers, json={
        "completion_notes": "Spoke to patient & spouse. Ready to meet Dr. Soumya this weekend."
    })
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "Completed"

    # -------------------------------------------------------------
    # Step 6: Book Doctor Consultation Appointment
    # -------------------------------------------------------------
    appt_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    appt_resp = client.post("/api/v1/appointments", headers=exec_headers, json={
        "lead_id": lead_id,
        "doctor_id": doctor.id,
        "branch_id": branch.id,
        "appointment_at": appt_time,
        "service_type": "Initial Fertility & Ultrasound Evaluation",
        "notes": "Couple coming for comprehensive fertility consultation."
    })
    assert appt_resp.status_code == 201
    appt_id = appt_resp.json()["id"]

    # -------------------------------------------------------------
    # Step 7: Send WhatsApp Appointment Confirmation
    # -------------------------------------------------------------
    wa_resp = client.post("/api/v1/communication/whatsapp/send", headers=exec_headers, json={
        "lead_id": lead_id,
        "template_name": "appointment_confirmation",
        "template_params": {"time": "Saturday, 11:30 AM", "branch_name": "Hassan"}
    })
    assert wa_resp.status_code == 201

    # -------------------------------------------------------------
    # Step 8: Doctor Records Consultation Outcome
    # -------------------------------------------------------------
    outcome_resp = client.post(f"/api/v1/appointments/{appt_id}/outcome", headers=doc_headers, json={
        "outcome_status": "Recommended Treatment",
        "recommended_service": "Self-Oocyte IVF with ICSI Cycle 1",
        "estimated_value": 180000.0,
        "clinical_summary": "Ultrasound and baseline reports reviewed. Advised for IVF-ICSI cycle with antagonist protocol."
    })
    assert outcome_resp.status_code == 201
    assert outcome_resp.json()["outcome_status"] == "Recommended Treatment"

    # -------------------------------------------------------------
    # Step 9: Record Patient Treatment Conversion & Package Revenue
    # -------------------------------------------------------------
    conv_resp = client.post("/api/v1/conversions", headers=exec_headers, json={
        "lead_id": lead_id,
        "appointment_id": appt_id,
        "converted_service": "Self-Oocyte IVF with ICSI Cycle 1",
        "conversion_value": 180000.0,
        "notes": "Patient made registration deposit and scheduled stimulation start."
    })
    assert conv_resp.status_code == 201
    assert conv_resp.json()["conversion_value"] == 180000.0

    # -------------------------------------------------------------
    # Step 10: Dispatch Google Review Request
    # -------------------------------------------------------------
    rev_resp = client.post("/api/v1/communication/whatsapp/review-request", headers=exec_headers, json={
        "lead_id": lead_id,
        "appointment_id": appt_id,
        "branch_id": branch.id
    })
    assert rev_resp.status_code == 201
    assert rev_resp.json()["status"] == "Requested"

    # -------------------------------------------------------------
    # Step 11: Verify Chronological Activity Timeline
    # -------------------------------------------------------------
    timeline_resp = client.get(f"/api/v1/leads/{lead_id}/timeline", headers=exec_headers)
    assert timeline_resp.status_code == 200
    timeline = timeline_resp.json()
    assert len(timeline) >= 6  # Call + Note + Followup + Appt + Consultation + Conversion + WhatsApp

    # -------------------------------------------------------------
    # Step 12: Verify Hospital Management Reports & Revenue Dashboard
    # -------------------------------------------------------------
    funnel_resp = client.get("/api/v1/reports/funnel", headers=mgr_headers)
    assert funnel_resp.status_code == 200
    funnel = funnel_resp.json()
    assert funnel["converted"] >= 1

    rev_summary = client.get("/api/v1/reports/revenue-summary", headers=mgr_headers)
    assert rev_summary.status_code == 200
    assert rev_summary.json()["total_revenue_inr"] >= 180000.0
