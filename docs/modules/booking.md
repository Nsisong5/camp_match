# Camp Match Module: Booking

## Purpose and Non-Purpose
- **Purpose:** Handle student booking creation, payment hold expiration, confirmation, and cancellation.
- **Non-Purpose:** Direct payment processing or escrow ledger entries (delegated to Payment module).

## Published Events
- **Events:** `BookingCreated`, `BookingConfirmed`, `BookingCancelled`, `BookingExpired`.
- **Fields:** `booking_id`, `student_id`, `property_id`, `listing_id` (plus `cancelled_by` for `BookingCancelled`).
- **Delivery:** Published best-effort via event bus after successful database commit.
