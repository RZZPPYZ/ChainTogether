from __future__ import annotations

import shutil
import tempfile
import unittest
import re
from pathlib import Path
from unittest import mock

from server.agent_manager import AgentManager
from server.config import settings
from server.database import Database
from server.feature_delivery import FeatureDeliveryManager
from server.feature_manager import FeatureManager
from server.group_manager import AgentTurnResult, GroupManager
from server.session_manager import FeatureTurnAuthority, SessionManager


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FeatureDispatchRuntimeTests(unittest.IsolatedAsyncioTestCase):
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
        self.sessions = SessionManager()
        await self.sessions.initialize(self.db)
        agent_manager = AgentManager(self.db)
        self.agents = [
            await agent_manager.create_agent(name=name)
            for name in ("Owner", "Reviewer", "Guardian")
        ]
        self.features = FeatureManager()
        self.features.bind(self.db)
        self.groups = GroupManager()
        self.groups.bind(self.sessions, self.db, self.features)
        self.group = await self.groups.create_group(
            "Feature Team",
            [agent["id"] for agent in self.agents],
            default_agent_id=self.agents[0]["id"],
            working_dir=str(self.workspace),
        )
        self.delivery = FeatureDeliveryManager()
        self.delivery.bind(self.db, self.features)

    async def asyncTearDown(self) -> None:
        self.groups.shutdown()
        await self.db.close()
        settings.agents_dir = self.old_agents_dir
        settings.group_prompt_state_dir = self.old_group_prompt_state_dir
        self.temp.cleanup()

    async def test_start_drives_pending_dispatch_when_group_runtime_is_bound(
        self,
    ) -> None:
        launcher = mock.AsyncMock(return_value={"id": "invocation-one"})
        runtime = mock.Mock(launch_feature_dispatch=launcher)
        self.delivery.bind_group_manager(runtime)

        started = await self.delivery.start(
            self.group["id"],
            request_key="feature-command-message-42",
            requirement="Build the autonomous feature command",
        )

        launcher.assert_awaited_once()
        call = launcher.await_args.kwargs
        self.assertEqual(started["run"]["id"], call["feature_run_id"])
        self.assertEqual(started["roles"]["owner"]["id"], call["target_agent_id"])
        self.assertTrue(call["dispatch_capability"])
        self.assertTrue(call["lease_token"])
        persisted = await self.db.get_feature_dispatch(call["dispatch_id"])
        assert persisted is not None
        self.assertNotIn(call["dispatch_capability"], repr(persisted))
        self.assertNotIn(call["lease_token"], repr(persisted))

    async def test_exact_target_turn_gets_ephemeral_authority_and_promotes_handoff(
        self,
    ) -> None:
        started = await self.delivery.start(
            self.group["id"],
            request_key="feature-runtime",
            requirement="Run the exact assigned feature generation",
        )
        leased = await self.delivery.lease_next_dispatch(
            started["run"]["id"], worker_id="test-worker"
        )
        assert leased is not None
        self.groups.bind(
            self.sessions,
            self.db,
            self.features,
            feature_delivery_mgr=self.delivery,
        )
        self.delivery.bind_group_manager(self.groups)
        captured: dict[str, object] = {}

        async def collect(
            reuse_session_id: str,
            prompt: str,
            **kwargs: object,
        ) -> AgentTurnResult:
            captured.update(kwargs)
            await self.features.transition_for_dispatch(
                started["run"]["id"],
                reuse_session_id,
                dispatch_id=str(kwargs["feature_dispatch_id"]),
                dispatch_capability=str(kwargs["feature_dispatch_capability"]),
                to_stage="design",
            )
            return AgentTurnResult("Lifecycle handoff committed.")

        with mock.patch.object(
            self.groups, "_collect_agent_reply", side_effect=collect
        ), mock.patch.object(
            self.delivery, "drive_pending", new=mock.AsyncMock(return_value=None)
        ):
            invocation = await self.groups.launch_feature_dispatch(
                group_id=self.group["id"],
                feature_run_id=started["run"]["id"],
                dispatch_id=leased["dispatch"]["id"],
                target_agent_id=leased["dispatch"]["target_agent_id"],
                target_role=leased["dispatch"]["target_role"],
                observed_stage=leased["dispatch"]["observed_stage"],
                requirement="Run the exact assigned feature generation",
                lease_token=leased["lease_token"],
                dispatch_capability=leased["dispatch_capability"],
            )
            self.assertEqual(0, invocation["depth"])
            run = self.groups._invocations[invocation["id"]]
            assert run.runner_task is not None
            await run.runner_task

        self.assertEqual(
            leased["dispatch"]["id"], captured["feature_dispatch_id"]
        )
        self.assertEqual(
            leased["dispatch_capability"],
            captured["feature_dispatch_capability"],
        )
        dispatches = await self.db.list_feature_dispatches(started["run"]["id"])
        self.assertEqual(
            ["completed", "pending"], [item["state"] for item in dispatches]
        )
        messages = await self.db.load_messages(self.group["session_id"])
        self.assertEqual(
            1,
            sum(
                str(message.get("content") or "").startswith(
                    f"[feature-request:{started['run']['id']}]"
                )
                for message in messages
            ),
        )
        self.assertNotIn(leased["dispatch_capability"], repr(messages))
        self.assertNotIn(leased["lease_token"], repr(messages))

    async def test_run_config_scopes_feature_authority_to_one_turn(self) -> None:
        member = await self.sessions.create_session(
            agent_id=self.agents[0]["id"],
            name="Owner member",
            working_dir=str(self.workspace),
            origin="group_member",
        )
        authority = FeatureTurnAuthority(
            feature_run_id="run-one",
            dispatch_id="dispatch-one",
            dispatch_capability="raw-one-turn-secret",
        )

        config = self.sessions._run_config(
            member,
            feature_turn_authority=authority,
        )
        ordinary = self.sessions._run_config(member)

        self.assertEqual("run-one", config.feature_run_id)
        self.assertEqual("dispatch-one", config.feature_dispatch_id)
        self.assertEqual(
            "raw-one-turn-secret", config.feature_dispatch_capability
        )
        self.assertIsNone(ordinary.feature_run_id)
        self.assertIsNone(ordinary.feature_dispatch_id)
        self.assertIsNone(ordinary.feature_dispatch_capability)
        session_rows = await self.db.load_sessions()
        self.assertNotIn("raw-one-turn-secret", repr(session_rows))

    async def test_startup_reclaims_lease_and_launches_same_generation(self) -> None:
        started = await self.delivery.start(
            self.group["id"],
            request_key="feature-restart-lease",
            requirement="Recover dispatch after a server restart",
        )
        leased = await self.delivery.lease_next_dispatch(
            started["run"]["id"], worker_id="dead-worker"
        )
        assert leased is not None
        launcher = mock.AsyncMock(return_value={"id": "recovered-invocation"})
        runtime = mock.Mock(launch_feature_dispatch=launcher)
        recovered = FeatureDeliveryManager()
        recovered.bind(self.db, self.features)
        recovered.bind_group_manager(runtime)

        await recovered.reconcile_startup()

        launcher.assert_awaited_once()
        call = launcher.await_args.kwargs
        self.assertEqual(leased["dispatch"]["id"], call["dispatch_id"])
        persisted = await self.db.get_feature_dispatch(call["dispatch_id"])
        assert persisted is not None
        self.assertEqual("leased", persisted["state"])
        self.assertEqual(2, persisted["attempt_count"])

    async def test_multi_round_review_journey_uses_fresh_role_bound_generations(
        self,
    ) -> None:
        started = await self.delivery.start(
            self.group["id"],
            request_key="feature-full-journey",
            requirement="Deliver through independent review and vision acceptance",
        )
        run_id = started["run"]["id"]
        doc = self.workspace / started["run"]["feature_doc_path"]
        sha = "a" * 40
        sessions: dict[str, str] = {}
        invocation_index = 0
        observed: list[tuple[str, str, str, int]] = []

        def evidence(name: str) -> str:
            evidence_dir = doc.parent / "evidence"
            evidence_dir.mkdir(exist_ok=True)
            (evidence_dir / name).write_text("verified", encoding="utf-8")
            return f"evidence/{name}"

        def section_fields(heading: str, values: dict[str, str]) -> None:
            text = doc.read_text(encoding="utf-8")
            start = text.index(f"## {heading}")
            end = text.find("\n## ", start + 3)
            if end < 0:
                end = len(text)
            section = text[start:end]
            for label, value in values.items():
                pattern = re.compile(rf"(?m)^- \*\*{re.escape(label)}\*\*:.*$")
                section = pattern.sub(
                    f"- **{label}**: {value}", section, count=1
                )
            doc.write_text(text[:start] + section + text[end:], encoding="utf-8")

        async def activate(leased: dict[str, object]) -> tuple[str, str]:
            nonlocal invocation_index
            dispatch = leased["dispatch"]
            assert isinstance(dispatch, dict)
            invocation_index += 1
            invocation_id = f"journey-{invocation_index}"
            invocation = await self.db.create_group_invocation(
                invocation_id,
                self.group["id"],
                f"[feature-dispatch:{dispatch['id']}]",
                f"2026-08-02T00:00:{invocation_index:02d}+00:00",
                feature_run_id=run_id,
            )
            self.assertEqual(0, invocation["depth"])
            await self.delivery.activate_dispatch(
                str(dispatch["id"]),
                lease_token=str(leased["lease_token"]),
                invocation_id=invocation_id,
            )
            agent_id = str(dispatch["target_agent_id"])
            if agent_id not in sessions:
                member = await self.sessions.create_session(
                    agent_id=agent_id,
                    name=f"Feature actor {agent_id}",
                    working_dir=str(self.workspace),
                    origin="group_member",
                )
                sessions[agent_id] = member.id
                await self.db.upsert_group_agent_session(
                    self.group["id"],
                    agent_id,
                    member.id,
                    "2026-08-02T00:00:00+00:00",
                )
            observed.append(
                (
                    str(dispatch["observed_stage"]),
                    str(dispatch["purpose"]),
                    str(dispatch["target_role"]),
                    invocation["depth"],
                )
            )
            return invocation_id, sessions[agent_id]

        async def next_lease() -> dict[str, object]:
            leased = await self.delivery.lease_next_dispatch(
                run_id, worker_id=f"journey-worker-{invocation_index}"
            )
            assert leased is not None
            return leased

        async def transition(
            leased: dict[str, object],
            to_stage: str,
            *,
            result: str = "",
            refs: list[str] | None = None,
            revision: str = "",
        ) -> dict[str, object] | None:
            dispatch = leased["dispatch"]
            assert isinstance(dispatch, dict)
            invocation_id, session_id = await activate(leased)
            await self.features.transition_for_dispatch(
                run_id,
                session_id,
                dispatch_id=str(dispatch["id"]),
                dispatch_capability=str(leased["dispatch_capability"]),
                to_stage=to_stage,
                result=result,
                evidence_refs=refs,
                revision=revision,
            )
            await self.delivery.complete_dispatch_invocation(
                str(dispatch["id"]), invocation_id, terminal_status="completed"
            )
            current = await self.db.get_feature_run(run_id)
            assert current is not None
            return None if current["state"] == "done" else await next_lease()

        leased = await next_lease()
        leased = await transition(leased, "design")
        text = doc.read_text(encoding="utf-8")
        doc.write_text(
            text.replace("**Verdict**: pending", "**Verdict**: approved", 1),
            encoding="utf-8",
        )
        assert leased is not None
        leased = await transition(leased, "planning", result="approved")
        assert leased is not None
        leased = await transition(leased, "implementation")
        assert leased is not None
        leased = await transition(leased, "quality")
        quality_one = evidence("quality-one.md")
        assert leased is not None
        leased = await transition(
            leased, "review", result="passed", refs=[quality_one]
        )
        assert leased is not None
        self.assertEqual("owner", leased["dispatch"]["target_role"])

        packet_one = evidence("review-packet-one.md")
        dispatch = leased["dispatch"]
        invocation_id, session_id = await activate(leased)
        with mock.patch.object(
            self.features, "_git_commit", return_value=sha
        ), mock.patch.object(self.features, "_git_head", return_value=sha):
            await self.features.request_review_for_dispatch(
                run_id,
                session_id,
                dispatch_id=str(dispatch["id"]),
                dispatch_capability=str(leased["dispatch_capability"]),
                reason="Request independent review",
                evidence_refs=[packet_one],
                revision=sha,
            )
        await self.delivery.complete_dispatch_invocation(
            str(dispatch["id"]), invocation_id, terminal_status="completed"
        )
        leased = await next_lease()
        self.assertEqual("reviewer", leased["dispatch"]["target_role"])

        review_findings = evidence("review-findings.md")
        leased = await transition(
            leased,
            "implementation",
            result="request_changes",
            refs=[review_findings],
        )
        assert leased is not None
        self.assertEqual("owner", leased["dispatch"]["target_role"])
        leased = await transition(leased, "quality")
        quality_two = evidence("quality-two.md")
        assert leased is not None
        leased = await transition(
            leased, "review", result="passed", refs=[quality_two]
        )
        assert leased is not None
        packet_two = evidence("review-packet-two.md")
        dispatch = leased["dispatch"]
        invocation_id, session_id = await activate(leased)
        with mock.patch.object(
            self.features, "_git_commit", return_value=sha
        ), mock.patch.object(self.features, "_git_head", return_value=sha):
            await self.features.request_review_for_dispatch(
                run_id,
                session_id,
                dispatch_id=str(dispatch["id"]),
                dispatch_capability=str(leased["dispatch_capability"]),
                reason="Request re-review",
                evidence_refs=[packet_two],
                revision=sha,
            )
        await self.delivery.complete_dispatch_invocation(
            str(dispatch["id"]), invocation_id, terminal_status="completed"
        )
        leased = await next_lease()

        section_fields(
            "Review Provenance",
            {
                "Reviewer": started["roles"]["reviewer"]["id"],
                "Base SHA": sha,
                "Reviewed HEAD": sha,
                "Verdict": "approved",
            },
        )
        review_approval = evidence("review-approval.md")
        with mock.patch.object(
            self.features, "_git_commit", return_value=sha
        ), mock.patch.object(
            self.features, "_git_head", return_value=sha
        ), mock.patch.object(
            self.features, "_git_is_ancestor", return_value=True
        ):
            leased = await transition(
                leased,
                "merge",
                result="approved",
                refs=[review_approval],
                revision=sha,
            )
        merge_ref = evidence("merge.md")
        assert leased is not None
        with mock.patch.object(
            self.features, "_git_commit", return_value=sha
        ), mock.patch.object(self.features, "_git_head", return_value=sha):
            leased = await transition(
                leased,
                "acceptance",
                result="merged",
                refs=[merge_ref],
                revision=sha,
            )
        vision_ref = evidence("vision.md")
        section_fields(
            "Vision Gate",
            {
                "Guardian": started["roles"]["vision_guardian"]["id"],
                "Merged revision": sha,
                "Verdict": "accepted",
                "Journey evidence": vision_ref,
            },
        )
        text = doc.read_text(encoding="utf-8")
        doc.write_text(text.replace("- [ ] AC-", "- [x] AC-"), encoding="utf-8")
        assert leased is not None
        with mock.patch.object(
            self.features, "_git_commit", return_value=sha
        ), mock.patch.object(self.features, "_git_head", return_value=sha):
            leased = await transition(
                leased,
                "closure",
                result="accepted",
                refs=[vision_ref],
                revision=sha,
            )
        closure_ref = evidence("closure.md")
        assert leased is not None
        with mock.patch.object(
            self.features, "_git_commit", return_value=sha
        ), mock.patch.object(self.features, "_git_head", return_value=sha):
            leased = await transition(
                leased,
                "done",
                result="closed",
                refs=[closure_ref],
                revision=sha,
            )

        self.assertIsNone(leased)
        done = await self.db.get_feature_run(run_id)
        assert done is not None
        self.assertEqual("done", done["state"])
        self.assertIsNone(await self.db.get_group_active_feature_id(self.group["id"]))
        checkpoint = await self.db.get_feature_start_for_run(run_id)
        assert checkpoint is not None
        self.assertEqual("done", checkpoint["state"])
        self.assertTrue(all(depth == 0 for *_, depth in observed))
        self.assertGreaterEqual(
            sum(1 for stage, purpose, role, _ in observed if stage == "review" and purpose == "review_request" and role == "reviewer"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
