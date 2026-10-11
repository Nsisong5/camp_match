from camp_match.modules.profile.application.ports.outbound import UniversityProvider, UniversitySummary
from camp_match.modules.university_location.application.ports.inbound import GetUniversity
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessUniversityProvider(UniversityProvider):
    def __init__(self, get_university_port: GetUniversity) -> None:
        self._get_university_port = get_university_port

    async def get_university(self, university_id: EntityId) -> UniversitySummary | None:
        try:
            resp = await self._get_university_port.execute(str(university_id))
            if not resp:
                return None
            return UniversitySummary(
                id=EntityId.from_string(resp.id) if isinstance(resp.id, str) else EntityId(resp.id),
                official_name=resp.official_name,
                status=resp.status,
            )
        except Exception as e:
            print("ERROR GET UNIVERSITY:", repr(e))
            raise e
