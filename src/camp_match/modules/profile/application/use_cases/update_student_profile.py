import structlog
from uuid import UUID

from camp_match.modules.profile.application.errors import ProfileNotFound, UnsupportedProfileType, InvalidProfileData
from camp_match.modules.profile.application.ports.inbound import (
    ProfileResponse,
    UpdateStudentProfileRequest,
)
from camp_match.modules.profile.application.ports.outbound import ProfileRepository, UniversityProvider
from camp_match.modules.profile.domain.value_objects import StudentProfileDetails
from camp_match.shared_kernel.domain.identifiers import EntityId
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork

logger = structlog.get_logger()

class UpdateStudentProfileUseCase:
    def __init__(
        self,
        repository: ProfileRepository,
        university_provider: UniversityProvider,
        uow: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._university_provider = university_provider
        self._uow = uow

    async def execute(self, request: UpdateStudentProfileRequest) -> ProfileResponse:
        profile = await self._repository.get_by_identity_id(request.identity_id)
        if not profile:
            raise ProfileNotFound("Profile not found.")
        
        if not profile.student_details:
            raise UnsupportedProfileType("Not a student profile")
            
        current = profile.student_details
        
        new_university_id = current.university_id
        new_university_name = current.university_name

        if request.university_id is not None:
            req_uni_id = request.university_id
            if not isinstance(req_uni_id, EntityId):
                if isinstance(req_uni_id, UUID):
                    req_uni_id = EntityId(req_uni_id)
                elif isinstance(req_uni_id, str):
                    req_uni_id = EntityId.from_string(req_uni_id)
            uni = await self._university_provider.get_university(req_uni_id)
            if not uni:
                raise InvalidProfileData(f"University with id {req_uni_id} not found.")
            new_university_id = req_uni_id
            new_university_name = None  # Clear legacy university_name when canonical university_id is set

        new_details = StudentProfileDetails(
            university_name=new_university_name,
            university_id=new_university_id,
            department=request.department if request.department is not None else current.department,
            budget_min_naira=request.budget_min_naira if request.budget_min_naira is not None else current.budget_min_naira,
            budget_max_naira=request.budget_max_naira if request.budget_max_naira is not None else current.budget_max_naira,
            preferred_accommodation_type=request.preferred_accommodation_type if request.preferred_accommodation_type is not None else current.preferred_accommodation_type,
            cleanliness_preference=request.cleanliness_preference if request.cleanliness_preference is not None else current.cleanliness_preference,
            sleep_schedule=request.sleep_schedule if request.sleep_schedule is not None else current.sleep_schedule,
        )
        
        profile.update_student_details(new_details)
        async with self._uow:
            await self._repository.update_student_extension(profile)
            await self._uow.commit()
        
        logger.info("student_profile_updated", identity_id=str(request.identity_id), profile_id=str(profile.id))
        
        return ProfileResponse(
            id=profile.id,
            identity_id=profile.identity_id,
            profile_type=profile.profile_type,
            display_name=profile.display_name,
            completeness_percentage=profile.completeness_percentage,
            bio=profile.bio,
            phone_number=profile.phone_number,
            avatar_url=profile.avatar_url,
            avatar_media_id=profile.avatar_media_id,
            student_details=profile.student_details.to_dict() if profile.student_details else None, # type: ignore
            scout_details=profile.scout_details.to_dict() if profile.scout_details else None, # type: ignore
        )
