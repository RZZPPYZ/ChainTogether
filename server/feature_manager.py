from __future__ import annotations

import json
import logging
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .database import Database
from .prompt_governance import get_prompt_registry


logger = logging.getLogger(__name__)


_FEATURE_DIR_RE = re.compile(r"^F(\d{3,})-")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_FRONTMATTER_LINE_RE = r"(?m)^{key}:.*$"
_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "assets" / "templates" / "feature.md"
)


class FeatureError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _yaml_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


class FeatureManager:
    """Durable feature lifecycle separate from per-message group custody."""

    def __init__(self) -> None:
        self.db: Database | None = None

    def bind(self, db: Database) -> None:
        self.db = db

    def _db(self) -> Database:
        if self.db is None:
            raise RuntimeError("FeatureManager not initialized")
        return self.db

    @staticmethod
    def _workflow_path(working_dir: str) -> Path:
        return (
            Path(working_dir)
            / ".chaintogether"
            / "workflows"
            / "feature-lifecycle.yaml"
        )

    def _load_workflow(self, working_dir: str) -> dict[str, Any]:
        path = self._workflow_path(working_dir)
        if not path.is_file():
            raise FeatureError(
                "Feature lifecycle is not configured for this working directory: "
                f"{path}",
                status_code=409,
            )
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FeatureError(f"Invalid feature workflow: {path}") from exc
        if not isinstance(value, dict) or not isinstance(value.get("stages"), dict):
            raise FeatureError(f"Invalid feature workflow structure: {path}")
        return value

    @staticmethod
    def _slug(title: str) -> str:
        slug = _SLUG_RE.sub("-", title.strip().lower()).strip("-")
        return slug or "feature"

    async def _next_feature_id(self, working_dir: str) -> str:
        used: set[int] = set()
        for row in await self._db().list_feature_runs(working_dir=working_dir):
            match = re.fullmatch(r"F(\d+)", row["feature_id"])
            if match:
                used.add(int(match.group(1)))
        docs_root = Path(working_dir) / "docs" / "features"
        if docs_root.is_dir():
            for path in docs_root.iterdir():
                match = _FEATURE_DIR_RE.match(path.name)
                if match:
                    used.add(int(match.group(1)))
        number = max(used, default=0) + 1
        return f"F{number:03d}"

    async def _validate_agent_role(
        self, group: dict[str, Any], agent_id: str | None, role: str
    ) -> None:
        if agent_id is None:
            return
        if agent_id not in group["agent_ids"]:
            raise FeatureError(
                f"{role} must be a current member of group {group['id']}"
            )
        if await self._db().get_agent(agent_id) is None:
            raise FeatureError(f"{role} agent not found", status_code=404)

    @staticmethod
    def _validate_distinct_roles(roles: dict[str, str | None]) -> None:
        assigned = [value for value in roles.values() if value]
        if len(assigned) != len(set(assigned)):
            raise FeatureError(
                "Feature owner, reviewer, and vision guardian must be different agents"
            )

    async def create_for_group(
        self,
        group_id: str,
        *,
        title: str,
        priority: str = "P1",
        owner_agent_id: str | None = None,
        operator_quote: str = "",
        origin_message_seq: int | None = None,
    ) -> dict[str, Any]:
        db = self._db()
        group = await db.get_group(group_id)
        if group is None:
            raise FeatureError("Group not found", status_code=404)
        title = title.strip()
        if not title:
            raise FeatureError("Feature title is required")
        if not re.fullmatch(r"P[0-3]", priority):
            raise FeatureError("Priority must be P0, P1, P2, or P3")
        await self._validate_agent_role(group, owner_agent_id, "owner")
        workflow = self._load_workflow(group["working_dir"])

        feature_id = await self._next_feature_id(group["working_dir"])
        relative_path = (
            Path("docs")
            / "features"
            / f"{feature_id}-{self._slug(title)}"
            / "feature.md"
        )
        feature_doc = Path(group["working_dir"]) / relative_path
        if feature_doc.exists():
            raise FeatureError(f"Feature document already exists: {feature_doc}")
        feature_doc.parent.mkdir(parents=True, exist_ok=False)

        created_at = _now()
        owner = owner_agent_id or ""
        substitutions = {
            "FEATURE_ID": feature_id,
            "TITLE": json.dumps(title, ensure_ascii=False)[1:-1],
            "PRIORITY": priority,
            "OWNER": json.dumps(owner, ensure_ascii=False)[1:-1],
            "ORIGIN_KIND": "group_message",
            "GROUP_ID": group_id,
            "MESSAGE_SEQ": (
                str(origin_message_seq)
                if origin_message_seq is not None
                else "null"
            ),
            "CREATED_AT": created_at,
            "OPERATOR_QUOTE": json.dumps(
                operator_quote.strip(), ensure_ascii=False
            )[1:-1],
        }
        template = _TEMPLATE_PATH.read_text(encoding="utf-8")
        for key, value in substitutions.items():
            template = template.replace("{{" + key + "}}", value)
        feature_doc.write_text(template, encoding="utf-8")

        run_id = uuid.uuid4().hex[:12]
        initial_stage = str(workflow.get("initial_stage", "discovery"))
        stage_spec = workflow["stages"].get(initial_stage) or {}
        row = await db.create_feature_run(
            run_id=run_id,
            feature_id=feature_id,
            group_id=group_id,
            working_dir=group["working_dir"],
            feature_doc_path=relative_path.as_posix(),
            title=title,
            stage=initial_stage,
            state="active",
            priority=priority,
            owner_agent_id=owner_agent_id,
            current_gate=stage_spec.get("gate"),
            operator_quote=operator_quote.strip(),
            origin_message_seq=origin_message_seq,
            artifact_refs=[relative_path.as_posix()],
            created_at=created_at,
        )
        await db.append_feature_run_event(
            run_id=run_id,
            from_stage="",
            to_stage=initial_stage,
            result="created",
            actor_agent_id=owner_agent_id,
            reason="Feature created from group context",
            evidence_refs=[relative_path.as_posix()],
            revision="",
            created_at=created_at,
        )
        await db.set_group_active_feature(group_id, run_id, created_at)
        return row

    async def get(self, run_id: str) -> dict[str, Any]:
        row = await self._db().get_feature_run(run_id)
        if row is None:
            raise FeatureError("Feature run not found", status_code=404)
        return row

    async def get_for_group(
        self, run_id: str, group_id: str
    ) -> dict[str, Any]:
        row = await self.get(run_id)
        if row["group_id"] != group_id:
            raise FeatureError(
                "Feature run does not belong to this group", status_code=409
            )
        return row

    async def list_for_group(self, group_id: str) -> list[dict[str, Any]]:
        if await self._db().get_group(group_id) is None:
            raise FeatureError("Group not found", status_code=404)
        return await self._db().list_feature_runs(group_id=group_id)

    async def get_active_for_group(
        self, group_id: str
    ) -> dict[str, Any] | None:
        if await self._db().get_group(group_id) is None:
            raise FeatureError("Group not found", status_code=404)
        run_id = await self._db().get_group_active_feature_id(group_id)
        if run_id is None:
            return None
        row = await self.get_for_group(run_id, group_id)
        if row["state"] == "done":
            await self._db().clear_group_active_feature(
                group_id, run_id=run_id
            )
            return None
        return row

    async def activate_for_group(
        self, run_id: str, group_id: str
    ) -> dict[str, Any]:
        row = await self.get_for_group(run_id, group_id)
        if row["state"] == "done":
            raise FeatureError(
                "Completed feature runs cannot become active", status_code=409
            )
        await self._db().set_group_active_feature(group_id, run_id, _now())
        return row

    async def clear_active_for_group(self, group_id: str) -> None:
        if await self._db().get_group(group_id) is None:
            raise FeatureError("Group not found", status_code=404)
        await self._db().clear_group_active_feature(group_id)

    async def update_roles(
        self, run_id: str, changes: dict[str, str | None]
    ) -> dict[str, Any]:
        row = await self.get(run_id)
        group = await self._db().get_group(row["group_id"])
        if group is None:
            raise FeatureError("Feature group not found", status_code=404)
        fields = (
            "owner_agent_id",
            "reviewer_agent_id",
            "vision_guardian_agent_id",
        )
        roles = {field: row[field] for field in fields}
        for field, value in changes.items():
            if field not in fields:
                continue
            await self._validate_agent_role(group, value, field)
            roles[field] = value
        self._validate_distinct_roles(roles)
        updated_at = _now()
        doc_path, doc_content = self._prepare_doc_sync(
            row,
            {
                "owner": roles["owner_agent_id"] or "",
                "reviewer": roles["reviewer_agent_id"] or "",
                "vision_guardian": roles["vision_guardian_agent_id"] or "",
                "updated_at": updated_at,
            },
        )
        updated = await self._db().update_feature_roles_with_doc_sync(
            run_id,
            expected_updated_at=row["updated_at"],
            fields={**roles, "updated_at": updated_at},
            feature_doc_path=str(doc_path),
            document_content=doc_content,
            updated_at=updated_at,
        )
        if not updated:
            raise FeatureError(
                "Feature roles changed concurrently; reload and retry",
                status_code=409,
            )
        await self._flush_doc_sync(run_id)
        return await self.get(run_id)

    async def transition_for_session(
        self,
        run_id: str,
        actor_session_id: str,
        *,
        to_stage: str,
        result: str = "",
        reason: str = "",
        evidence_refs: list[str] | None = None,
        revision: str = "",
    ) -> dict[str, Any]:
        """Transition using the server-owned group-session identity."""
        row = await self.get(run_id)
        actor_agent_id = await self._db().get_group_agent_by_session(
            row["group_id"], actor_session_id
        )
        if actor_agent_id is None:
            raise FeatureError(
                "Actor session is not bound to this FeatureRun group",
                status_code=403,
            )
        return await self.transition(
            run_id,
            to_stage=to_stage,
            result=result,
            actor_agent_id=actor_agent_id,
            reason=reason,
            evidence_refs=evidence_refs,
            revision=revision,
        )

    async def transition(
        self,
        run_id: str,
        *,
        to_stage: str,
        result: str = "",
        actor_agent_id: str | None = None,
        reason: str = "",
        evidence_refs: list[str] | None = None,
        revision: str = "",
    ) -> dict[str, Any]:
        row = await self.get(run_id)
        if row["state"] == "done":
            raise FeatureError("Completed feature runs cannot transition")
        group = await self._db().get_group(row["group_id"])
        if group is None:
            raise FeatureError("Feature group not found", status_code=404)
        await self._validate_agent_role(group, actor_agent_id, "actor")
        workflow = self._load_workflow(row["working_dir"])
        stages = workflow["stages"]
        if to_stage not in stages:
            raise FeatureError(f"Unknown feature stage: {to_stage}")
        candidates = [
            item
            for item in workflow.get("transitions", [])
            if item.get("from") == row["stage"] and item.get("to") == to_stage
        ]
        matching = [
            item
            for item in candidates
            if not item.get("result") or item.get("result") == result
        ]
        if not matching:
            expected = sorted(
                str(item.get("result") or "(none)") for item in candidates
            )
            suffix = f"; expected result: {', '.join(expected)}" if expected else ""
            raise FeatureError(
                f"Invalid feature transition {row['stage']} -> {to_stage}{suffix}"
            )

        roles = {
            "owner_agent_id": row["owner_agent_id"],
            "reviewer_agent_id": row["reviewer_agent_id"],
            "vision_guardian_agent_id": row["vision_guardian_agent_id"],
        }
        self._validate_distinct_roles(roles)
        if to_stage in {"review", "merge"} and not row["reviewer_agent_id"]:
            raise FeatureError("An independent reviewer must be assigned first")
        if to_stage in {"closure", "done"} and not row["vision_guardian_agent_id"]:
            raise FeatureError("An independent vision guardian must be assigned first")
        if row["stage"] == "review":
            if actor_agent_id != row["reviewer_agent_id"]:
                raise FeatureError(
                    "Only the assigned reviewer may issue a review verdict"
                )
        if row["stage"] == "acceptance":
            if actor_agent_id != row["vision_guardian_agent_id"]:
                raise FeatureError(
                    "Only the assigned vision guardian may issue an acceptance verdict"
                )

        evidence = self._validate_evidence_refs(row, evidence_refs or [])
        edge = f"{row['stage']}->{to_stage}"
        if edge in set(workflow.get("evidence_required_for", [])) and not evidence:
            raise FeatureError(f"Transition {edge} requires evidence_refs")
        revision = self._validate_revision(row, edge, revision)
        self._assert_doc_gate(
            row,
            edge,
            actor_agent_id=actor_agent_id,
            revision=revision,
        )

        updated_at = _now()
        state = "done" if to_stage in workflow.get("terminal_stages", []) else "active"
        completed_at = updated_at if state == "done" else None
        stage_spec = stages.get(to_stage) or {}
        artifact_refs = list(dict.fromkeys([*row["artifact_refs"], *evidence]))
        doc_path, doc_content = self._prepare_doc_sync(
            row,
            {"stage": to_stage, "state": state, "updated_at": updated_at},
        )
        transitioned = await self._db().transition_feature_run(
            run_id,
            expected_stage=row["stage"],
            expected_updated_at=row["updated_at"],
            fields={
                "stage": to_stage,
                "state": state,
                "current_gate": stage_spec.get("gate"),
                "artifact_refs": artifact_refs,
                "updated_at": updated_at,
                "completed_at": completed_at,
            },
            from_stage=row["stage"],
            to_stage=to_stage,
            result=result,
            actor_agent_id=actor_agent_id,
            reason=reason.strip(),
            evidence_refs=evidence,
            revision=revision,
            created_at=updated_at,
            feature_doc_path=str(doc_path),
            document_content=doc_content,
            clear_active_group_id=row["group_id"] if state == "done" else None,
        )
        if not transitioned:
            raise FeatureError(
                "Stale feature transition; stage changed concurrently",
                status_code=409,
            )
        await self._flush_doc_sync(run_id)
        return await self.get(run_id)

    async def list_events(self, run_id: str) -> list[dict[str, Any]]:
        await self.get(run_id)
        return await self._db().list_feature_run_events(run_id)

    async def render_turn_context(
        self, run_id: str, group_id: str, agent_id: str
    ) -> str:
        row = await self.get_for_group(run_id, group_id)
        workflow = self._load_workflow(row["working_dir"])
        stage_spec = workflow["stages"][row["stage"]]
        role = "collaborator"
        if agent_id == row["owner_agent_id"]:
            role = "owner"
        elif agent_id == row["reviewer_agent_id"]:
            role = "reviewer"
        elif agent_id == row["vision_guardian_agent_id"]:
            role = "vision_guardian"
        role_skills = stage_spec.get("skills_by_role")
        if isinstance(role_skills, dict):
            skills = role_skills.get(role, [])
        else:
            skills = stage_spec.get("skills")
            if not isinstance(skills, list):
                skills = (
                    [stage_spec["skill"]] if stage_spec.get("skill") else []
                )
        if not isinstance(skills, list):
            skills = []
        skill_lines = ", ".join("$" + name for name in skills) or "(none)"
        return get_prompt_registry().render(
            "dynamic.update_workflow_sop",
            feature_run_id=row["id"],
            feature_id=row["feature_id"],
            stage=row["stage"],
            state=row["state"],
            role=role,
            canonical_doc=row["feature_doc_path"],
            suggested_skills=skill_lines,
            current_gate=row["current_gate"] or "(none)",
            next_step=stage_spec.get("next_step") or "Consult the Feature Doc.",
        )

    def _prepare_doc_sync(
        self, row: dict[str, Any], values: dict[str, Any]
    ) -> tuple[Path, str]:
        path = Path(row["working_dir"]) / row["feature_doc_path"]
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise FeatureError(f"Cannot read canonical Feature Doc: {path}") from exc
        for key, value in values.items():
            pattern = re.compile(_FRONTMATTER_LINE_RE.format(key=re.escape(key)))
            replacement = f"{key}: {_yaml_value(value)}"
            if not pattern.search(text):
                raise FeatureError(f"Feature Doc frontmatter lacks {key}: {path}")
            text = pattern.sub(replacement, text, count=1)
        return path, text

    @staticmethod
    def _write_doc_content(path: Path, content: str) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()

    async def _flush_doc_sync(self, run_id: str) -> bool:
        pending = await self._db().get_feature_doc_sync(run_id)
        if pending is None:
            return True
        try:
            self._write_doc_content(
                Path(pending["feature_doc_path"]), pending["content"]
            )
        except OSError:
            logger.exception(
                "Feature %s document sync remains pending", run_id
            )
            return False
        await self._db().complete_feature_doc_sync(
            run_id, pending["updated_at"]
        )
        return True

    async def reconcile_document_syncs(self) -> None:
        for pending in await self._db().list_feature_doc_syncs():
            await self._flush_doc_sync(pending["feature_run_id"])

    @staticmethod
    def _section_body(text: str, heading: str) -> str:
        match = re.search(
            rf"^## {re.escape(heading)}\s*$\r?\n(.*?)(?=^## |\Z)",
            text,
            re.MULTILINE | re.DOTALL,
        )
        return match.group(1).strip() if match else ""

    @staticmethod
    def _section_field(section: str, label: str) -> str:
        match = re.search(
            rf"(?m)^- \*\*{re.escape(label)}\*\*:\s*(.*?)\s*$", section
        )
        return match.group(1).strip() if match else ""

    def _assert_doc_gate(
        self,
        row: dict[str, Any],
        edge: str,
        *,
        actor_agent_id: str | None,
        revision: str,
    ) -> None:
        """Require verdict-bearing transitions in the canonical Feature Doc."""
        path = Path(row["working_dir"]) / row["feature_doc_path"]
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise FeatureError(f"Cannot read canonical Feature Doc: {path}") from exc

        required_verdicts = {
            "design->planning": ("Design Gate", "approved"),
            "review->merge": ("Review Provenance", "approved"),
            "acceptance->closure": ("Vision Gate", "accepted"),
        }
        requirement = required_verdicts.get(edge)
        if requirement is not None:
            heading, verdict = requirement
            section = self._section_body(text, heading)
            if not re.search(
                rf"\*\*Verdict\*\*:\s*{re.escape(verdict)}\b",
                section,
                re.IGNORECASE,
            ):
                raise FeatureError(
                    f"Transition {edge} requires {heading} verdict={verdict} "
                    "in the canonical Feature Doc"
                )
        if edge == "review->merge":
            section = self._section_body(text, "Review Provenance")
            reviewer = self._section_field(section, "Reviewer")
            base_sha = self._section_field(section, "Base SHA")
            reviewed_head = self._section_field(section, "Reviewed HEAD")
            if reviewer != str(row["reviewer_agent_id"] or ""):
                raise FeatureError(
                    "Review Provenance Reviewer must match the assigned reviewer"
                )
            if actor_agent_id != row["reviewer_agent_id"]:
                raise FeatureError(
                    "Review Provenance actor must be the assigned reviewer"
                )
            if not re.fullmatch(r"[0-9a-fA-F]{7,64}", base_sha):
                raise FeatureError("Review Provenance Base SHA is required")
            if reviewed_head.lower() != revision.lower():
                raise FeatureError(
                    "Review Provenance Reviewed HEAD must match transition revision"
                )
        if edge in {"acceptance->closure", "closure->done"}:
            section = self._section_body(text, "Vision Gate")
            guardian = self._section_field(section, "Guardian")
            merged_revision = self._section_field(section, "Merged revision")
            journey_evidence = self._section_field(section, "Journey evidence")
            if guardian != str(row["vision_guardian_agent_id"] or ""):
                raise FeatureError(
                    "Vision Gate Guardian must match the assigned guardian"
                )
            if merged_revision.lower() != revision.lower():
                raise FeatureError(
                    "Vision Gate Merged revision must match transition revision"
                )
            if not journey_evidence:
                raise FeatureError("Vision Gate Journey evidence is required")
        if edge == "closure->done":
            unchecked = re.findall(r"^-\s*\[ \]\s+AC-", text, re.MULTILINE)
            if unchecked:
                raise FeatureError(
                    "Feature cannot close while acceptance criteria are unchecked"
                )
            vision = self._section_body(text, "Vision Gate")
            if not re.search(
                r"\*\*Verdict\*\*:\s*accepted\b", vision, re.IGNORECASE
            ):
                raise FeatureError(
                    "Feature cannot close without an accepted Vision Gate"
                )

    @staticmethod
    def _git_head(working_dir: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        value = completed.stdout.strip()
        return value if completed.returncode == 0 and value else None

    def _validate_revision(
        self, row: dict[str, Any], edge: str, revision: str
    ) -> str:
        revision = revision.strip()
        required = {
            "review->merge",
            "merge->acceptance",
            "acceptance->closure",
            "closure->done",
        }
        if edge not in required:
            return revision
        if not re.fullmatch(r"[0-9a-fA-F]{7,64}", revision):
            raise FeatureError(f"Transition {edge} requires a valid revision")
        current = self._git_head(row["working_dir"])
        if current is not None and current.lower() != revision.lower():
            raise FeatureError(
                f"Transition {edge} revision does not match current HEAD"
            )
        return revision

    def _validate_evidence_refs(
        self, row: dict[str, Any], refs: list[str]
    ) -> list[str]:
        root = Path(row["working_dir"]).resolve()
        feature_dir = (root / row["feature_doc_path"]).resolve().parent
        valid: list[str] = []
        for value in refs:
            ref = str(value).strip()
            if not ref:
                raise FeatureError("Evidence references must be non-empty")
            if re.fullmatch(r"https?://\S+", ref):
                valid.append(ref)
                continue
            candidate = Path(ref)
            if not candidate.is_absolute():
                candidate = (
                    root / candidate
                    if candidate.parts and candidate.parts[0] == "docs"
                    else feature_dir / candidate
                )
            resolved = candidate.resolve()
            if not resolved.is_relative_to(root) or not resolved.is_file():
                raise FeatureError(
                    f"Invalid or missing evidence reference: {ref}"
                )
            valid.append(ref)
        return list(dict.fromkeys(valid))


feature_manager = FeatureManager()
