from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from ..auth import verify_token
from ..group_session_chain import SessionChainAccessError, SessionChainReader
from ..session_manager import session_manager


router = APIRouter(prefix="/api/sessions", tags=["session-chain"])


def _reader(session_id: str, capability: str) -> SessionChainReader:
    if not session_manager.verify_session_capability(session_id, capability):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid session capability")
    if session_manager.db is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Session chain unavailable")
    return SessionChainReader(session_manager.db)


def _http_error(exc: SessionChainAccessError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc))


@router.get("/{session_id}/session-chain")
async def list_session_chain(
    session_id: str,
    session_capability: str = Header(..., alias="X-Octopus-Session-Capability"),
    _: str = Depends(verify_token),
) -> dict[str, Any]:
    try:
        return await _reader(session_id, session_capability).list_chain(session_id)
    except SessionChainAccessError as exc:
        raise _http_error(exc)


@router.get("/{session_id}/session-chain/{target_session_id}/events")
async def read_session_chain_events(
    session_id: str,
    target_session_id: str,
    view: str = Query("chat", pattern="^(raw|chat|handoff)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session_capability: str = Header(..., alias="X-Octopus-Session-Capability"),
    _: str = Depends(verify_token),
) -> dict[str, Any]:
    try:
        return await _reader(session_id, session_capability).read_events(
            session_id, target_session_id, view=view, offset=offset, limit=limit
        )
    except SessionChainAccessError as exc:
        raise _http_error(exc)


@router.get("/{session_id}/session-chain/{target_session_id}/invocations/{seq}")
async def read_session_chain_invocation(
    session_id: str,
    target_session_id: str,
    seq: int,
    session_capability: str = Header(..., alias="X-Octopus-Session-Capability"),
    _: str = Depends(verify_token),
) -> dict[str, Any]:
    try:
        return await _reader(session_id, session_capability).read_invocation(
            session_id, target_session_id, seq=seq
        )
    except SessionChainAccessError as exc:
        raise _http_error(exc)


@router.get("/{session_id}/session-chain/search")
async def search_session_chain(
    session_id: str,
    q: str = Query(..., min_length=1, max_length=256),
    limit: int = Query(20, ge=1, le=100),
    session_capability: str = Header(..., alias="X-Octopus-Session-Capability"),
    _: str = Depends(verify_token),
) -> dict[str, Any]:
    try:
        return await _reader(session_id, session_capability).search(
            session_id, q, limit=limit
        )
    except SessionChainAccessError as exc:
        raise _http_error(exc)
