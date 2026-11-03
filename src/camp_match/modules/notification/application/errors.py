"""Notification application errors."""
from __future__ import annotations

from camp_match.shared_kernel.application.errors import NotFoundError


class NotificationNotFound(NotFoundError):
    code = "notification_not_found"
