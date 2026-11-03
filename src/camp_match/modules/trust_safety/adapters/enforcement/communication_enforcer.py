"""Communication enforcer adapter for Trust & Safety."""
from __future__ import annotations

from datetime import datetime

from camp_match.config.settings import get_settings
from camp_match.modules.messaging.application.errors import RestrictionNotFound
from camp_match.modules.messaging.application.ports.inbound import (
    LiftCommunicationRestrictionRequest,
    RestrictCommunicationRequest,
)
from camp_match.modules.messaging.application.use_cases.restriction_management import (
    LiftCommunicationRestrictionUseCase,
    RestrictCommunicationUseCase,
)
from camp_match.modules.trust_safety.application.errors import (
    PermanentEnforcementError,
    TransientEnforcementError,
)
from camp_match.shared_kernel.application.errors import ForbiddenError, NotFoundError, ValidationError
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessCommunicationEnforcer:
    def __init__(
        self,
        restrict_uc: RestrictCommunicationUseCase,
        lift_uc: LiftCommunicationRestrictionUseCase,
    ) -> None:
        self._restrict_uc = restrict_uc
        self._lift_uc = lift_uc

    def _check_debug(self) -> None:
        settings = get_settings()
        if settings.app_env in ("local", "test") and getattr(settings, "safety_debug_fail_enforcement", False):
            raise TransientEnforcementError("Debug enforcement failure requested.")

    async def restrict(
        self, actor_id: EntityId, user_id: EntityId, ends_at: datetime, reference: EntityId
    ) -> None:
        self._check_debug()
        try:
            await self._restrict_uc.execute(
                RestrictCommunicationRequest(
                    actor_id=actor_id,
                    user_id=user_id,
                    ends_at=ends_at,
                    source_reference=reference,
                )
            )
        except (RestrictionNotFound, NotFoundError, ForbiddenError, ValidationError):
            raise PermanentEnforcementError("Permanent enforcement failure on communication restrict.")
        except Exception as e:
            if isinstance(e, PermanentEnforcementError):
                raise
            raise TransientEnforcementError(str(e)) from e

    async def lift(self, actor_id: EntityId, reference: EntityId) -> None:
        self._check_debug()
        try:
            await self._lift_uc.execute(
                LiftCommunicationRestrictionRequest(
                    actor_id=actor_id,
                    source_reference=reference,
                )
            )
        except RestrictionNotFound:
            # Treated as success per C8 / specification (nothing to lift)
            return
        except (NotFoundError, ForbiddenError, ValidationError):
            raise PermanentEnforcementError("Permanent enforcement failure on communication lift.")
        except Exception as e:
            if isinstance(e, PermanentEnforcementError):
                raise
            raise TransientEnforcementError(str(e)) from e
