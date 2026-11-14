"""Dev mailbox inspection router (local/test only)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from camp_match.config.settings import Settings, get_settings
from camp_match.modules.identity.adapters.email.dev_mailbox import DevMailbox

router = APIRouter(prefix="/api/v1/dev", tags=["dev-mailbox"])

_global_dev_mailbox = DevMailbox()


def get_dev_mailbox() -> DevMailbox:
    return _global_dev_mailbox


@router.get("/mailbox", response_model=list[dict[str, Any]])
async def get_mailbox_messages(
    to: Annotated[str, Query(..., description="Recipient email address")],
    settings: Annotated[Settings, Depends(get_settings)],
    mailbox: Annotated[DevMailbox, Depends(get_dev_mailbox)],
) -> list[dict[str, Any]]:
    if settings.app_env.lower() not in ("local", "test"):
        raise HTTPException(status_code=404, detail="Not found")
    messages = mailbox.list_for_address(to)
    return [
        {
            "to": m.to,
            "subject": m.subject,
            "text": m.text,
            "sent_at": m.sent_at.isoformat() if hasattr(m, "sent_at") and m.sent_at else None,
        }
        for m in messages
    ]
