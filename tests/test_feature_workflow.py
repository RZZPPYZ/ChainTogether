from __future__ import annotations

import asyncio
import re
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

from server.agent_manager import AgentManager
from server.config import settings
from server.database import Database
from server.feature_manager import FeatureError, FeatureManager
from server.group_manager import AgentTurnResult, GroupManager
from server.harness import RunConfig, get_harness
from server.harness.assembly import build_callback_env
from server.routers import features as feature_routes
from server.session_manager import SessionManager


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FeatureWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        workflow_dir = self.workspace / ".chaintogether" / "workflows"
        workflow_dir.mkdir(parents=True)
        shutil.copyfile(
            PROJECT_ROOT
            / ".chaintogether"
            / "workflows"
            / "feature-lifecycle.yaml",
            workflow_dir / "feature-lifecycle.yaml",
        )
        subprocess.run(
            ["git", "init", "-q"], cwd=self.workspace, check=True
        )
        subprocess.run(
            ["git", "add", "."], cwd=self.workspace, check=True
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=ChainTogether Tests",
                "-c",
                "user.email=tests@chaintogether.invalid",
                "commit",
                "-qm",
                "test baseline",
            ],
            cwd=self.workspace,
            check=True,
        )
        self.git_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.workspace,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.old_agents_dir = settings.agents_dir
        self.old_group_prompt_state_dir = settings.group_prompt_state_dir
        settings.agents_dir = str(self.root / "agents")
        settings.group_prompt_state_dir = str(self.root / "groups")

        self.db = Database(str(self.root / "test.db"))
        await self.db.initialize()
        self.session_manager = SessionManager()
        await self.session_manager.initialize(self.db)
        agent_manager = AgentManager(self.db)
        self.owner = await agent_manager.create_agent(name="Builder")
        self.reviewer = await agent_manager.create_agent(name="Reviewer")
        self.guardian = await agent_manager.create_agent(name="Guardian")

        self.feature_manager = FeatureManager()
        self.feature_manager.bind(self.db)
        self.group_manager = GroupManager()
        self.group_manager.bind(
            self.session_manager, self.db, self.feature_manager
        )
        self.group = await self.group_manager.create_group(
            "Feature Team",
            [
                self.owner["id"],
                self.reviewer["id"],
                self.guardian["id"],
            ],
            working_dir=str(self.workspace),
        )

    async def asyncTearDown(self) -> None:
        self.group_manager.shutdown()
        await self.db.close()
        settings.agents_dir = self.old_agents_dir
        settings.group_prompt_state_dir = self.old_group_prompt_state_dir
        self.temp.cleanup()

    async def _create_feature(self) -> dict[str, object]:
        return await self.feature_manager.create_for_group(
            self.group["id"],
            title="Durable group handoff",
            owner_agent_id=self.owner["id"],
            operator_quote="Ship one feature across several agents.",
        )

    @staticmethod
    def _set_section_verdict(path: Path, heading: str, verdict: str) -> None:
        text = path.read_text(encoding="utf-8")
        marker = f"## {heading}"
        start = text.index(marker)
        verdict_pos = text.index("**Verdict**: pending", start)
        text = (
            text[:verdict_pos]
            + f"**Verdict**: {verdict}"
            + text[verdict_pos + len("**Verdict**: pending") :]
        )
        path.write_text(text, encoding="utf-8")

    @staticmethod
    def _set_section_fields(
        path: Path, heading: str, values: dict[str, str]
    ) -> None:
        text = path.read_text(encoding="utf-8")
        start = text.index(f"## {heading}")
        next_heading = text.find("\n## ", start + 3)
        end = len(text) if next_heading < 0 else next_heading
        section = text[start:end]
        for label, value in values.items():
            pattern = re.compile(rf"(?m)^- \*\*{re.escape(label)}\*\*:.*$")
            if not pattern.search(section):
                raise AssertionError(f"Missing field {label!r} in {heading}")
            section = pattern.sub(f"- **{label}**: {value}", section, count=1)
        path.write_text(text[:start] + section + text[end:], encoding="utf-8")

    def _write_evidence(
        self, run: dict[str, object], name: str, content: str = "verified"
    ) -> str:
        feature_dir = (self.workspace / str(run["feature_doc_path"])).parent
        evidence_dir = feature_dir / "evidence"
        evidence_dir.mkdir(exist_ok=True)
        (evidence_dir / name).write_text(content, encoding="utf-8")
        return f"evidence/{name}"

    async def _advance_to_quality(self) -> tuple[dict[str, object], Path]:
        run = await self._create_feature()
        doc = self.workspace / str(run["feature_doc_path"])
        await self.feature_manager.update_roles(
            str(run["id"]),
            {
                "reviewer_agent_id": self.reviewer["id"],
                "vision_guardian_agent_id": self.guardian["id"],
            },
        )
        await self.feature_manager.transition(str(run["id"]), to_stage="design")
        self._set_section_verdict(doc, "Design Gate", "approved")
        await self.feature_manager.transition(
            str(run["id"]), to_stage="planning", result="approved"
        )
        await self.feature_manager.transition(
            str(run["id"]), to_stage="implementation"
        )
        await self.feature_manager.transition(str(run["id"]), to_stage="quality")
        return run, doc

    async def test_feature_doc_roles_events_and_hard_gates(self) -> None:
        run = await self._create_feature()
        doc = self.workspace / str(run["feature_doc_path"])

        self.assertEqual(run["feature_id"], "F001")
        self.assertTrue(doc.is_file())
        self.assertIn("stage: discovery", doc.read_text(encoding="utf-8"))
        active = await self.feature_manager.get_active_for_group(self.group["id"])
        assert active is not None
        self.assertEqual(active["id"], run["id"])
        events = await self.feature_manager.list_events(str(run["id"]))
        self.assertEqual(events[0]["result"], "created")

        with self.assertRaisesRegex(FeatureError, "must be different"):
            await self.feature_manager.update_roles(
                str(run["id"]),
                {"reviewer_agent_id": self.owner["id"]},
            )
        run = await self.feature_manager.update_roles(
            str(run["id"]),
            {
                "reviewer_agent_id": self.reviewer["id"],
                "vision_guardian_agent_id": self.guardian["id"],
            },
        )
        self.assertEqual(run["reviewer_agent_id"], self.reviewer["id"])

        await self.feature_manager.transition(str(run["id"]), to_stage="design")
        with self.assertRaisesRegex(FeatureError, "Design Gate"):
            await self.feature_manager.transition(
                str(run["id"]), to_stage="planning", result="approved"
            )
        self._set_section_verdict(doc, "Design Gate", "approved")
        await self.feature_manager.transition(
            str(run["id"]), to_stage="planning", result="approved"
        )
        await self.feature_manager.transition(
            str(run["id"]), to_stage="implementation"
        )
        await self.feature_manager.transition(str(run["id"]), to_stage="quality")

        with self.assertRaisesRegex(FeatureError, "requires evidence_refs"):
            await self.feature_manager.transition(
                str(run["id"]), to_stage="review", result="passed"
            )
        quality_ref = self._write_evidence(run, "quality-report.md")
        await self.feature_manager.transition(
            str(run["id"]),
            to_stage="review",
            result="passed",
            evidence_refs=[quality_ref],
        )
        reviewer_hint = await self.feature_manager.render_turn_context(
            str(run["id"]), self.group["id"], self.reviewer["id"]
        )
        owner_hint = await self.feature_manager.render_turn_context(
            str(run["id"]), self.group["id"], self.owner["id"]
        )
        self.assertIn("Suggested skill(s): $review-feature", reviewer_hint)
        self.assertNotIn("$request-review", reviewer_hint)
        self.assertIn("$request-review", owner_hint)
        self.assertIn("$receive-review", owner_hint)
        self.assertNotIn("$review-feature", owner_hint)
        review_revision = self.git_head
        self._set_section_fields(
            doc,
            "Review Provenance",
            {
                "Reviewer": str(self.reviewer["id"]),
                "Base SHA": self.git_head,
                "Reviewed HEAD": review_revision,
                "Verdict": "approved",
            },
        )
        review_ref = self._write_evidence(run, "review.md")
        with self.assertRaisesRegex(FeatureError, "assigned reviewer"):
            await self.feature_manager.transition(
                str(run["id"]),
                to_stage="merge",
                result="approved",
                actor_agent_id=self.owner["id"],
                evidence_refs=[review_ref],
                revision=review_revision,
            )
        merged = await self.feature_manager.transition(
            str(run["id"]),
            to_stage="merge",
            result="approved",
            actor_agent_id=self.reviewer["id"],
            evidence_refs=[review_ref],
            revision=review_revision,
        )
        self.assertEqual(merged["stage"], "merge")
        self.assertEqual(
            merged["artifact_refs"],
            [
                str(run["feature_doc_path"]),
                quality_ref,
                review_ref,
            ],
        )
        merged_revision = self.git_head
        merge_ref = self._write_evidence(run, "merge.md")
        await self.feature_manager.transition(
            str(run["id"]),
            to_stage="acceptance",
            result="merged",
            evidence_refs=[merge_ref],
            revision=merged_revision,
        )
        vision_ref = self._write_evidence(run, "vision.md")
        self._set_section_fields(
            doc,
            "Vision Gate",
            {
                "Guardian": str(self.guardian["id"]),
                "Merged revision": merged_revision,
                "Verdict": "accepted",
                "Journey evidence": vision_ref,
            },
        )
        text = doc.read_text(encoding="utf-8")
        doc.write_text(text.replace("- [ ] AC-1:", "- [x] AC-1:"), encoding="utf-8")
        await self.feature_manager.transition(
            str(run["id"]),
            to_stage="closure",
            result="accepted",
            actor_agent_id=self.guardian["id"],
            evidence_refs=[vision_ref],
            revision=merged_revision,
        )
        closure_ref = self._write_evidence(run, "closure.md")
        done = await self.feature_manager.transition(
            str(run["id"]),
            to_stage="done",
            result="closed",
            actor_agent_id=self.owner["id"],
            evidence_refs=[closure_ref],
            revision=merged_revision,
        )
        self.assertEqual(done["state"], "done")
        self.assertIsNone(
            await self.feature_manager.get_active_for_group(self.group["id"])
        )

    async def test_group_invocation_persists_and_injects_feature_context(self) -> None:
        run = await self._create_feature()
        captured: dict[str, str] = {}

        async def collect(
            _session_id: str, prompt: str, **_kwargs: object
        ) -> AgentTurnResult:
            captured["prompt"] = prompt
            return AgentTurnResult("Discovery evidence recorded.")

        self.group_manager._collect_agent_reply = collect  # type: ignore[method-assign]
        invocation = await self.group_manager.send_message(
            self.group["id"],
            "@Builder inspect the operator need",
        )
        self.assertIsNotNone(invocation)
        assert invocation is not None
        active = self.group_manager._invocations[invocation["id"]]
        assert active.runner_task is not None
        await active.runner_task

        stored = await self.db.get_group_invocation(invocation["id"])
        assert stored is not None
        self.assertEqual(stored["feature_run_id"], run["id"])
        self.assertEqual(invocation["feature_run_id"], run["id"])
        self.assertIn("D14 — update-workflow-sop", captured["prompt"])
        self.assertIn(f"FeatureRun: {run['id']} | Feature: F001", captured["prompt"])
        self.assertIn("Stage: discovery | State: active | Role: owner", captured["prompt"])
        self.assertIn("Suggested skill(s): $feature-discovery", captured["prompt"])
        self.assertIn("Next step:", captured["prompt"])
        self.assertIn(str(run["feature_doc_path"]), captured["prompt"])

    async def test_concurrent_transitions_use_compare_and_swap(self) -> None:
        run, _doc = await self._advance_to_quality()
        quality_ref = self._write_evidence(run, "quality-report.md")

        results = await asyncio.gather(
            self.feature_manager.transition(
                str(run["id"]),
                to_stage="review",
                result="passed",
                evidence_refs=[quality_ref],
            ),
            self.feature_manager.transition(
                str(run["id"]),
                to_stage="implementation",
                result="failed",
            ),
            return_exceptions=True,
        )

        self.assertEqual(sum(isinstance(item, FeatureError) for item in results), 1)
        events = await self.feature_manager.list_events(str(run["id"]))
        quality_events = [item for item in events if item["from_stage"] == "quality"]
        self.assertEqual(len(quality_events), 1)
        current = await self.feature_manager.get(str(run["id"]))
        self.assertEqual(current["stage"], quality_events[0]["to_stage"])

    async def test_doc_preflight_failure_does_not_advance_database(self) -> None:
        run = await self._create_feature()
        doc = self.workspace / str(run["feature_doc_path"])
        await self.feature_manager.transition(str(run["id"]), to_stage="design")
        text = doc.read_text(encoding="utf-8")
        doc.write_text(
            re.sub(r"(?m)^updated_at:.*\n", "", text), encoding="utf-8"
        )

        with self.assertRaisesRegex(FeatureError, "lacks updated_at"):
            await self.feature_manager.transition(
                str(run["id"]),
                to_stage="discovery",
                result="changes_required",
            )

        current = await self.feature_manager.get(str(run["id"]))
        self.assertEqual(current["stage"], "design")
        events = await self.feature_manager.list_events(str(run["id"]))
        self.assertEqual(events[-1]["to_stage"], "design")

    async def test_failed_doc_delivery_is_recovered_from_outbox(self) -> None:
        run = await self._create_feature()
        doc = self.workspace / str(run["feature_doc_path"])
        await self.feature_manager.transition(str(run["id"]), to_stage="design")

        with mock.patch.object(
            FeatureManager,
            "_write_doc_content",
            side_effect=OSError("simulated filesystem failure"),
        ):
            transitioned = await self.feature_manager.transition(
                str(run["id"]),
                to_stage="discovery",
                result="changes_required",
            )

        self.assertEqual(transitioned["stage"], "discovery")
        self.assertIn("stage: \"design\"", doc.read_text(encoding="utf-8"))
        self.assertIsNotNone(
            await self.db.get_feature_doc_sync(str(run["id"]))
        )

        await self.feature_manager.reconcile_document_syncs()
        self.assertIn("stage: \"discovery\"", doc.read_text(encoding="utf-8"))
        self.assertIsNone(await self.db.get_feature_doc_sync(str(run["id"])))

    async def test_later_mutation_preserves_pending_document_image(self) -> None:
        run = await self._create_feature()
        doc = self.workspace / str(run["feature_doc_path"])
        with mock.patch.object(
            FeatureManager,
            "_write_doc_content",
            side_effect=OSError("simulated role delivery failure"),
        ):
            await self.feature_manager.update_roles(
                str(run["id"]),
                {
                    "reviewer_agent_id": self.reviewer["id"],
                    "vision_guardian_agent_id": self.guardian["id"],
                },
            )

        self.assertIn('reviewer: ""', doc.read_text(encoding="utf-8"))
        self.assertIsNotNone(await self.db.get_feature_doc_sync(str(run["id"])))

        await self.feature_manager.transition(str(run["id"]), to_stage="design")

        delivered = doc.read_text(encoding="utf-8")
        self.assertIn(f'reviewer: "{self.reviewer["id"]}"', delivered)
        self.assertIn(
            f'vision_guardian: "{self.guardian["id"]}"', delivered
        )
        self.assertIn('stage: "design"', delivered)
        self.assertIsNone(await self.db.get_feature_doc_sync(str(run["id"])))

    async def test_manual_doc_edit_blocks_pending_image_supersession(self) -> None:
        run = await self._create_feature()
        doc = self.workspace / str(run["feature_doc_path"])
        with mock.patch.object(
            FeatureManager,
            "_write_doc_content",
            side_effect=OSError("simulated role delivery failure"),
        ):
            await self.feature_manager.update_roles(
                str(run["id"]),
                {"reviewer_agent_id": self.reviewer["id"]},
            )
        doc.write_text(
            doc.read_text(encoding="utf-8") + "\nmanual operator note\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(FeatureError, "changed while document sync"):
            await self.feature_manager.transition(
                str(run["id"]), to_stage="design"
            )

        self.assertEqual(
            (await self.feature_manager.get(str(run["id"])))["stage"],
            "discovery",
        )
        self.assertIn("manual operator note", doc.read_text(encoding="utf-8"))
        self.assertIsNotNone(await self.db.get_feature_doc_sync(str(run["id"])))

    async def test_evidence_and_provenance_cannot_be_faked(self) -> None:
        run, _doc = await self._advance_to_quality()
        with self.assertRaisesRegex(FeatureError, "evidence reference"):
            await self.feature_manager.transition(
                str(run["id"]),
                to_stage="review",
                result="passed",
                evidence_refs=["evidence/does-not-exist.md"],
            )
        self.assertEqual(
            (await self.feature_manager.get(str(run["id"])))["stage"],
            "quality",
        )

        quality_ref = self._write_evidence(run, "quality-report.md")
        await self.feature_manager.transition(
            str(run["id"]),
            to_stage="review",
            result="passed",
            evidence_refs=[quality_ref],
        )
        doc = self.workspace / str(run["feature_doc_path"])
        self._set_section_verdict(doc, "Review Provenance", "approved")
        review_ref = self._write_evidence(run, "review.md")
        with self.assertRaisesRegex(FeatureError, "Reviewer"):
            await self.feature_manager.transition(
                str(run["id"]),
                to_stage="merge",
                result="approved",
                actor_agent_id=self.reviewer["id"],
                evidence_refs=[review_ref],
                revision=self.git_head,
            )

    async def test_protected_revision_fails_closed_without_git(self) -> None:
        run, doc = await self._advance_to_quality()
        quality_ref = self._write_evidence(run, "quality-report.md")
        await self.feature_manager.transition(
            str(run["id"]),
            to_stage="review",
            result="passed",
            evidence_refs=[quality_ref],
        )
        self._set_section_fields(
            doc,
            "Review Provenance",
            {
                "Reviewer": str(self.reviewer["id"]),
                "Base SHA": self.git_head,
                "Reviewed HEAD": self.git_head,
                "Verdict": "approved",
            },
        )
        review_ref = self._write_evidence(run, "review.md")

        with mock.patch.object(FeatureManager, "_git_commit", return_value=None):
            with self.assertRaisesRegex(FeatureError, "cannot verify"):
                await self.feature_manager.transition(
                    str(run["id"]),
                    to_stage="merge",
                    result="approved",
                    actor_agent_id=self.reviewer["id"],
                    evidence_refs=[review_ref],
                    revision="deadbee",
                )

        self.assertEqual(
            (await self.feature_manager.get(str(run["id"])))["stage"],
            "review",
        )

    async def test_gate_snapshot_change_is_rejected_before_commit(self) -> None:
        run, doc = await self._advance_to_quality()
        quality_ref = self._write_evidence(run, "quality-report.md")
        await self.feature_manager.transition(
            str(run["id"]),
            to_stage="review",
            result="passed",
            evidence_refs=[quality_ref],
        )
        self._set_section_fields(
            doc,
            "Review Provenance",
            {
                "Reviewer": str(self.reviewer["id"]),
                "Base SHA": self.git_head,
                "Reviewed HEAD": self.git_head,
                "Verdict": "approved",
            },
        )
        review_ref = self._write_evidence(run, "review.md")
        original_read = Path.read_text
        mutated = False

        def racing_read(path: Path, *args, **kwargs) -> str:
            nonlocal mutated
            text = original_read(path, *args, **kwargs)
            if path.resolve() == doc.resolve() and not mutated:
                mutated = True
                doc.write_text(
                    text.replace(
                        "- **Verdict**: approved",
                        "- **Verdict**: pending",
                        1,
                    ),
                    encoding="utf-8",
                )
            return text

        with mock.patch.object(Path, "read_text", new=racing_read):
            with self.assertRaisesRegex(FeatureError, "changed before"):
                await self.feature_manager.transition(
                    str(run["id"]),
                    to_stage="merge",
                    result="approved",
                    actor_agent_id=self.reviewer["id"],
                    evidence_refs=[review_ref],
                    revision=self.git_head,
                )

        self.assertEqual(
            (await self.feature_manager.get(str(run["id"])))["stage"],
            "review",
        )
        self.assertIn(
            "- **Verdict**: pending", doc.read_text(encoding="utf-8")
        )

    async def test_session_bound_transition_derives_actor(self) -> None:
        run, doc = await self._advance_to_quality()
        quality_ref = self._write_evidence(run, "quality-report.md")
        await self.feature_manager.transition(
            str(run["id"]),
            to_stage="review",
            result="passed",
            evidence_refs=[quality_ref],
        )
        revision = self.git_head
        self._set_section_fields(
            doc,
            "Review Provenance",
            {
                "Reviewer": str(self.reviewer["id"]),
                "Base SHA": self.git_head,
                "Reviewed HEAD": revision,
                "Verdict": "approved",
            },
        )
        review_ref = self._write_evidence(run, "review.md")
        owner_session = await self.session_manager.create_session(
            agent_id=str(self.owner["id"]), working_dir=str(self.workspace)
        )
        reviewer_session = await self.session_manager.create_session(
            agent_id=str(self.reviewer["id"]), working_dir=str(self.workspace)
        )
        now = datetime.now(timezone.utc).isoformat()
        await self.db.upsert_group_agent_session(
            self.group["id"], str(self.owner["id"]), owner_session.id, now
        )
        await self.db.upsert_group_agent_session(
            self.group["id"], str(self.reviewer["id"]), reviewer_session.id, now
        )

        with self.assertRaisesRegex(FeatureError, "assigned reviewer"):
            await self.feature_manager.transition_for_session(
                str(run["id"]),
                owner_session.id,
                to_stage="merge",
                result="approved",
                evidence_refs=[review_ref],
                revision=revision,
            )
        merged = await self.feature_manager.transition_for_session(
            str(run["id"]),
            reviewer_session.id,
            to_stage="merge",
            result="approved",
            evidence_refs=[review_ref],
            revision=revision,
        )
        self.assertEqual(merged["stage"], "merge")

    async def test_session_capability_binds_transition_identity(self) -> None:
        owner_session = await self.session_manager.create_session(
            agent_id=str(self.owner["id"]), working_dir=str(self.workspace)
        )
        reviewer_session = await self.session_manager.create_session(
            agent_id=str(self.reviewer["id"]), working_dir=str(self.workspace)
        )
        self.assertNotEqual(
            owner_session._capability_token,
            reviewer_session._capability_token,
        )
        self.assertTrue(
            self.session_manager.verify_session_capability(
                reviewer_session.id, reviewer_session._capability_token
            )
        )
        self.assertFalse(
            self.session_manager.verify_session_capability(
                reviewer_session.id, owner_session._capability_token
            )
        )
        callback_env = build_callback_env(
            reviewer_session.id, reviewer_session._capability_token
        )
        self.assertEqual(
            callback_env["OCTOPUS_SESSION_CAPABILITY"],
            reviewer_session._capability_token,
        )

        with mock.patch.object(
            feature_routes, "session_manager", self.session_manager
        ):
            with self.assertRaises(HTTPException) as caught:
                feature_routes._require_session_capability(
                    reviewer_session.id, owner_session._capability_token
                )
            self.assertEqual(caught.exception.status_code, 403)
            feature_routes._require_session_capability(
                reviewer_session.id, reviewer_session._capability_token
            )

        for backend in ("claude-code", "codex"):
            run = get_harness(backend).create_run(
                RunConfig(
                    session_id=reviewer_session.id,
                    session_capability=reviewer_session._capability_token,
                    mcp_servers=["ask"],
                )
            )
            argv, kwargs = run.build_argv(
                "verify callback isolation", str(self.workspace)
            )
            self.assertNotIn(
                reviewer_session._capability_token, "\0".join(argv)
            )
            self.assertEqual(
                kwargs["env"]["OCTOPUS_SESSION_CAPABILITY"],
                reviewer_session._capability_token,
            )


class FeatureDatabaseMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_doc_outbox_gains_base_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "legacy.db"
            feature_doc = Path(directory) / "feature.md"
            feature_doc.write_text("old disk\n", encoding="utf-8")
            legacy = sqlite3.connect(db_path)
            legacy.execute(
                "CREATE TABLE feature_doc_syncs ("
                "feature_run_id TEXT PRIMARY KEY, "
                "feature_doc_path TEXT NOT NULL, "
                "content TEXT NOT NULL, "
                "updated_at TEXT NOT NULL)"
            )
            legacy.execute(
                "INSERT INTO feature_doc_syncs "
                "(feature_run_id, feature_doc_path, content, updated_at) "
                "VALUES (?, ?, ?, ?)",
                ("legacy-run", str(feature_doc), "desired disk\n", "v1"),
            )
            legacy.commit()
            legacy.close()

            database = Database(str(db_path))
            await database.initialize()
            try:
                self.assertTrue(
                    await database._has_column(
                        "feature_doc_syncs", "base_hash"
                    )
                )
                pending = await database.get_feature_doc_sync("legacy-run")
                self.assertIsNotNone(pending)
                self.assertTrue(pending["base_hash"])
                manager = FeatureManager()
                manager.bind(database)
                self.assertTrue(await manager._flush_doc_sync("legacy-run"))
                self.assertEqual(
                    feature_doc.read_text(encoding="utf-8"), "desired disk\n"
                )
                self.assertIsNone(
                    await database.get_feature_doc_sync("legacy-run")
                )
            finally:
                await database.close()


if __name__ == "__main__":
    unittest.main()
