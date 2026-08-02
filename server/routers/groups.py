from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import verify_token
from ..group_manager import GroupError, GroupManager
from ..models import (
    GroupCreate,
    GroupInfo,
    GroupInvocationInfo,
    GroupInvocationResumeRequest,
    GroupSendRequest,
    GroupUpdate,
)

router = APIRouter(prefix="/api/groups", tags=["groups"])

# The GroupManager singleton -- wired in main.py.
_manager: GroupManager | None = None


def _get_manager() -> GroupManager:
    if _manager is None:
        raise RuntimeError("GroupManager not initialized")
    return _manager


def set_group_manager(mgr: GroupManager) -> None:
    global _manager
    _manager = mgr


@router.get("", response_model=list[GroupInfo])
async def list_groups(_: str = Depends(verify_token)):
    mgr = _get_manager()
    groups = await mgr.list_groups()
    return groups


@router.post("", response_model=GroupInfo, status_code=status.HTTP_201_CREATED)
async def create_group(req: GroupCreate, _: str = Depends(verify_token)):
    mgr = _get_manager()
    try:
        group = await mgr.create_group(
            req.name,
            req.agent_ids,
            default_agent_id=req.default_agent_id,
            working_dir=req.working_dir,
        )
    except GroupError as e:
        raise HTTPException(e.status_code, str(e))
    return group


@router.patch("/{group_id}", response_model=GroupInfo)

async def update_group(
    group_id: str, req: GroupUpdate, _: str = Depends(verify_token)
):

    mgr = _get_manager()

    try:

        group = await mgr.update_group(
            group_id,
            name=req.name,
            default_agent_id=req.default_agent_id,
        )

    except GroupError as e:

        raise HTTPException(e.status_code, str(e))

    if group is None:

        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")

    return group



@router.get("/{group_id}", response_model=GroupInfo)
async def get_group(group_id: str, _: str = Depends(verify_token)):
    mgr = _get_manager()
    group = await mgr.get_group(group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: str, _: str = Depends(verify_token)):
    mgr = _get_manager()
    try:
        deleted = await mgr.delete_group(group_id)
    except GroupError as e:
        raise HTTPException(e.status_code, str(e))
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")


@router.post("/{group_id}/members/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_member(group_id: str, agent_id: str, _: str = Depends(verify_token)):
    mgr = _get_manager()
    try:
        await mgr.add_member(group_id, agent_id)
    except GroupError as e:
        raise HTTPException(e.status_code, str(e))


@router.delete("/{group_id}/members/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(group_id: str, agent_id: str, _: str = Depends(verify_token)):
    mgr = _get_manager()
    try:
        await mgr.remove_member(group_id, agent_id)
    except GroupError as e:
        raise HTTPException(e.status_code, str(e))


@router.post("/{group_id}/send")
async def send_message(
    group_id: str, req: GroupSendRequest, _: str = Depends(verify_token)
):
    mgr = _get_manager()
    try:
        invocation = await mgr.send_message(
            group_id,
            req.content,
            req.attachment_ids,
            feature_run_id=req.feature_run_id,
        )
    except GroupError as e:
        raise HTTPException(e.status_code, str(e))
    return {"status": "ok", "invocation": invocation}


@router.get("/{group_id}/worklist")
async def get_worklist(group_id: str, _: str = Depends(verify_token)):
    mgr = _get_manager()
    return mgr.get_worklist(group_id)


@router.get(
    "/{group_id}/invocations", response_model=list[GroupInvocationInfo]
)
async def list_invocations(
    group_id: str,
    active_only: bool = False,
    _: str = Depends(verify_token),
):
    mgr = _get_manager()
    try:
        return await mgr.list_invocations(group_id, active_only=active_only)
    except GroupError as e:
        raise HTTPException(e.status_code, str(e))


@router.post(
    "/{group_id}/invocations/{invocation_id}/cancel",
    response_model=GroupInvocationInfo,
)
async def cancel_invocation(
    group_id: str,
    invocation_id: str,
    _: str = Depends(verify_token),
):
    mgr = _get_manager()
    try:
        return await mgr.cancel_invocation(group_id, invocation_id)
    except GroupError as e:
        raise HTTPException(e.status_code, str(e))


@router.post(
    "/{group_id}/invocations/{invocation_id}/resume",
    response_model=GroupInvocationInfo,
)
async def resume_invocation(
    group_id: str,
    invocation_id: str,
    req: GroupInvocationResumeRequest,
    _: str = Depends(verify_token),
):
    mgr = _get_manager()
    try:
        return await mgr.resume_invocation(group_id, invocation_id, req.reason)
    except GroupError as e:
        raise HTTPException(e.status_code, str(e))
