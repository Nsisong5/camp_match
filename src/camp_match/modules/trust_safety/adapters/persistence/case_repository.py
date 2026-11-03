"""SQLAlchemy Case Repository adapter."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update

from camp_match.modules.trust_safety.adapters.persistence.models import (
    SafetyCaseEventModel,
    SafetyCaseModel,
    SafetyCaseReportModel,
)
from camp_match.modules.trust_safety.domain.entities import SafetyCase
from camp_match.modules.trust_safety.domain.value_objects import (
    CasePriority,
    CaseStatus,
    ReportCategory,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


def _to_domain(m: SafetyCaseModel) -> SafetyCase:
    return SafetyCase(
        id=EntityId(m.id),
        category=ReportCategory(m.category),
        priority=CasePriority(m.priority),
        status=CaseStatus(m.status),
        subject_user_id=EntityId(m.subject_user_id),
        assigned_to=EntityId(m.assigned_to) if m.assigned_to else None,
        version=m.version,
        cycle=m.cycle,
        created_by=EntityId(m.created_by),
        created_at=m.created_at,
        updated_at=m.updated_at,
        resolved_at=m.resolved_at,
        closed_at=m.closed_at,
    )


class SqlAlchemyCaseRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def add(self, case: SafetyCase) -> None:
        model = SafetyCaseModel(
            id=case.id.value,
            category=case.category.value,
            priority=case.priority.value,
            status=case.status.value,
            subject_user_id=case.subject_user_id.value,
            assigned_to=case.assigned_to.value if case.assigned_to else None,
            version=case.version,
            cycle=case.cycle,
            created_by=case.created_by.value,
            created_at=case.created_at,
            updated_at=case.updated_at,
            resolved_at=case.resolved_at,
            closed_at=case.closed_at,
        )
        self.session.add(model)
        await self.session.flush()

    async def get_by_id(self, case_id: EntityId) -> SafetyCase | None:
        res = await self.session.get(SafetyCaseModel, case_id.value)
        return _to_domain(res) if res else None

    async def update(self, case: SafetyCase, expected_version: int) -> bool:
        stmt = (
            update(SafetyCaseModel)
            .where(
                SafetyCaseModel.id == case.id.value,
                SafetyCaseModel.version == expected_version,
            )
            .values(
                status=case.status.value,
                priority=case.priority.value,
                assigned_to=case.assigned_to.value if case.assigned_to else None,
                version=case.version,
                cycle=case.cycle,
                updated_at=case.updated_at,
                resolved_at=case.resolved_at,
                closed_at=case.closed_at,
            )
        )
        res = await self.session.execute(stmt)
        return res.rowcount == 1

    async def link_report(self, case_id: EntityId, report_id: EntityId) -> None:
        from datetime import datetime, timezone
        model = SafetyCaseReportModel(
            report_id=report_id.value,
            case_id=case_id.value,
            linked_by=case_id.value,  # or actor id passed / handled in use case
            linked_at=datetime.now(timezone.utc),
        )
        self.session.add(model)
        await self.session.flush()

    async def list_cases(
        self,
        status: CaseStatus | None = None,
        category: ReportCategory | None = None,
        assigned_to: EntityId | None = None,
        page_request: PageRequest = PageRequest(page=1, page_size=20),
    ) -> Page[SafetyCase]:
        base_stmt = select(SafetyCaseModel)
        if status:
            base_stmt = base_stmt.where(SafetyCaseModel.status == status.value)
        if category:
            base_stmt = base_stmt.where(SafetyCaseModel.category == category.value)
        if assigned_to:
            base_stmt = base_stmt.where(SafetyCaseModel.assigned_to == assigned_to.value)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        offset = (page_request.page - 1) * page_request.page_size
        stmt = (
            base_stmt.order_by(SafetyCaseModel.created_at.desc())
            .offset(offset)
            .limit(page_request.page_size)
        )
        res = await self.session.execute(stmt)
        items = [_to_domain(m) for m in res.scalars().all()]
        return Page(items=items, total=total, page=page_request.page, page_size=page_request.page_size)

    async def add_event(
        self,
        case_id: EntityId | None,
        report_id: EntityId | None,
        event_type: str,
        actor_id: EntityId | None,
        details: dict[str, Any] | None,
    ) -> None:
        from datetime import datetime, timezone
        model = SafetyCaseEventModel(
            id=EntityId.new().value,
            case_id=case_id.value if case_id else None,
            report_id=report_id.value if report_id else None,
            event_type=event_type,
            actor_id=actor_id.value if actor_id else None,
            occurred_at=datetime.now(timezone.utc),
            details=details,
        )
        self.session.add(model)
        await self.session.flush()

    async def list_events(self, case_id: EntityId) -> list[Any]:
        stmt = (
            select(SafetyCaseEventModel)
            .where(SafetyCaseEventModel.case_id == case_id.value)
            .order_by(SafetyCaseEventModel.occurred_at.asc(), SafetyCaseEventModel.id.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def count_cases_by_status(self) -> dict[str, int]:
        stmt = (
            select(SafetyCaseModel.status, func.count(SafetyCaseModel.id))
            .where(SafetyCaseModel.status != CaseStatus.CLOSED.value)
            .group_by(SafetyCaseModel.status)
        )
        res = await self.session.execute(stmt)
        return {row[0]: row[1] for row in res.all()}

    async def count_high_or_urgent_open_cases(self) -> int:
        stmt = select(func.count(SafetyCaseModel.id)).where(
            SafetyCaseModel.status != CaseStatus.CLOSED.value,
            SafetyCaseModel.priority.in_([CasePriority.HIGH.value, CasePriority.URGENT.value]),
        )
        res = await self.session.execute(stmt)
        return res.scalar_one()
