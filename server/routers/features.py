from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import verify_token
from ..feature_manager import FeatureError, FeatureManager
from ..models import (
    FeatureRolesUpdate,
    FeatureRunEventInfo,
    FeatureRunInfo,
    FeatureTransitionRequest,
    GroupFeatureCreate,
)


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


@router.post("/features/{run_id}/transition", response_model=FeatureRunInfo)
async def transition_feature(
    run_id: str,
    request: FeatureTransitionRequest,
    _: str = Depends(verify_token),
):
    try:
        return await _get_manager().transition(
            run_id,
            to_stage=request.to_stage,
            result=request.result,
            actor_agent_id=request.actor_agent_id,
            reason=request.reason,
            evidence_refs=request.evidence_refs,
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
