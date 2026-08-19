from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from server.database import Database
from server.group_session_chain import ContextSealPolicy


class ContextSealPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ContextSealPolicy(
            enabled=True,
            warn_ratio=0.85,
            action_ratio=0.90,
            reserve_tokens=8_000,
        )

    def test_warns_before_action_and_projects_the_next_turn(self) -> None:
        warning = self.policy.evaluate(
            {"total_tokens": 170_000, "context_window": 200_000}
        )
        projected = self.policy.evaluate(
            {"total_tokens": 168_000, "context_window": 200_000},
            projected_prompt_tokens=5_000,
        )

        self.assertEqual(warning.action, "warning")
        self.assertEqual(projected.action, "seal")
        self.assertEqual(projected.reason, "projected_context_limit")

    def test_missing_health_and_disabled_policy_fail_open(self) -> None:
        self.assertEqual(self.policy.evaluate(None).action, "unknown")
        disabled = ContextSealPolicy(
            enabled=False,
            warn_ratio=0.85,
            action_ratio=0.90,
            reserve_tokens=8_000,
        )
        self.assertEqual(
            disabled.evaluate(
                {"total_tokens": 199_000, "context_window": 200_000}
            ).action,
            "disabled",
        )


class GroupSessionGenerationDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = Database(str(self.root / "test.db"))
        await self.db.initialize()
        now = "2026-08-19T00:00:00+00:00"
        await self.db.save_agent(
            agent_id="agent-1",
            name="Builder",
            created_at=now,
            updated_at=now,
        )
        await self.db.save_session(
            "group-root", "Group", str(self.root), now,
            agent_id="agent-1", origin="group",
        )
        await self.db.create_group(
            group_id="group-1",
            name="Team",
            agent_ids=["agent-1"],
            created_at=now,
            session_id="group-root",
            default_agent_id="agent-1",
            working_dir=str(self.root),
        )
        await self.db.save_session(
            "session-1", "Builder in Team", str(self.root), now,
            agent_id="agent-1", origin="group_member", backend="codex",
        )
        await self.db.upsert_group_agent_session(
            "group-1", "agent-1", "session-1", now
        )

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.temp.cleanup()

    async def test_adopt_is_idempotent_and_seal_claim_is_compare_and_swap(self) -> None:
        first, second = await asyncio.gather(
            self.db.adopt_group_session_generation(
                "group-1", "agent-1", "session-1",
                "2026-08-19T00:00:00+00:00",
            ),
            self.db.adopt_group_session_generation(
                "group-1", "agent-1", "session-1",
                "2026-08-19T00:00:00+00:00",
            ),
        )
        self.assertEqual(first["generation"], 1)
        self.assertEqual(second["session_id"], "session-1")

        claims = await asyncio.gather(
            self.db.begin_group_session_seal(
                "group-1", "agent-1", "session-1",
                reason="context_limit",
                context_usage={"total_tokens": 180_000},
                started_at="2026-08-19T00:01:00+00:00",
            ),
            self.db.begin_group_session_seal(
                "group-1", "agent-1", "session-1",
                reason="context_limit",
                context_usage={"total_tokens": 180_000},
                started_at="2026-08-19T00:01:00+00:00",
            ),
        )
        self.assertEqual(sorted(claims), [False, True])
        chain = await self.db.list_group_session_chain("group-1", "agent-1")
        self.assertEqual([row["status"] for row in chain], ["sealing"])

    async def test_rotation_preserves_cursor_and_has_one_active_generation(self) -> None:
        await self.db.adopt_group_session_generation(
            "group-1", "agent-1", "session-1",
            "2026-08-19T00:00:00+00:00",
        )
        await self.db.update_group_agent_cursor("group-1", "agent-1", 42)
        claimed = await self.db.begin_group_session_seal(
            "group-1", "agent-1", "session-1",
            reason="context_limit",
            context_usage={"remaining_ratio": 0.1},
            started_at="2026-08-19T00:01:00+00:00",
        )
        self.assertTrue(claimed)
        await self.db.save_session(
            "session-2", "Builder in Team", str(self.root),
            "2026-08-19T00:02:00+00:00",
            agent_id="agent-1", origin="group_member", backend="codex",
        )

        rotated = await self.db.complete_group_session_rotation(
            group_id="group-1",
            agent_id="agent-1",
            predecessor_session_id="session-1",
            successor_session_id="session-2",
            digest="Implemented the API; review remains.",
            digest_provenance="fresh_model",
            completed_at="2026-08-19T00:02:00+00:00",
        )

        self.assertTrue(rotated)
        self.assertEqual(
            await self.db.get_group_agent_session("group-1", "agent-1"),
            "session-2",
        )
        self.assertEqual(
            await self.db.get_group_agent_cursor("group-1", "agent-1"), 42
        )
        chain = await self.db.list_group_session_chain("group-1", "agent-1")
        self.assertEqual(
            [(row["generation"], row["status"]) for row in chain],
            [(1, "sealed"), (2, "active")],
        )
        self.assertEqual(chain[1]["predecessor_session_id"], "session-1")


if __name__ == "__main__":
    unittest.main()
