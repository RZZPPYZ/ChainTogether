from __future__ import annotations

import unittest
from typing import Any

from server.group_manager import GroupManager


class _FakeSessionManager:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = events
        self.broadcasts: list[dict[str, Any]] = []

    async def send_message(self, _session_id: str, _prompt: str):
        for event in self.events:
            yield event

    async def _broadcast(self, event: dict[str, Any]) -> None:
        self.broadcasts.append(event)


class GroupStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_collect_reply_broadcasts_normal_streaming_text(self) -> None:
        session_manager = _FakeSessionManager(
            [
                {"type": "thinking"},
                {
                    "type": "tool_use",
                    "tool": "Bash",
                    "input": {"command": "python -m unittest"},
                    "tool_use_id": "tool-1",
                },
                {
                    "type": "tool_result",
                    "tool_use_id": "tool-1",
                    "output": "OK",
                    "is_error": False,
                },
                {"type": "assistant_text", "content": "Finished the checks."},
                {
                    "type": "result",
                    "duration_ms": 1250,
                    "cost": 0.01,
                },
            ]
        )
        manager = GroupManager()
        manager.session_manager = session_manager  # type: ignore[assignment]

        turn = await manager._collect_agent_reply(
            "member-session",
            "Run checks",
            group_session_id="group-session",
            agent_name="Builder",
            invocation_id="invocation-1",
        )

        self.assertEqual(turn.text, "Finished the checks.")
        self.assertEqual(turn.tool_names, ("Bash",))
        self.assertEqual(
            session_manager.broadcasts,
            [
                {
                    "type": "group_agent_text",
                    "session_id": "group-session",
                    "invocation_id": "invocation-1",
                    "agent_name": "Builder",
                    "content": "Finished the checks.",
                }
            ],
        )

    async def test_backend_error_remains_visible_to_caller(self) -> None:
        session_manager = _FakeSessionManager(
            [{"type": "error", "message": "Backend unavailable"}]
        )
        manager = GroupManager()
        manager.session_manager = session_manager  # type: ignore[assignment]

        with self.assertRaisesRegex(Exception, "Backend unavailable"):
            await manager._collect_agent_reply(
                "member-session",
                "Run",
                group_session_id="group-session",
                agent_name="Builder",
                invocation_id="invocation-1",
            )

        self.assertEqual(session_manager.broadcasts, [])


if __name__ == "__main__":
    unittest.main()
