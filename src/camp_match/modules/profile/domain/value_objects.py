from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from camp_match.shared_kernel.domain.identifiers import EntityId


class ProfileType(Enum):
    STUDENT = "STUDENT"
    SCOUT = "SCOUT"

class AccommodationTypePreference(Enum):
    SELF_CONTAINED = "SELF_CONTAINED"
    SHARED_ROOM = "SHARED_ROOM"
    HOSTEL = "HOSTEL"
    NO_PREFERENCE = "NO_PREFERENCE"

class CleanlinessPreference(Enum):
    VERY_TIDY = "VERY_TIDY"
    MODERATE = "MODERATE"
    RELAXED = "RELAXED"

class SleepSchedule(Enum):
    EARLY_BIRD = "EARLY_BIRD"
    NIGHT_OWL = "NIGHT_OWL"
    FLEXIBLE = "FLEXIBLE"

class ScoutAvailabilityStatus(Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"

@dataclass(frozen=True)
class StudentProfileDetails:
    university_name: str | None = None
    university_id: EntityId | None = None
    department: str | None = None
    budget_min_naira: int | None = None
    budget_max_naira: int | None = None
    preferred_accommodation_type: AccommodationTypePreference | None = None
    cleanliness_preference: CleanlinessPreference | None = None
    sleep_schedule: SleepSchedule | None = None

    def __post_init__(self) -> None:
        if isinstance(self.university_id, str):
            object.__setattr__(self, "university_id", EntityId.from_string(self.university_id))
        elif isinstance(self.university_id, UUID):
            object.__setattr__(self, "university_id", EntityId(self.university_id))

        if self.budget_min_naira is not None and self.budget_min_naira < 0:
            raise ValueError("budget_min_naira must be non-negative")
        if self.budget_max_naira is not None and self.budget_max_naira < 0:
            raise ValueError("budget_max_naira must be non-negative")
        if (
            self.budget_min_naira is not None 
            and self.budget_max_naira is not None 
            and self.budget_min_naira > self.budget_max_naira
        ):
            raise ValueError("budget_min_naira must be ≤ budget_max_naira")
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "university_name": self.university_name,
            "university_id": str(self.university_id.value) if self.university_id else None,
            "department": self.department,
            "budget_min_naira": self.budget_min_naira,
            "budget_max_naira": self.budget_max_naira,
            "preferred_accommodation_type": self.preferred_accommodation_type.value if self.preferred_accommodation_type else None,
            "cleanliness_preference": self.cleanliness_preference.value if self.cleanliness_preference else None,
            "sleep_schedule": self.sleep_schedule.value if self.sleep_schedule else None,
        }

@dataclass(frozen=True)
class ScoutProfileDetails:
    business_name: str | None = None
    business_description: str | None = None
    years_active: int | None = None
    availability_status: ScoutAvailabilityStatus = ScoutAvailabilityStatus.ACTIVE

    def __post_init__(self) -> None:
        if self.years_active is not None and self.years_active < 0:
            raise ValueError("years_active must be non-negative")
    
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key, value in data.items():
            if isinstance(value, Enum):
                data[key] = value.value
        return data
