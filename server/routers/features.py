from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status

from ..auth import verify_token
from ..feature_manager import FeatureError, FeatureManager
from ..models import (
    FeatureRolesUpdate,
    FeatureRunEventInfo,
    FeatureRunInfo,
    FeatureTransitionRequest,
    GroupActiveFeatureUpdate,
    GroupFeatureCreate,
)
from ..session_manager import session_manager


router = APIRouter(prefix="/api", tags=["features"])
_manager: FeatureManager | None = None


def set_feature_manager(manager: FeatureManager) -> None:
    global _manager
    _manager = manager


def _get_manager() -> FeatureManager:
    if _manager is None:
        raise RuntimeError("FeatureManager not initialized")
    return _manager


def _http_error(error: FeatureError) -> HTTPException:
    return HTTPException(error.status_code, str(error))


def _require_session_capability(
    session_id: str, session_capability: str
) -> None:
    if not session_manager.verify_session_capability(
        session_id, session_capability
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Invalid session capability",
        )


@router.post(
    "/groups/{group_id}/features",
    response_model=FeatureRunInfo,
    status_code=status.HTTP_201_CREATED,
)
async def create_feature(
    group_id: str,
    request: GroupFeatureCreate,
    _: str = Depends(verify_token),
):
    try:
        return await _get_manager().create_for_group(
            group_id,
            title=request.title,
            priority=request.priority,
            owner_agent_id=request.owner_agent_id,
            operator_quote=request.operator_quote,
            origin_message_seq=request.origin_message_seq,
        )
    except FeatureError as error:
        raise _http_error(error)


@router.get(
    "/groups/{group_id}/features", response_model=list[FeatureRunInfo]
)
async def list_group_features(
    group_id: str, _: str = Depends(verify_token)
):
    try:
        return await _get_manager().list_for_group(group_id)
    except FeatureError as error:
        raise _http_error(error)


@router.get(
    "/groups/{group_id}/active-feature",
    response_model=FeatureRunInfo | None,
)
async def get_active_group_feature(
    group_id: str, _: str = Depends(verify_token)
):
    try:
        return await _get_manager().get_active_for_group(group_id)
    except FeatureError as error:
        raise _http_error(error)


@router.put(
    "/groups/{group_id}/active-feature",
    response_model=FeatureRunInfo | None,
)
async def update_active_group_feature(
    group_id: str,
    request: GroupActiveFeatureUpdate,
    _: str = Depends(verify_token),
):
    try:
        if request.feature_run_id is None:
            await _get_manager().clear_active_for_group(group_id)
            return None
        return await _get_manager().activate_for_group(
            request.feature_run_id, group_id
        )
    except FeatureError as error:
        raise _http_error(error)


@router.get("/features/{run_id}", response_model=FeatureRunInfo)
async def get_feature(run_id: str, _: str = Depends(verify_token)):
    try:
        return await _get_manager().get(run_id)
    except FeatureError as error:
        raise _http_error(error)


@router.patch("/features/{run_id}/roles", response_model=FeatureRunInfo)
async def update_feature_roles(
    run_id: str,
    request: FeatureRolesUpdate,
    _: str = Depends(verify_token),
):
    changes = {
        key: getattr(request, key)
        for key in request.model_fields_set
    }
    try:
        return await _get_manager().update_roles(run_id, changes)
    except FeatureError as error:
        raise _http_error(error)


@router.post(
    "/sessions/{session_id}/features/{run_id}/transition",
    response_model=FeatureRunInfo,
)
async def transition_feature(
    session_id: str,
    run_id: str,
    request: FeatureTransitionRequest,
    session_capability: str = Header(
        ..., alias="X-Octopus-Session-Capability"
    ),
    _: str = Depends(verify_token),
):
    _require_session_capability(session_id, session_capability)
    try:
        return await _get_manager().transition_for_session(
            run_id,
            session_id,
            to_stage=request.to_stage,
            result=request.result,
            reason=request.reason,
            evidence_refs=request.evidence_refs,
            revision=request.revision,
        )
    except FeatureError as error:
        raise _http_error(error)


@router.get(
    "/features/{run_id}/events", response_model=list[FeatureRunEventInfo]
)
async def list_feature_events(
    run_id: str, _: str = Depends(verify_token)
):
    try:
        return await _get_manager().list_events(run_id)
    except FeatureError as error:
        raise _http_error(error)
