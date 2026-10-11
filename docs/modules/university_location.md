# University Location Module

The University Location module manages the catalog of universities and their respective campuses.

## Key Features
- University registration and lifecycle management.
- Campus management under universities.
- Location-based querying.
- In-process query port (`UniversityLocationQueryPort`) supporting `get_university`, `get_campus`, `get_campus_location`, `list_campuses_for_university`, and `get_main_campus(university_id) -> CampusSummary | None` (returning the campus flagged with `is_main_campus = True`).

## Testability
This module is fully independently testable. It does not have any pending dependencies on future modules; all required components (including Identity and Security) are fully integrated.
