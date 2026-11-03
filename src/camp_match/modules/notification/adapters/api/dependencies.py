"""Notification API dependencies."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.modules.notification.adapters.persistence.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from camp_match.modules.notification.application.use_cases.get_unread_count import (
    GetUnreadCountUseCase,
)
from camp_match.modules.notification.application.use_cases.list_notifications import (
    ListNotificationsUseCase,
)
from camp_match.modules.notification.application.use_cases.mark_all_read import (
    MarkAllReadUseCase,
)
from camp_match.modules.notification.application.use_cases.mark_notification_read import (
    MarkNotificationReadUseCase,
)
from camp_match.platform.clock import get_clock
from camp_match.platform.db.session import get_db_session
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock


def get_notification_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SqlAlchemyNotificationRepository:
    return SqlAlchemyNotificationRepository(session)


def get_uow(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(session)


def get_list_notifications_use_case(
    repo: Annotated[SqlAlchemyNotificationRepository, Depends(get_notification_repository)],
) -> ListNotificationsUseCase:
    return ListNotificationsUseCase(repo)


def get_unread_count_use_case(
    repo: Annotated[SqlAlchemyNotificationRepository, Depends(get_notification_repository)],
) -> GetUnreadCountUseCase:
    return GetUnreadCountUseCase(repo)


def get_mark_notification_read_use_case(
    repo: Annotated[SqlAlchemyNotificationRepository, Depends(get_notification_repository)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> MarkNotificationReadUseCase:
    return MarkNotificationReadUseCase(repo, uow, clock)


def get_mark_all_read_use_case(
    repo: Annotated[SqlAlchemyNotificationRepository, Depends(get_notification_repository)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> MarkAllReadUseCase:
    return MarkAllReadUseCase(repo, uow, clock)
