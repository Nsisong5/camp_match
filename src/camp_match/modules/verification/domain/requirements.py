from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.verification.domain.value_objects import (
    EvidenceReviewStatus,
    EvidenceType,
    InspectionStatus,
    VerificationTargetType,
)

if TYPE_CHECKING:
    from camp_match.modules.verification.domain.entities import (
        Evidence,
        Inspection,
        VerificationCase,
    )


def decision_prerequisites_satisfied(
    case: VerificationCase,
    evidence_list: list[Evidence],
    inspection: Inspection | None,
) -> tuple[bool, str | None]:
    if case.target_type == VerificationTargetType.PROVIDER:
        has_accepted_identity = any(
            e.evidence_type == EvidenceType.IDENTITY_DOCUMENT
            and e.review_status == EvidenceReviewStatus.ACCEPTED
            for e in evidence_list
        )
        if not has_accepted_identity:
            return False, "Provider verification requires at least one accepted identity document."
        return True, None

    if case.target_type == VerificationTargetType.PROPERTY:
        has_accepted_property_doc = any(
            e.evidence_type == EvidenceType.PROPERTY_DOCUMENT
            and e.review_status == EvidenceReviewStatus.ACCEPTED
            for e in evidence_list
        )
        if not has_accepted_property_doc:
            return False, "Property verification requires at least one accepted property document."
        if inspection is None or inspection.status != InspectionStatus.COMPLETED or inspection.result is None:
            return False, "Property verification requires a completed inspection with a result."
        return True, None

    return False, "Unknown verification target type."
