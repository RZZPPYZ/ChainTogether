from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status

from ..auth import verify_token
from ..feature_manager import FeatureError, FeatureManager
from ..feature_delivery import FeatureDeliveryManager
from ..models import (
    FeatureDeliveryRolesRequest,
    FeatureDeliveryStartRequest,
    FeatureReviewRequest,
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
_delivery_manager: FeatureDeliveryManager | None = None


def set_feature_manager(manager: FeatureManager) -> None:
    global _manager
    _manager = manager


def set_feature_delivery_manager(manager: FeatureDeliveryManager) -> None:
    global _delivery_manager
    _delivery_manager = manager


def _get_manager() -> FeatureManager:
    if _manager is None:
        raise RuntimeError("FeatureManager not initialized")
    return _manager


def _get_delivery_manager() -> FeatureDeliveryManager:
    if _delivery_manager is None:
        raise RuntimeError("FeatureDeliveryManager not initialized")
    return _delivery_manager


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


@router.post("/groups/{group_id}/feature-delivery")
async def start_feature_delivery(
    group_id: str,
    request: FeatureDeliveryStartRequest,
    _: str = Depends(verify_token),
):
    try:
        return await _get_delivery_manager().start(
            group_id,
            request_key=request.request_key,
            requirement=request.requirement,
            priority=request.priority,
            origin_message_seq=request.origin_message_seq,
        )
    except FeatureError as error:
        raise _http_error(error)


@router.get("/groups/{group_id}/feature-delivery/status")
async def get_feature_delivery_status(
    group_id: str, _: str = Depends(verify_token)
):
    try:
        return await _get_delivery_manager().status_for_group(group_id)
    except FeatureError as error:
        raise _http_error(error)


@router.post("/groups/{group_id}/feature-delivery/resume")
async def resume_feature_delivery(
    group_id: str, _: str = Depends(verify_token)
):
    try:
        return await _get_delivery_manager().resume_for_group(group_id)
    except FeatureError as error:
        raise _http_error(error)


@router.put("/groups/{group_id}/feature-delivery/roles")
async def update_feature_delivery_roles(
    group_id: str,
    request: FeatureDeliveryRolesRequest,
    _: str = Depends(verify_token),
):
    try:
        return await _get_delivery_manager().update_roles_for_group(
            group_id,
            owner_agent_id=request.owner_agent_id,
            reviewer_agent_id=request.reviewer_agent_id,
            vision_guardian_agent_id=request.vision_guardian_agent_id,
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


@router.get("/sessions/{session_id}/features/{run_id}/status")
async def get_feature_delivery_status_for_session(
    session_id: str,
    run_id: str,
    session_capability: str = Header(
        ..., alias="X-Octopus-Session-Capability"
    ),
    _: str = Depends(verify_token),
):
    _require_session_capability(session_id, session_capability)
    try:
        return await _get_delivery_manager().status(
            run_id, actor_session_id=session_id
        )
    except FeatureError as error:
        raise _http_error(error)


@router.post("/sessions/{session_id}/features/{run_id}/dispatch/transition")
async def transition_feature_dispatch(
    session_id: str,
    run_id: str,
    request: FeatureTransitionRequest,
    session_capability: str = Header(
        ..., alias="X-Octopus-Session-Capability"
    ),
    dispatch_id: str = Header(..., alias="X-Octopus-Feature-Dispatch"),
    dispatch_capability: str = Header(
        ..., alias="X-Octopus-Dispatch-Capability"
    ),
    _: str = Depends(verify_token),
):
    _require_session_capability(session_id, session_capability)
    try:
        await _get_manager().transition_for_dispatch(
            run_id,
            session_id,
            dispatch_id=dispatch_id,
            dispatch_capability=dispatch_capability,
            to_stage=request.to_stage,
            result=request.result,
            reason=request.reason,
            evidence_refs=request.evidence_refs,
            revision=request.revision,
        )
        return await _get_delivery_manager().status(
            run_id, actor_session_id=session_id
        )
    except FeatureError as error:
        raise _http_error(error)


@router.post(
    "/sessions/{session_id}/features/{run_id}/dispatch/request-review"
)
async def request_feature_review(
    session_id: str,
    run_id: str,
    request: FeatureReviewRequest,
    session_capability: str = Header(
        ..., alias="X-Octopus-Session-Capability"
    ),
    dispatch_id: str = Header(..., alias="X-Octopus-Feature-Dispatch"),
    dispatch_capability: str = Header(
        ..., alias="X-Octopus-Dispatch-Capability"
    ),
    _: str = Depends(verify_token),
):
    _require_session_capability(session_id, session_capability)
    try:
        await _get_manager().request_review_for_dispatch(
            run_id,
            session_id,
            dispatch_id=dispatch_id,
            dispatch_capability=dispatch_capability,
            reason=request.reason,
            evidence_refs=request.evidence_refs,
            revision=request.revision,
        )
        return await _get_delivery_manager().status(
            run_id, actor_session_id=session_id
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
