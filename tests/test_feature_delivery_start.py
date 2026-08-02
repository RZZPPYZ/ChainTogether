from __future__ import annotations

import asyncio
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from server.agent_manager import AgentManager
from server.config import settings
from server.database import Database
from server.feature_delivery import FeatureDeliveryManager
from server.feature_manager import FeatureError, FeatureManager
from server.group_manager import GroupManager
from server.session_manager import SessionManager


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FeatureDeliveryStartTests(unittest.IsolatedAsyncioTestCase):
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
            for name in ("Alpha", "Beta", "Gamma", "Delta")
        ]
        self.features = FeatureManager()
        self.features.bind(self.db)
        self.groups = GroupManager()
        self.groups.bind(self.sessions, self.db, self.features)
        self.group = await self.groups.create_group(
            "Autonomous Feature Team",
            [agent["id"] for agent in self.agents],
            default_agent_id=self.agents[2]["id"],
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

    async def _count(self, table: str) -> int:
        cursor = await self.db._conn.execute(f"SELECT COUNT(*) FROM {table}")
        row = await cursor.fetchone()
        return int(row[0])

    async def test_ac2_insufficient_roster_has_zero_feature_side_effects(self) -> None:
        small_group = await self.groups.create_group(
            "Two agents",
            [self.agents[0]["id"], self.agents[1]["id"]],
            working_dir=str(self.workspace),
        )
        before_messages = await self._count("messages")
        with self.assertRaisesRegex(FeatureError, "at least three"):
            await self.delivery.start(
                small_group["id"],
                request_key="request-small",
                requirement="Build the command",
            )
        self.assertEqual(before_messages, await self._count("messages"))
        for table in (
            "feature_runs",
            "feature_run_events",
            "feature_start_requests",
            "feature_dispatches",
            "feature_doc_syncs",
            "group_active_features",
        ):
            self.assertEqual(0, await self._count(table), table)
        self.assertFalse((self.workspace / "docs" / "features").exists())

    async def test_ac3_ac4_start_assigns_roles_and_commits_one_checkpoint(self) -> None:
        result = await self.delivery.start(
            self.group["id"],
            request_key="request-one",
            requirement="Build autonomous group feature delivery",
        )
        live = sorted(
            (agent["id"] for agent in self.agents),
        )
        owner_id = self.agents[2]["id"]
        remaining = [agent_id for agent_id in live if agent_id != owner_id]
        self.assertEqual(owner_id, result["roles"]["owner"]["id"])
        self.assertEqual(remaining[0], result["roles"]["reviewer"]["id"])
        self.assertEqual(
            remaining[1], result["roles"]["vision_guardian"]["id"]
        )
        self.assertEqual(3, len({role["id"] for role in result["roles"].values()}))
        self.assertFalse(result["replayed"])
        self.assertEqual("dispatch_pending", result["checkpoint_state"])

        run = await self.db.get_feature_run(result["run"]["id"])
        assert run is not None
        self.assertEqual(owner_id, run["owner_agent_id"])
        self.assertEqual(remaining[0], run["reviewer_agent_id"])
        self.assertEqual(remaining[1], run["vision_guardian_agent_id"])
        self.assertEqual(result["run"]["id"], await self.db.get_group_active_feature_id(self.group["id"]))
        events = await self.db.list_feature_run_events(result["run"]["id"])
        self.assertEqual(["created"], [event["result"] for event in events])
        dispatches = await self.db.list_feature_dispatches(result["run"]["id"])
        self.assertEqual(1, len(dispatches))
        self.assertEqual("pending", dispatches[0]["state"])
        self.assertEqual(owner_id, dispatches[0]["target_agent_id"])

        document = self.workspace / str(run["feature_doc_path"])
        text = document.read_text(encoding="utf-8")
        self.assertIn(f'owner: "{owner_id}"', text)
        self.assertIn(f'reviewer: "{remaining[0]}"', text)
        self.assertIn(f'vision_guardian: "{remaining[1]}"', text)
        self.assertIsNone(await self.db.get_feature_doc_sync(run["id"]))

        start = await self.db.get_feature_start_request("request-one")
        assert start is not None
        self.assertEqual("dispatch_pending", start["state"])
        self.assertTrue(start["authorization"]["commit"])
        self.assertTrue(start["authorization"]["merge_after_green_gates"])
        self.assertFalse(start["authorization"]["force_push"])
        self.assertFalse(start["authorization"]["deploy"])

    async def test_ac9_same_key_is_idempotent_and_mismatch_fails_closed(self) -> None:
        first, second = await asyncio.gather(
            self.delivery.start(
                self.group["id"],
                request_key="request-retry",
                requirement="Implement one durable run",
            ),
            self.delivery.start(
                self.group["id"],
                request_key="request-retry",
                requirement="Implement one durable run",
            ),
        )
        self.assertEqual(first["run"]["id"], second["run"]["id"])
        self.assertEqual(1, sum(not item["replayed"] for item in (first, second)))
        self.assertEqual(1, await self._count("feature_runs"))
        self.assertEqual(1, await self._count("feature_start_requests"))
        self.assertEqual(1, await self._count("feature_dispatches"))

        with self.assertRaisesRegex(FeatureError, "request key"):
            await self.delivery.start(
                self.group["id"],
                request_key="request-retry",
                requirement="A different requirement",
            )
        self.assertEqual(1, await self._count("feature_runs"))

    async def test_ac9_concurrent_distinct_keys_have_one_active_winner(self) -> None:
        outcomes = await asyncio.gather(
            self.delivery.start(
                self.group["id"],
                request_key="request-a",
                requirement="First competing feature",
            ),
            self.delivery.start(
                self.group["id"],
                request_key="request-b",
                requirement="Second competing feature",
            ),
            return_exceptions=True,
        )
        successes = [item for item in outcomes if isinstance(item, dict)]
        failures = [item for item in outcomes if isinstance(item, Exception)]
        self.assertEqual(1, len(successes))
        self.assertEqual(1, len(failures))
        self.assertIn("active FeatureRun", str(failures[0]))
        self.assertEqual(1, await self._count("feature_runs"))
        self.assertEqual(1, await self._count("feature_start_requests"))
        self.assertEqual(1, await self._count("feature_dispatches"))

    async def test_ac4_create_only_doc_failure_resumes_same_checkpoint(self) -> None:
        with mock.patch.object(
            self.features,
            "_write_doc_create_only",
            side_effect=OSError("simulated document failure"),
        ):
            first = await self.delivery.start(
                self.group["id"],
                request_key="request-doc-recovery",
                requirement="Recover the exact document checkpoint",
            )
        self.assertEqual("doc_pending", first["checkpoint_state"])
        self.assertFalse(
            (self.workspace / str(first["run"]["feature_doc_path"])).exists()
        )

        second = await self.delivery.start(
            self.group["id"],
            request_key="request-doc-recovery",
            requirement="Recover the exact document checkpoint",
        )
        self.assertTrue(second["replayed"])
        self.assertEqual(first["run"]["id"], second["run"]["id"])
        self.assertEqual("dispatch_pending", second["checkpoint_state"])
        self.assertTrue(
            (self.workspace / str(second["run"]["feature_doc_path"])).is_file()
        )
        self.assertEqual(1, await self._count("feature_runs"))
        self.assertEqual(1, await self._count("feature_dispatches"))

    async def test_ac10_lease_rotation_invalidates_old_raw_capability(self) -> None:
        started = await self.delivery.start(
            self.group["id"],
            request_key="request-lease",
            requirement="Lease one exact feature generation",
        )
        first = await self.delivery.lease_next_dispatch(
            started["run"]["id"], worker_id="worker-a", lease_seconds=0
        )
        assert first is not None
        second = await self.delivery.lease_next_dispatch(
            started["run"]["id"], worker_id="worker-b", lease_seconds=30
        )
        assert second is not None
        self.assertEqual(first["dispatch"]["id"], second["dispatch"]["id"])
        self.assertNotEqual(first["lease_token"], second["lease_token"])
        self.assertNotEqual(
            first["dispatch_capability"], second["dispatch_capability"]
        )
        persisted = await self.db.get_feature_dispatch(
            second["dispatch"]["id"]
        )
        assert persisted is not None
        self.assertEqual(
            hashlib.sha256(second["lease_token"].encode()).hexdigest(),
            persisted["lease_token_hash"],
        )
        self.assertEqual(
            hashlib.sha256(second["dispatch_capability"].encode()).hexdigest(),
            persisted["capability_hash"],
        )
        self.assertNotIn(second["lease_token"], repr(persisted))
        self.assertNotIn(second["dispatch_capability"], repr(persisted))

    async def test_ac10_activation_and_terminal_resume_bind_exact_generation(self) -> None:
        started = await self.delivery.start(
            self.group["id"],
            request_key="request-generation",
            requirement="Bind and recover one exact invocation generation",
        )
        leased = await self.delivery.lease_next_dispatch(
            started["run"]["id"], worker_id="worker", lease_seconds=30
        )
        assert leased is not None
        invocation = await self.db.create_group_invocation(
            "feature-invocation-1",
            self.group["id"],
            "feature delivery turn",
            "2026-08-02T00:00:00+00:00",
            feature_run_id=started["run"]["id"],
        )
        with self.assertRaisesRegex(FeatureError, "lease"):
            await self.delivery.activate_dispatch(
                leased["dispatch"]["id"],
                lease_token="wrong-token",
                invocation_id=invocation["id"],
            )
        active = await self.delivery.activate_dispatch(
            leased["dispatch"]["id"],
            lease_token=leased["lease_token"],
            invocation_id=invocation["id"],
        )
        self.assertEqual("active", active["state"])
        cursor = await self.db._conn.execute(
            "SELECT dispatch_id FROM feature_invocation_links "
            "WHERE invocation_id = ?",
            (invocation["id"],),
        )
        self.assertEqual((active["id"],), await cursor.fetchone())

        terminal = await self.delivery.complete_dispatch_invocation(
            active["id"], invocation["id"], terminal_status="failed"
        )
        self.assertEqual("failed", terminal["state"])
        resumed = await self.delivery.resume(started["run"]["id"])
        self.assertEqual("pending", resumed["dispatch"]["state"])
        self.assertEqual(2, resumed["dispatch"]["generation"])
        again = await self.delivery.resume(started["run"]["id"])
        self.assertEqual(resumed["dispatch"]["id"], again["dispatch"]["id"])
        self.assertEqual(2, await self._count("feature_dispatches"))

    async def test_ac6_ac7_transition_commits_waiting_successor_atomically(self) -> None:
        started = await self.delivery.start(
            self.group["id"],
            request_key="request-handoff",
            requirement="Commit an exact lifecycle handoff pair",
        )
        owner_id = started["roles"]["owner"]["id"]
        leased = await self.delivery.lease_next_dispatch(
            started["run"]["id"], worker_id="worker", lease_seconds=30
        )
        assert leased is not None
        invocation = await self.db.create_group_invocation(
            "feature-invocation-handoff",
            self.group["id"],
            "feature discovery turn",
            "2026-08-02T00:00:00+00:00",
            feature_run_id=started["run"]["id"],
        )
        await self.delivery.activate_dispatch(
            leased["dispatch"]["id"],
            lease_token=leased["lease_token"],
            invocation_id=invocation["id"],
        )
        member_session = await self.sessions.create_session(
            agent_id=owner_id,
            name="Feature owner turn",
            working_dir=str(self.workspace),
            origin="group_member",
        )
        await self.db.upsert_group_agent_session(
            self.group["id"],
            owner_id,
            member_session.id,
            "2026-08-02T00:00:00+00:00",
        )

        with self.assertRaisesRegex(FeatureError, "dispatch"):
            await self.features.transition_for_dispatch(
                started["run"]["id"],
                member_session.id,
                dispatch_id=leased["dispatch"]["id"],
                dispatch_capability="wrong-capability",
                to_stage="design",
            )
        unchanged = await self.db.get_feature_run(started["run"]["id"])
        assert unchanged is not None
        self.assertEqual("discovery", unchanged["stage"])

        transitioned = await self.features.transition_for_dispatch(
            started["run"]["id"],
            member_session.id,
            dispatch_id=leased["dispatch"]["id"],
            dispatch_capability=leased["dispatch_capability"],
            to_stage="design",
        )
        self.assertEqual("design", transitioned["stage"])
        dispatches = await self.db.list_feature_dispatches(started["run"]["id"])
        self.assertEqual(
            ["handoff_committed", "waiting"],
            [dispatch["state"] for dispatch in dispatches],
        )
        self.assertEqual(dispatches[0]["id"], dispatches[1]["predecessor_dispatch_id"])
        self.assertEqual(owner_id, dispatches[1]["target_agent_id"])
        with self.assertRaisesRegex(FeatureError, "dispatch"):
            await self.features.transition_for_dispatch(
                started["run"]["id"],
                member_session.id,
                dispatch_id=leased["dispatch"]["id"],
                dispatch_capability=leased["dispatch_capability"],
                to_stage="discovery",
                result="changes_required",
            )

        completed = await self.delivery.complete_dispatch_invocation(
            dispatches[0]["id"],
            invocation["id"],
            terminal_status="completed",
        )
        self.assertEqual("completed", completed["state"])
        promoted = await self.db.get_feature_dispatch(dispatches[1]["id"])
        assert promoted is not None
        self.assertEqual("pending", promoted["state"])
        await self.delivery.complete_dispatch_invocation(
            dispatches[0]["id"],
            invocation["id"],
            terminal_status="completed",
        )
        self.assertEqual(2, await self._count("feature_dispatches"))


if __name__ == "__main__":
    unittest.main()
