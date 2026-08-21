"""
Hospital CRM - Telephony Provider Abstraction Interface
Decouples CRM core from specific providers (Exotel, Twilio, Asterisk, Mock).
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import re
from pydantic import BaseModel, Field


class CallInitiateRequest(BaseModel):
    agent_phone: str
    patient_phone: str
    lead_id: Optional[str] = None
    custom_tags: Dict[str, Any] = Field(default_factory=dict)


class CallResponse(BaseModel):
    success: bool
    provider_call_id: str
    status: str
    message: Optional[str] = None
    raw_response: Dict[str, Any] = Field(default_factory=dict)


class WebhookEvent(BaseModel):
    event_type: str
    provider_call_id: str
    status: str
    duration_seconds: Optional[int] = 0
    recording_url: Optional[str] = None
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


class TelephonyProvider(ABC):
    """Abstract Base Class for all Telephony Provider Adapters."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of telephony provider (e.g. 'mock', 'exotel', 'twilio')."""
        pass

    @abstractmethod
    async def make_call(self, request: CallInitiateRequest) -> CallResponse:
        """Initiate outbound click-to-call between executive and patient."""
        pass

    @abstractmethod
    async def parse_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> WebhookEvent:
        """Parse incoming provider webhook payload into a normalized WebhookEvent."""
        pass

    @abstractmethod
    def verify_webhook_signature(self, payload_bytes: bytes, signature: str) -> bool:
        """Verify authenticity of webhook callback signature."""
        pass

    @abstractmethod
    async def get_call_status(self, provider_call_id: str) -> Dict[str, Any]:
        """Fetch real-time call status from provider."""
        pass

    @abstractmethod
    async def get_recording_url(self, provider_call_id: str) -> Optional[str]:
        """Fetch signed or direct recording URL from provider."""
        pass

    def normalize_phone_number(self, phone: str, default_country: str = "IN") -> str:
        """
        Normalize phone numbers into standard E.164-compatible format.
        Preserves original digits while stripping whitespace and special chars.
        """
        cleaned = re.sub(r"[^\d+]", "", phone.strip())
        
        # Handle Indian numbers (+91)
        if default_country == "IN":
            if cleaned.startswith("+91"):
                cleaned = cleaned[3:]
            elif cleaned.startswith("0") and len(cleaned) == 11:
                cleaned = cleaned[1:]
            
            if len(cleaned) == 10 and cleaned.isdigit():
                return f"+91{cleaned}"
        
        if not cleaned.startswith("+") and cleaned:
            return f"+{cleaned}"
        return cleaned


class MockTelephonyAdapter(TelephonyProvider):
    """Mock implementation for testing, CI/CD, and local development."""

    @property
    def provider_name(self) -> str:
        return "mock"

    async def make_call(self, request: CallInitiateRequest) -> CallResponse:
        import uuid
        call_id = f"mock_call_{uuid.uuid4().hex[:12]}"
        return CallResponse(
            success=True,
            provider_call_id=call_id,
            status="initiated",
            message="Mock call initiated successfully",
            raw_response={"mock": True, "lead_id": request.lead_id}
        )

    async def parse_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> WebhookEvent:
        return WebhookEvent(
            event_type=payload.get("event_type", "call_status"),
            provider_call_id=payload.get("call_id", "mock_call_001"),
            status=payload.get("status", "completed"),
            duration_seconds=payload.get("duration", 60),
            recording_url=payload.get("recording_url", "https://crm.local/storage/mock_rec.mp3"),
            raw_payload=payload
        )

    def verify_webhook_signature(self, payload_bytes: bytes, signature: str) -> bool:
        return True

    async def get_call_status(self, provider_call_id: str) -> Dict[str, Any]:
        return {"provider_call_id": provider_call_id, "status": "completed", "duration": 120}

    async def get_recording_url(self, provider_call_id: str) -> Optional[str]:
        return f"https://crm.local/storage/recordings/{provider_call_id}.mp3"
