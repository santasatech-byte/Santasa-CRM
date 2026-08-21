"""
Hospital CRM - Telephony Provider Factory
Dynamically instantiates and returns the configured telephony adapter.
"""
from app.core.config import settings
from app.adapters.telephony_base import TelephonyProvider, MockTelephonyAdapter
from app.adapters.exotel_adapter import ExotelAdapter


def get_telephony_provider(provider_name: str = None) -> TelephonyProvider:
    """Factory resolving the active TelephonyProvider adapter."""
    name = (provider_name or settings.TELEPHONY_PROVIDER).lower().strip()
    
    if name == "exotel":
        return ExotelAdapter()
    elif name in ["mock", "test"]:
        return MockTelephonyAdapter()
    else:
        # Default fallback to mock adapter
        return MockTelephonyAdapter()
