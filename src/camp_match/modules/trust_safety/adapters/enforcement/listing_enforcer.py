"""Listing enforcer adapter for Trust & Safety."""
from __future__ import annotations

from camp_match.config.settings import get_settings
from camp_match.modules.housing.application.ports.inbound import (
    LiftListingSuspensionCommand,
    SuspendListingForSafetyCommand,
)
from camp_match.modules.housing.application.use_cases.unit_listing_management import (
    LiftListingSuspensionUseCase,
    SuspendListingForSafetyUseCase,
)
from camp_match.modules.trust_safety.application.errors import (
    PermanentEnforcementError,
    TransientEnforcementError,
)
from camp_match.shared_kernel.application.errors import ForbiddenError, NotFoundError, ValidationError
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessListingEnforcer:
    def __init__(
        self,
        suspend_uc: SuspendListingForSafetyUseCase,
        lift_uc: LiftListingSuspensionUseCase,
    ) -> None:
        self._suspend_uc = suspend_uc
        self._lift_uc = lift_uc

    def _check_debug(self) -> None:
        settings = get_settings()
        if settings.app_env in ("local", "test") and getattr(settings, "safety_debug_fail_enforcement", False):
            raise TransientEnforcementError("Debug enforcement failure requested.")

    async def suspend(self, actor_id: EntityId, listing_id: EntityId, reference: EntityId) -> None:
        self._check_debug()
        try:
            await self._suspend_uc(SuspendListingForSafetyCommand(identity_id=actor_id, listing_id=listing_id, source_reference=reference))
        except (NotFoundError, ForbiddenError, ValidationError):
            raise PermanentEnforcementError("Permanent enforcement failure on listing suspend.")
        except Exception as e:
            if isinstance(e, PermanentEnforcementError):
                raise
            raise TransientEnforcementError(str(e)) from e

    async def lift(self, actor_id: EntityId, listing_id: EntityId, reference: EntityId) -> None:
        self._check_debug()
        try:
            await self._lift_uc(LiftListingSuspensionCommand(identity_id=actor_id, listing_id=listing_id, source_reference=reference))
        except (NotFoundError, ForbiddenError, ValidationError):
            raise PermanentEnforcementError("Permanent enforcement failure on listing lift.")
        except Exception as e:
            if isinstance(e, PermanentEnforcementError):
                raise
            raise TransientEnforcementError(str(e)) from e
