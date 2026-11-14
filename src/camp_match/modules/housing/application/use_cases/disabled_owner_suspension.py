"""Disabled owner suspension use cases."""
from __future__ import annotations

from typing import Any
import structlog

from camp_match.modules.housing.domain.events import (
    ListingSuspended,
    ListingSuspensionLifted,
)
from camp_match.modules.housing.domain.value_objects import ListingStatus
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger(__name__)


class SuspendListingsForDisabledOwnerUseCase:
    def __init__(
        self,
        session_factory: Any,
        settings: Any,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings

    async def __call__(self, owner_id: EntityId, source_event_id: EntityId) -> None:
        from camp_match.modules.housing.adapters.persistence.repository import (
            SqlAlchemyListingRepository,
        )
        from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork

        batch_size = getattr(
            self.settings, "housing_owner_suspension_batch_size", 100
        )

        while True:
            async with self.session_factory() as session:
                listing_repo = SqlAlchemyListingRepository(session)
                listings = await listing_repo.list_by_provider_and_status(
                    owner_id,
                    [
                        ListingStatus.PUBLISHED.value,
                        ListingStatus.UNAVAILABLE.value,
                    ],
                    batch_size,
                )
            if not listings:
                break

            for listing in listings:
                try:
                    async with self.session_factory() as session:
                        listing_repo = SqlAlchemyListingRepository(session)
                        uow = SqlAlchemyUnitOfWork(session)

                        current = await listing_repo.get_by_id(listing.id)
                        if not current or current.status == ListingStatus.SUSPENDED:
                            continue

                        current.status = ListingStatus.SUSPENDED
                        current.suspension_reason = "OWNER_ACCOUNT_DISABLED"
                        current.suspension_reference = owner_id

                        await listing_repo.update(current)
                        uow.add_event(
                            ListingSuspended(
                                listing_id=current.id,
                                property_id=current.property_id,
                                owner_id=owner_id,
                                reason_code="OWNER_ACCOUNT_DISABLED",
                                reference_id=owner_id,
                            )
                        )
                        await uow.commit()
                        logger.info(
                            "listing_suspended_for_disabled_owner",
                            listing_id=current.id,
                            owner_id=owner_id,
                        )
                except Exception as e:
                    logger.warning(
                        "failed_to_suspend_listing_for_disabled_owner",
                        listing_id=listing.id,
                        error=str(e),
                    )

            if len(listings) < batch_size:
                break


class LiftOwnerAccountSuspensionsUseCase:
    def __init__(
        self,
        session_factory: Any,
        settings: Any,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings

    async def __call__(self, owner_id: EntityId, source_event_id: EntityId) -> None:
        from camp_match.modules.housing.adapters.persistence.repository import (
            SqlAlchemyListingRepository,
        )
        from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork

        batch_size = getattr(
            self.settings, "housing_owner_suspension_batch_size", 100
        )

        while True:
            async with self.session_factory() as session:
                listing_repo = SqlAlchemyListingRepository(session)
                listings = await listing_repo.list_suspended_by_provider_and_reason(
                    owner_id,
                    "OWNER_ACCOUNT_DISABLED",
                    owner_id,
                    batch_size,
                )
            if not listings:
                break

            for listing in listings:
                try:
                    async with self.session_factory() as session:
                        listing_repo = SqlAlchemyListingRepository(session)
                        uow = SqlAlchemyUnitOfWork(session)

                        current = await listing_repo.get_by_id(listing.id)
                        if not current or current.status != ListingStatus.SUSPENDED:
                            continue
                        if current.suspension_reason != "OWNER_ACCOUNT_DISABLED":
                            continue

                        current.status = ListingStatus.UNAVAILABLE
                        current.suspension_reason = None
                        current.suspension_reference = None

                        await listing_repo.update(current)
                        uow.add_event(
                            ListingSuspensionLifted(
                                listing_id=current.id,
                                property_id=current.property_id,
                                owner_id=owner_id,
                            )
                        )
                        await uow.commit()
                        logger.info(
                            "listing_suspension_lifted_for_reactivated_owner",
                            listing_id=current.id,
                            owner_id=owner_id,
                        )
                except Exception as e:
                    logger.warning(
                        "failed_to_lift_suspension_for_owner",
                        listing_id=listing.id,
                        error=str(e),
                    )

            if len(listings) < batch_size:
                break


class ListSuspendedListingIdsUseCase:
    def __init__(self, listing_repo: Any) -> None:
        self.listing_repo = listing_repo

    async def __call__(
        self, limit: int = 100, after_id: EntityId | None = None
    ) -> list[EntityId]:
        return await self.listing_repo.list_suspended_ids(limit, after_id)
