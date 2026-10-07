from __future__ import annotations

from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.config.settings import get_settings
from camp_match.platform.db.session import get_db_session
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork

from camp_match.modules.verification.adapters.persistence.repository import (
    SQLAlchemyVerificationCaseRepository,
    SQLAlchemyEvidenceRepository,
    SQLAlchemyInspectionRepository,
    SQLAlchemyInspectionObservationRepository,
    SQLAlchemyVerificationDecisionRepository,
    SQLAlchemyHistoryRepository,
)
from camp_match.modules.verification.adapters.housing.housing_provider import InProcessHousingProvider
from camp_match.modules.verification.adapters.profile.profile_provider import InProcessProfileProvider
from camp_match.modules.verification.adapters.media.media_provider import InProcessMediaProvider

from camp_match.modules.media.adapters.persistence.repository import SqlAlchemyMediaRepository
from camp_match.modules.media.adapters.storage.local_storage_adapter import LocalFileSystemStorageAdapter
from camp_match.modules.media.application.use_cases.upload_media import UploadMediaUseCase
from camp_match.modules.media.application.use_cases.get_authorized_access import GetAuthorizedAccessUseCase

from camp_match.modules.security.adapters.persistence.repository import SqlAlchemyRoleRepository
from camp_match.modules.security.application.use_cases.authorize_action import AuthorizeActionUseCase
from camp_match.modules.security.adapters.profile.profile_provider import InProcessProfileProvider as SecurityProfileProvider
from camp_match.modules.profile.adapters.persistence.repository import SqlAlchemyProfileRepository
from camp_match.modules.profile.application.use_cases.get_current_user_profile import GetCurrentUserProfileUseCase
from camp_match.modules.verification.adapters.security.authorization import InProcessAuthorizationService


def get_uow(session: Annotated[AsyncSession, Depends(get_db_session)]) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(session)


def get_verification_case_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SQLAlchemyVerificationCaseRepository:
    return SQLAlchemyVerificationCaseRepository(session)


def get_evidence_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SQLAlchemyEvidenceRepository:
    return SQLAlchemyEvidenceRepository(session)


def get_inspection_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SQLAlchemyInspectionRepository:
    return SQLAlchemyInspectionRepository(session)


def get_observation_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SQLAlchemyInspectionObservationRepository:
    return SQLAlchemyInspectionObservationRepository(session)


def get_decision_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SQLAlchemyVerificationDecisionRepository:
    return SQLAlchemyVerificationDecisionRepository(session)


def get_history_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SQLAlchemyHistoryRepository:
    return SQLAlchemyHistoryRepository(session)


def get_housing_provider(session: Annotated[AsyncSession, Depends(get_db_session)]) -> InProcessHousingProvider:
    return InProcessHousingProvider(session)


def get_profile_provider(session: Annotated[AsyncSession, Depends(get_db_session)]) -> InProcessProfileProvider:
    return InProcessProfileProvider(session)


def get_media_provider(session: Annotated[AsyncSession, Depends(get_db_session)]) -> InProcessMediaProvider:
    media_repo = SqlAlchemyMediaRepository(session)
    settings = get_settings()
    storage = LocalFileSystemStorageAdapter(
        storage_path=settings.media_storage_path,
        secret=settings.media_access_token_secret,
        ttl_seconds=settings.media_access_token_ttl_seconds,
    )
    uow = SqlAlchemyUnitOfWork(session)
    upload_uc = UploadMediaUseCase(media_repo, storage, uow)
    get_access_uc = GetAuthorizedAccessUseCase(media_repo, storage)
    return InProcessMediaProvider(upload_uc, get_access_uc)


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InProcessAuthorizationService:
    role_repo = SqlAlchemyRoleRepository(session)
    profile_repo = SqlAlchemyProfileRepository(session)
    profile_use_case = GetCurrentUserProfileUseCase(profile_repo)
    sec_profile_provider = SecurityProfileProvider(profile_use_case)
    auth_uc = AuthorizeActionUseCase(role_repo, sec_profile_provider)
    return InProcessAuthorizationService(auth_uc)
