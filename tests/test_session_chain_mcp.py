from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import HTTPException

from server.database import Database
from server.group_session_chain import SessionChainAccessError, SessionChainReader
from server.harness.assembly import build_callback_env, select_mcp_servers
from server.routers import session_chains as router_module


class SessionChainRecallTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = Database(str(self.root / "test.db"))
        await self.db.initialize()
        now = "2026-08-19T00:00:00+00:00"
        await self.db.save_agent(
            agent_id="agent-1", name="Builder", created_at=now, updated_at=now
        )
        await self.db.save_session(
            "group-root", "Group", str(self.root), now,
            agent_id="agent-1", origin="group",
        )
        await self.db.create_group(
            group_id="group-1", name="Team", agent_ids=["agent-1"],
            created_at=now, session_id="group-root",
            default_agent_id="agent-1", working_dir=str(self.root),
        )
        await self.db.save_session(
            "session-1", "Builder 1", str(self.root), now,
            agent_id="agent-1", origin="group_member", backend="codex",
        )
        await self.db.upsert_group_agent_session(
            "group-1", "agent-1", "session-1", now
        )
        await self.db.adopt_group_session_generation(
            "group-1", "agent-1", "session-1", now
        )
        await self.db.append_message(
            "session-1", 0, "user", "text", "Use SQLite as durable truth"
        )
        await self.db.append_message(
            "session-1", 1, "assistant", "text",
            "Implemented the rotation transaction; reviewer should inspect CAS.",
        )
        await self.db.flush()
        await self.db.begin_group_session_seal(
            "group-1", "agent-1", "session-1",
            reason="context_limit", context_usage={"remaining_ratio": 0.1},
            started_at="2026-08-19T00:01:00+00:00",
        )
        await self.db.save_session(
            "session-2", "Builder 2", str(self.root),
            "2026-08-19T00:02:00+00:00", agent_id="agent-1",
            origin="group_member", backend="codex",
        )
        await self.db.complete_group_session_rotation(
            group_id="group-1", agent_id="agent-1",
            predecessor_session_id="session-1", successor_session_id="session-2",
            digest="SQLite chosen; CAS review remains.",
            digest_provenance="fresh_model",
            completed_at="2026-08-19T00:02:00+00:00",
        )
        self.reader = SessionChainReader(self.db)

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.temp.cleanup()

    async def test_successor_can_page_search_and_read_exact_sealed_evidence(self) -> None:
        listing = await self.reader.list_chain("session-2")
        page = await self.reader.read_events(
            "session-2", "session-1", view="chat", offset=1, limit=1
        )
        hit = await self.reader.search("session-2", "sqlite", limit=5)
        invocation = await self.reader.read_invocation(
            "session-2", "session-1", seq=1
        )

        self.assertEqual(listing["chain_length"], 2)
        self.assertEqual(listing["active_session_id"], "session-2")
        self.assertEqual(page["events"][0]["seq"], 1)
        self.assertIsNone(page["next_offset"])
        self.assertEqual(hit["matches"][0]["session_id"], "session-1")
        self.assertIn("rotation transaction", invocation["content"])

    async def test_current_cross_chain_and_unknown_targets_fail_closed(self) -> None:
        with self.assertRaises(SessionChainAccessError):
            await self.reader.read_events(
                "session-2", "session-2", view="raw", offset=0, limit=10
            )
        with self.assertRaises(SessionChainAccessError):
            await self.reader.read_events(
                "session-2", "other-session", view="raw", offset=0, limit=10
            )

    async def test_router_requires_live_session_capability(self) -> None:
        fake_manager = Mock()
        fake_manager.db = self.db
        fake_manager.verify_session_capability.side_effect = (
            lambda session_id, token: session_id == "session-2" and token == "cap"
        )
        with patch.object(router_module, "session_manager", fake_manager):
            with self.assertRaises(HTTPException) as caught:
                await router_module.list_session_chain(
                    "session-2", session_capability="wrong", _="bearer"
                )
            self.assertEqual(caught.exception.status_code, 403)
            payload = await router_module.list_session_chain(
                "session-2", session_capability="cap", _="bearer"
            )
        self.assertEqual(payload["chain_length"], 2)

    def test_session_chain_mcp_is_mandatory_and_receives_bound_identity(self) -> None:
        env = build_callback_env("session-2", "cap")
        entries = select_mcp_servers([], [], env)
        keys = [entry.key for entry in entries]

        self.assertIn("session_chain", keys)
        self.assertEqual(env["OCTOPUS_SESSION_ID"], "session-2")
        self.assertEqual(env["OCTOPUS_SESSION_CAPABILITY"], "cap")


if __name__ == "__main__":
    unittest.main()
