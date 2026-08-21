"""
Hospital CRM - Application Configuration
Pydantic Settings with full environment variable support and validation.
"""
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core Application
    APP_NAME: str = "Hospital Lead & Follow-up CRM"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    SECRET_KEY: str = "dev-secret-key-change-in-production-hospital-crm"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # Database
    DATABASE_URL: str = "postgresql://postgres.vdwpxcdpzhreonutitrc:cmW7zEtAJH5ziFyo@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

    # Redis & Workers
    REDIS_URL: str = "redis://localhost:6379/0"
    USE_IN_MEMORY_QUEUE: bool = True

    # Telephony Provider Configuration
    TELEPHONY_PROVIDER: str = "mock"
    TELEPHONY_API_KEY: Optional[str] = None
    TELEPHONY_API_SECRET: Optional[str] = None
    TELEPHONY_ACCOUNT_SID: Optional[str] = None
    TELEPHONY_WEBHOOK_SECRET: str = "whsec_mock_telephony_secret"

    # WhatsApp Provider Configuration
    WHATSAPP_PROVIDER: str = "mock"
    WHATSAPP_API_KEY: Optional[str] = None
    WHATSAPP_WEBHOOK_SECRET: str = "whsec_mock_whatsapp_secret"

    # Storage
    RECORDING_STORAGE_TYPE: str = "supabase"
    RECORDING_STORAGE_PATH: str = "./storage/recordings"

    # Supabase Integration (Database & Audio Storage)
    SUPABASE_URL: Optional[str] = "https://vdwpxcdpzhreonutitrc.supabase.co"
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkd3B4Y2RwemhyZW9udXRpdHJjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjY3OTQ0OSwiZXhwIjoyMTAyMjU1NDQ5fQ.e_H5V4N7x94W5iV8d-aU9QW6zE2oP4Y3bK8X1jM0rNs"
    SUPABASE_STORAGE_BUCKET: str = "call-recordings"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"


settings = Settings()
