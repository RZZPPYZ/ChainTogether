from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server.database import Database


class MessageContextUsagePersistenceTests(unittest.IsolatedAsyncioTestCase):
    """Result rows carry the per-turn usage snapshot so the "Done · N
    tokens" badge survives a session reload (the WS event is ephemeral)."""

    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.temp.name) / "test.db"))
        await self.db.initialize()
        now = "2026-11-09T00:00:00+00:00"
        await self.db.save_agent(
            agent_id="agent-1", name="Builder", created_at=now, updated_at=now
        )
        await self.db.save_session(
            "session-1", "Chat", str(Path(self.temp.name)), now,
            agent_id="agent-1",
        )

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.temp.cleanup()

    async def test_result_usage_round_trips(self) -> None:
        usage = {
            "backend": "claude-code",
            "input_tokens": 250,
            "cached_input_tokens": 24832,
            "output_tokens": 2,
            "turn_tokens": 25084,
            "source": "estimated",
        }
        await self.db.append_message(
            "session-1", 0, "system", "result",
            cost=0.0042, context_usage=usage,
        )
        await self.db.flush()

        rows = await self.db.load_messages("session-1")

        self.assertEqual(rows[0]["context_usage"], usage)
        self.assertAlmostEqual(rows[0]["cost"], 0.0042)

    async def test_rows_without_usage_load_none(self) -> None:
        await self.db.append_message(
            "session-1", 0, "user", "text", "hello",
        )
        await self.db.flush()

        rows = await self.db.load_messages("session-1")

        self.assertIsNone(rows[0]["context_usage"])


if __name__ == "__main__":
    unittest.main()
