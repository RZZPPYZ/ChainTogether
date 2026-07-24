from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server.agent_manager import AgentError, AgentManager
from server.config import settings
from server.database import Database
from server.delegations import DelegationManager
from server.group_manager import GroupManager, parse_mentions


class AgentAliasTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.old_agents_dir = settings.agents_dir
        settings.agents_dir = str(root / "agents")
        self.db = Database(str(root / "test.db"))
        await self.db.initialize()
        self.manager = AgentManager(self.db)

    async def asyncTearDown(self) -> None:
        await self.db.close()
        settings.agents_dir = self.old_agents_dir
        self.temp.cleanup()

    async def test_alias_routes_to_same_agent_and_updates_immediately(self) -> None:
        agent = await self.manager.create_agent(name="胖虎", alias="峰哥")
        group_manager = GroupManager()

        self.assertEqual(agent["alias"], "峰哥")
        self.assertEqual(parse_mentions("@峰哥 帮我看一下"), ["峰哥"])
        self.assertEqual(
            group_manager._resolve_agent_by_name("峰哥", [agent])["id"],
            agent["id"],
        )
        self.assertEqual(
            group_manager._resolve_agent_by_name("胖虎", [agent])["id"],
            agent["id"],
        )

        updated = await self.manager.update_agent(agent["id"], alias="阿峰")
        self.assertIsNone(
            group_manager._resolve_agent_by_name(
                "峰哥", [updated], allow_prefix=False
            )
        )
        self.assertEqual(
            group_manager._resolve_agent_by_name(
                "阿峰", [updated], allow_prefix=False
            )["id"],
            agent["id"],
        )

    async def test_name_and_alias_conflicts_are_rejected(self) -> None:
        first = await self.manager.create_agent(name="胖虎", alias="峰哥")

        with self.assertRaisesRegex(AgentError, "conflicts"):
            await self.manager.create_agent(name="峰哥")
        with self.assertRaisesRegex(AgentError, "conflicts"):
            await self.manager.create_agent(name="小夫", alias="胖虎")
        with self.assertRaisesRegex(AgentError, "differ"):
            await self.manager.update_agent(first["id"], alias="胖虎")

    async def test_alias_validation_and_clearing(self) -> None:
        with self.assertRaisesRegex(AgentError, "only letters"):
            await self.manager.create_agent(name="胖虎", alias="峰 哥")
        with self.assertRaisesRegex(AgentError, "cannot be 'user'"):
            await self.manager.create_agent(name="胖虎", alias="user")

        agent = await self.manager.create_agent(name="胖虎", alias="峰哥")
        updated = await self.manager.update_agent(agent["id"], alias=None)
        self.assertEqual(updated["alias"], "")

    async def test_delegation_target_accepts_name_or_alias(self) -> None:
        agent = await self.manager.create_agent(name="胖虎", alias="峰哥")
        latin_agent = await self.manager.create_agent(name="Coach", alias="FÉNG")
        delegations = DelegationManager()
        delegations.db = self.db

        by_name = await delegations._resolve_target_agent("胖虎")
        by_alias = await delegations._resolve_target_agent("峰哥")
        by_unicode_casefold = await delegations._resolve_target_agent("féng")

        self.assertEqual(by_name["id"], agent["id"])
        self.assertEqual(by_alias["id"], agent["id"])
        self.assertEqual(by_unicode_casefold["id"], latin_agent["id"])


if __name__ == "__main__":
    unittest.main()
