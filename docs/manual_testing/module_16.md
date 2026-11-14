# Module 16 Manual Testing Guide: Saved Listings

## Start Here
Welcome to the manual testing guide for Module 16 (Saved Listings). You will test saving listings, viewing saved items, availability states, and the heart indicator (`is_saved`).

### Test Accounts
- **Ada**: `ada@example.com` (Student)
- **Bola**: `Bola@example.com` or `scout@example.com` (Scout)
- **Ade**: `admin@example.com` (Admin)

### Helpers (Paste once per Termux session)
```bash
BASE=http://localhost:8000/api/v1
login() { curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' -d "{\"email\":\"$1\",\"password\":\"$2\"}" | jq -r '.access_token'; }
api() { curl -s -X "$1" "$BASE$2" -H "Authorization: Bearer $3" -H 'Content-Type: application/json' ${4:+-d "$4"} | jq .; }
```

---

## Test Scenarios

### S1 — Save and Unsave
*What this proves:* Tapping the heart works and is idempotent (safe to repeat).
*Do this:*
```bash
ADA=$(login ada@example.com password123)
api PUT /saved-listings/YOUR_LISTING_ID $ADA
api PUT /saved-listings/YOUR_LISTING_ID $ADA
api GET /saved-listings $ADA
api DELETE /saved-listings/YOUR_LISTING_ID $ADA
```
*You should see:* Both `PUT` requests succeed with `"already_saved": true` or `saved: true`. The list shows the item; after `DELETE`, the list is empty.
*If you don't:* Duplicate rows or errors on repeat `PUT` indicate a bug.
*Cleanup:* None required.

### S2 — The Heart on Search & Detail
*What this proves:* Search results and listing detail correctly reflect `is_saved`.
*Do this:*
```bash
api GET /search/listings $ADA
api GET /listings/YOUR_LISTING_ID $ADA
```
*You should see:* `is_saved: true` (if saved) or `false` (if unsaved) on search items and detail responses.
*If you don't:* Check authentication token and listing ID.
*Cleanup:* None.

### S3 — Saves are Private
*What this proves:* Other users cannot view Ada's saved listings.
*Do this:*
```bash
BOLA_TOKEN=$(login scout@example.com password123)
api GET /saved-listings $BOLA_TOKEN
```
*You should see:* An empty list (`total: 0`).
*If you don't:* Data isolation failure.
*Cleanup:* None.

### S4 — Cannot Save Own Listing
*What this proves:* Scouts cannot save their own listings.
*Do this:*
```bash
api PUT /saved-listings/BOLA_LISTING_ID $BOLA_TOKEN
```
*You should see:* `409 Conflict` with `cannot_save_own_listing`.
*If you don't:* Incorrect ownership check.
*Cleanup:* None.

### S5 — Hidden Listings Look Non-Existent
*What this proves:* Paused or non-existent listings produce identical `404` errors.
*Do this:*
```bash
api PUT /saved-listings/PAUSED_LISTING_ID $ADA
api PUT /saved-listings/00000000-0000-0000-0000-000000000000 $ADA
```
*You should see:* Identical `404` error bodies (`listing_not_found`).
*If you don't:* Information leakage between hidden and non-existent IDs.
*Cleanup:* None.
