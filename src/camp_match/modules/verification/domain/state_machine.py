from __future__ import annotations

from camp_match.modules.verification.domain.entities import VerificationCase
from camp_match.modules.verification.domain.value_objects import (
    VerificationStatus,
    VerificationTargetType,
)


def can_transition(
    current: VerificationStatus,
    target: VerificationStatus,
    target_type: VerificationTargetType,
) -> bool:
    # Terminal states have no outbound transitions
    if current in {VerificationStatus.REJECTED, VerificationStatus.REVOKED, VerificationStatus.CANCELLED}:
        return False

    if current == VerificationStatus.DRAFT:
        return target in {VerificationStatus.SUBMITTED, VerificationStatus.CANCELLED}

    if current == VerificationStatus.SUBMITTED:
        return target == VerificationStatus.UNDER_REVIEW

    if current == VerificationStatus.UNDER_REVIEW:
        if target == VerificationStatus.INSPECTION_REQUIRED:
            return target_type == VerificationTargetType.PROPERTY
        if target == VerificationStatus.DECISION_PENDING:
            return True
        return False

    if current == VerificationStatus.INSPECTION_REQUIRED:
        return target == VerificationStatus.INSPECTION_IN_PROGRESS

    if current == VerificationStatus.INSPECTION_IN_PROGRESS:
        return target == VerificationStatus.INSPECTION_COMPLETED

    if current == VerificationStatus.INSPECTION_COMPLETED:
        return target == VerificationStatus.DECISION_PENDING

    if current == VerificationStatus.DECISION_PENDING:
        return target in {VerificationStatus.VERIFIED, VerificationStatus.REJECTED}

    if current == VerificationStatus.VERIFIED:
        return target == VerificationStatus.REVOKED

    return False


def transition(case: VerificationCase, target: VerificationStatus) -> None:
    if not can_transition(case.status, target, case.target_type):
        raise ValueError(
            f"Invalid verification state transition from {case.status.value} to {target.value} for target type {case.target_type.value}."
        )
    case.status = target
