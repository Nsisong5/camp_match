from __future__ import annotations

from camp_match.modules.verification.application.ports.inbound import ListMyInspectionsRequest
from camp_match.modules.verification.application.ports.outbound import InspectionRepository


class ListMyInspectionsUseCase:
    def __init__(self, inspection_repo: InspectionRepository):
        self.inspection_repo = inspection_repo

    async def execute(self, request: ListMyInspectionsRequest) -> list:
        return await self.inspection_repo.list_by_inspector(request.caller_id)
