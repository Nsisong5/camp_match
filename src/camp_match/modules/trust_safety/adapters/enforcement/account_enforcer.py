"""Account enforcer adapter for Trust & Safety."""
from __future__ import annotations

from camp_match.config.settings import get_settings
from camp_match.modules.identity.application.ports.inbound import UpdateStatusRequest
from camp_match.modules.identity.application.use_cases.disable_account import DisableAccountUseCase
from camp_match.modules.identity.application.use_cases.reactivate_account import ReactivateAccountUseCase
from camp_match.modules.trust_safety.application.errors import (
    PermanentEnforcementError,
    TransientEnforcementError,
)
from camp_match.shared_kernel.application.errors import ForbiddenError, NotFoundError, ValidationError
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessAccountEnforcer:
    def __init__(
        self,
        disable_uc: DisableAccountUseCase,
        reactivate_uc: ReactivateAccountUseCase,
    ) -> None:
        self._disable_uc = disable_uc
        self._reactivate_uc = reactivate_uc

    def _check_debug(self) -> None:
        settings = get_settings()
        if settings.app_env in ("local", "test") and getattr(settings, "safety_debug_fail_enforcement", False):
            raise TransientEnforcementError("Debug enforcement failure requested.")

    async def disable(self, identity_id: EntityId) -> None:
        self._check_debug()
        try:
            await self._disable_uc.execute(UpdateStatusRequest(identity_id=str(identity_id)))
        except (NotFoundError, ForbiddenError, ValidationError):
            raise PermanentEnforcementError("Permanent enforcement failure on account disable.")
        except Exception as e:
            if isinstance(e, PermanentEnforcementError):
                raise
            raise TransientEnforcementError(str(e)) from e

    async def reactivate(self, identity_id: EntityId) -> None:
        self._check_debug()
        try:
            await self._reactivate_uc.execute(UpdateStatusRequest(identity_id=str(identity_id)))
        except (NotFoundError, ForbiddenError, ValidationError):
            raise PermanentEnforcementError("Permanent enforcement failure on account reactivate.")
        except Exception as e:
            if isinstance(e, PermanentEnforcementError):
                raise
            raise TransientEnforcementError(str(e)) from e
