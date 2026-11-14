"""Saved listings API dependencies."""

from __future__ import annotations

import importlib
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.config.settings import get_settings
from camp_match.modules.saved_listings.adapters.housing.housing_catalog_adapter import (
    HousingCatalogAdapter,
)
from camp_match.modules.saved_listings.adapters.persistence.repository import (
    SqlAlchemySavedListingRepository,
)
from camp_match.modules.saved_listings.application.use_cases.get_saved_state import (
    GetSavedStateUseCase,
)
from camp_match.modules.saved_listings.application.use_cases.list_saved_listings import (
    ListSavedListingsUseCase,
)
from camp_match.modules.saved_listings.application.use_cases.save_listing import (
    SaveListingUseCase,
)
from camp_match.modules.saved_listings.application.use_cases.unsave_listing import (
    UnsaveListingUseCase,
)
from camp_match.platform.clock import get_clock
from camp_match.platform.db.session import get_db_session


def get_housing_catalog_adapter(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HousingCatalogAdapter:
    housing_repo_mod = importlib.import_module(
        "camp_match.modules.housing.adapters.persistence.repository"
    )
    get_saving_mod = importlib.import_module(
        "camp_match.modules.housing.application.use_cases.get_listing_for_saving"
    )
    get_cards_mod = importlib.import_module(
        "camp_match.modules.housing.application.use_cases.get_listing_cards"
    )

    listing_repo = housing_repo_mod.SqlAlchemyListingRepository(session)
    property_repo = housing_repo_mod.SqlAlchemyPropertyRepository(session)
    unit_repo = housing_repo_mod.SqlAlchemyUnitRepository(session)

    get_for_saving_uc = get_saving_mod.GetListingForSavingUseCase(
        listing_repo, property_repo
    )
    get_cards_uc = get_cards_mod.GetListingCardsUseCase(
        listing_repo, property_repo, unit_repo
    )
    return HousingCatalogAdapter(get_for_saving_uc, get_cards_uc)


def get_save_listing_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    catalog_adapter: Annotated[
        HousingCatalogAdapter, Depends(get_housing_catalog_adapter)
    ],
) -> SaveListingUseCase:
    saved_repo = SqlAlchemySavedListingRepository(session)
    clock = get_clock()
    settings = get_settings()
    return SaveListingUseCase(
        saved_repo, catalog_adapter, clock, settings.saved_listings_max_per_user
    )


def get_unsave_listing_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UnsaveListingUseCase:
    saved_repo = SqlAlchemySavedListingRepository(session)
    return UnsaveListingUseCase(saved_repo)


def get_list_saved_listings_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    catalog_adapter: Annotated[
        HousingCatalogAdapter, Depends(get_housing_catalog_adapter)
    ],
) -> ListSavedListingsUseCase:
    saved_repo = SqlAlchemySavedListingRepository(session)
    return ListSavedListingsUseCase(saved_repo, catalog_adapter)


def get_saved_state_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GetSavedStateUseCase:
    saved_repo = SqlAlchemySavedListingRepository(session)
    return GetSavedStateUseCase(saved_repo)
