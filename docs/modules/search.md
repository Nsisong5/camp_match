# CAMP MATCH — MODULE 06: SEARCH & DISCOVERY

## Overview
Search & Discovery owns no facts of its own; every field in every result is sourced from other modules. Its purpose is to filter Housing listings, rank them based on relevance, and provide discovery feeds.

## Filtering Rules
A listing is eligible only if it is `PUBLISHED` and has `available_count > 0` (inherited from Housing).
- **campus_id:** Exact match. No `campus_id` in listing = no match.
- **price:** Price bounds inclusive. Billing period must match exactly.
- **accommodation_type:** Exact match.
- **amenities:** Intersection of requested vs listing amenities must equal requested set (all must match).
- **max_distance_km:** Applicable only if `campus_id` is present.
- **verified_only:** If true, only `VERIFIED` state matches.

## Ranking Formula
Weighted sum: `Score = w_p * P_p + w_r * P_r + w_v * P_v + w_f * P_f` (normalized)

| Factor | Weight | Formula | When excluded |
|---|---|---|---|
| Preference match | 0.40 | Unchanged from Module 6 | Student has no preferences set at all |
| Proximity | 0.20 | `max(0, 1 - distance_km / 10)` | Student's `university_id` is unset, or `get_main_campus_coordinates` returns `None` |
| Verification | 0.20 | Unchanged | Never excluded |
| Freshness | 0.20 | Unchanged | Never excluded |

### Haversine Formula
```
Δlat = radians(lat2 − lat1)
Δlon = radians(lon2 − lon1)
a = sin²(Δlat/2) + cos(radians(lat1)) · cos(radians(lat2)) · sin²(Δlon/2)
c = 2 · atan2(√a, √(1−a))
distance_km = R · c
```

## Discovery Strategies
1. **Recently Added:** Freshness and verification weighted equally.
2. **Recommended For You:** Weighted sum of Preference match (0.40), Proximity (0.20), Verification (0.20), and Freshness (0.20) (ADR-091). Proximity is live and resolves via University & Location's main campus coordinates (retiring ADR-062). Fallback to RecentlyAdded if no profile exists (ADR-067).

## Cross-Module Dependencies
- **Housing:** Consumed via the `ListEligibleCandidates` port.
- **University & Location:** Consumed for campus coordinates and main campus location, once per request.
- **Profile:** Consumed for Discovery personalization (`university_id`, preferences) via in-process provider.
- **Verification:** Port real, data is a stub (`UNKNOWN`) or real integration.
- **Security:** Authentication only, no permission.
