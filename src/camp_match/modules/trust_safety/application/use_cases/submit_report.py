"""Submit report use case for Trust & Safety."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

import structlog

from camp_match.config.settings import get_settings
from camp_match.modules.trust_safety.application.errors import (
    DuplicateOpenReport,
    IdempotencyKeyConflict,
    InvalidIdempotencyKey,
    InvalidReportDescription,
    InvalidReportSubject,
    ReportRateLimitExceeded,
)
from camp_match.modules.trust_safety.application.ports.events import SafetyUpdatePublished
from camp_match.modules.trust_safety.application.ports.inbound import ReportAck, SubmitReportRequest
from camp_match.modules.trust_safety.application.ports.outbound import (
    BookingSubjectProvider,
    EvidenceRepository,
    ListingSubjectProvider,
    MessageEvidenceProvider,
    ReportRepository,
)
from camp_match.modules.trust_safety.domain.entities import EvidenceItem, Report
from camp_match.modules.trust_safety.domain.value_objects import (
    Confidentiality,
    EvidenceType,
    ReportCategory,
    ReportDescription,
    ReportStatus,
    SafetyUpdateKind,
    SubjectType,
)
from camp_match.shared_kernel.application.event_bus import EventBus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()

_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class SubmitReportUseCase:
    def __init__(
        self,
        report_repo: ReportRepository,
        evidence_repo: EvidenceRepository,
        listing_subject_provider: ListingSubjectProvider,
        booking_subject_provider: BookingSubjectProvider,
        message_evidence_provider: MessageEvidenceProvider,
        authorization_service: Any,
        event_bus: EventBus,
        unit_of_work: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._report_repo = report_repo
        self._evidence_repo = evidence_repo
        self._listing_provider = listing_subject_provider
        self._booking_provider = booking_subject_provider
        self._message_provider = message_evidence_provider
        self._auth = authorization_service
        self._event_bus = event_bus
        self._uow = unit_of_work
        self._clock = clock

    async def execute(self, request: SubmitReportRequest) -> ReportAck:
        from camp_match.modules.security.domain.value_objects import Permission
        await self._auth.authorize(request.actor_id, Permission.SAFETY_REPORT_SUBMIT)

        if not request.idempotency_key or not _IDEMPOTENCY_KEY_RE.match(request.idempotency_key):
            raise InvalidIdempotencyKey("Invalid idempotency key format.")

        settings = get_settings()
        if not request.description or not (settings.safety_report_description_min <= len(request.description) <= settings.safety_report_description_max):
            raise InvalidReportDescription("Invalid report description length.")

        cat_val = request.category.value if hasattr(request.category, "value") else str(request.category)
        sub_type_val = request.subject_type.value if hasattr(request.subject_type, "value") else str(request.subject_type)
        cat_obj = ReportCategory(request.category) if isinstance(request.category, str) else request.category
        sub_type_obj = SubjectType(request.subject_type) if isinstance(request.subject_type, str) else request.subject_type

        fp_payload = json.dumps({
            "category": cat_val,
            "subject_type": sub_type_val,
            "subject_id": str(request.subject_id),
            "description": request.description,
        }, sort_keys=True)
        request_fingerprint = hashlib.sha256(fp_payload.encode()).hexdigest()

        existing = await self._report_repo.get_by_idempotency_key(request.actor_id, request.idempotency_key)
        if existing:
            if existing.request_fingerprint == request_fingerprint:
                return ReportAck(
                    report_id=existing.id,
                    status=existing.status,
                    created_at=existing.created_at,
                    replayed=True,
                )
            else:
                raise IdempotencyKeyConflict("Idempotency key conflict.")

        since = self._clock.now().timestamp() - settings.safety_report_rate_limit_window_seconds
        recent_count = await self._report_repo.count_recent_by_reporter(request.actor_id, datetime.fromtimestamp(since, timezone.utc))
        if recent_count >= settings.safety_report_rate_limit_count:
            raise ReportRateLimitExceeded("Rate limit exceeded.", retry_after_seconds=settings.safety_report_rate_limit_window_seconds)

        subject_user_id: EntityId | None = None
        evidence_items: list[tuple[EvidenceType, str, EntityId, dict[str, Any] | None, str | None]] = []

        if request.subject_type == SubjectType.LISTING:
            listing = await self._listing_provider.get_listing(request.subject_id, request.actor_id)
            if not listing or listing.owner_id == request.actor_id:
                raise InvalidReportSubject("Invalid report subject.")
            subject_user_id = listing.owner_id
            evidence_items.append((EvidenceType.RESOURCE_REFERENCE, "LISTING", listing.listing_id, None, None))

        elif request.subject_type == SubjectType.BOOKING:
            booking = await self._booking_provider.get_booking(request.subject_id, request.actor_id)
            if not booking or (request.actor_id != booking.student_id and request.actor_id != booking.provider_id):
                raise InvalidReportSubject("Invalid report subject.")
            subject_user_id = booking.provider_id if request.actor_id == booking.student_id else booking.student_id
            evidence_items.append((EvidenceType.RESOURCE_REFERENCE, "BOOKING", booking.booking_id, None, None))

        elif request.subject_type == SubjectType.CONVERSATION:
            if not request.conversation_id or not request.message_id:
                raise InvalidReportSubject("Invalid report subject.")
            msg_snap = await self._message_provider.get_message(request.actor_id, request.conversation_id, request.message_id)
            if not msg_snap or msg_snap.sender_id == request.actor_id:
                raise InvalidReportSubject("Invalid report subject.")
            subject_user_id = msg_snap.sender_id

            snapshot_dict = {
                "message_id": str(msg_snap.message_id),
                "conversation_id": str(msg_snap.conversation_id),
                "sender_id": str(msg_snap.sender_id),
                "content": msg_snap.content,
                "sequence": msg_snap.sequence,
                "created_at": msg_snap.created_at.isoformat(),
            }
            snap_json = json.dumps(snapshot_dict, sort_keys=True)
            content_sha256 = hashlib.sha256(snap_json.encode()).hexdigest()
            evidence_items.append((EvidenceType.MESSAGE_SNAPSHOT, "MESSAGE", msg_snap.message_id, snapshot_dict, content_sha256))
        else:
            raise InvalidReportSubject("Invalid report subject.")

        now = self._clock.now()
        report_id = EntityId.new()
        report = Report(
            id=report_id,
            reporter_id=request.actor_id,
            category=cat_obj,
            subject_type=sub_type_obj,
            subject_id=request.subject_id,
            subject_user_id=subject_user_id,
            description=ReportDescription(request.description),
            status=ReportStatus.RECEIVED,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request_fingerprint,
            created_at=now,
        )

        async with self._uow:
            try:
                await self._report_repo.add(report)
                for ev_type, res_type, res_id, snapshot, sha256 in evidence_items:
                    evidence = EvidenceItem(
                        id=EntityId.new(),
                        report_id=report_id,
                        evidence_type=ev_type,
                        resource_type=res_type,
                        resource_id=res_id,
                        conversation_id=request.conversation_id if ev_type == EvidenceType.MESSAGE_SNAPSHOT else None,
                        snapshot=snapshot,
                        content_sha256=sha256,
                        collected_by=request.actor_id,
                        collected_at=now,
                        source="api",
                        confidentiality=Confidentiality.RESTRICTED if ev_type == EvidenceType.MESSAGE_SNAPSHOT else Confidentiality.INTERNAL,
                    )
                    await self._evidence_repo.add(evidence)
                await self._uow.commit()
            except (IdempotencyKeyConflict, DuplicateOpenReport):
                await self._uow.rollback()
                raise
            except Exception as e:
                import traceback
                traceback.print_exc()
                await self._uow.rollback()
                raise IdempotencyKeyConflict("Idempotency key conflict or duplicate report.") from e

        try:
            await self._event_bus.publish(
                SafetyUpdatePublished(
                    recipient_id=request.actor_id,
                    kind=SafetyUpdateKind.REPORT_RECEIVED,
                    reference_type="REPORT",
                    reference_id=report_id,
                )
            )
        except Exception:
            pass

        logger.info(
            "safety_report_accepted",
            report_id=str(report_id),
            category=request.category.value,
            subject_type=request.subject_type.value,
        )

        return ReportAck(
            report_id=report_id,
            status=ReportStatus.RECEIVED,
            created_at=now,
            replayed=False,
        )
