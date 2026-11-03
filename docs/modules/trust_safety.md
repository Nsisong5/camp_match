# CAMP MATCH — MODULE 13: TRUST & SAFETY (T&S)

## 1. Purpose and Exclusions
Module 13 (Trust & Safety) provides safety reporting, investigation case management, evidence provenance, structured decision-making, and durable enforcement workflows across the Camp Match platform.
- **Exclusions:** No payment or financial actions exist in this module; payment concerns produce a `REFERRED` decision only. No user-level appeals, no investigator-attached file uploads, no anonymous reporting, and no automated data retention/purge policies are included.

## 2. Domain Model & Core Entities
- **Report (`SafetyReport`):** An allegation submitted by a student or scout against a listing, booking, or conversation/message. Append-only, immutable.
- **Case (`SafetyCase`):** An investigative container grouping reports, evidence, investigation notes, decisions, and enforcement actions. Managed through 7 lifecycle states (`OPEN`, `TRIAGED`, `IN_REVIEW`, `AWAITING_INFORMATION`, `ESCALATED`, `RESOLVED`, `CLOSED`) with optimistic locking (`version`) and cycle counting (`cycle`).
- **EvidenceItem (`EvidenceItem`):** Provenance-tracked evidence items (message snapshots or resource references) protected by database immutability triggers.
- **InvestigationNote (`InvestigationNote`):** Notes (`OBSERVATION`, `WORKING_NOTE`, `CORROBORATED_FACT`) associated with cases. Protected by database immutability triggers.
- **CaseDecision (`CaseDecision`):** Formal determinations (`VIOLATION_ESTABLISHED`, `NO_VIOLATION_ESTABLISHED`, `INSUFFICIENT_EVIDENCE`, `REFERRED`, `FURTHER_INVESTIGATION_REQUIRED`). At most one final decision per case cycle.
- **EnforcementAction (`EnforcementAction`):** Durable state machine actions (`WARNING`, `COMMUNICATION_RESTRICTION`, `LISTING_SUSPENSION`, `ACCOUNT_SUSPENSION`) requiring four-eyes approval (proposer ≠ approver) and idempotent downstream execution.

## 3. Categories and Submission Rules
- **Categories:** `SCAM_OR_FRAUD`, `MISLEADING_LISTING`, `HARASSMENT`, `IMPERSONATION`, `PAYMENT_CONCERN`, `THREAT_OR_DANGER`, `OTHER`.
- **Rules:** Reporters cannot report themselves or their own content. Duplicate open reports on the same subject triple by the same reporter are rejected (`409 duplicate_open_report`). Rate limiting enforces max 5 reports per rolling window.

## 4. Case Lifecycle (C6) & Permissions
- **States:** `OPEN`, `TRIAGED`, `IN_REVIEW`, `AWAITING_INFORMATION`, `ESCALATED`, `RESOLVED`, `CLOSED`.
- **Permissions:** `SAFETY_REPORT_SUBMIT` (Student, Scout), `SAFETY_CASE_REVIEW` (Operations/Reviewer), `SAFETY_EVIDENCE_VIEW` (Operations/Reviewer - strict audit), `SAFETY_ENFORCEMENT_APPROVE` (Admin/Approver), `MESSAGING_RESTRICT` (Admin), `HOUSING_SAFETY_SUSPEND` (Admin).
- **Separation of Duties:** Reviewer ≠ Approver for non-warning actions. No actor may touch a case they are the subject or reporter of (`404` existence leak prevention).

## 5. Enforcement Workflow (C7)
- `PROPOSED` → `APPROVED` (requires non-proposing admin) → `APPLIED` (upon successful return from owning module) or `FAILED` / `REVERSAL_PENDING` / `REVERSAL_FAILED`.
- Idempotent execution using `reference = action id`.

## 6. Integration Contracts & Amendments
- **Housing Amendment:** Adds `SUSPENDED` listing status; use cases `SuspendListingForSafety` and `LiftListingSuspension`.
- **Messaging Amendment:** `messaging_restrictions` table; communication restrictions block sending/starting conversations while reading remains unaffected.
- **Identity Amendment:** Account suspension / reactivation integration.
- **Notification Amendment:** Fixed safety notification templates (`REPORT_RECEIVED`, `REPORT_REVIEWED`, `WARNING_ISSUED`, `LISTING_SUSPENDED`, `COMMUNICATION_RESTRICTED`, `ACCOUNT_SUSPENDED`, `RESTRICTION_LIFTED`, `SUSPENSION_LIFTED`).

## 7. Known Limitations
- No appeals workflow.
- No file attachments or external evidence uploads.
- No anonymous or unauthenticated reports.
- No automated data retention/purge policy.
- Account suspension reversal can re-enable an account an administrator separately disabled.
- Safety notifications are at-most-once across a crash between commit and publish.
- Admin & Operations module provides overview data and recovery actions; staff UI remains to be built.
