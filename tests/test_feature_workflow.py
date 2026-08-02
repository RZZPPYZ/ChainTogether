from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from server.agent_manager import AgentManager
from server.config import settings
from server.database import Database
from server.feature_manager import FeatureError, FeatureManager
from server.group_manager import AgentTurnResult, GroupManager
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
        await self.feature_manager.transition(
            str(run["id"]),
            to_stage="review",
            result="passed",
            evidence_refs=["evidence/quality-report.md"],
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
        self._set_section_verdict(doc, "Review Provenance", "approved")
        with self.assertRaisesRegex(FeatureError, "assigned reviewer"):
            await self.feature_manager.transition(
                str(run["id"]),
                to_stage="merge",
                result="approved",
                actor_agent_id=self.owner["id"],
                evidence_refs=["evidence/review.md"],
            )
        merged = await self.feature_manager.transition(
            str(run["id"]),
            to_stage="merge",
            result="approved",
            actor_agent_id=self.reviewer["id"],
            evidence_refs=["evidence/review.md"],
        )
        self.assertEqual(merged["stage"], "merge")
        self.assertEqual(
            merged["artifact_refs"],
            [
                str(run["feature_doc_path"]),
                "evidence/quality-report.md",
                "evidence/review.md",
            ],
        )
        await self.feature_manager.transition(
            str(run["id"]),
            to_stage="acceptance",
            result="merged",
            evidence_refs=["evidence/merge.md"],
        )
        self._set_section_verdict(doc, "Vision Gate", "accepted")
        text = doc.read_text(encoding="utf-8")
        doc.write_text(text.replace("- [ ] AC-1:", "- [x] AC-1:"), encoding="utf-8")
        await self.feature_manager.transition(
            str(run["id"]),
            to_stage="closure",
            result="accepted",
            actor_agent_id=self.guardian["id"],
            evidence_refs=["evidence/vision.md"],
        )
        done = await self.feature_manager.transition(
            str(run["id"]),
            to_stage="done",
            result="closed",
            actor_agent_id=self.owner["id"],
            evidence_refs=["evidence/closure.md"],
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


if __name__ == "__main__":
    unittest.main()
