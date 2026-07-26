from __future__ import annotations

import json
import unittest
from typing import Any

from server.group_manager import GroupManager
from server.session_manager import SessionManager


class _FakeSessionManager:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = events
        self.activities: list[dict[str, Any]] = []

    async def send_message(self, _session_id: str, _prompt: str):
        for event in self.events:
            yield event

    async def inject_group_agent_activity(
        self,
        session_id: str,
        payload: dict[str, Any],
        *,
        agent_id: str | None = None,
    ) -> None:
        self.activities.append({
            "session_id": session_id,
            "agent_id_arg": agent_id,
            **payload,
        })


class GroupStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_collect_reply_persists_execution_activity(self) -> None:
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
            agent_id="agent-1",
            agent_name="Builder",
            invocation_id="invocation-1",
        )

        self.assertEqual(turn.text, "Finished the checks.")
        self.assertEqual(turn.tool_names, ("Bash",))
        self.assertEqual(
            [event["phase"] for event in session_manager.activities],
            [
                "started",
                "thinking",
                "tool_started",
                "tool_finished",
                "text",
                "result",
                "completed",
            ],
        )
        run_ids = {event["run_id"] for event in session_manager.activities}
        self.assertEqual(len(run_ids), 1)
        self.assertTrue(next(iter(run_ids)))
        self.assertTrue(all(
            event["session_id"] == "group-session"
            and event["agent_id"] == "agent-1"
            and event["agent_id_arg"] == "agent-1"
            for event in session_manager.activities
        ))
        tool_event = session_manager.activities[2]
        self.assertEqual(tool_event["tool_name"], "Bash")
        self.assertEqual(tool_event["tool_input"], {"command": "python -m unittest"})
        self.assertEqual(session_manager.activities[3]["output"], "OK")

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

        self.assertEqual(
            [event["phase"] for event in session_manager.activities],
            ["started", "error"],
        )


class _SessionManagerRecorder:
    def __init__(self) -> None:
        self.sessions = {"group-session": object()}
        self.persisted: list[tuple[object, Any, str | None]] = []
        self.broadcasts: list[dict[str, Any]] = []

    async def _persist_message(
        self, session: object, message: Any, *, agent_id: str | None = None
    ) -> int:
        self.persisted.append((session, message, agent_id))
        return 7

    async def _broadcast(self, event: dict[str, Any]) -> None:
        self.broadcasts.append(event)


class GroupActivityPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_activity_is_persisted_before_broadcast_with_seq(self) -> None:
        recorder = _SessionManagerRecorder()
        payload = {
            "run_id": "run-1",
            "agent_name": "Builder",
            "phase": "tool_started",
            "tool_input": {"command": "npm test"},
        }

        seq = await SessionManager.inject_group_agent_activity(  # type: ignore[arg-type]
            recorder,
            "group-session",
            payload,
            agent_id="agent-1",
        )

        self.assertEqual(seq, 7)
        self.assertEqual(len(recorder.persisted), 1)
        _, message, agent_id = recorder.persisted[0]
        self.assertEqual(message.role.value, "system")
        self.assertEqual(message.type, "group_agent_activity")
        self.assertEqual(json.loads(message.content), payload)
        self.assertEqual(agent_id, "agent-1")
        self.assertEqual(
            recorder.broadcasts,
            [{
                "type": "group_agent_activity",
                "session_id": "group-session",
                **payload,
                "seq": 7,
            }],
        )


if __name__ == "__main__":
    unittest.main()
