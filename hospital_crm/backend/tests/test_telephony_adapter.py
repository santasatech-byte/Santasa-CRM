"""
Tests for Telephony Abstraction Layer & Phone Number Normalization.
"""
import pytest
from app.adapters.telephony_base import MockTelephonyAdapter, CallInitiateRequest


def test_phone_number_normalization():
    """Verify phone normalization adheres to Indian and international standards."""
    adapter = MockTelephonyAdapter()
    
    # 10-digit Indian standard
    assert adapter.normalize_phone_number("9876543210") == "+919876543210"
    # Indian with leading 0
    assert adapter.normalize_phone_number("09876543210") == "+919876543210"
    # Indian with formatted dashes and spaces
    assert adapter.normalize_phone_number("+91 98765-43210") == "+919876543210"
    # International number
    assert adapter.normalize_phone_number("+14155552671") == "+14155552671"


@pytest.mark.asyncio
async def test_mock_telephony_click_to_call():
    """Verify telephony adapter initiates outbound calls with structured response."""
    adapter = MockTelephonyAdapter()
    request = CallInitiateRequest(
        agent_phone="+919876500001",
        patient_phone="+919876543210",
        lead_id="lead_abc123"
    )
    
    response = await adapter.make_call(request)
    
    assert response.success is True
    assert response.provider_call_id.startswith("mock_call_")
    assert response.status == "initiated"
    assert response.raw_response["lead_id"] == "lead_abc123"
