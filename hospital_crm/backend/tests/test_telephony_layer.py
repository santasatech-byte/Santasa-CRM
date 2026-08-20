"""
Module 10: Telephony Abstraction Layer Test Suite
"""
import hashlib
import hmac
import pytest
from app.adapters.telephony_base import MockTelephonyAdapter, CallInitiateRequest
from app.adapters.exotel_adapter import ExotelAdapter
from app.adapters.telephony_factory import get_telephony_provider


def test_telephony_factory_resolution():
    """Verify factory returns appropriate provider instance."""
    mock_p = get_telephony_provider("mock")
    assert isinstance(mock_p, MockTelephonyAdapter)
    assert mock_p.provider_name == "mock"

    exo_p = get_telephony_provider("exotel")
    assert isinstance(exo_p, ExotelAdapter)
    assert exo_p.provider_name == "exotel"


@pytest.mark.asyncio
async def test_exotel_adapter_make_call_and_webhook():
    """Test Exotel click-to-call flow and webhook parsing."""
    adapter = ExotelAdapter(webhook_secret="test_secret_123")
    
    # 1. Click-to-call
    req = CallInitiateRequest(
        agent_phone="9876500001",
        patient_phone="7676550644",
        lead_id="lead_100"
    )
    call_resp = await adapter.make_call(req)
    assert call_resp.success is True
    assert call_resp.provider_call_id.startswith("exo_")
    assert call_resp.status == "initiated"

    # 2. Webhook Parsing
    raw_payload = {
        "CallSid": call_resp.provider_call_id,
        "Status": "completed",
        "Duration": "180",
        "RecordingUrl": "https://api.exotel.com/storage/rec_100.mp3"
    }
    event = await adapter.parse_webhook(raw_payload, headers={})
    assert event.provider_call_id == call_resp.provider_call_id
    assert event.status == "completed"
    assert event.duration_seconds == 180
    assert "rec_100.mp3" in event.recording_url


def test_webhook_hmac_signature_verification():
    """Test HMAC SHA256 webhook signature security validation."""
    adapter = ExotelAdapter(webhook_secret="super_secret_webhook_key")
    payload = b'{"CallSid":"exo_123","Status":"completed"}'

    # Compute valid signature
    valid_sig = hmac.new(b"super_secret_webhook_key", payload, hashlib.sha256).hexdigest()
    assert adapter.verify_webhook_signature(payload, valid_sig) is True

    # Tampered signature should be rejected
    assert adapter.verify_webhook_signature(payload, "invalid_forged_signature") is False
    assert adapter.verify_webhook_signature(payload, "") is False
