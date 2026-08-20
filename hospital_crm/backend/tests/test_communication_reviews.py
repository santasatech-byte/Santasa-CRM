"""
Module 23, 24 & 25: WhatsApp Communication & Google Reviews Test Suite
"""
import pytest
from app.core.security import hash_password, create_access_token
from app.modules.administration.models import User, UserRole
from app.modules.leads.models import Lead


@pytest.fixture
def exec_user(db_session):
    u = User(
        email="exec.comm@santasa.com",
        full_name="Communication Exec",
        hashed_password=hash_password("ValidPass123!"),
        role=UserRole.CRM_EXECUTIVE.value,
        is_active=True
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    token = create_access_token(data={"sub": u.id, "email": u.email, "role": u.role})
    return {"Authorization": f"Bearer {token}"}, u


def test_send_whatsapp_template_and_custom(client, exec_user, db_session):
    """Test dispatching pre-approved WhatsApp template and custom message."""
    headers, _ = exec_user
    lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Sayeda Tabasuma",
        "primary_phone": "7676550644"
    }).json()

    # 1. Template Message
    tmpl_resp = client.post("/api/v1/communication/whatsapp/send", headers=headers, json={
        "lead_id": lead["id"],
        "template_name": "appointment_confirmation",
        "template_params": {"time": "Saturday, 11:30 AM", "branch_name": "Hassan"}
    })
    assert tmpl_resp.status_code == 201
    tmpl_data = tmpl_resp.json()
    assert tmpl_data["channel"] == "WhatsApp"
    assert "Sayeda Tabasuma" in tmpl_data["message_body"]
    assert "Saturday, 11:30 AM" in tmpl_data["message_body"]

    # 2. Custom Message
    custom_resp = client.post("/api/v1/communication/whatsapp/send", headers=headers, json={
        "lead_id": lead["id"],
        "custom_body": "Hello Sayeda, your consultation report has been uploaded to your portal."
    })
    assert custom_resp.status_code == 201
    assert "consultation report" in custom_resp.json()["message_body"]


def test_google_review_request_flow(client, exec_user):
    """Test dispatching Google review request link to patient."""
    headers, _ = exec_user
    lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Review Patient",
        "primary_phone": "9876500881"
    }).json()

    rev_resp = client.post("/api/v1/communication/whatsapp/review-request", headers=headers, json={
        "lead_id": lead["id"]
    })
    assert rev_resp.status_code == 201
    rev_data = rev_resp.json()
    assert rev_data["status"] == "Requested"
    assert "google_review_url" in rev_data


def test_whatsapp_webhook_delivery_receipts(client, exec_user):
    """Test webhook updates message status from Sent to Delivered to Read."""
    headers, _ = exec_user
    lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Receipt Patient",
        "primary_phone": "9876500882"
    }).json()

    msg = client.post("/api/v1/communication/whatsapp/send", headers=headers, json={
        "lead_id": lead["id"],
        "custom_body": "Test delivery receipt"
    }).json()
    msg_ext_id = msg["external_message_id"]

    # Delivery Receipt
    d_resp = client.post("/api/v1/communication/whatsapp-webhook", json={
        "message_id": msg_ext_id,
        "status": "delivered"
    })
    assert d_resp.status_code == 200

    # Read Receipt
    r_resp = client.post("/api/v1/communication/whatsapp-webhook", json={
        "message_id": msg_ext_id,
        "status": "read"
    })
    assert r_resp.status_code == 200
