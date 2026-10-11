from camp_match.modules.search.application.ports.outbound import UniversityLocationProvider
from camp_match.modules.university_location.application.ports.inbound import GetCampus, GetMainCampus
from camp_match.modules.university_location.application.errors import CampusNotFound
from camp_match.modules.search.domain.value_objects import Coordinates, EntityId

class UniversityLocationProviderAdapter(UniversityLocationProvider):
    def __init__(self, get_campus: GetCampus, get_main_campus: GetMainCampus | None = None):
        self._get_campus = get_campus
        self._get_main_campus = get_main_campus

    async def get_campus_coordinates(self, campus_id: EntityId) -> Coordinates | None:
        try:
            campus = await self._get_campus.execute(str(campus_id))
            return Coordinates(latitude=campus.latitude, longitude=campus.longitude)
        except CampusNotFound:
            return None
        except Exception:
            return None

    async def get_main_campus_coordinates(self, university_id: EntityId) -> Coordinates | None:
        if not self._get_main_campus:
            return None
        try:
            main_campus = await self._get_main_campus.execute(str(university_id))
            if not main_campus:
                return None
            campus = await self._get_campus.execute(main_campus.id)
            return Coordinates(latitude=campus.latitude, longitude=campus.longitude)
        except Exception:
            return None
