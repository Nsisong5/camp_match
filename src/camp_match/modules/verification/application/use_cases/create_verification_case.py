from __future__ import annotations

from camp_match.modules.verification.application.errors import (
    VerificationCaseNotFound,
    VerificationForbiddenError,
    InvalidVerificationTransition,
)
from camp_match.modules.verification.application.ports.inbound import (
    CreateVerificationCaseRequest,
    CreateVerificationCaseResponse,
)
from camp_match.modules.verification.application.ports.outbound import (
    HistoryRepository,
    HousingProvider,
    VerificationCaseRepository,
)
from camp_match.modules.verification.domain.entities import VerificationCase
from camp_match.modules.verification.domain.value_objects import (
    VerificationStatus,
    VerificationTargetType,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId


class CreateVerificationCaseUseCase:
    def __init__(
        self,
        case_repo: VerificationCaseRepository,
        housing_provider: HousingProvider,
        history_repo: HistoryRepository,
        uow: UnitOfWork,
    ):
        self.case_repo = case_repo
        self.housing_provider = housing_provider
        self.history_repo = history_repo
        self.uow = uow

    async def execute(self, request: CreateVerificationCaseRequest) -> CreateVerificationCaseResponse:
        if request.target_type == VerificationTargetType.PROVIDER:
            owner_id = request.target_id
        elif request.target_type == VerificationTargetType.PROPERTY:
            owner_id = await self.housing_provider.get_property_owner(request.target_id)
            if not owner_id:
                raise VerificationCaseNotFound("Property not found or has no owner.")
        else:
            raise InvalidVerificationTransition("Invalid verification target type.")

        if request.caller_id != owner_id:
            raise VerificationForbiddenError("Caller is not the owner of the verification target.")

        latest_case = await self.case_repo.get_latest_by_target(request.target_type, request.target_id)
        terminal_statuses = {
            VerificationStatus.VERIFIED,
            VerificationStatus.REJECTED,
            VerificationStatus.REVOKED,
            VerificationStatus.CANCELLED,
        }
        if latest_case and latest_case.status not in terminal_statuses:
            raise InvalidVerificationTransition("An in-flight verification case already exists for this target.")

        case_id = EntityId.new()
        case = VerificationCase(
            id=case_id,
            target_type=request.target_type,
            target_id=request.target_id,
            status=VerificationStatus.DRAFT,
            submitted_by=owner_id,
        )

        async with self.uow:
            await self.case_repo.add(case)
            await self.history_repo.add(
                case_id=case.id,
                event_type="verification_case_created",
                actor_id=request.caller_id,
                details=f"Verification case created for {request.target_type.value}",
            )

        return CreateVerificationCaseResponse(case_id=case_id)
