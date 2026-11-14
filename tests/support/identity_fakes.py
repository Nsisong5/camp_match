"""Test fakes for Identity module outbound ports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.identity.application.errors import (
    EmailDeliveryError,
    GoogleAlreadyLinked,
    GoogleIdentityInUse,
    IdentityAlreadyExists,
    InvalidCredentials,
)
from camp_match.modules.identity.application.ports.outbound import (
    EmailMessage,
    TokenPair,
    VerifiedGoogleIdentity,
)
from camp_match.modules.identity.adapters.security.one_time_code_service import OneTimeCodeServiceAdapter
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from datetime import datetime
    from camp_match.modules.identity.domain.entities import UserAccount, OneTimeCode, ExternalIdentity
    from camp_match.modules.identity.domain.value_objects import EmailAddress, OneTimeCodePurpose, ExternalProvider
else:
    from camp_match.modules.identity.domain.entities import ExternalIdentity
    from camp_match.modules.identity.domain.value_objects import ExternalProvider


class FakeIdentityRepository:
    def __init__(self) -> None:
        self.accounts: dict[EntityId, UserAccount] = {}

    async def add(self, account: UserAccount) -> None:
        for acc in self.accounts.values():
            if acc.email == account.email:
                raise IdentityAlreadyExists("Email is already registered.")
        self.accounts[account.id] = account

    async def get_by_email(self, email: EmailAddress) -> UserAccount | None:
        for acc in self.accounts.values():
            if acc.email == email:
                return acc
        return None

    async def get_by_id(self, identity_id: EntityId) -> UserAccount | None:
        return self.accounts.get(identity_id)

    async def update(self, account: UserAccount) -> None:
        self.accounts[account.id] = account


class FakePasswordHasher:
    def hash(self, raw_password: str) -> str:
        return f"hashed_{raw_password}"

    def verify(self, raw_password: str, encoded_hash: str) -> bool:
        return f"hashed_{raw_password}" == encoded_hash


class FakeAuthenticationSessionPort:
    def __init__(self) -> None:
        self.revoked_tokens: set[str] = set()

    async def issue_tokens(self, identity_id: EntityId) -> TokenPair:
        return TokenPair(
            access_token=f"access_{identity_id}",
            refresh_token=f"refresh_{identity_id}",
            token_type="bearer",
            expires_in=3600,
        )

    async def refresh(self, refresh_token: str) -> TokenPair:
        if refresh_token in self.revoked_tokens or not refresh_token.startswith("refresh_"):
            raise InvalidCredentials("Invalid or revoked refresh token.")
        identity_id_str = refresh_token.replace("refresh_", "")
        identity_id = EntityId.from_string(identity_id_str)
        return await self.issue_tokens(identity_id)

    async def revoke(self, refresh_token: str) -> None:
        self.revoked_tokens.add(refresh_token)

    async def decode_access_token(self, access_token: str) -> EntityId:
        if not access_token.startswith("access_"):
            raise InvalidCredentials("Invalid access token.")
        identity_id_str = access_token.replace("access_", "")
        return EntityId.from_string(identity_id_str)


class FakeEventBus:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def publish(self, event: object) -> None:
        self.events.append(event)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.events: list[object] = []

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass

    def add_event(self, event: object) -> None:
        self.events.append(event)


class FakeOneTimeCodeRepository:
    def __init__(self) -> None:
        self.codes: dict[EntityId, OneTimeCode] = {}

    async def get_active(
        self, account_id: EntityId, purpose: OneTimeCodePurpose
    ) -> OneTimeCode | None:
        for code in self.codes.values():
            if (
                code.account_id == account_id
                and code.purpose == purpose
                and code.consumed_at is None
                and code.invalidated_at is None
            ):
                return code
        return None

    async def add_replacing_active(self, code: OneTimeCode) -> None:
        await self.invalidate_all(code.account_id, code.purpose, code.issued_at)
        self.codes[code.id] = code

    async def update(self, code: OneTimeCode) -> None:
        if code.id in self.codes:
            self.codes[code.id] = code

    async def count_issued_since(
        self, account_id: EntityId, purpose: OneTimeCodePurpose, since: datetime
    ) -> int:
        count = 0
        for code in self.codes.values():
            if (
                code.account_id == account_id
                and code.purpose == purpose
                and code.issued_at >= since
            ):
                count += 1
        return count

    async def latest_issued_at(
        self, account_id: EntityId, purpose: OneTimeCodePurpose
    ) -> datetime | None:
        latest = None
        for code in self.codes.values():
            if code.account_id == account_id and code.purpose == purpose:
                if latest is None or code.issued_at > latest:
                    latest = code.issued_at
        return latest

    async def invalidate_all(
        self, account_id: EntityId, purpose: OneTimeCodePurpose, now: datetime
    ) -> None:
        for code in self.codes.values():
            if (
                code.account_id == account_id
                and code.purpose == purpose
                and code.consumed_at is None
                and code.invalidated_at is None
            ):
                code.invalidated_at = now


class FakeEmailSender:
    def __init__(self, fail: bool = False) -> None:
        self.sent_messages: list[EmailMessage] = []
        self.fail = fail

    async def send(self, message: EmailMessage) -> None:
        if self.fail:
            raise EmailDeliveryError("Simulated email delivery failure.")
        self.sent_messages.append(message)


class FakeOneTimeCodeService:
    def __init__(self) -> None:
        self._adapter = OneTimeCodeServiceAdapter()

    def generate(self) -> str:
        return self._adapter.generate()

    def hash(
        self, account_id: EntityId, purpose: OneTimeCodePurpose, code: str
    ) -> str:
        return self._adapter.hash(account_id, purpose, code)

    def matches(
        self,
        account_id: EntityId,
        purpose: OneTimeCodePurpose,
        code: str,
        code_hash: str,
    ) -> bool:
        return self._adapter.matches(account_id, purpose, code, code_hash)


class FakeExternalIdentityRepository:
    def __init__(self, identity_repo: FakeIdentityRepository | None = None) -> None:
        self.identities: list[ExternalIdentity] = []
        self._identity_repo = identity_repo

    async def get_by_subject(
        self, provider: ExternalProvider, subject: str
    ) -> ExternalIdentity | None:
        for ext in self.identities:
            if ext.provider == provider and ext.subject == subject:
                return ext
        return None

    async def get_by_account(
        self, account_id: EntityId, provider: ExternalProvider
    ) -> list[ExternalIdentity]:
        return [
            ext
            for ext in self.identities
            if ext.account_id == account_id and ext.provider == provider
        ]

    async def add(self, identity: ExternalIdentity) -> None:
        for ext in self.identities:
            if ext.provider == identity.provider and ext.subject == identity.subject:
                raise GoogleIdentityInUse(
                    "That Google account is linked to a different account."
                )
            if ext.account_id == identity.account_id and ext.provider == identity.provider:
                raise GoogleAlreadyLinked("A Google account is already linked.")
        self.identities.append(identity)

    async def remove(self, account_id: EntityId, provider: ExternalProvider) -> bool:
        initial_len = len(self.identities)
        self.identities = [
            ext
            for ext in self.identities
            if not (ext.account_id == account_id and ext.provider == provider)
        ]
        return len(self.identities) < initial_len

    async def touch_last_login(self, identity_id: EntityId, now: datetime) -> None:
        for ext in self.identities:
            if ext.id == identity_id:
                ext.last_login_at = now

    async def list_methods(self, account_id: EntityId) -> list[str]:
        methods: list[str] = []
        if self._identity_repo:
            acc = await self._identity_repo.get_by_id(account_id)
            if acc and acc.has_password:
                methods.append("PASSWORD")
        for ext in self.identities:
            if ext.account_id == account_id and ext.provider.value not in methods:
                methods.append(ext.provider.value)
        return methods


class FakeGoogleIdentityVerifier:
    def __init__(self) -> None:
        self.verify_result: VerifiedGoogleIdentity | None = None
        self.side_effect: Exception | None = None

    async def verify(
        self, id_token: str, nonce: str | None = None
    ) -> VerifiedGoogleIdentity:
        if self.side_effect:
            raise self.side_effect
        if self.verify_result:
            return self.verify_result
        return VerifiedGoogleIdentity(
            subject="default-sub",
            email="googleuser@gmail.com",
            email_verified=True,
            hosted_domain=None,
        )


