# Camp Match Module: Verification

## Purpose and Non-Purpose
- **Purpose:** Manage property and provider verification inspection workflows, evidence submission, and decision making (approve, reject, revoke).
- **Non-Purpose:** Housing listing management.

## Published Events
- **Events:** `VerificationDecisionRecorded`.
- **Fields:** `case_id`, `target_type` (`PROVIDER`/`PROPERTY`), `target_id`, `decision` (`VERIFIED`/`REJECTED`/`REVOKED`).
- **Delivery:** Published best-effort via event bus after successful database commit.
