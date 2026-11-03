"""Verification domain events."""
from __future__ import annotations

from dataclasses import dataclass

from camp_match.modules.verification.domain.value_objects import VerificationTargetType
from camp_match.shared_kernel.domain.events import DomainEvent
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, kw_only=True)
class VerificationDecisionRecorded(DomainEvent):
    case_id: EntityId
    target_type: VerificationTargetType
    target_id: EntityId
    decision: str
