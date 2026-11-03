from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, status

from camp_match.modules.media.adapters.api.dependencies import (
    get_get_authorized_access,
    get_upload_media,
)
from camp_match.modules.media.application.ports.inbound import (
    GetAuthorizedAccessRequest,
    UploadMediaRequest,
)
from camp_match.modules.media.domain.value_objects import MediaPurpose
from camp_match.modules.profile.adapters.api import schemas
from camp_match.modules.profile.adapters.api.dependencies import (
    get_create_profile,
    get_get_current_user_profile,
    get_get_public_profile,
    get_profile_repository,
    get_university_provider,
    get_uow,
    get_update_profile,
    get_update_scout_profile,
    get_update_student_profile,
)
from camp_match.modules.profile.application.ports.inbound import (
    CreateProfileRequest,
    GetProfileRequest,
    GetPublicProfileRequest,
    UpdateProfileRequest,
    UpdateScoutProfileRequest,
    UpdateStudentProfileRequest,
)
from camp_match.platform.security.authentication import get_current_identity_id
from camp_match.shared_kernel.domain.identifiers import EntityId

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


async def _build_avatar_response(profile, get_access_uc=None):
    avatar_media_id = getattr(profile, "avatar_media_id", None)
    avatar_url = getattr(profile, "avatar_url", None)

    if avatar_media_id:
        media_id_val = avatar_media_id.value if hasattr(avatar_media_id, "value") else avatar_media_id
        stream_path = f"/api/v1/media/{media_id_val}/stream"
        if get_access_uc:
            try:
                grant = await get_access_uc.execute(GetAuthorizedAccessRequest(media_id=EntityId(media_id_val) if isinstance(media_id_val, UUID) else EntityId.from_string(str(media_id_val))))
                stream_path = f"{stream_path}?token={grant.token}"
            except Exception:
                pass
        return {
            "type": "media",
            "media_id": str(media_id_val),
            "stream_path": stream_path,
        }
    elif avatar_url:
        return {
            "type": "legacy_url",
            "url": avatar_url,
        }
    return None


async def _build_student_details_response(student_details_dict, profile_obj, university_provider):
    details = getattr(profile_obj, "student_details", None) if profile_obj else None
    if isinstance(details, dict):
        student_details_dict = details
        details = None

    uni_id = getattr(details, "university_id", None) if details else (student_details_dict.get("university_id") if student_details_dict else None)
    uni_name = getattr(details, "university_name", None) if details else (student_details_dict.get("university_name") if student_details_dict else None)

    if uni_id is not None and not isinstance(uni_id, EntityId):
        try:
            if isinstance(uni_id, UUID):
                uni_id = EntityId(uni_id)
            elif isinstance(uni_id, str) and uni_id.strip():
                uni_id = EntityId.from_string(uni_id)
            else:
                uni_id = None
        except Exception:
            uni_id = None

    univ_obj = None
    if uni_id and university_provider:
        uni_sum = await university_provider.get_university(uni_id)
        if uni_sum:
            univ_obj = {
                "type": "canonical",
                "value": {
                    "id": str(uni_sum.id.value if hasattr(uni_sum.id, "value") else uni_sum.id),
                    "official_name": uni_sum.official_name,
                }
            }
    if not univ_obj and uni_name:
        univ_obj = {
            "type": "legacy_text",
            "value": uni_name,
        }

    base_dict = dict(student_details_dict) if student_details_dict else (details.to_dict() if details and hasattr(details, "to_dict") else {})
    base_dict["university"] = univ_obj
    base_dict.pop("university_name", None)
    base_dict.pop("university_id", None)
    return base_dict


@router.post("", response_model=schemas.ProfileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_profile(
    data: Annotated[schemas.ProfileCreateRequest, Body(...)],
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case=Depends(get_create_profile),
    get_access_uc=Depends(get_get_authorized_access),
    university_provider=Depends(get_university_provider),
) -> schemas.ProfileResponseSchema:
    request = CreateProfileRequest(
        identity_id=identity_id,
        **data.model_dump(),
    )
    result = await use_case.execute(request)
    avatar_obj = await _build_avatar_response(result, get_access_uc)
    student_details_res = await _build_student_details_response(result.student_details, result, university_provider)
    return schemas.ProfileResponseSchema(
        id=result.id.value,
        identity_id=result.identity_id.value,
        profile_type=result.profile_type,
        display_name=result.display_name,
        completeness_percentage=result.completeness_percentage,
        bio=result.bio,
        phone_number=result.phone_number,
        avatar_url=result.avatar_url,
        avatar_media_id=result.avatar_media_id.value if result.avatar_media_id else None,
        avatar=avatar_obj,
        student_details=student_details_res,
        scout_details=result.scout_details,
    )


@router.post("/me/avatar", response_model=schemas.ProfileResponseSchema)
async def upload_avatar(
    file: UploadFile,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    repo=Depends(get_profile_repository),
    upload_media_uc=Depends(get_upload_media),
    get_access_uc=Depends(get_get_authorized_access),
    uow=Depends(get_uow),
    university_provider=Depends(get_university_provider),
) -> schemas.ProfileResponseSchema:
    profile = await repo.get_by_identity_id(identity_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    data = await file.read()
    upload_req = UploadMediaRequest(
        purpose=MediaPurpose.PROFILE_AVATAR,
        data=data,
        content_type=file.content_type or "image/jpeg",
        original_filename=file.filename or "avatar.jpg",
        uploaded_by=identity_id,
    )
    upload_res = await upload_media_uc.execute(upload_req)

    profile.set_avatar_media(upload_res.media_id)
    async with uow:
        await repo.update_core(profile)
        await uow.commit()

    avatar_obj = await _build_avatar_response(profile, get_access_uc)
    student_details_res = await _build_student_details_response(profile.student_details.to_dict() if profile.student_details else None, profile, university_provider)
    return schemas.ProfileResponseSchema(
        id=profile.id.value,
        identity_id=profile.identity_id.value,
        profile_type=profile.profile_type,
        display_name=profile.display_name,
        completeness_percentage=profile.completeness_percentage,
        bio=profile.bio,
        phone_number=profile.phone_number,
        avatar_url=profile.avatar_url,
        avatar_media_id=profile.avatar_media_id.value if profile.avatar_media_id else None,
        avatar=avatar_obj,
        student_details=student_details_res,
        scout_details=profile.scout_details.to_dict() if profile.scout_details else None,
    )


@router.get("/me", response_model=schemas.ProfileResponseSchema)
async def get_current_user_profile(
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case=Depends(get_get_current_user_profile),
    get_access_uc=Depends(get_get_authorized_access),
    university_provider=Depends(get_university_provider),
) -> schemas.ProfileResponseSchema:
    request = GetProfileRequest(identity_id=identity_id)
    result = await use_case.execute(request)
    avatar_obj = await _build_avatar_response(result, get_access_uc)
    student_details_res = await _build_student_details_response(result.student_details, result, university_provider)
    return schemas.ProfileResponseSchema(
        id=result.id.value,
        identity_id=result.identity_id.value,
        profile_type=result.profile_type,
        display_name=result.display_name,
        completeness_percentage=result.completeness_percentage,
        bio=result.bio,
        phone_number=result.phone_number,
        avatar_url=result.avatar_url,
        avatar_media_id=result.avatar_media_id.value if result.avatar_media_id else None,
        avatar=avatar_obj,
        student_details=student_details_res,
        scout_details=result.scout_details,
    )


@router.get("/{profile_id}", response_model=schemas.PublicProfileResponseSchema)
async def get_public_profile(
    profile_id: UUID,
    use_case=Depends(get_get_public_profile),
    get_access_uc=Depends(get_get_authorized_access),
    university_provider=Depends(get_university_provider),
) -> schemas.PublicProfileResponseSchema:
    request = GetPublicProfileRequest(profile_id=EntityId(profile_id))
    result = await use_case.execute(request)
    avatar_obj = await _build_avatar_response(result, get_access_uc)
    student_details_res = await _build_student_details_response(result.student_details, result, university_provider)
    return schemas.PublicProfileResponseSchema(
        id=result.id.value,
        profile_type=result.profile_type,
        display_name=result.display_name,
        completeness_percentage=result.completeness_percentage,
        bio=result.bio,
        avatar_url=result.avatar_url,
        avatar_media_id=result.avatar_media_id.value if result.avatar_media_id else None,
        avatar=avatar_obj,
        student_details=student_details_res,
        scout_details=result.scout_details,
    )


@router.patch("/me", response_model=schemas.ProfileResponseSchema)
async def update_profile(
    data: Annotated[schemas.ProfileUpdateRequest, Body(...)],
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case=Depends(get_update_profile),
    get_access_uc=Depends(get_get_authorized_access),
    university_provider=Depends(get_university_provider),
) -> schemas.ProfileResponseSchema:
    request = UpdateProfileRequest(identity_id=identity_id, **data.model_dump(exclude_unset=True))
    result = await use_case.execute(request)
    avatar_obj = await _build_avatar_response(result, get_access_uc)
    student_details_res = await _build_student_details_response(result.student_details, result, university_provider)
    return schemas.ProfileResponseSchema(
        id=result.id.value,
        identity_id=result.identity_id.value,
        profile_type=result.profile_type,
        display_name=result.display_name,
        completeness_percentage=result.completeness_percentage,
        bio=result.bio,
        phone_number=result.phone_number,
        avatar_url=result.avatar_url,
        avatar_media_id=result.avatar_media_id.value if result.avatar_media_id else None,
        avatar=avatar_obj,
        student_details=student_details_res,
        scout_details=result.scout_details,
    )


@router.patch("/me/student", response_model=schemas.ProfileResponseSchema)
async def update_student_profile(
    data: Annotated[schemas.StudentProfileUpdateRequest, Body(...)],
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case=Depends(get_update_student_profile),
    get_access_uc=Depends(get_get_authorized_access),
    university_provider=Depends(get_university_provider),
) -> schemas.ProfileResponseSchema:
    request = UpdateStudentProfileRequest(identity_id=identity_id, **data.model_dump(exclude_unset=True))
    result = await use_case.execute(request)
    avatar_obj = await _build_avatar_response(result, get_access_uc)
    student_details_res = await _build_student_details_response(result.student_details, result, university_provider)
    return schemas.ProfileResponseSchema(
        id=result.id.value,
        identity_id=result.identity_id.value,
        profile_type=result.profile_type,
        display_name=result.display_name,
        completeness_percentage=result.completeness_percentage,
        bio=result.bio,
        phone_number=result.phone_number,
        avatar_url=result.avatar_url,
        avatar_media_id=result.avatar_media_id.value if result.avatar_media_id else None,
        avatar=avatar_obj,
        student_details=student_details_res,
        scout_details=result.scout_details,
    )


@router.patch("/me/scout", response_model=schemas.ProfileResponseSchema)
async def update_scout_profile(
    data: Annotated[schemas.ScoutProfileUpdateRequest, Body(...)],
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case=Depends(get_update_scout_profile),
    get_access_uc=Depends(get_get_authorized_access),
    university_provider=Depends(get_university_provider),
) -> schemas.ProfileResponseSchema:
    request = UpdateProfileRequest(identity_id=identity_id, **data.model_dump(exclude_unset=True)) # wait, UpdateScoutProfileRequest
    request = UpdateScoutProfileRequest(identity_id=identity_id, **data.model_dump(exclude_unset=True))
    result = await use_case.execute(request)
    avatar_obj = await _build_avatar_response(result, get_access_uc)
    student_details_res = await _build_student_details_response(result.student_details, result, university_provider)
    return schemas.ProfileResponseSchema(
        id=result.id.value,
        identity_id=result.identity_id.value,
        profile_type=result.profile_type,
        display_name=result.display_name,
        completeness_percentage=result.completeness_percentage,
        bio=result.bio,
        phone_number=result.phone_number,
        avatar_url=result.avatar_url,
        avatar_media_id=result.avatar_media_id.value if result.avatar_media_id else None,
        avatar=avatar_obj,
        student_details=student_details_res,
        scout_details=result.scout_details,
    )
