from __future__ import annotations

from typing import cast

from camp_match.modules.booking.domain.events import (
    BookingCancelled,
    BookingConfirmed,
    BookingCreated,
    BookingExpired,
    BookingInvalidated,
    BookingReminderDue,
    HandoverAccepted,
    HandoverOffered,
)
from camp_match.modules.housing.domain.events import (
    ListingSuspended,
    ListingSuspensionLifted,
)
from camp_match.modules.identity.domain.events import (
    AccountDisabled,
    AccountReactivated,
)
from camp_match.modules.payment.domain.events import (
    PaymentAutoReleaseWarning,
    PaymentDisputeRaised,
    PaymentFundsRefunded,
    PaymentFundsReleased,
    PaymentOutcomeRecorded,
    PaymentReleaseDue,
)
from camp_match.modules.platform_runtime.adapters.registry.event_contract_registry import (
    EventContractRegistry,
)
from camp_match.modules.trust_safety.domain.events import SafetyUpdatePublished
from camp_match.modules.trust_safety.domain.value_objects import SafetyUpdateKind
from camp_match.modules.verification.domain.events import VerificationDecisionRecorded
from camp_match.modules.verification.domain.value_objects import VerificationTargetType
from camp_match.shared_kernel.domain.events import EventContract
from camp_match.shared_kernel.domain.identifiers import EntityId


def create_default_event_registry() -> EventContractRegistry:
    registry = EventContractRegistry()

    # Booking contracts
    registry.register(
        EventContract(
            event_type="booking.created",
            event_class=BookingCreated,
            to_payload=lambda ev: {
                "booking_id": str(cast(BookingCreated, ev).booking_id),
                "student_id": str(cast(BookingCreated, ev).student_id),
                "property_id": str(cast(BookingCreated, ev).property_id),
                "listing_id": str(cast(BookingCreated, ev).listing_id),
            },
            from_payload=lambda pl, eid, occ: BookingCreated(
                event_id=eid,
                occurred_at=occ,
                booking_id=EntityId(pl["booking_id"]),
                student_id=EntityId(pl["student_id"]),
                property_id=EntityId(pl["property_id"]),
                listing_id=EntityId(pl["listing_id"]),
            ),
        )
    )

    registry.register(
        EventContract(
            event_type="booking.confirmed",
            event_class=BookingConfirmed,
            to_payload=lambda ev: {
                "booking_id": str(cast(BookingConfirmed, ev).booking_id),
                "student_id": str(cast(BookingConfirmed, ev).student_id),
                "property_id": str(cast(BookingConfirmed, ev).property_id),
                "listing_id": str(cast(BookingConfirmed, ev).listing_id),
            },
            from_payload=lambda pl, eid, occ: BookingConfirmed(
                event_id=eid,
                occurred_at=occ,
                booking_id=EntityId(pl["booking_id"]),
                student_id=EntityId(pl["student_id"]),
                property_id=EntityId(pl["property_id"]),
                listing_id=EntityId(pl["listing_id"]),
            ),
        )
    )

    registry.register(
        EventContract(
            event_type="booking.cancelled",
            event_class=BookingCancelled,
            to_payload=lambda ev: {
                "booking_id": str(cast(BookingCancelled, ev).booking_id),
                "student_id": str(cast(BookingCancelled, ev).student_id),
                "property_id": str(cast(BookingCancelled, ev).property_id),
                "listing_id": str(cast(BookingCancelled, ev).listing_id),
                "cancelled_by": str(cast(BookingCancelled, ev).cancelled_by),
            },
            from_payload=lambda pl, eid, occ: BookingCancelled(
                event_id=eid,
                occurred_at=occ,
                booking_id=EntityId(pl["booking_id"]),
                student_id=EntityId(pl["student_id"]),
                property_id=EntityId(pl["property_id"]),
                listing_id=EntityId(pl["listing_id"]),
                cancelled_by=EntityId(pl["cancelled_by"]),
            ),
        )
    )

    registry.register(
        EventContract(
            event_type="booking.expired",
            event_class=BookingExpired,
            to_payload=lambda ev: {
                "booking_id": str(cast(BookingExpired, ev).booking_id),
                "student_id": str(cast(BookingExpired, ev).student_id),
                "property_id": str(cast(BookingExpired, ev).property_id),
                "listing_id": str(cast(BookingExpired, ev).listing_id),
            },
            from_payload=lambda pl, eid, occ: BookingExpired(
                event_id=eid,
                occurred_at=occ,
                booking_id=EntityId(pl["booking_id"]),
                student_id=EntityId(pl["student_id"]),
                property_id=EntityId(pl["property_id"]),
                listing_id=EntityId(pl["listing_id"]),
            ),
        )
    )

    # Housing contracts
    registry.register(
        EventContract(
            event_type="housing.listing_suspended",
            event_class=ListingSuspended,
            to_payload=lambda ev: {
                "listing_id": str(cast(ListingSuspended, ev).listing_id),
                "property_id": str(cast(ListingSuspended, ev).property_id),
                "owner_id": str(cast(ListingSuspended, ev).owner_id),
                "reason_code": cast(ListingSuspended, ev).reason_code,
                "reference_id": str(cast(ListingSuspended, ev).reference_id)
                if cast(ListingSuspended, ev).reference_id
                else None,
            },
            from_payload=lambda pl, eid, occ: ListingSuspended(
                event_id=eid,
                occurred_at=occ,
                listing_id=EntityId(pl["listing_id"]),
                property_id=EntityId(pl["property_id"]),
                owner_id=EntityId(pl["owner_id"]),
                reason_code=pl["reason_code"],
                reference_id=EntityId(pl["reference_id"])
                if pl.get("reference_id")
                else None,
            ),
        )
    )

    registry.register(
        EventContract(
            event_type="housing.listing_suspension_lifted",
            event_class=ListingSuspensionLifted,
            to_payload=lambda ev: {
                "listing_id": str(cast(ListingSuspensionLifted, ev).listing_id),
                "property_id": str(cast(ListingSuspensionLifted, ev).property_id),
                "owner_id": str(cast(ListingSuspensionLifted, ev).owner_id),
            },
            from_payload=lambda pl, eid, occ: ListingSuspensionLifted(
                event_id=eid,
                occurred_at=occ,
                listing_id=EntityId(pl["listing_id"]),
                property_id=EntityId(pl["property_id"]),
                owner_id=EntityId(pl["owner_id"]),
            ),
        )
    )

    # Verification contracts
    registry.register(
        EventContract(
            event_type="verification.decision_recorded",
            event_class=VerificationDecisionRecorded,
            to_payload=lambda ev: {
                "case_id": str(cast(VerificationDecisionRecorded, ev).case_id),
                "target_type": cast(VerificationDecisionRecorded, ev).target_type.value,
                "target_id": str(cast(VerificationDecisionRecorded, ev).target_id),
                "decision": cast(VerificationDecisionRecorded, ev).decision,
            },
            from_payload=lambda pl, eid, occ: VerificationDecisionRecorded(
                event_id=eid,
                occurred_at=occ,
                case_id=EntityId(pl["case_id"]),
                target_type=VerificationTargetType(pl["target_type"]),
                target_id=EntityId(pl["target_id"]),
                decision=pl["decision"],
            ),
        )
    )

    # Trust & Safety contracts
    registry.register(
        EventContract(
            event_type="trust_safety.update_published",
            event_class=SafetyUpdatePublished,
            to_payload=lambda ev: {
                "recipient_id": str(cast(SafetyUpdatePublished, ev).recipient_id),
                "kind": cast(SafetyUpdatePublished, ev).kind.value,
                "reference_type": cast(SafetyUpdatePublished, ev).reference_type,
                "reference_id": str(cast(SafetyUpdatePublished, ev).reference_id)
                if cast(SafetyUpdatePublished, ev).reference_id
                else None,
            },
            from_payload=lambda pl, eid, occ: SafetyUpdatePublished(
                event_id=eid,
                occurred_at=occ,
                recipient_id=EntityId(pl["recipient_id"]),
                kind=SafetyUpdateKind(pl["kind"]),
                reference_type=pl.get("reference_type"),
                reference_id=EntityId(pl["reference_id"])
                if pl.get("reference_id")
                else None,
            ),
        )
    )

    # Identity contracts
    registry.register(
        EventContract(
            event_type="identity.account_disabled",
            event_class=AccountDisabled,
            to_payload=lambda ev: {"user_id": str(cast(AccountDisabled, ev).user_id)},
            from_payload=lambda pl, eid, occ: AccountDisabled(
                event_id=eid, occurred_at=occ, user_id=EntityId(pl["user_id"])
            ),
        )
    )

    registry.register(
        EventContract(
            event_type="identity.account_reactivated",
            event_class=AccountReactivated,
            to_payload=lambda ev: {"user_id": str(cast(AccountReactivated, ev).user_id)},
            from_payload=lambda pl, eid, occ: AccountReactivated(
                event_id=eid, occurred_at=occ, user_id=EntityId(pl["user_id"])
            ),
        )
    )

    # Booking lifecycle event contracts (Handover, Invalidation, Reminders)
    registry.register(
        EventContract(
            event_type="HandoverOffered",
            event_class=HandoverOffered,
            to_payload=lambda ev: {
                "booking_id": str(cast(HandoverOffered, ev).booking_id),
                "student_id": str(cast(HandoverOffered, ev).student_id),
                "property_id": str(cast(HandoverOffered, ev).property_id),
                "listing_id": str(cast(HandoverOffered, ev).listing_id),
                "offered_by": str(cast(HandoverOffered, ev).offered_by),
            },
            from_payload=lambda pl, eid, occ: HandoverOffered(
                event_id=eid,
                occurred_at=occ,
                booking_id=EntityId(pl["booking_id"]),
                student_id=EntityId(pl["student_id"]),
                property_id=EntityId(pl["property_id"]),
                listing_id=EntityId(pl["listing_id"]),
                offered_by=EntityId(pl["offered_by"]),
            ),
        )
    )

    registry.register(
        EventContract(
            event_type="HandoverAccepted",
            event_class=HandoverAccepted,
            to_payload=lambda ev: {
                "booking_id": str(cast(HandoverAccepted, ev).booking_id),
                "student_id": str(cast(HandoverAccepted, ev).student_id),
                "property_id": str(cast(HandoverAccepted, ev).property_id),
                "listing_id": str(cast(HandoverAccepted, ev).listing_id),
            },
            from_payload=lambda pl, eid, occ: HandoverAccepted(
                event_id=eid,
                occurred_at=occ,
                booking_id=EntityId(pl["booking_id"]),
                student_id=EntityId(pl["student_id"]),
                property_id=EntityId(pl["property_id"]),
                listing_id=EntityId(pl["listing_id"]),
            ),
        )
    )

    registry.register(
        EventContract(
            event_type="BookingInvalidated",
            event_class=BookingInvalidated,
            to_payload=lambda ev: {
                "booking_id": str(cast(BookingInvalidated, ev).booking_id),
                "student_id": str(cast(BookingInvalidated, ev).student_id),
                "property_id": str(cast(BookingInvalidated, ev).property_id),
                "listing_id": str(cast(BookingInvalidated, ev).listing_id),
                "reason_code": cast(BookingInvalidated, ev).reason_code,
                "was_confirmed": cast(BookingInvalidated, ev).was_confirmed,
            },
            from_payload=lambda pl, eid, occ: BookingInvalidated(
                event_id=eid,
                occurred_at=occ,
                booking_id=EntityId(pl["booking_id"]),
                student_id=EntityId(pl["student_id"]),
                property_id=EntityId(pl["property_id"]),
                listing_id=EntityId(pl["listing_id"]),
                reason_code=pl["reason_code"],
                was_confirmed=pl["was_confirmed"],
            ),
        )
    )

    registry.register(
        EventContract(
            event_type="BookingReminderDue",
            event_class=BookingReminderDue,
            to_payload=lambda ev: {
                "booking_id": str(cast(BookingReminderDue, ev).booking_id),
                "student_id": str(cast(BookingReminderDue, ev).student_id),
                "property_id": str(cast(BookingReminderDue, ev).property_id),
                "listing_id": str(cast(BookingReminderDue, ev).listing_id),
                "reminder_type": cast(BookingReminderDue, ev).reminder_type,
            },
            from_payload=lambda pl, eid, occ: BookingReminderDue(
                event_id=eid,
                occurred_at=occ,
                booking_id=EntityId(pl["booking_id"]),
                student_id=EntityId(pl["student_id"]),
                property_id=EntityId(pl["property_id"]),
                listing_id=EntityId(pl["listing_id"]),
                reminder_type=pl["reminder_type"],
            ),
        )
    )

    # Payment event contracts
    registry.register(
        EventContract(
            event_type="PaymentOutcomeRecorded",
            event_class=PaymentOutcomeRecorded,
            to_payload=lambda ev: {
                "payment_attempt_id": str(cast(PaymentOutcomeRecorded, ev).payment_attempt_id),
                "booking_id": str(cast(PaymentOutcomeRecorded, ev).booking_id),
                "student_id": str(cast(PaymentOutcomeRecorded, ev).student_id),
                "property_id": str(cast(PaymentOutcomeRecorded, ev).property_id),
                "listing_id": str(cast(PaymentOutcomeRecorded, ev).listing_id),
                "outcome": cast(PaymentOutcomeRecorded, ev).outcome,
            },
            from_payload=lambda pl, eid, occ: PaymentOutcomeRecorded(
                event_id=eid,
                occurred_at=occ,
                payment_attempt_id=EntityId(pl["payment_attempt_id"]),
                booking_id=EntityId(pl["booking_id"]),
                student_id=EntityId(pl["student_id"]),
                property_id=EntityId(pl["property_id"]),
                listing_id=EntityId(pl["listing_id"]),
                outcome=pl["outcome"],
            ),
        )
    )

    registry.register(
        EventContract(
            event_type="PaymentReleaseDue",
            event_class=PaymentReleaseDue,
            to_payload=lambda ev: {
                "payment_id": str(cast(PaymentReleaseDue, ev).payment_id),
                "booking_id": str(cast(PaymentReleaseDue, ev).booking_id),
                "student_id": str(cast(PaymentReleaseDue, ev).student_id),
                "cycle": cast(PaymentReleaseDue, ev).cycle,
            },
            from_payload=lambda pl, eid, occ: PaymentReleaseDue(
                event_id=eid,
                occurred_at=occ,
                payment_id=EntityId(pl["payment_id"]),
                booking_id=EntityId(pl["booking_id"]),
                student_id=EntityId(pl["student_id"]),
                cycle=pl["cycle"],
            ),
        )
    )

    registry.register(
        EventContract(
            event_type="PaymentAutoReleaseWarning",
            event_class=PaymentAutoReleaseWarning,
            to_payload=lambda ev: {
                "payment_id": str(cast(PaymentAutoReleaseWarning, ev).payment_id),
                "booking_id": str(cast(PaymentAutoReleaseWarning, ev).booking_id),
                "student_id": str(cast(PaymentAutoReleaseWarning, ev).student_id),
                "cycle": cast(PaymentAutoReleaseWarning, ev).cycle,
                "warning_stage": cast(PaymentAutoReleaseWarning, ev).warning_stage,
            },
            from_payload=lambda pl, eid, occ: PaymentAutoReleaseWarning(
                event_id=eid,
                occurred_at=occ,
                payment_id=EntityId(pl["payment_id"]),
                booking_id=EntityId(pl["booking_id"]),
                student_id=EntityId(pl["student_id"]),
                cycle=pl["cycle"],
                warning_stage=pl["warning_stage"],
            ),
        )
    )

    registry.register(
        EventContract(
            event_type="PaymentFundsReleased",
            event_class=PaymentFundsReleased,
            to_payload=lambda ev: {
                "payment_id": str(cast(PaymentFundsReleased, ev).payment_id),
                "booking_id": str(cast(PaymentFundsReleased, ev).booking_id),
                "student_id": str(cast(PaymentFundsReleased, ev).student_id),
                "origin": cast(PaymentFundsReleased, ev).origin,
            },
            from_payload=lambda pl, eid, occ: PaymentFundsReleased(
                event_id=eid,
                occurred_at=occ,
                payment_id=EntityId(pl["payment_id"]),
                booking_id=EntityId(pl["booking_id"]),
                student_id=EntityId(pl["student_id"]),
                origin=pl["origin"],
            ),
        )
    )

    registry.register(
        EventContract(
            event_type="PaymentFundsRefunded",
            event_class=PaymentFundsRefunded,
            to_payload=lambda ev: {
                "payment_id": str(cast(PaymentFundsRefunded, ev).payment_id),
                "booking_id": str(cast(PaymentFundsRefunded, ev).booking_id),
                "student_id": str(cast(PaymentFundsRefunded, ev).student_id),
            },
            from_payload=lambda pl, eid, occ: PaymentFundsRefunded(
                event_id=eid,
                occurred_at=occ,
                payment_id=EntityId(pl["payment_id"]),
                booking_id=EntityId(pl["booking_id"]),
                student_id=EntityId(pl["student_id"]),
            ),
        )
    )

    registry.register(
        EventContract(
            event_type="PaymentDisputeRaised",
            event_class=PaymentDisputeRaised,
            to_payload=lambda ev: {
                "payment_id": str(cast(PaymentDisputeRaised, ev).payment_id),
                "booking_id": str(cast(PaymentDisputeRaised, ev).booking_id),
                "student_id": str(cast(PaymentDisputeRaised, ev).student_id),
            },
            from_payload=lambda pl, eid, occ: PaymentDisputeRaised(
                event_id=eid,
                occurred_at=occ,
                payment_id=EntityId(pl["payment_id"]),
                booking_id=EntityId(pl["booking_id"]),
                student_id=EntityId(pl["student_id"]),
            ),
        )
    )

    return registry
