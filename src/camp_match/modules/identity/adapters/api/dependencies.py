from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.config.settings import Settings, get_settings
from camp_match.modules.identity.adapters.email.dev_mailbox_router import get_dev_mailbox
from camp_match.modules.identity.adapters.email.log_email_sender import LogEmailSender
from camp_match.modules.identity.adapters.email.smtp_email_sender import SmtpEmailSender
from camp_match.modules.identity.adapters.google.composite_google_verifier import (
    CompositeGoogleVerifier,
)
from camp_match.modules.identity.adapters.persistence.external_identity_repository import (
    SqlAlchemyExternalIdentityRepository,
)
from camp_match.modules.identity.adapters.persistence.one_time_code_repository import (
    SqlAlchemyOneTimeCodeRepository,
)
from camp_match.modules.identity.adapters.persistence.repository import (
    SqlAlchemyIdentityRepository,
)
from camp_match.modules.identity.adapters.security.jwt_session import (
    JwtAuthenticationSessionAdapter,
)
from camp_match.modules.identity.adapters.security.one_time_code_service import (
    OneTimeCodeServiceAdapter,
)
from camp_match.modules.identity.adapters.security.password_hasher import (
    ScryptPasswordHasher,
)
from camp_match.modules.identity.application.services.email_verification_issuer import (
    EmailVerificationIssuer,
)
from camp_match.modules.identity.application.use_cases.authenticate_user import (
    AuthenticateUserUseCase,
)
from camp_match.modules.identity.application.use_cases.get_google_sign_in_config import (
    GetGoogleSignInConfigUseCase,
)
from camp_match.modules.identity.application.use_cases.get_identity import (
    GetIdentityByIdUseCase,
)
from camp_match.modules.identity.application.use_cases.link_google_account import (
    LinkGoogleAccountUseCase,
)
from camp_match.modules.identity.application.use_cases.logout import LogoutUseCase
from camp_match.modules.identity.application.use_cases.refresh_session import (
    RefreshSessionUseCase,
)
from camp_match.modules.identity.application.use_cases.register_account import (
    RegisterAccountUseCase,
)
from camp_match.modules.identity.application.use_cases.resend_email_verification import (
    ResendEmailVerificationUseCase,
)
from camp_match.modules.identity.application.use_cases.set_password import (
    SetPasswordUseCase,
)
from camp_match.modules.identity.application.use_cases.sign_in_with_google import (
    SignInWithGoogleUseCase,
)
from camp_match.modules.identity.application.use_cases.unlink_google_account import (
    UnlinkGoogleAccountUseCase,
)
from camp_match.modules.identity.application.use_cases.verify_email import (
    VerifyEmailUseCase,
)
from camp_match.platform.clock import SystemClock, get_clock
from camp_match.platform.db.session import get_db_session
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
from camp_match.platform.event_bus import get_event_bus
from camp_match.shared_kernel.application.event_bus import EventBus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork


def get_uow(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(session)


def get_identity_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SqlAlchemyIdentityRepository:
    return SqlAlchemyIdentityRepository(session)


def get_otc_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SqlAlchemyOneTimeCodeRepository:
    return SqlAlchemyOneTimeCodeRepository(session)


def get_external_identity_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SqlAlchemyExternalIdentityRepository:
    return SqlAlchemyExternalIdentityRepository(session)


def get_password_hasher() -> ScryptPasswordHasher:
    return ScryptPasswordHasher()


def get_otc_service() -> OneTimeCodeServiceAdapter:
    return OneTimeCodeServiceAdapter()


def get_email_sender(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LogEmailSender | SmtpEmailSender:
    if settings.email_backend.lower() == "log":
        return LogEmailSender(mailbox=get_dev_mailbox(), settings=settings)
    return SmtpEmailSender(settings=settings)


def get_google_verifier(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CompositeGoogleVerifier:
    return CompositeGoogleVerifier(settings)


def get_auth_session(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> JwtAuthenticationSessionAdapter:
    return JwtAuthenticationSessionAdapter(session, settings, uow)


def get_email_verification_issuer(
    otc_repo: Annotated[
        SqlAlchemyOneTimeCodeRepository, Depends(get_otc_repository)
    ],
    otc_service: Annotated[OneTimeCodeServiceAdapter, Depends(get_otc_service)],
    email_sender: Annotated[
        LogEmailSender | SmtpEmailSender, Depends(get_email_sender)
    ],
    clock: Annotated[SystemClock, Depends(get_clock)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmailVerificationIssuer:
    return EmailVerificationIssuer(
        otc_repo, otc_service, email_sender, clock, uow, settings
    )


def get_register_account(
    repo: Annotated[
        SqlAlchemyIdentityRepository, Depends(get_identity_repository)
    ],
    hasher: Annotated[ScryptPasswordHasher, Depends(get_password_hasher)],
    clock: Annotated[SystemClock, Depends(get_clock)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    issuer: Annotated[
        EmailVerificationIssuer, Depends(get_email_verification_issuer)
    ],
    otc_repo: Annotated[
        SqlAlchemyOneTimeCodeRepository, Depends(get_otc_repository)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RegisterAccountUseCase:
    return RegisterAccountUseCase(
        repository=repo,
        password_hasher=hasher,
        clock=clock,
        event_bus=event_bus,
        unit_of_work=uow,
        issuer=issuer,
        otc_repo=otc_repo,
        settings=settings,
    )


def get_authenticate_user(
    repo: Annotated[
        SqlAlchemyIdentityRepository, Depends(get_identity_repository)
    ],
    hasher: Annotated[ScryptPasswordHasher, Depends(get_password_hasher)],
    auth: Annotated[JwtAuthenticationSessionAdapter, Depends(get_auth_session)],
    issuer: Annotated[
        EmailVerificationIssuer, Depends(get_email_verification_issuer)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticateUserUseCase:
    return AuthenticateUserUseCase(
        repository=repo,
        password_hasher=hasher,
        session_port=auth,
        issuer=issuer,
        settings=settings,
    )


def get_verify_email(
    identity_repo: Annotated[
        SqlAlchemyIdentityRepository, Depends(get_identity_repository)
    ],
    otc_repo: Annotated[
        SqlAlchemyOneTimeCodeRepository, Depends(get_otc_repository)
    ],
    otc_service: Annotated[OneTimeCodeServiceAdapter, Depends(get_otc_service)],
    clock: Annotated[SystemClock, Depends(get_clock)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> VerifyEmailUseCase:
    return VerifyEmailUseCase(identity_repo, otc_repo, otc_service, clock, uow)


def get_resend_verification(
    identity_repo: Annotated[
        SqlAlchemyIdentityRepository, Depends(get_identity_repository)
    ],
    issuer: Annotated[
        EmailVerificationIssuer, Depends(get_email_verification_issuer)
    ],
) -> ResendEmailVerificationUseCase:
    return ResendEmailVerificationUseCase(identity_repo, issuer)


def get_sign_in_with_google(
    identity_repo: Annotated[
        SqlAlchemyIdentityRepository, Depends(get_identity_repository)
    ],
    ext_repo: Annotated[
        SqlAlchemyExternalIdentityRepository,
        Depends(get_external_identity_repository),
    ],
    otc_repo: Annotated[
        SqlAlchemyOneTimeCodeRepository, Depends(get_otc_repository)
    ],
    verifier: Annotated[
        CompositeGoogleVerifier, Depends(get_google_verifier)
    ],
    auth: Annotated[JwtAuthenticationSessionAdapter, Depends(get_auth_session)],
    clock: Annotated[SystemClock, Depends(get_clock)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> SignInWithGoogleUseCase:
    return SignInWithGoogleUseCase(
        identity_repo, ext_repo, otc_repo, verifier, auth, clock, event_bus, uow
    )


def get_link_google(
    identity_repo: Annotated[
        SqlAlchemyIdentityRepository, Depends(get_identity_repository)
    ],
    ext_repo: Annotated[
        SqlAlchemyExternalIdentityRepository,
        Depends(get_external_identity_repository),
    ],
    verifier: Annotated[
        CompositeGoogleVerifier, Depends(get_google_verifier)
    ],
    clock: Annotated[SystemClock, Depends(get_clock)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> LinkGoogleAccountUseCase:
    return LinkGoogleAccountUseCase(identity_repo, ext_repo, verifier, clock, uow)


def get_unlink_google(
    identity_repo: Annotated[
        SqlAlchemyIdentityRepository, Depends(get_identity_repository)
    ],
    ext_repo: Annotated[
        SqlAlchemyExternalIdentityRepository,
        Depends(get_external_identity_repository),
    ],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> UnlinkGoogleAccountUseCase:
    return UnlinkGoogleAccountUseCase(identity_repo, ext_repo, uow)


def get_set_password(
    identity_repo: Annotated[
        SqlAlchemyIdentityRepository, Depends(get_identity_repository)
    ],
    hasher: Annotated[ScryptPasswordHasher, Depends(get_password_hasher)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> SetPasswordUseCase:
    return SetPasswordUseCase(identity_repo, hasher, uow)


def get_refresh_session(
    auth: Annotated[JwtAuthenticationSessionAdapter, Depends(get_auth_session)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> RefreshSessionUseCase:
    return RefreshSessionUseCase(session_port=auth, uow=uow)


def get_logout(
    auth: Annotated[JwtAuthenticationSessionAdapter, Depends(get_auth_session)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> LogoutUseCase:
    return LogoutUseCase(session_port=auth, uow=uow)


def get_get_identity(
    repo: Annotated[
        SqlAlchemyIdentityRepository, Depends(get_identity_repository)
    ],
    ext_repo: Annotated[
        SqlAlchemyExternalIdentityRepository,
        Depends(get_external_identity_repository),
    ],
) -> GetIdentityByIdUseCase:
    return GetIdentityByIdUseCase(
        repository=repo, external_identity_repository=ext_repo
    )


def get_google_sign_in_config(
    settings: Annotated[Settings, Depends(get_settings)],
) -> GetGoogleSignInConfigUseCase:
    return GetGoogleSignInConfigUseCase(settings)
