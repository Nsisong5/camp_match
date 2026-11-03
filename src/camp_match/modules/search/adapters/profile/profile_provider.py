from camp_match.modules.profile.application.ports.inbound import GetProfileRequest
from camp_match.modules.profile.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from camp_match.modules.search.application.ports.outbound import ProfileProvider
from camp_match.shared_kernel.domain.identifiers import EntityId


class ProfileProviderAdapter(ProfileProvider):
    def __init__(self, get_profile_use_case: GetCurrentUserProfileUseCase):
        self._get_profile_use_case = get_profile_use_case

    async def get_student_preferences(self, identity_id: EntityId) -> dict | None:
        try:
            req = GetProfileRequest(identity_id=identity_id)
            profile = await self._get_profile_use_case.execute(req)
            if not profile or not profile.student_details:
                return None
            
            # profile.student_details from ProfileResponse is a dict or object
            details = profile.student_details
            if isinstance(details, dict):
                uni_id = details.get("university_id")
                if uni_id and not isinstance(uni_id, EntityId):
                    uni_id = EntityId.from_string(uni_id) if isinstance(uni_id, str) else EntityId(uni_id)
                return {
                    "budget_min": details.get("budget_min_naira"),
                    "budget_max": details.get("budget_max_naira"),
                    "accommodation_type": details.get("preferred_accommodation_type"),
                    "university_id": uni_id,
                }
            else:
                return {
                    "budget_min": details.budget_min_naira,
                    "budget_max": details.budget_max_naira,
                    "accommodation_type": details.preferred_accommodation_type,
                    "university_id": details.university_id,
                }
        except Exception:
            return None
