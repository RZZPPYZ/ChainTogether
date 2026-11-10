from __future__ import annotations

import unittest

from server.harness.events import HarnessEvent
from server.models import MessageRole
from server.session_manager import SessionManager


class ThinkingEventTests(unittest.TestCase):
    def test_thinking_is_persisted_and_broadcast(self) -> None:
        event = HarnessEvent(
            type="thinking", content="First inspect the caller."
        )

        message = SessionManager._event_to_message_content(event)
        self.assertIsNotNone(message)
        self.assertEqual(message.role, MessageRole.assistant)
        self.assertEqual(message.type, "thinking")
        self.assertEqual(message.content, "First inspect the caller.")

        ws_event = SessionManager._event_to_ws_message("session-1", event)
        self.assertEqual(
            ws_event,
            {
                "type": "assistant_thinking",
                "session_id": "session-1",
                "content": "First inspect the caller.",
            },
        )

    def test_blank_thinking_is_dropped(self) -> None:
        for content in (None, "", "   \n"):
            event = HarnessEvent(type="thinking", content=content)
            self.assertIsNone(
                SessionManager._event_to_message_content(event),
                f"persisted blank thinking {content!r}",
            )
            self.assertIsNone(
                SessionManager._event_to_ws_message("session-1", event),
                f"broadcast blank thinking {content!r}",
            )


if __name__ == "__main__":
    unittest.main()
