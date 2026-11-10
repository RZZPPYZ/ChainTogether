from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server.agent_manager import AgentManager
from server.config import settings
from server.database import Database
from server.session_manager import SessionManager


class SessionFolderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_agents_dir = settings.agents_dir
        settings.agents_dir = str(self.root / "agents")

        self.db = Database(str(self.root / "test.db"))
        await self.db.initialize()
        self.manager = SessionManager()
        await self.manager.initialize(self.db)

        agents = AgentManager(self.db)
        self.agent = await agents.create_agent(name="Folder Owner")
        self.other_agent = await agents.create_agent(name="Other Agent")
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

    async def asyncTearDown(self) -> None:
        await self.db.close()
        settings.agents_dir = self.old_agents_dir
        self.temp.cleanup()

    async def _create_folder(self, name: str = "Frontend") -> dict:
        return await self.db.create_session_folder(
            self.agent["id"], name, str(self.workspace)
        )

    async def test_folder_session_inherits_path_and_counts(self) -> None:
        folder = await self._create_folder()
        self.assertEqual(folder["working_dir"], str(self.workspace.resolve()))
        self.assertEqual(folder["session_count"], 0)

        ignored = self.root / "ignored"
        ignored.mkdir()
        session = await self.manager.create_session(
            self.agent["id"],
            "Child",
            working_dir=str(ignored),
            folder_id=folder["id"],
        )

        self.assertEqual(session.folder_id, folder["id"])
        self.assertEqual(session.working_dir, folder["working_dir"])
        refreshed = await self.db.get_session_folder(folder["id"])
        self.assertEqual(refreshed["session_count"], 1)

        stored = next(
            row
            for row in await self.db.load_sessions()
            if row["id"] == session.id
        )
        self.assertEqual(stored["folder_id"], folder["id"])
        self.assertEqual(stored["working_dir"], folder["working_dir"])

    async def test_folder_must_belong_to_the_session_agent(self) -> None:
        folder = await self._create_folder()

        with self.assertRaisesRegex(ValueError, "different agent"):
            await self.manager.create_session(
                self.other_agent["id"], folder_id=folder["id"]
            )
        with self.assertRaisesRegex(ValueError, "not found"):
            await self.manager.create_session(
                self.agent["id"], folder_id="missing-folder"
            )

    async def test_folder_names_are_unique_per_agent_case_insensitively(
        self,
    ) -> None:
        await self._create_folder("Frontend")

        with self.assertRaisesRegex(ValueError, "already exists"):
            await self._create_folder("frontend")

        # The same display name is fine under a different agent.
        other = await self.db.create_session_folder(
            self.other_agent["id"], "Frontend", str(self.workspace)
        )
        self.assertEqual(other["agent_id"], self.other_agent["id"])

        # Renames obey the same uniqueness rule.
        second = await self._create_folder("Backend")
        with self.assertRaisesRegex(ValueError, "already exists"):
            await self.db.update_session_folder(
                second["id"], name="FRONTEND"
            )

    async def test_folder_path_edit_only_affects_new_sessions(self) -> None:
        folder = await self._create_folder()
        old_session = await self.manager.create_session(
            self.agent["id"], folder_id=folder["id"]
        )
        old_path = old_session.working_dir

        new_workspace = self.root / "workspace-2"
        new_workspace.mkdir()
        updated = await self.db.update_session_folder(
            folder["id"], name="Frontend v2", working_dir=str(new_workspace)
        )
        self.assertEqual(updated["name"], "Frontend v2")
        self.assertEqual(
            updated["working_dir"], str(new_workspace.resolve())
        )

        # Existing sessions keep the path they were created with.
        self.assertEqual(old_session.working_dir, old_path)
        new_session = await self.manager.create_session(
            self.agent["id"], folder_id=folder["id"]
        )
        self.assertEqual(new_session.working_dir, updated["working_dir"])

    async def test_deleting_folder_detaches_sessions_without_deleting_them(
        self,
    ) -> None:
        folder = await self._create_folder()
        session = await self.manager.create_session(
            self.agent["id"], folder_id=folder["id"]
        )
        path = session.working_dir

        self.assertTrue(await self.manager.delete_session_folder(folder["id"]))
        self.assertFalse(
            await self.manager.delete_session_folder(folder["id"])
        )

        live = self.manager.get_session(session.id)
        self.assertIsNotNone(live)
        self.assertIsNone(live.folder_id)
        self.assertEqual(live.working_dir, path)

        stored = next(
            row
            for row in await self.db.load_sessions()
            if row["id"] == session.id
        )
        self.assertIsNone(stored["folder_id"])
        self.assertEqual(stored["working_dir"], path)

    async def test_archive_successor_stays_in_the_folder(self) -> None:
        folder = await self._create_folder()
        old = await self.manager.create_session(
            self.agent["id"], "Child", folder_id=folder["id"]
        )

        new = await self.manager.archive_session(old.id)

        self.assertNotEqual(new.id, old.id)
        self.assertEqual(new.folder_id, folder["id"])
        self.assertEqual(new.working_dir, folder["working_dir"])
        self.assertEqual(new.sort_order, old.sort_order)
        stored = next(
            row
            for row in await self.db.load_sessions(include_archived=True)
            if row["id"] == new.id
        )
        self.assertEqual(stored["folder_id"], folder["id"])
        archived = next(
            row
            for row in await self.db.load_sessions(include_archived=True)
            if row["id"] == old.id
        )
        self.assertEqual(archived["folder_id"], folder["id"])
        self.assertTrue(archived["archived"])

    async def test_fork_rows_persist_their_folder_choice(self) -> None:
        folder = await self._create_folder()
        parent = await self.manager.create_session(
            self.agent["id"], folder_id=folder["id"]
        )
        await self.db.create_fork_session(
            fork_id="rewind-fork",
            name="Rewind fork",
            working_dir=parent.working_dir,
            created_at="2026-11-10T00:00:00Z",
            parent_id=parent.id,
            backend=parent.backend,
            agent_id=parent.agent_id,
            credential_id=None,
            resume_id=None,
            fork_after_seq=0,
            folder_id=folder["id"],
        )
        await self.db.create_fork_session(
            fork_id="copy-fork",
            name="Copy fork",
            working_dir=str(self.root / "copy"),
            created_at="2026-11-10T00:00:00Z",
            parent_id=parent.id,
            backend=parent.backend,
            agent_id=parent.agent_id,
            credential_id=None,
            resume_id=None,
            fork_after_seq=0,
            folder_id=None,
        )

        rows = {
            row["id"]: row
            for row in await self.db.load_sessions(include_archived=True)
        }
        self.assertEqual(rows["rewind-fork"]["folder_id"], folder["id"])
        self.assertIsNone(rows["copy-fork"]["folder_id"])

    async def test_folder_session_survives_restart(self) -> None:
        folder = await self._create_folder()
        session = await self.manager.create_session(
            self.agent["id"], folder_id=folder["id"]
        )

        await self.db.close()
        self.db = Database(str(self.root / "test.db"))
        await self.db.initialize()
        self.manager = SessionManager()
        await self.manager.initialize(self.db)

        reloaded = self.manager.get_session(session.id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.folder_id, folder["id"])
        self.assertEqual(reloaded.working_dir, folder["working_dir"])
        folders = await self.db.load_session_folders(self.agent["id"])
        self.assertEqual([f["id"] for f in folders], [folder["id"]])
        self.assertEqual(folders[0]["session_count"], 1)


if __name__ == "__main__":
    unittest.main()
