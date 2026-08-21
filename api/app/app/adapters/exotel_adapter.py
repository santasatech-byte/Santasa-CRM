"""
Hospital CRM - Exotel Telephony Provider Adapter
Implements Exotel Click-to-Call REST API and Passthru Applet webhook parsing.
"""
import hashlib
import hmac
from typing import Any, Dict, Optional
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.core.errors import TelephonyProviderError
from app.adapters.telephony_base import (
    TelephonyProvider,
    CallInitiateRequest,
    CallResponse,
    WebhookEvent,
)


class ExotelAdapter(TelephonyProvider):
    def __init__(
        self,
        account_sid: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        webhook_secret: Optional[str] = None
    ):
        self.account_sid = account_sid or settings.TELEPHONY_ACCOUNT_SID or "dummy_exotel_sid"
        self.api_key = api_key or settings.TELEPHONY_API_KEY or "dummy_exotel_key"
        self.api_secret = api_secret or settings.TELEPHONY_API_SECRET or "dummy_exotel_secret"
        self.webhook_secret = webhook_secret or settings.TELEPHONY_WEBHOOK_SECRET

    @property
    def provider_name(self) -> str:
        return "exotel"

    async def make_call(self, request: CallInitiateRequest) -> CallResponse:
        """
        Initiates an outbound Click-to-Call connection via Exotel Voice API.
        Executive endpoint is dialed first; once answered, patient endpoint is connected.
        """
        endpoint = f"https://api.exotel.com/v1/Accounts/{self.account_sid}/Calls/connect.json"
        
        payload = {
            "From": self.normalize_phone_number(request.agent_phone),
            "To": self.normalize_phone_number(request.patient_phone),
            "CallerId": self.normalize_phone_number(request.agent_phone),
            "CallType": "trans",
            "CustomField": request.lead_id or ""
        }

        # If running in mock / test environment, return simulated Exotel response
        if settings.APP_ENV in ["development", "testing"] or "dummy" in self.account_sid:
            import uuid
            mock_call_sid = f"exo_{uuid.uuid4().hex[:16]}"
            return CallResponse(
                success=True,
                provider_call_id=mock_call_sid,
                status="initiated",
                message="Exotel call connected to executive endpoint",
                raw_response={"Call": {"Sid": mock_call_sid, "Status": "in-progress"}}
            )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    endpoint,
                    data=payload,
                    auth=(self.api_key, self.api_secret)
                )
                if res.status_code not in [200, 201]:
                    raise TelephonyProviderError("exotel", f"HTTP {res.status_code}: {res.text}")
                data = res.json().get("Call", {})
                return CallResponse(
                    success=True,
                    provider_call_id=data.get("Sid", "unknown_exo_sid"),
                    status="initiated",
                    raw_response=res.json()
                )
        except Exception as e:
            logger.error(f"Exotel make_call failed: {str(e)}", exc_info=True)
            raise TelephonyProviderError("exotel", str(e))

    async def parse_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> WebhookEvent:
        """Parses Exotel CallStatus or Passthru webhook payload."""
        call_sid = payload.get("CallSid") or payload.get("Sid") or payload.get("call_id", "")
        status = payload.get("Status") or payload.get("status", "completed")
        duration = int(payload.get("Duration") or payload.get("duration", 0))
        recording_url = payload.get("RecordingUrl") or payload.get("recording_url")

        return WebhookEvent(
            event_type="call_status",
            provider_call_id=call_sid,
            status=status.lower(),
            duration_seconds=duration,
            recording_url=recording_url,
            raw_payload=payload
        )

    def verify_webhook_signature(self, payload_bytes: bytes, signature: str) -> bool:
        """Verifies HMAC SHA256 webhook signature."""
        if not signature:
            return False
        expected_sig = hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_sig, signature)

    async def get_call_status(self, provider_call_id: str) -> Dict[str, Any]:
        return {"provider_call_id": provider_call_id, "provider": "exotel", "status": "completed"}

    async def get_recording_url(self, provider_call_id: str) -> Optional[str]:
        return f"https://api.exotel.com/v1/Accounts/{self.account_sid}/Recordings/{provider_call_id}"
