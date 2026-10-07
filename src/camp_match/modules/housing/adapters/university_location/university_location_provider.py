"""Module Housing: university_location_provider.py"""
"""Housing University Location Provider adapter."""

from camp_match.modules.housing.application.ports.outbound import UniversityLocationProvider
from camp_match.modules.university_location.application.ports.inbound import GetCampus
from camp_match.modules.university_location.application.errors import CampusNotFound
from camp_match.shared_kernel.domain.identifiers import EntityId

class InProcessUniversityLocationProvider(UniversityLocationProvider):
    def __init__(self, get_campus_port: GetCampus):
        self._get_campus_port = get_campus_port

    async def campus_exists(self, campus_id: EntityId) -> bool:
        try:
            cid_str = str(campus_id.value if hasattr(campus_id, "value") else campus_id)
            await self._get_campus_port.execute(cid_str)
            return True
        except CampusNotFound:
            return False
        except Exception:
            return False
