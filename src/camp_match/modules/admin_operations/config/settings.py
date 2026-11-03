from __future__ import annotations

from dataclasses import dataclass

from camp_match.config.settings import get_settings


@dataclass(frozen=True)
class AdminSettings:
    admin_overview_section_timeout_seconds: float = 3.0
    admin_reason_min_length: int = 10
    admin_resolution_min_length: int = 10
    admin_issue_description_max: int = 2000
    admin_audit_uncertain_after_seconds: int = 300
    admin_debug_fail_section: str = ""
    admin_debug_account_action_mode: str = ""

    @classmethod
    def from_env(cls) -> AdminSettings:
        s = get_settings()
        return cls(
            admin_overview_section_timeout_seconds=getattr(
                s, "admin_overview_section_timeout_seconds", 3.0
            ),
            admin_reason_min_length=getattr(s, "admin_reason_min_length", 10),
            admin_resolution_min_length=getattr(s, "admin_resolution_min_length", 10),
            admin_issue_description_max=getattr(s, "admin_issue_description_max", 2000),
            admin_audit_uncertain_after_seconds=getattr(
                s, "admin_audit_uncertain_after_seconds", 300
            ),
            admin_debug_fail_section=getattr(s, "admin_debug_fail_section", ""),
            admin_debug_account_action_mode=getattr(s, "admin_debug_account_action_mode", ""),
        )
