from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Camp Match API"
    app_env: str = "local"  # local | test | staging | production
    debug: bool = False
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://jasper:what1234@localhost:5432/camp_match_dev"
    database_pool_size: int = 5
    database_echo: bool = False
    jwt_secret_key: str = "placeholder-key-for-dev-only-change-in-prod"
    jwt_access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    media_storage_path: str = "./var/media"
    media_access_token_secret: str = "media-secret-key-placeholder"
    media_access_token_ttl_seconds: int = 300
    booking_hold_duration_minutes: int = 30
    payment_release_fallback_hours: int = 48
    payment_verification_staleness_minutes: int = 15

    # Messaging Settings (C8)
    messaging_max_message_length: int = 2000
    messaging_history_default_limit: int = 30
    messaging_history_max_limit: int = 100
    messaging_send_rate_limit: int = 30
    messaging_send_rate_window_seconds: int = 60
    messaging_create_rate_limit: int = 10
    messaging_create_rate_window_seconds: int = 60
    messaging_ws_auth_ttl_seconds: int = 900
    messaging_ws_connect_rate_limit: int = 10
    messaging_ws_auth_timeout_seconds: float = 10.0
    messaging_ws_idle_timeout_seconds: float = 90.0
    messaging_ws_max_connections_per_user: int = 5
    messaging_ws_max_subscriptions_per_connection: int = 50
    messaging_ws_command_rate_limit: int = 30
    messaging_ws_reauth_grace_seconds: float = 60.0
    messaging_ws_max_frame_bytes: int = 16384
    messaging_debug_failing_subscriber: bool = False
    messaging_outbox_batch_size: int = 50
    messaging_realtime_backend: Literal["in_memory"] = "in_memory"

    # Notification Settings (C10)
    notification_inbox_max_attempts: int = 8
    notification_inbox_backoff_base_seconds: int = 30
    notification_inbox_backoff_cap_seconds: int = 3600
    notification_worker_batch_size: int = 100
    notification_debug_fail_processing: bool = False

    # Trust & Safety Settings (C10)
    safety_report_rate_limit_count: int = 5
    safety_report_rate_limit_window_seconds: int = 86400
    safety_report_description_min: int = 10
    safety_report_description_max: int = 2000
    safety_max_reported_messages: int = 5
    safety_note_max_length: int = 4000
    safety_rationale_min: int = 20
    safety_rationale_max: int = 4000
    safety_restriction_max_days: int = 90
    safety_enforcement_max_attempts: int = 6
    safety_enforcement_backoff_base_seconds: int = 60
    safety_enforcement_backoff_cap_seconds: int = 3600
    safety_worker_batch_size: int = 100
    safety_debug_fail_enforcement: bool = False

    # Admin & Operations Settings (C10)
    admin_overview_section_timeout_seconds: float = 3.0
    admin_reason_min_length: int = 10
    admin_resolution_min_length: int = 10
    admin_issue_description_max: int = 2000
    admin_audit_uncertain_after_seconds: int = 300
    admin_debug_fail_section: str = ""
    admin_debug_account_action_mode: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
