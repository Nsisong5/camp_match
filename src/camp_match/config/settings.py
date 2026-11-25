from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Camp Match API"
    app_env: str = "local"  # local | test | staging | production
    debug: bool = False
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://jasper:what1234@localhost:5432/camp_match_dev"
    database_pool_size: int = 20
    database_max_overflow: int = 30
    database_echo: bool = False
    jwt_secret_key: str = "placeholder-key-for-dev-only-change-in-prod"
    jwt_access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    media_storage_path: str = "./var/media"
    media_access_token_secret: str = "media-secret-key-placeholder"
    media_access_token_ttl_seconds: int = 300
    booking_hold_duration_minutes: int = 30
    payment_auto_release_delay_hours: int = 48
    payment_release_warning_offsets_hours: str = "24,12,3"
    payment_release_warning_min_spacing_minutes: int = 60
    payment_release_final_warning_min_lead_minutes: int = 60
    payment_handover_unconfirmed_alert_hours: int = 168
    admin_tasks_per_source_limit_default: int = 20
    payment_verification_staleness_minutes: int = 15
    saved_listings_max_per_user: int = Field(default=200, ge=1)

    # Payment Provider Settings (C13)
    payment_provider: Literal["mock", "paystack"] = "mock"
    paystack_secret_key: SecretStr | None = None
    paystack_base_url: str = "https://api.paystack.co"
    paystack_callback_url: str | None = None
    paystack_connect_timeout_seconds: float = 5.0
    paystack_read_timeout_seconds: float = 15.0
    payout_account_change_cooloff_hours: int = 24
    bank_resolve_max_per_hour: int = 10
    bank_directory_cache_ttl_seconds: int = 86400
    payment_operation_stale_hours: int = 24
    payment_operation_lookup_grace_minutes: int = 10
    payout_account_prompt_interval_hours: int = 24
    platform_job_payment_payout_account_prompts_interval_seconds: int = 3600

    @model_validator(mode="after")
    def validate_payment_provider_settings(self) -> Settings:
        if self.payment_provider == "paystack":
            if not self.paystack_secret_key or not self.paystack_secret_key.get_secret_value():
                raise ValueError("paystack_secret_key is required when payment_provider is paystack")
            key_val = self.paystack_secret_key.get_secret_value()
            if not (key_val.startswith("sk_test_") or key_val.startswith("sk_live_")):
                raise ValueError("paystack_secret_key must start with sk_test_ or sk_live_")
            if not self.paystack_callback_url:
                raise ValueError("paystack_callback_url is required when payment_provider is paystack")
            if not self.paystack_base_url.startswith("https://"):
                raise ValueError("paystack_base_url must start with https://")
            if self.app_env not in ("local", "test"):
                if not self.paystack_callback_url.startswith("https://"):
                    raise ValueError("paystack_callback_url must start with https:// outside local/test")
                if "api.paystack.co" not in self.paystack_base_url:
                    raise ValueError("paystack_base_url must be api.paystack.co outside local/test")

            if key_val.startswith("sk_live_") and self.app_env != "production":
                raise ValueError("Live Paystack key (sk_live_) cannot be used outside production")
            if key_val.startswith("sk_test_") and self.app_env == "production":
                import structlog
                structlog.get_logger(__name__).warning("paystack_test_key_in_production", message="Test Paystack key (sk_test_) used in production; this deployment cannot take real money.")

        if self.paystack_connect_timeout_seconds <= 0:
            raise ValueError("paystack_connect_timeout_seconds must be positive")
        if self.paystack_read_timeout_seconds <= 0:
            raise ValueError("paystack_read_timeout_seconds must be positive")
        if self.payout_account_change_cooloff_hours < 0:
            raise ValueError("payout_account_change_cooloff_hours must be non-negative")
        if self.bank_resolve_max_per_hour < 1:
            raise ValueError("bank_resolve_max_per_hour must be at least 1")
        if self.bank_directory_cache_ttl_seconds < 60:
            raise ValueError("bank_directory_cache_ttl_seconds must be at least 60")
        if self.payment_operation_stale_hours < 1:
            raise ValueError("payment_operation_stale_hours must be at least 1")
        if self.payment_operation_lookup_grace_minutes < 1:
            raise ValueError("payment_operation_lookup_grace_minutes must be at least 1")
        if self.payout_account_prompt_interval_hours < 1:
            raise ValueError("payout_account_prompt_interval_hours must be at least 1")
        return self

    @model_validator(mode="after")
    def validate_payment_warning_offsets(self) -> Settings:
        try:
            raw_parts = self.payment_release_warning_offsets_hours.split(",")
            offsets = [int(x.strip()) for x in raw_parts if x.strip()]
        except ValueError as e:
            raise ValueError(
                "payment_release_warning_offsets_hours must be comma-separated integers"
            ) from e

        if len(offsets) < 3:
            raise ValueError(
                "payment_release_warning_offsets_hours must contain at least 3 entries"
            )
        if any(o <= 0 for o in offsets):
            raise ValueError(
                "payment_release_warning_offsets_hours entries must be positive integers"
            )
        if any(a <= b for a, b in zip(offsets, offsets[1:], strict=False)):
            raise ValueError(
                "payment_release_warning_offsets_hours must be strictly decreasing"
            )
        if offsets[0] >= self.payment_auto_release_delay_hours:
            raise ValueError(
                "First payment release warning offset must be less than "
                "payment_auto_release_delay_hours"
            )
        if self.payment_auto_release_delay_hours < 2:
            raise ValueError("payment_auto_release_delay_hours must be at least 2")
        if self.payment_release_warning_min_spacing_minutes < 1:
            raise ValueError("payment_release_warning_min_spacing_minutes must be at least 1")
        if self.payment_release_final_warning_min_lead_minutes < 1:
            raise ValueError("payment_release_final_warning_min_lead_minutes must be at least 1")
        if self.payment_handover_unconfirmed_alert_hours < 1:
            raise ValueError("payment_handover_unconfirmed_alert_hours must be at least 1")
        if not (1 <= self.admin_tasks_per_source_limit_default <= 100):
            raise ValueError("admin_tasks_per_source_limit_default must be between 1 and 100")
        return self

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
    messaging_rate_limiter_backend: Literal["in_memory", "postgres"] = "in_memory"
    messaging_realtime_backend: Literal["in_memory", "postgres_notify"] = "in_memory"

    # Platform Reliability Settings (C15)
    platform_outbox_batch_size: int = 50
    platform_outbox_max_attempts: int = 8
    platform_outbox_backoff_base_seconds: int = 5
    platform_outbox_backoff_cap_seconds: int = 300
    platform_outbox_nudge_enabled: bool = True
    platform_debug_disable_nudge: bool = False
    platform_worker_job_timeout_seconds: int = 120
    platform_jobs_disabled: str = "payment_auto_release,payment_release_warnings"
    platform_job_platform_outbox_relay_interval_seconds: int = 3
    platform_job_messaging_outbox_relay_interval_seconds: int = 5
    platform_job_notification_inbox_interval_seconds: int = 15
    platform_job_safety_enforcement_interval_seconds: int = 30
    platform_job_booking_hold_expiry_interval_seconds: int = 60
    platform_job_payment_recovery_interval_seconds: int = 60
    platform_job_payment_auto_release_interval_seconds: int = 3600
    platform_job_payment_release_warnings_interval_seconds: int = 300
    platform_job_payment_review_reconcile_interval_seconds: int = 86400
    platform_job_booking_reminders_interval_seconds: int = 300
    platform_job_suspended_listing_reconcile_interval_seconds: int = 300
    platform_job_retention_sweep_interval_seconds: int = 86400
    platform_job_failure_backoff_cap_seconds: int = 300
    platform_job_failing_after_failures: int = 3
    platform_job_stale_after_multiplier: int = 3
    retention_platform_outbox_days: int = 7
    retention_messaging_outbox_days: int = 7
    retention_notification_inbox_days: int = 14
    retention_notification_read_days: int = 90
    retention_rate_limit_hours: int = 24
    retention_batch_size: int = 500
    booking_invalidation_batch_size: int = 50
    booking_handover_reminder_after_seconds: int = 86400
    booking_acceptance_reminder_after_seconds: int = 86400
    housing_owner_suspension_batch_size: int = 100
    admin_role_grant_requires_second_approver: bool = False
    admin_role_grant_request_ttl_seconds: int = 259200

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

    # Identity / Google Sign-In & Email Verification Settings (Module 17)
    identity_email_verification_required: bool = True
    identity_otp_ttl_seconds: int = Field(default=600, ge=30)
    identity_otp_max_attempts: int = Field(default=5, ge=1)
    identity_otp_resend_cooldown_seconds: int = Field(default=60, ge=0)
    identity_otp_max_sends_per_hour: int = Field(default=5, ge=1)
    google_auth_backend: Literal["disabled", "google", "fake", "both"] = "disabled"
    google_oauth_client_ids: str = ""
    google_require_nonce: bool = False
    google_verify_timeout_seconds: int = Field(default=5, ge=1)
    email_backend: Literal["log", "smtp"] = "log"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_use_starttls: bool = True
    smtp_from_address: str = ""
    smtp_timeout_seconds: int = Field(default=10, ge=1)
    retention_identity_codes_days: int = Field(default=7, ge=1)
    cors_allowed_origins: str = ""

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        if self.cors_allowed_origins:
            parts = [c.strip() for c in self.cors_allowed_origins.split(",")]
            return [p for p in parts if p]
        if self.app_env.lower() in ("local", "test"):
            return ["http://localhost:5500"]
        return []

    @property
    def google_oauth_client_ids_list(self) -> list[str]:
        if not self.google_oauth_client_ids:
            return []
        parts = [c.strip() for c in self.google_oauth_client_ids.split(",")]
        seen = set()
        cleaned = []
        for p in parts:
            if p and p not in seen:
                seen.add(p)
                cleaned.append(p)
        return cleaned

    @model_validator(mode="after")
    def validate_identity_settings(self) -> Settings:
        env = self.app_env.lower()
        is_local_or_test = env in ("local", "test")

        if not self.identity_email_verification_required and not is_local_or_test:
            raise ValueError(
                "identity_email_verification_required can only be false in local or test environments."
            )

        if self.email_backend == "log" and not is_local_or_test:
            raise ValueError("email_backend=log is only allowed in local or test environments.")

        if self.email_backend == "smtp" and (not self.smtp_host or not self.smtp_from_address):
            raise ValueError(
                "email_backend=smtp requires smtp_host and smtp_from_address to be set."
            )

        if self.google_auth_backend in ("fake", "both") and not is_local_or_test:
            raise ValueError(
                f"google_auth_backend={self.google_auth_backend} is only allowed in local or test environments."
            )

        if self.google_auth_backend in ("google", "both"):
            if not self.google_oauth_client_ids_list:
                raise ValueError(
                    f"google_auth_backend={self.google_auth_backend} requires non-empty google_oauth_client_ids."
                )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
