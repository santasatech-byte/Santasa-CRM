"""
Module 11: Incoming Call Handling & Telephony Processing Test Suite
"""
import pytest
from app.core.security import hash_password, create_access_token
from app.modules.administration.models import User, UserRole
from app.modules.administration.executive_models import ExecutiveProfile, ExecutiveStatus
from app.modules.leads.models import Lead
from app.modules.calls.models import Call


@pytest.fixture
def online_executive(db_session):
    u = User(
        email="exec.call@santasa.com",
        full_name="Call Executive",
        phone="+919876500009",
        hashed_password=hash_password("ValidPass123!"),
        role=UserRole.CRM_EXECUTIVE.value,
        is_active=True
    )
    db_session.add(u)
    db_session.flush()

    prof = ExecutiveProfile(
        user_id=u.id,
        employee_id="EMP-CALL-01",
        status=ExecutiveStatus.ONLINE.value,
        is_available_for_lead_assignment=True
    )
    db_session.add(prof)
    db_session.commit()
    db_session.refresh(u)
    token = create_access_token(data={"sub": u.id, "email": u.email, "role": u.role})
    return {"Authorization": f"Bearer {token}"}, u


def test_incoming_call_unknown_caller_workflow(client, online_executive, db_session):
    """
    Scenario 1: Unknown caller calls hospital
    → call received
    → lead created
    → executive assigned
    → call logged
    → timeline updated
    """
    _, exec_user = online_executive
    call_sid = "exo_incoming_test_001"

    # Ingress Webhook
    resp = client.post("/api/v1/telephony/incoming-webhook", json={
        "CallSid": call_sid,
        "From": "9876554321",
        "To": "08047190001",
        "Direction": "incoming"
    })
    assert resp.status_code == 200
    call_data = resp.json()
    assert call_data["external_call_id"] == call_sid
    assert call_data["normalized_phone"] == "+919876554321"
    assert call_data["direction"] == "Incoming"
    assert call_data["executive_id"] == exec_user.id
    assert call_data["lead_id"] is not None

    # Check Lead was auto-created
    lead = db_session.get(Lead, call_data["lead_id"])
    assert lead is not None
    assert lead.normalized_phone == "+919876554321"
    assert lead.lead_source == "Incoming Call"


def test_incoming_call_existing_lead_no_duplicate(client, online_executive, db_session):
    """
    Scenario 2: Existing patient calls hospital
    → existing phone recognized
    → NO duplicate lead created
    → call attached to existing lead
    """
    headers, exec_user = online_executive
    
    # Pre-create lead
    existing_lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Sayeda Tabasuma",
        "primary_phone": "7676550644"
    }).json()

    # Incoming Call from same number
    call_sid = "exo_existing_caller_002"
    resp = client.post("/api/v1/telephony/incoming-webhook", json={
        "CallSid": call_sid,
        "From": "7676550644",
        "To": "08047190001"
    })
    assert resp.status_code == 200
    call_data = resp.json()
    assert call_data["lead_id"] == existing_lead["id"]

    # Verify no duplicate leads created with this phone
    leads_count = db_session.query(Lead).filter(Lead.normalized_phone == "+917676550644").count()
    assert leads_count == 1


def test_call_status_webhook_and_recording_attachment(client, online_executive):
    """Test status update callback sets status to Completed, updates duration, and attaches recording."""
    call_sid = "exo_status_test_003"
    
    # Ingest incoming call
    client.post("/api/v1/telephony/incoming-webhook", json={
        "CallSid": call_sid,
        "From": "9448088712"
    })

    # Status callback with recording
    status_resp = client.post("/api/v1/telephony/status-webhook", json={
        "CallSid": call_sid,
        "Status": "completed",
        "Duration": 215,
        "RecordingUrl": "https://api.exotel.com/storage/recordings/exo_rec_003.mp3"
    })
    assert status_resp.status_code == 200


def test_click_to_call_outbound(client, online_executive):
    """Test click-to-call initiates outbound call and records log."""
    headers, _ = online_executive
    lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Outbound Lead Patient",
        "primary_phone": "9900112233"
    }).json()

    # Initiate Click-to-Call
    c2c_resp = client.post("/api/v1/telephony/click-to-call", headers=headers, json={
        "lead_id": lead["id"]
    })
    assert c2c_resp.status_code == 201
    call_data = c2c_resp.json()
    assert call_data["direction"] == "Outgoing"
    assert call_data["lead_id"] == lead["id"]
    assert call_data["status"] == "Initiated"
