# Module 16: Saved Listings Specification & Overview

## Purpose
The Saved Listings module allows students and users to like or save housing listings, organize and review their saved listings in a dedicated view, and see favorite heart indicators (`is_saved`) across search results, discovery feeds, and listing detail pages.

## Availability States
When listing saved items, each saved listing has an availability state derived from the housing catalog:
1. **`AVAILABLE`**: The listing is published and has free capacity. The response includes the full listing card details.
2. **`FULLY_BOOKED`**: The listing is published but all units are currently occupied. The response includes the full listing card with a fully booked indicator.
3. **`UNAVAILABLE`**: The listing is hidden, paused, suspended, archived, or no longer exists. The `listing` field is `null`. Users can remove unavailable items from their saved list.

## Privacy & Security Rules
- Saved listings are strictly private. Users cannot view another user's saved listings.
- A user cannot save their own listing (`cannot_save_own_listing`).
- Unauthenticated requests are rejected with `401`.
- Non-existent and hidden listings produce identical `404` errors (`listing_not_found`).

## Concurrency & Limits
- Saves are fully idempotent (re-saving an already saved listing returns `already_saved = true` without duplication).
- Per-user capacity limits (`saved_listings_max_per_user`, default 200) prevent abuse, raising `saved_limit_reached` (409) when exceeded. Re-saving existing saves at the cap always succeeds.

## Integration Amendments
- **Housing:** Provides system lookups (`GetListingForSaving`, `GetListingCards`) via in-process inbound ports, and populates `is_saved` on listing detail views.
- **Search & Discovery:** Integrates via `SavedStateProvider` to decorate search and discovery feed items with `is_saved` without affecting ranking, filters, pagination, or visibility.

## Known Limitations
- No push/in-app notifications for saved listing status changes.
- No scout-facing save counts or aggregate analytics.
