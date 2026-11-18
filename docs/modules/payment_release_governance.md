# Payment Release Governance Documentation

## Overview
Release Governance ensures that funds paid into escrow for a camp housing booking are released to the scout only after strict conditions are satisfied, protecting students against fraudulent withdrawals and premature payouts.

## Four Enforcement Layers
1. **Student Confirmation:** Funds can only be released if the student has explicitly confirmed that the housing handover has taken place and they have occupied or accepted the unit.
2. **Review & Schedule State:** Every confirmed payment is tracked via a transaction review record with states (`HELD`, `RELEASE_DUE`, `RELEASED`, `REFUNDED`) and strict `next_action` flags (`RELEASE_FUNDS`, `RESOLVE_DISPUTE`, `DECIDE_REFUND`, `RECONCILE_OPERATION`).
3. **Database Check Constraints:** PostgreSQL check constraints ensure that no manual or automatic release can occur unless `student_confirmed = true` and `open_dispute_id IS NULL`.
4. **Security Role Authorization:** Only users with `PAYMENT_AUTHORIZE_RELEASE` (for release) or `PAYMENT_AUTHORIZE_REFUND` (for refund) can execute fund state mutations.

## Notice Period & Worked Timeline
- **Handover Offered:** Scout marks handover as complete.
- **Student Acceptance:** Student confirms handover.
- **Warning Schedule:** Automated warning jobs dispatch warning notices to admins prior to automatic release (default offsets: 24h, 12h, 3h before 48h deadline).
- **Automatic Release:** If no dispute is raised, funds are automatically released after the delay period expires and minimum warnings have been sent.

## Settings & Jobs
- `payment_auto_release_delay_hours = 48`
- `payment_release_warning_offsets_hours = "24,12,3"`
- Jobs: `payment_release_warnings`, `payment_auto_release`, `payment_review_reconcile`.

## How to Operate It
1. Enable `payment_release_warnings` and `payment_auto_release` in platform job settings when ready for production release automation.
2. Monitor admin tasks via `GET /api/v1/admin/tasks` to resolve pending release items (`RELEASE_DUE`) and open disputes (`RESOLVE_DISPUTE`).
