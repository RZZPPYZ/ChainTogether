from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any


_ASSET_ROOT = Path(__file__).resolve().parent / "assets"
_SAFE_GROUP_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class PromptAssetError(RuntimeError):
    pass


@dataclass(frozen=True)
class RoutingPolicy:
    version: str
    max_mention_targets: int
    a2a_depth_cap: int
    pingpong_warn_threshold: int
    pingpong_block_threshold: int
    substantive_output_length: int
    hold_min_seconds: int
    hold_max_seconds: int

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RoutingPolicy":
        if raw.get("schema_version") != 1:
            raise PromptAssetError("Unsupported routing policy schema")
        policy = cls(
            version=str(raw["version"]),
            max_mention_targets=int(raw["max_mention_targets"]),
            a2a_depth_cap=int(raw["a2a_depth_cap"]),
            pingpong_warn_threshold=int(raw["pingpong_warn_threshold"]),
            pingpong_block_threshold=int(raw["pingpong_block_threshold"]),
            substantive_output_length=int(raw["substantive_output_length"]),
            hold_min_seconds=int(raw["hold_min_seconds"]),
            hold_max_seconds=int(raw["hold_max_seconds"]),
        )
        if not (
            0 < policy.pingpong_warn_threshold
            < policy.pingpong_block_threshold
        ):
            raise PromptAssetError("Invalid ping-pong thresholds")
        if not (0 < policy.hold_min_seconds <= policy.hold_max_seconds):
            raise PromptAssetError("Invalid hold duration range")
        return policy


@dataclass(frozen=True)
class _CompiledTemplate:
    template: Template
    required: frozenset[str]


class PromptAssetRegistry:
    """Load and compile trusted prompt assets once for the server process."""

    def __init__(self, asset_root: Path = _ASSET_ROOT) -> None:
        self.asset_root = asset_root
        self.routing_policy = self._load_policy()
        self._templates = self._load_templates()

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise PromptAssetError(f"Failed to load prompt asset {path}") from exc
        if not isinstance(raw, dict):
            raise PromptAssetError(f"Prompt asset must be an object: {path}")
        return raw

    def _load_policy(self) -> RoutingPolicy:
        raw = self._read_json(
            self.asset_root / "policies" / "routing-policy.json"
        )
        return RoutingPolicy.from_dict(raw)

    def _load_templates(self) -> dict[str, _CompiledTemplate]:
        manifest = self._read_json(self.asset_root / "prompt-manifest.json")
        if manifest.get("schema_version") != 1:
            raise PromptAssetError("Unsupported prompt manifest schema")
        entries = manifest.get("templates")
        if not isinstance(entries, dict):
            raise PromptAssetError("Prompt manifest has no templates")
        compiled: dict[str, _CompiledTemplate] = {}
        for key, spec in entries.items():
            if not isinstance(spec, dict):
                raise PromptAssetError(f"Invalid template entry: {key}")
            path = self.asset_root / str(spec["path"])
            try:
                source = path.read_text(encoding="utf-8").strip()
            except Exception as exc:
                raise PromptAssetError(f"Failed to load template {path}") from exc
            required = spec.get("required") or []
            if not isinstance(required, list):
                raise PromptAssetError(f"Invalid required variables for {key}")
            compiled[str(key)] = _CompiledTemplate(
                template=Template(source),
                required=frozenset(str(item) for item in required),
            )
        return compiled

    def render(self, key: str, **values: Any) -> str:
        compiled = self._templates.get(key)
        if compiled is None:
            raise PromptAssetError(f"Unknown prompt template: {key}")
        missing = compiled.required - values.keys()
        if missing:
            raise PromptAssetError(
                f"Missing template values for {key}: {', '.join(sorted(missing))}"
            )
        try:
            return compiled.template.substitute(
                {name: str(value) for name, value in values.items()}
            ).strip()
        except (KeyError, ValueError) as exc:
            raise PromptAssetError(f"Failed to render template {key}") from exc


@lru_cache(maxsize=1)
def get_prompt_registry() -> PromptAssetRegistry:
    return PromptAssetRegistry()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


class GroupPromptGovernance:
    def __init__(
        self,
        registry: PromptAssetRegistry | None = None,
        state_root: str | Path | None = None,
    ) -> None:
        self.registry = registry or get_prompt_registry()
        self._state_root = Path(state_root).expanduser() if state_root else None

    def _resolved_state_root(self) -> Path:
        if self._state_root is not None:
            return self._state_root
        from .config import settings

        return Path(settings.group_prompt_state_dir).expanduser()

    def build_roster_snapshot(
        self, group: dict[str, Any], members: list[dict[str, Any]]
    ) -> dict[str, Any]:
        member_rows = [
            {
                "agent_id": str(member["id"]),
                "canonical_name": str(member["name"]),
                "backend": str(member.get("backend") or "claude-code"),
            }
            for member in members
        ]
        stable = {
            "schema_version": 1,
            "group_id": str(group["id"]),
            "group_name": str(group["name"]),
            "default_agent_id": group.get("default_agent_id"),
            "members": member_rows,
        }
        roster_version = hashlib.sha256(
            _canonical_json(stable).encode("utf-8")
        ).hexdigest()[:16]
        return {
            **stable,
            "roster_version": roster_version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def persist_roster_snapshot(self, snapshot: dict[str, Any]) -> Path:
        group_id = str(snapshot["group_id"])
        if not _SAFE_GROUP_ID.fullmatch(group_id):
            raise PromptAssetError("Unsafe group id for roster snapshot")
        target_dir = self._resolved_state_root() / group_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "group-members.json"
        if target.is_file():
            try:
                current = json.loads(target.read_text(encoding="utf-8"))
                if current.get("roster_version") == snapshot.get("roster_version"):
                    return target
            except Exception:
                pass
        temp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        temp.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp, target)
        return target

    def remove_roster_snapshot(self, group_id: str) -> None:
        if not _SAFE_GROUP_ID.fullmatch(group_id):
            return
        shutil.rmtree(self._resolved_state_root() / group_id, ignore_errors=True)

    def render_l0(
        self,
        group: dict[str, Any],
        current_agent: dict[str, Any],
        members: list[dict[str, Any]],
        *,
        persist_snapshot: bool = True,
    ) -> str:
        snapshot = self.build_roster_snapshot(group, members)
        if persist_snapshot:
            self.persist_roster_snapshot(snapshot)
        roster_lines = "\n".join(
            f"- @{member['canonical_name']} "
            f"(id: {member['agent_id']}, backend: {member['backend']})"
            for member in snapshot["members"]
        )
        valid_handles = ", ".join(
            f"@{member['canonical_name']}" for member in snapshot["members"]
        )
        policy = self.registry.routing_policy
        return self.registry.render(
            "l0.system",
            policy_version=policy.version,
            group_id=snapshot["group_id"],
            group_name=snapshot["group_name"],
            roster_version=snapshot["roster_version"],
            agent_id=current_agent["id"],
            agent_name=current_agent["name"],
            agent_backend=current_agent.get("backend") or "claude-code",
            roster_lines=roster_lines,
            valid_handles=valid_handles,
            max_mention_targets=policy.max_mention_targets,
            a2a_depth_cap=policy.a2a_depth_cap,
            hold_min_seconds=policy.hold_min_seconds,
            hold_max_seconds=policy.hold_max_seconds,
        )

    def render_dynamic(self, template_key: str, **values: Any) -> str:
        return self.registry.render(f"dynamic.{template_key}", **values)

    def assemble_dynamic_turn(
        self,
        *,
        directives: list[str],
        delta_messages: list[dict[str, Any]],
        current_message: dict[str, Any],
        delta_from_seq: int,
        delta_to_seq: int,
    ) -> str:
        runtime_directives = (
            "\n\n".join(item.strip() for item in directives if item.strip())
            or "No additional controller directive for this turn."
        )
        return self.registry.render(
            "dynamic.turn",
            runtime_directives=runtime_directives,
            delta_from_seq=delta_from_seq,
            delta_to_seq=delta_to_seq,
            group_delta_json=json.dumps(
                delta_messages, ensure_ascii=False, indent=2
            ),
            current_message_json=json.dumps(
                current_message, ensure_ascii=False, indent=2
            ),
        )
