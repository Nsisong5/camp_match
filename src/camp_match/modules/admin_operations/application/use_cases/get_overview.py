from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, cast

import structlog

from camp_match.modules.admin_operations.application.ports.inbound import (
    OverviewSectionView,
    OverviewView,
)
from camp_match.modules.admin_operations.domain.value_objects import SectionStatus
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class GetOverviewUseCase:
    def __init__(
        self,
        verification_source: Any,
        payment_source: Any,
        safety_source: Any,
        notification_source: Any,
        messaging_source: Any,
        issue_repo: Any,
        audit_repo: Any,
        authorizer: Any,
        uow_factory: Any,
        clock: Any,
        settings: Any,
    ) -> None:
        self._verification_source = verification_source
        self._payment_source = payment_source
        self._safety_source = safety_source
        self._notification_source = notification_source
        self._messaging_source = messaging_source
        self._issue_repo = issue_repo
        self._audit_repo = audit_repo
        self._authorizer = authorizer
        self._uow_factory = uow_factory
        self._clock = clock
        self._settings = settings

    async def execute(self, actor_id: EntityId) -> OverviewView:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_OVERVIEW_VIEW)

        timeout = getattr(
            self._settings, "admin_overview_section_timeout_seconds", 3.0
        )
        fail_section = getattr(self._settings, "admin_debug_fail_section", "")
        app_env = getattr(self._settings, "app_env", "local")

        def check_debug_fail(section_name: str) -> None:
            if app_env in {"local", "test"} and fail_section == section_name:
                raise RuntimeError(
                    f"Debug forced failure for section {section_name}"
                )

        async def run_section(
            name: str, coroutine_func: Any
        ) -> OverviewSectionView:
            try:
                check_debug_fail(name)
                async with self._uow_factory():
                    data = await asyncio.wait_for(
                        coroutine_func(), timeout=timeout
                    )
                as_of = self._clock.now()
                return OverviewSectionView(
                    name=name,
                    status=SectionStatus.OK,
                    as_of=as_of,
                    data=data,
                    reason_code=None,
                )
            except Exception as e:
                as_of = self._clock.now()
                err_str = str(e).lower()
                is_forbidden = (
                    "forbidden" in err_str
                    or "unauthorized" in err_str
                    or "not permitted" in err_str
                    or isinstance(e, PermissionError)
                    or getattr(e, "code", None) == "forbidden"
                )
                if is_forbidden:
                    return OverviewSectionView(
                        name=name,
                        status=SectionStatus.NOT_AUTHORIZED,
                        as_of=as_of,
                        data=None,
                        reason_code=None,
                    )
                elif isinstance(e, asyncio.TimeoutError):
                    return OverviewSectionView(
                        name=name,
                        status=SectionStatus.UNAVAILABLE,
                        as_of=as_of,
                        data=None,
                        reason_code="timeout",
                    )
                else:
                    logger.warning(
                        "overview_section_unavailable",
                        section=name,
                        error_class=e.__class__.__name__,
                    )
                    return OverviewSectionView(
                        name=name,
                        status=SectionStatus.UNAVAILABLE,
                        as_of=as_of,
                        data=None,
                        reason_code="source_error",
                    )

        async def fetch_verification() -> dict[str, Any]:
            res = await self._verification_source.fetch(actor_id)
            return cast(dict[str, Any], res)

        verification_sec = await run_section("verification", fetch_verification)

        async def fetch_payments() -> dict[str, Any]:
            res = await self._payment_source.fetch(actor_id)
            return cast(dict[str, Any], res)

        payments_sec = await run_section("payments", fetch_payments)

        async def fetch_safety() -> dict[str, Any]:
            res = await self._safety_source.fetch(actor_id)
            return cast(dict[str, Any], res)

        safety_sec = await run_section("safety", fetch_safety)

        async def fetch_notifications() -> dict[str, Any]:
            res = await self._notification_source.fetch()
            return cast(dict[str, Any], res)

        notifications_sec = await run_section(
            "notifications", fetch_notifications
        )

        async def fetch_messaging() -> dict[str, Any]:
            res = await self._messaging_source.fetch()
            return cast(dict[str, Any], res)

        messaging_sec = await run_section("messaging", fetch_messaging)

        async def fetch_issues() -> dict[str, Any]:
            counts = await self._issue_repo.counts_by_status()
            unassigned = await self._issue_repo.count_unassigned_open()
            high_pri = await self._issue_repo.count_high_priority_open()
            return {
                "open_by_status": counts,
                "unassigned_open": unassigned,
                "high_priority_open": high_pri,
            }

        issues_sec = await run_section("issues", fetch_issues)

        async def fetch_admin_actions() -> dict[str, Any]:
            try:
                await self._authorizer.authorize(
                    actor_id, Permission.ADMIN_AUDIT_VIEW
                )
            except Exception as e:
                raise PermissionError("ADMIN_AUDIT_VIEW required") from e

            uncertain_after = getattr(
                self._settings, "admin_audit_uncertain_after_seconds", 300
            )
            now_dt = self._clock.now()
            cutoff_dt = now_dt - timedelta(seconds=uncertain_after)

            count, oldest_at = await self._audit_repo.count_uncertain(
                cutoff_dt
            )
            oldest_age = None
            if oldest_at:
                oldest_age = int((now_dt - oldest_at).total_seconds())

            return {
                "uncertain_actions": count,
                "oldest_age_seconds": oldest_age,
            }

        admin_actions_sec = await run_section(
            "admin_actions", fetch_admin_actions
        )

        return OverviewView(
            verification=verification_sec,
            payments=payments_sec,
            safety=safety_sec,
            notifications=notifications_sec,
            messaging=messaging_sec,
            issues=issues_sec,
            admin_actions=admin_actions_sec,
        )
