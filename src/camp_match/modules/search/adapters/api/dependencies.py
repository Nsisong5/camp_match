from __future__ import annotations

import importlib
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from camp_match.platform.db.session import get_db_session
from camp_match.modules.search.adapters.housing.housing_provider import HousingProviderAdapter
from camp_match.modules.search.adapters.university_location.university_location_provider import UniversityLocationProviderAdapter
from camp_match.modules.search.adapters.verification.verification_provider import InProcessVerificationProvider
from camp_match.modules.search.domain.ranking import SearchRankingStrategy
from camp_match.modules.search.application.use_cases.search_listings import SearchListings


def get_housing_provider(session: Annotated[AsyncSession, Depends(get_db_session)]) -> HousingProviderAdapter:
    housing_repo_mod = importlib.import_module("camp_match.modules.housing.adapters.persistence.repository")
    listing_repo = housing_repo_mod.SqlAlchemyListingRepository(session)
    property_repo = housing_repo_mod.SqlAlchemyPropertyRepository(session)
    unit_repo = housing_repo_mod.SqlAlchemyUnitRepository(session)
    return HousingProviderAdapter(listing_repo, property_repo, unit_repo)


def get_university_location_provider(session: Annotated[AsyncSession, Depends(get_db_session)]) -> UniversityLocationProviderAdapter:
    univ_repo_mod = importlib.import_module("camp_match.modules.university_location.adapters.persistence.repository")
    get_campus_mod = importlib.import_module("camp_match.modules.university_location.application.use_cases.get_campus")
    campus_repo = univ_repo_mod.SqlAlchemyCampusRepository(session)
    query_port = get_campus_mod.GetCampusUseCase(campus_repo)
    return UniversityLocationProviderAdapter(query_port)


def get_verification_provider(session: Annotated[AsyncSession, Depends(get_db_session)]) -> InProcessVerificationProvider:
    housing_repo_mod = importlib.import_module("camp_match.modules.housing.adapters.persistence.repository")
    verif_repo_mod = importlib.import_module("camp_match.modules.verification.adapters.persistence.repository")
    verif_uc_mod = importlib.import_module("camp_match.modules.verification.application.use_cases.get_verification_status")

    listing_repo = housing_repo_mod.SqlAlchemyListingRepository(session)
    case_repo = verif_repo_mod.SQLAlchemyVerificationCaseRepository(session)
    decision_repo = verif_repo_mod.SQLAlchemyVerificationDecisionRepository(session)
    get_status_uc = verif_uc_mod.GetVerificationStatusUseCase(case_repo, decision_repo)
    return InProcessVerificationProvider(listing_repo, get_status_uc)


def get_search_listings_use_case(
    housing_provider: Annotated[HousingProviderAdapter, Depends(get_housing_provider)],
    univ_provider: Annotated[UniversityLocationProviderAdapter, Depends(get_university_location_provider)],
    verif_provider: Annotated[InProcessVerificationProvider, Depends(get_verification_provider)],
) -> SearchListings:
    ranking_strategy = SearchRankingStrategy()
    return SearchListings(housing_provider, univ_provider, verif_provider, ranking_strategy)
