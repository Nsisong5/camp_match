from __future__ import annotations

from typing import TYPE_CHECKING
from camp_match.modules.verification.application.ports.outbound import MediaProvider, AccessGrant
from camp_match.modules.media.application.ports.inbound import UploadMediaRequest, GetAuthorizedAccessRequest
from camp_match.modules.media.application.use_cases.upload_media import UploadMediaUseCase
from camp_match.modules.media.application.use_cases.get_authorized_access import GetAuthorizedAccessUseCase
from camp_match.modules.media.domain.value_objects import AccessPolicy, MediaPurpose
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessMediaProvider(MediaProvider):
    def __init__(self, upload_uc: UploadMediaUseCase, get_access_uc: GetAuthorizedAccessUseCase) -> None:
        self._upload_uc = upload_uc
        self._get_access_uc = get_access_uc

    async def upload(
        self, purpose: str, content: bytes, content_type: str, uploaded_by: EntityId
    ) -> EntityId:
        media_purpose = MediaPurpose.VERIFICATION_EVIDENCE if purpose == "VERIFICATION_EVIDENCE" else MediaPurpose(purpose)
        response = await self._upload_uc.execute(
            UploadMediaRequest(
                purpose=media_purpose,
                data=content,
                content_type=content_type,
                original_filename="evidence.jpg",
                uploaded_by=uploaded_by,
            )
        )
        return response.media_id

    async def get_access(self, media_id: EntityId) -> AccessGrant:
        grant = await self._get_access_uc.execute(
            GetAuthorizedAccessRequest(media_id=media_id)
        )
        return AccessGrant(token=grant.token, expires_at=grant.expires_at)
