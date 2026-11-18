from __future__ import annotations

from collections.abc import Callable
from typing import Any

from camp_match.modules.platform_runtime.adapters.jobs.booking_hold_expiry import (
    build_booking_hold_expiry_job,
)
from camp_match.modules.platform_runtime.adapters.jobs.booking_reminders import (
    build_booking_reminders_job,
)
from camp_match.modules.platform_runtime.adapters.jobs.messaging_outbox_relay import (
    build_messaging_outbox_relay_job,
)
from camp_match.modules.platform_runtime.adapters.jobs.notification_inbox import (
    build_notification_inbox_job,
)
from camp_match.modules.platform_runtime.adapters.jobs.payment_auto_release import (
    build_payment_auto_release_job,
)
from camp_match.modules.platform_runtime.adapters.jobs.payment_recovery import (
    build_payment_recovery_job,
)
from camp_match.modules.platform_runtime.adapters.jobs.payment_release_warnings import (
    build_payment_release_warnings_job,
)
from camp_match.modules.platform_runtime.adapters.jobs.payment_review_reconcile import (
    build_payment_review_reconcile_job,
)
from camp_match.modules.platform_runtime.adapters.jobs.platform_outbox_relay import (
    build_platform_outbox_relay_job,
)
from camp_match.modules.platform_runtime.adapters.jobs.safety_enforcement import (
    build_safety_enforcement_job,
)
from camp_match.modules.platform_runtime.adapters.jobs.suspended_listing_reconcile import (
    build_suspended_listing_reconcile_job,
)
from camp_match.modules.platform_runtime.adapters.jobs.retention_sweep import (
    build_retention_sweep_job,
)


def get_job_registry(settings: Any) -> dict[str, tuple[int, Callable[..., Any]]]:
    return {
        "platform_outbox_relay": (
            settings.platform_job_platform_outbox_relay_interval_seconds,
            build_platform_outbox_relay_job,
        ),
        "messaging_outbox_relay": (
            settings.platform_job_messaging_outbox_relay_interval_seconds,
            build_messaging_outbox_relay_job,
        ),
        "notification_inbox": (
            settings.platform_job_notification_inbox_interval_seconds,
            build_notification_inbox_job,
        ),
        "safety_enforcement": (
            settings.platform_job_safety_enforcement_interval_seconds,
            build_safety_enforcement_job,
        ),
        "booking_hold_expiry": (
            settings.platform_job_booking_hold_expiry_interval_seconds,
            build_booking_hold_expiry_job,
        ),
        "booking_reminders": (
            settings.platform_job_booking_reminders_interval_seconds,
            build_booking_reminders_job,
        ),
        "suspended_listing_reconcile": (
            settings.platform_job_suspended_listing_reconcile_interval_seconds,
            build_suspended_listing_reconcile_job,
        ),
        "payment_recovery": (
            settings.platform_job_payment_recovery_interval_seconds,
            build_payment_recovery_job,
        ),
        "payment_auto_release": (
            settings.platform_job_payment_auto_release_interval_seconds,
            build_payment_auto_release_job,
        ),
        "payment_release_warnings": (
            getattr(settings, "platform_job_payment_release_warnings_interval_seconds", 300),
            build_payment_release_warnings_job,
        ),
        "payment_review_reconcile": (
            getattr(settings, "platform_job_payment_review_reconcile_interval_seconds", 86400),
            build_payment_review_reconcile_job,
        ),
        "retention_sweep": (
            getattr(settings, "platform_job_retention_sweep_interval_seconds", 86400),
            build_retention_sweep_job,
        ),
    }
