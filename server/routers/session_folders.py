"""Agent-scoped session folders (session-folders).

A folder is an organizational container in the sidebar that owns a working
directory. Sessions created inside it inherit that directory and do not ask
the user for a path. Deleting a folder never deletes conversations: the
sessions are detached (folder_id -> NULL) and keep the path they inherited.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import verify_token
from ..database import Database
from ..models import (
    CreateSessionFolderRequest,
    SessionFolderInfo,
    UpdateSessionFolderRequest,
)
from ..session_manager import resolve_working_dir, session_manager

router = APIRouter(prefix="/api", tags=["session-folders"])

# Injected at startup (mirrors schedules/credentials routers).
_db: Database | None = None


def set_db(db: Database) -> None:
    global _db
    _db = db


def _get_db() -> Database:
    assert _db is not None
    return _db


async def _require_agent(agent_id: str) -> None:
    if await _get_db().get_agent(agent_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")


def _clean_name(raw: str) -> str:
    name = raw.strip()
    if not name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Folder name must not be empty"
        )
    return name


def _clean_working_dir(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "working_dir must not be empty"
        )
    # Reuse the exact same normalization as session working directories:
    # expand ~, resolve relative paths against the server cwd, and freeze
    # the absolute path. Folder sessions then inherit this canonical form.
    return resolve_working_dir(value)


@router.get(
    "/agents/{agent_id}/folders", response_model=list[SessionFolderInfo]
)
async def list_session_folders(
    agent_id: str, _: str = Depends(verify_token)
):
    await _require_agent(agent_id)
    return await _get_db().load_session_folders(agent_id)


@router.post(
    "/agents/{agent_id}/folders",
    response_model=SessionFolderInfo,
    status_code=status.HTTP_201_CREATED,
)
async def create_session_folder(
    agent_id: str,
    req: CreateSessionFolderRequest,
    _: str = Depends(verify_token),
):
    await _require_agent(agent_id)
    try:
        return await _get_db().create_session_folder(
            agent_id,
            _clean_name(req.name),
            _clean_working_dir(req.working_dir),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.patch("/folders/{folder_id}", response_model=SessionFolderInfo)
async def update_session_folder(
    folder_id: str,
    req: UpdateSessionFolderRequest,
    _: str = Depends(verify_token),
):
    db = _get_db()
    if await db.get_session_folder(folder_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Folder not found")

    fields = req.model_dump(exclude_unset=True)
    # `str | None` accepts an explicit JSON null; a folder must always keep
    # both a name and a working directory, so reject rather than ignore.
    if "name" in fields:
        if fields["name"] is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Folder name must not be empty"
            )
        fields["name"] = _clean_name(fields["name"])
    if "working_dir" in fields:
        if fields["working_dir"] is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "working_dir must not be empty"
            )
        fields["working_dir"] = _clean_working_dir(fields["working_dir"])

    try:
        folder = await db.update_session_folder(folder_id, **fields)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if folder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Folder not found")
    return folder


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session_folder(
    folder_id: str, _: str = Depends(verify_token)
):
    """Remove the folder only. Its sessions survive at the agent's top level;
    the FK (ON DELETE SET NULL) detaches them and they keep their path."""
    if not await session_manager.delete_session_folder(folder_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Folder not found")
