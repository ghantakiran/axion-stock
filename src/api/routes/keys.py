"""API Key Management — CRUD endpoints for API key lifecycle.

Provides endpoints for creating, listing, and revoking API keys.
Create and revoke require admin scope; list shows the caller's own keys.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import (
    AuthContext,
    check_rate_limit,
    get_key_manager,
    require_scope,
)
from src.api.models import APIKeyCreateRequest, APIKeyResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/keys", tags=["API Keys"])


@router.post("", response_model=APIKeyResponse, status_code=201)
async def create_key(
    body: APIKeyCreateRequest,
    auth: AuthContext = Depends(require_scope("admin")),
):
    """Create a new API key.

    Requires admin scope.  The raw key is returned **only once** in the
    response — store it securely.
    """
    manager = get_key_manager()
    result = manager.create_key(
        user_id=auth.user_id,
        name=body.name,
        scopes=body.scopes,
        expires_in_days=body.expires_in_days,
    )

    return APIKeyResponse(
        key_id=result["key_id"],
        name=result["name"],
        key=result["key"],
        key_preview=result["key_preview"],
        scopes=result["scopes"],
        is_active=result["is_active"],
        created_at=result["created_at"],
        expires_at=result.get("expires_at"),
        last_used=result.get("last_used"),
    )


@router.get("", response_model=list[APIKeyResponse])
async def list_keys(
    auth: AuthContext = Depends(check_rate_limit),
):
    """List the caller's API keys.

    Returns metadata only — raw key values are never re-exposed.
    """
    manager = get_key_manager()
    keys = manager.list_keys(auth.user_id)

    return [
        APIKeyResponse(
            key_id=k["key_id"],
            name=k["name"],
            key_preview=f"ax_...{k['key_id'][-4:]}",
            scopes=k["scopes"],
            is_active=k["is_active"],
            created_at=k["created_at"],
            expires_at=k.get("expires_at"),
            last_used=k.get("last_used"),
        )
        for k in keys
    ]


@router.delete("/{key_id}", status_code=200)
async def revoke_key(
    key_id: str,
    auth: AuthContext = Depends(require_scope("admin")),
):
    """Revoke an API key by ID.

    Requires admin scope.  Revoked keys immediately stop authenticating.
    """
    manager = get_key_manager()
    revoked = manager.revoke_key(key_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Key not found")

    return {"key_id": key_id, "revoked": True}
