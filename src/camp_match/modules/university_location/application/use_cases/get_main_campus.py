from camp_match.modules.university_location.application.ports.inbound import (
    CampusSummary,
    GetMainCampus,
)
from camp_match.modules.university_location.application.ports.outbound import (
    CampusRepository,
    UniversityRepository,
)
from camp_match.shared_kernel.application.pagination import PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class GetMainCampusUseCase(GetMainCampus):
    def __init__(
        self,
        university_repo: UniversityRepository,
        campus_repo: CampusRepository,
    ) -> None:
        self._university_repo = university_repo
        self._campus_repo = campus_repo

    async def execute(self, university_id: str) -> CampusSummary | None:
        try:
            u_id = EntityId.from_string(university_id)
        except (ValueError, Exception):
            return None

        university = await self._university_repo.get_by_id(u_id)
        if not university:
            return None

        page = await self._campus_repo.list_campuses(
            PageRequest(page=1, page_size=100),
            include_inactive=True,
        )

        for campus in page.items:
            if campus.university_id == u_id and campus.is_main_campus:
                return CampusSummary(
                    id=str(campus.id),
                    university_id=str(campus.university_id),
                    name=campus.name,
                    is_main_campus=campus.is_main_campus,
                    status=campus.status.value,
                    city=campus.city,
                    state_region=campus.state_region,
                )

        return None
