from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server.agent_manager import AgentManager
from server.config import settings
from server.database import Database
from server.group_manager import AgentTurnResult, GroupError, GroupManager
from server.session_manager import SessionManager


class GroupWorkingDirectoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_agents_dir = settings.agents_dir
        self.old_group_prompt_state_dir = settings.group_prompt_state_dir
        settings.agents_dir = str(self.root / "agents")
        settings.group_prompt_state_dir = str(self.root / "groups")

        self.db = Database(str(self.root / "test.db"))
        await self.db.initialize()
        self.session_manager = SessionManager()
        await self.session_manager.initialize(self.db)
        self.agent_manager = AgentManager(self.db)
        self.first = await self.agent_manager.create_agent(name="Builder")
        self.second = await self.agent_manager.create_agent(name="Reviewer")

        self.manager = GroupManager()
        self.manager.bind(self.session_manager, self.db)

    async def asyncTearDown(self) -> None:
        await self.db.close()
        settings.agents_dir = self.old_agents_dir
        settings.group_prompt_state_dir = self.old_group_prompt_state_dir
        self.temp.cleanup()

    async def test_group_and_member_sessions_share_selected_directory(self) -> None:
        workspace = self.root / "workspace"
        workspace.mkdir()

        group = await self.manager.create_group(
            "Build Team",
            [self.first["id"], self.second["id"]],
            working_dir=f"  {workspace}  ",
        )

        expected = str(workspace.resolve())
        self.assertEqual(group["working_dir"], expected)
        self.assertEqual(
            self.session_manager.sessions[group["session_id"]].working_dir,
            expected,
        )
        stored = await self.db.get_group(group["id"])
        self.assertEqual(stored["working_dir"], expected)

        child_id = await self.manager._get_or_create_member_session(
            self.manager._runs[group["id"]], self.first, stored
        )
        self.assertEqual(
            self.session_manager.sessions[child_id].working_dir,
            expected,
        )
        self.assertEqual(
            await self.db.get_group_agent_cursor(group["id"], self.first["id"]),
            -1,
        )
        await self.db.update_group_agent_cursor(group["id"], self.first["id"], 7)
        await self.db.update_group_agent_cursor(group["id"], self.first["id"], 3)
        self.assertEqual(
            await self.db.get_group_agent_cursor(group["id"], self.first["id"]),
            7,
        )

    async def test_missing_group_directory_is_rejected(self) -> None:
        missing = self.root / "missing"

        with self.assertRaisesRegex(GroupError, "does not exist"):
            await self.manager.create_group(
                "Build Team",
                [self.first["id"], self.second["id"]],
                working_dir=str(missing),
            )

    async def test_group_turn_injects_l0_and_advances_d_cursor(self) -> None:
        workspace = self.root / "workspace"
        workspace.mkdir()
        group = await self.manager.create_group(
            "Build Team",
            [self.first["id"], self.second["id"]],
            working_dir=str(workspace),
        )
        stored = await self.db.get_group(group["id"])
        prior_seq = await self.session_manager.inject_message(
            group["session_id"], "user", "Previous group context"
        )
        current_seq = await self.session_manager.inject_message(
            group["session_id"], "user", "@Builder implement the change"
        )
        captured: dict[str, str] = {}

        async def collect(
            session_id: str, prompt: str, **_kwargs: object
        ) -> AgentTurnResult:
            captured["prompt"] = prompt
            captured["l0"] = (
                self.session_manager.sessions[session_id]._group_l0_prompt or ""
            )
            return AgentTurnResult("Implementation complete.")

        self.manager._collect_agent_reply = collect  # type: ignore[method-assign]
        await self.manager._run_mentioned_agent(
            self.manager._runs[group["id"]],
            self.first,
            stored,
            current_message="@Builder implement the change",
            current_message_seq=current_seq,
            current_source="User",
        )

        self.assertIsNotNone(prior_seq)
        self.assertIn("Your canonical identity: @Builder", captured["l0"])
        self.assertIn("Previous group context", captured["prompt"])
        self.assertEqual(captured["prompt"].count("@Builder implement the change"), 1)
        self.assertEqual(
            await self.db.get_group_agent_cursor(group["id"], self.first["id"]),
            current_seq,
        )


if __name__ == "__main__":
    unittest.main()
