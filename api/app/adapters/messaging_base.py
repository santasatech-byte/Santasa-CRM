"""
Hospital CRM - Messaging Provider Abstraction Interface
Decouples CRM from WhatsApp & Email providers (Meta Cloud API, Gupshup, Twilio, Sendgrid).
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OutgoingMessage(BaseModel):
    recipient_phone_or_email: str
    template_name: Optional[str] = None
    template_params: Dict[str, Any] = Field(default_factory=dict)
    body: Optional[str] = None
    lead_id: Optional[str] = None


class MessageSendResponse(BaseModel):
    success: bool
    provider_message_id: str
    status: str
    error: Optional[str] = None


class WhatsAppProvider(ABC):
    """Abstract Base Class for WhatsApp Providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    async def send_message(self, message: OutgoingMessage) -> MessageSendResponse:
        pass

    @abstractmethod
    async def parse_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def verify_webhook(self, payload_bytes: bytes, signature: str) -> bool:
        pass


class MockWhatsAppAdapter(WhatsAppProvider):
    @property
    def provider_name(self) -> str:
        return "mock"

    async def send_message(self, message: OutgoingMessage) -> MessageSendResponse:
        import uuid
        return MessageSendResponse(
            success=True,
            provider_message_id=f"mock_wa_{uuid.uuid4().hex[:12]}",
            status="sent"
        )

    async def parse_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        return {"event": "delivered", "payload": payload}

    def verify_webhook(self, payload_bytes: bytes, signature: str) -> bool:
        return True
