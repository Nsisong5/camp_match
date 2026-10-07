from camp_match.modules.search.application.ports.outbound import UniversityLocationProvider
from camp_match.modules.university_location.application.ports.inbound import GetCampus
from camp_match.modules.university_location.application.errors import CampusNotFound
from camp_match.modules.search.domain.value_objects import Coordinates, EntityId

class UniversityLocationProviderAdapter(UniversityLocationProvider):
    def __init__(self, get_campus: GetCampus):
        self._get_campus = get_campus

    async def get_campus_coordinates(self, campus_id: EntityId) -> Coordinates | None:
        try:
            campus = await self._get_campus.execute(str(campus_id))
            return Coordinates(latitude=campus.latitude, longitude=campus.longitude)
        except CampusNotFound:
            return None
        except Exception:
            return None
