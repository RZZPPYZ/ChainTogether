from __future__ import annotations

import asyncio
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .database import Database
from .feature_manager import FeatureError, FeatureManager


_RUN_AUTHORIZATION: dict[str, bool] = {
    "commit": True,
    "push": True,
    "pull_request": True,
    "merge_after_green_gates": True,
    "force_push": False,
    "bypass_policy": False,
    "deploy": False,
    "unrelated_external_effects": False,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FeatureDeliveryManager:
    """Coordinates one-sentence Feature starts without becoming a state machine.

    FeatureRun remains lifecycle truth. This manager owns only start checkpoint
    creation/recovery and, in later stages, delivery of revision-bound actors.
    """

    def __init__(self) -> None:
        self.db: Database | None = None
        self.feature_manager: FeatureManager | None = None
        self._start_lock = asyncio.Lock()

    def bind(self, db: Database, feature_manager: FeatureManager) -> None:
        self.db = db
        self.feature_manager = feature_manager

    def _db(self) -> Database:
        if self.db is None:
            raise RuntimeError("FeatureDeliveryManager not initialized")
        return self.db

    def _features(self) -> FeatureManager:
        if self.feature_manager is None:
            raise RuntimeError("FeatureDeliveryManager not initialized")
        return self.feature_manager

    @staticmethod
    def _normalize_requirement(requirement: str) -> str:
        normalized = requirement.strip()
        if not normalized:
            raise FeatureError("Feature requirement is required")
        if len(normalized) > 10000:
            raise FeatureError("Feature requirement must be at most 10000 characters")
        return normalized

    @staticmethod
    def _title(requirement: str) -> str:
        first_line = next(
            (line.strip() for line in requirement.splitlines() if line.strip()),
            "Feature",
        )
        return first_line[:200]

    @staticmethod
    def _requirement_hash(requirement: str) -> str:
        return hashlib.sha256(requirement.encode("utf-8")).hexdigest()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _target_for_stage(run: dict[str, Any]) -> tuple[str, str | None]:
        stage = str(run["stage"])
        if stage == "review":
            return "reviewer", run.get("reviewer_agent_id")
        if stage == "acceptance":
            return "vision_guardian", run.get("vision_guardian_agent_id")
        return "owner", run.get("owner_agent_id")

    async def _resolve_roles(
        self, group: dict[str, Any],
    ) -> dict[str, dict[str, str]]:
        members = await self._db().list_live_group_members(str(group["id"]))
        if len(members) < 3:
            raise FeatureError(
                "Autonomous feature delivery requires at least three live "
                "group agents for owner, reviewer, and vision guardian",
                status_code=409,
            )
        by_id = {member["id"]: member for member in members}
        default_agent_id = group.get("default_agent_id")
        owner = (
            by_id[default_agent_id]
            if isinstance(default_agent_id, str) and default_agent_id in by_id
            else members[0]
        )
        remaining = [member for member in members if member["id"] != owner["id"]]
        return {
            "owner": owner,
            "reviewer": remaining[0],
            "vision_guardian": remaining[1],
        }

    async def start(
        self,
        group_id: str,
        *,
        request_key: str,
        requirement: str,
        priority: str = "P1",
        origin_message_seq: int | None = None,
    ) -> dict[str, Any]:
        requirement = self._normalize_requirement(requirement)
        request_key = request_key.strip()
        if not request_key:
            raise FeatureError("Feature request key is required")
        if len(request_key) > 200:
            raise FeatureError("Feature request key must be at most 200 characters")
        if priority not in {"P0", "P1", "P2", "P3"}:
            raise FeatureError("Priority must be P0, P1, P2, or P3")
        requirement_hash = self._requirement_hash(requirement)

        async with self._start_lock:
            group = await self._db().get_group(group_id)
            if group is None:
                raise FeatureError("Group not found", status_code=404)

            existing = await self._db().get_feature_start_request(request_key)
            if existing is not None:
                if (
                    existing["group_id"] != group_id
                    or existing["requirement_hash"] != requirement_hash
                ):
                    raise FeatureError(
                        "Feature request key is already bound to another request",
                        status_code=409,
                    )
                return await self._resume_start(existing, replayed=True)

            roles = await self._resolve_roles(group)
            created_at = _now()
            prepared = await self._features().prepare_autonomous_start(
                group,
                title=self._title(requirement),
                priority=priority,
                owner_agent_id=roles["owner"]["id"],
                reviewer_agent_id=roles["reviewer"]["id"],
                vision_guardian_agent_id=roles["vision_guardian"]["id"],
                operator_quote=requirement,
                origin_message_seq=origin_message_seq,
                created_at=created_at,
            )
            run_id = uuid.uuid4().hex[:12]
            outcome = await self._db().create_feature_delivery_checkpoint(
                request_key=request_key,
                requirement=requirement,
                requirement_hash=requirement_hash,
                authorization=dict(_RUN_AUTHORIZATION),
                run_id=run_id,
                feature_id=str(prepared["feature_id"]),
                group_id=group_id,
                working_dir=str(group["working_dir"]),
                feature_doc_path=str(prepared["feature_doc_path"]),
                feature_doc_absolute_path=str(
                    prepared["feature_doc_absolute_path"]
                ),
                document_content=str(prepared["document_content"]),
                title=self._title(requirement),
                stage=str(prepared["stage"]),
                priority=priority,
                owner_agent_id=roles["owner"]["id"],
                reviewer_agent_id=roles["reviewer"]["id"],
                vision_guardian_agent_id=roles["vision_guardian"]["id"],
                current_gate=(
                    str(prepared["current_gate"])
                    if prepared["current_gate"] is not None
                    else None
                ),
                operator_quote=requirement,
                origin_message_seq=origin_message_seq,
                dispatch_id=uuid.uuid4().hex[:16],
                created_at=created_at,
            )
            status = str(outcome["status"])
            if status == "request_conflict":
                raise FeatureError(
                    "Feature request key is already bound to another request",
                    status_code=409,
                )
            if status == "active_conflict":
                raise FeatureError(
                    "Group already has active FeatureRun "
                    f"{outcome['feature_run_id']}; use /feature status or "
                    "/feature resume",
                    status_code=409,
                )
            checkpoint = await self._db().get_feature_start_request(request_key)
            assert checkpoint is not None
            return await self._resume_start(
                checkpoint,
                replayed=status == "replayed",
            )

    async def _resume_start(
        self,
        checkpoint: dict[str, Any],
        *,
        replayed: bool,
    ) -> dict[str, Any]:
        run_id = str(checkpoint["feature_run_id"])
        delivered = await self._features().deliver_pending_document(run_id)
        if delivered and checkpoint["state"] == "doc_pending":
            await self._db().update_feature_start_state(
                run_id,
                state="dispatch_pending",
                error=None,
                updated_at=_now(),
            )
        run = await self._db().get_feature_run(run_id)
        if run is None:
            raise FeatureError(
                "Feature start checkpoint references a missing run",
                status_code=409,
            )
        checkpoint = await self._db().get_feature_start_for_run(run_id)
        assert checkpoint is not None
        dispatches = await self._db().list_feature_dispatches(run_id)
        role_ids = {
            "owner": run["owner_agent_id"],
            "reviewer": run["reviewer_agent_id"],
            "vision_guardian": run["vision_guardian_agent_id"],
        }
        roles: dict[str, dict[str, str]] = {}
        for role, agent_id in role_ids.items():
            if not isinstance(agent_id, str):
                raise FeatureError(
                    f"Feature checkpoint has no assigned {role}", status_code=409
                )
            agent = await self._db().get_agent(agent_id)
            roles[role] = {
                "id": agent_id,
                "name": str(agent["name"]) if agent is not None else agent_id,
            }
        return {
            "run": run,
            "roles": roles,
            "authorization": checkpoint["authorization"],
            "checkpoint_state": checkpoint["state"],
            "checkpoint_error": checkpoint["error"],
            "dispatch": dispatches[-1] if dispatches else None,
            "replayed": replayed,
        }

    async def lease_next_dispatch(
        self,
        run_id: str,
        *,
        worker_id: str,
        lease_seconds: int = 30,
    ) -> dict[str, Any] | None:
        if lease_seconds < 0:
            raise FeatureError("Dispatch lease duration cannot be negative")
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        lease_token = secrets.token_urlsafe(32)
        dispatch_capability = secrets.token_urlsafe(32)
        dispatch = await self._db().lease_next_feature_dispatch(
            run_id,
            lease_owner=worker_id,
            lease_token_hash=self._token_hash(lease_token),
            capability_hash=self._token_hash(dispatch_capability),
            lease_expires_at=(now_dt + timedelta(seconds=lease_seconds)).isoformat(),
            now=now,
        )
        if dispatch is None:
            return None
        return {
            "dispatch": dispatch,
            "lease_token": lease_token,
            "dispatch_capability": dispatch_capability,
        }

    async def activate_dispatch(
        self,
        dispatch_id: str,
        *,
        lease_token: str,
        invocation_id: str,
    ) -> dict[str, Any]:
        activated = await self._db().activate_feature_dispatch(
            dispatch_id,
            lease_token_hash=self._token_hash(lease_token),
            invocation_id=invocation_id,
            updated_at=_now(),
        )
        if not activated:
            raise FeatureError(
                "Feature dispatch lease is stale, invalid, or bound to another "
                "invocation",
                status_code=409,
            )
        dispatch = await self._db().get_feature_dispatch(dispatch_id)
        assert dispatch is not None
        await self._db().update_feature_start_state(
            str(dispatch["feature_run_id"]),
            state="running",
            error=None,
            updated_at=_now(),
        )
        return dispatch

    async def complete_dispatch_invocation(
        self,
        dispatch_id: str,
        invocation_id: str,
        *,
        terminal_status: str,
    ) -> dict[str, Any]:
        dispatch = await self._db().complete_feature_dispatch_invocation(
            dispatch_id,
            invocation_id,
            terminal_status=terminal_status,
            updated_at=_now(),
        )
        if dispatch is None:
            raise FeatureError(
                "Feature dispatch is not bound to this invocation",
                status_code=409,
            )
        if dispatch["state"] == "failed":
            await self._db().update_feature_start_state(
                str(dispatch["feature_run_id"]),
                state="blocked",
                error=str(dispatch["error"] or "Feature dispatch failed"),
                updated_at=_now(),
            )
        return dispatch

    async def resume(self, run_id: str) -> dict[str, Any]:
        run = await self._db().get_feature_run(run_id)
        if run is None:
            raise FeatureError("Feature run not found", status_code=404)
        if run["state"] == "done":
            raise FeatureError("Completed FeatureRun cannot be resumed", status_code=409)
        target_role, target_agent_id = self._target_for_stage(run)
        if not isinstance(target_agent_id, str):
            raise FeatureError(
                f"FeatureRun has no assigned {target_role}; correct roles first",
                status_code=409,
            )
        live = {
            member["id"]
            for member in await self._db().list_live_group_members(run["group_id"])
        }
        if target_agent_id not in live:
            raise FeatureError(
                f"Assigned {target_role} is not a live group member; correct "
                "roles before resume",
                status_code=409,
            )
        dispatch = await self._db().ensure_recovery_feature_dispatch(
            run_id,
            expected_stage=str(run["stage"]),
            expected_revision=str(run["updated_at"]),
            target_role=target_role,
            target_agent_id=target_agent_id,
            dispatch_id=uuid.uuid4().hex[:16],
            created_at=_now(),
        )
        if dispatch is None:
            raise FeatureError(
                "FeatureRun changed while resume was reconciling; reload and retry",
                status_code=409,
            )
        if dispatch["state"] == "pending":
            await self._db().update_feature_start_state(
                run_id,
                state="dispatch_pending",
                error=None,
                updated_at=_now(),
            )
        checkpoint = await self._db().get_feature_start_for_run(run_id)
        return {
            "run": run,
            "dispatch": dispatch,
            "checkpoint_state": checkpoint["state"] if checkpoint else None,
        }


feature_delivery_manager = FeatureDeliveryManager()
