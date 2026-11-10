from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import httpx

from server.agent_manager import AgentManager
from server.config import settings
from server.database import Database
from server.main import app
from server.routers import agents as agents_router
from server.routers import session_folders as session_folders_router
from server.session_manager import session_manager


class SessionFolderApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_agents_dir = settings.agents_dir
        self.old_auth_token = settings.auth_token
        settings.agents_dir = str(self.root / "agents")
        settings.auth_token = "test-token"

        self.db = Database(str(self.root / "test.db"))
        await self.db.initialize()
        session_manager.sessions.clear()
        await session_manager.initialize(self.db)
        agent_manager = AgentManager(self.db)
        agents_router.set_manager(agent_manager)
        session_folders_router.set_db(self.db)
        self.manager = agent_manager
        self.agent = await agent_manager.create_agent(name="Folder Owner")
        self.other_agent = await agent_manager.create_agent(name="Other Agent")
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-token"},
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        await self.db.close()
        settings.agents_dir = self.old_agents_dir
        settings.auth_token = self.old_auth_token
        self.temp.cleanup()

    async def _create_folder(
        self, name: str = "Frontend", agent_id: str | None = None
    ) -> dict:
        res = await self.client.post(
            f"/api/agents/{agent_id or self.agent['id']}/folders",
            json={"name": name, "working_dir": str(self.workspace)},
        )
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    async def test_folder_crud_and_session_inheritance(self) -> None:
        folder = await self._create_folder()
        self.assertEqual(folder["working_dir"], str(self.workspace.resolve()))

        listed = await self.client.get(
            f"/api/agents/{self.agent['id']}/folders"
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([f["id"] for f in listed.json()], [folder["id"]])

        renamed = await self.client.patch(
            f"/api/folders/{folder['id']}", json={"name": "Frontend v2"}
        )
        self.assertEqual(renamed.status_code, 200, renamed.text)
        self.assertEqual(renamed.json()["name"], "Frontend v2")

        ignored = self.root / "ignored"
        ignored.mkdir()
        created = await self.client.post(
            f"/api/agents/{self.agent['id']}/sessions",
            json={
                "name": "Child",
                "folder_id": folder["id"],
                "working_dir": str(ignored),
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        session = created.json()
        self.assertEqual(session["folder_id"], folder["id"])
        self.assertEqual(session["working_dir"], folder["working_dir"])

        detail = await self.client.get(f"/api/sessions/{session['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["folder_id"], folder["id"])

        deleted = await self.client.delete(f"/api/folders/{folder['id']}")
        self.assertEqual(deleted.status_code, 204)

        detached = await self.client.get(f"/api/sessions/{session['id']}")
        self.assertEqual(detached.status_code, 200)
        self.assertIsNone(detached.json()["folder_id"])
        self.assertEqual(
            detached.json()["working_dir"], folder["working_dir"]
        )

    async def test_drag_order_persists_and_validates_the_group(self) -> None:
        ids: list[str] = []
        for name in ("A", "B", "C"):
            res = await self.client.post(
                f"/api/agents/{self.agent['id']}/sessions",
                json={"name": name},
            )
            self.assertEqual(res.status_code, 201, res.text)
            ids.append(res.json()["id"])

        reordered = await self.client.put(
            f"/api/agents/{self.agent['id']}/sessions/order",
            json={"folder_id": None, "session_ids": [ids[2], ids[0], ids[1]]},
        )
        self.assertEqual(reordered.status_code, 204, reordered.text)

        listing = (await self.client.get("/api/sessions")).json()
        top_level = [
            item["id"]
            for item in listing
            if item["agent_id"] == self.agent["id"]
            and not item["folder_id"]
            and item["origin"] == "user"
        ]
        self.assertEqual(top_level, [ids[2], ids[0], ids[1]])

        rows = {row["id"]: row for row in await self.db.load_sessions()}
        self.assertEqual(rows[ids[2]]["sort_order"], 0.0)
        self.assertEqual(rows[ids[0]]["sort_order"], 1.0)
        self.assertEqual(rows[ids[1]]["sort_order"], 2.0)

        # A folder has its own ordering group.
        folder = await self._create_folder("Ordered")
        folder_ids: list[str] = []
        for name in ("F1", "F2"):
            res = await self.client.post(
                f"/api/agents/{self.agent['id']}/sessions",
                json={"name": name, "folder_id": folder["id"]},
            )
            self.assertEqual(res.status_code, 201, res.text)
            folder_ids.append(res.json()["id"])
        folder_order = await self.client.put(
            f"/api/agents/{self.agent['id']}/sessions/order",
            json={
                "folder_id": folder["id"],
                "session_ids": [folder_ids[1], folder_ids[0]],
            },
        )
        self.assertEqual(folder_order.status_code, 204, folder_order.text)
        listing = (await self.client.get("/api/sessions")).json()
        in_folder = [
            item["id"]
            for item in listing
            if item["folder_id"] == folder["id"]
        ]
        self.assertEqual(in_folder, [folder_ids[1], folder_ids[0]])

        # Cross-group / duplicate / cross-agent payloads are rejected.
        mixed = await self.client.put(
            f"/api/agents/{self.agent['id']}/sessions/order",
            json={"folder_id": folder["id"], "session_ids": [folder_ids[0], ids[0]]},
        )
        self.assertEqual(mixed.status_code, 400)
        duplicate = await self.client.put(
            f"/api/agents/{self.agent['id']}/sessions/order",
            json={"folder_id": None, "session_ids": [ids[0], ids[0]]},
        )
        self.assertEqual(duplicate.status_code, 400)
        wrong_root = await self.client.put(
            f"/api/agents/{self.agent['id']}/sessions/order",
            json={"folder_id": None, "session_ids": [folder_ids[0]]},
        )
        self.assertEqual(wrong_root.status_code, 400)

        other = await self.client.post(
            f"/api/agents/{self.other_agent['id']}/sessions",
            json={"name": "Other"},
        )
        self.assertEqual(other.status_code, 201, other.text)
        cross_agent = await self.client.put(
            f"/api/agents/{self.agent['id']}/sessions/order",
            json={"folder_id": None, "session_ids": [other.json()["id"]]},
        )
        self.assertEqual(cross_agent.status_code, 400)

    async def test_folder_validation_errors(self) -> None:
        folder = await self._create_folder()

        duplicate = await self.client.post(
            f"/api/agents/{self.agent['id']}/folders",
            json={"name": "frontend", "working_dir": str(self.workspace)},
        )
        self.assertEqual(duplicate.status_code, 400)

        blank_name = await self.client.post(
            f"/api/agents/{self.agent['id']}/folders",
            json={"name": "   ", "working_dir": str(self.workspace)},
        )
        self.assertEqual(blank_name.status_code, 400)

        null_name = await self.client.patch(
            f"/api/folders/{folder['id']}", json={"name": None}
        )
        self.assertEqual(null_name.status_code, 400)

        missing_agent = await self.client.get("/api/agents/missing/folders")
        self.assertEqual(missing_agent.status_code, 404)

        cross_agent = await self.client.post(
            f"/api/agents/{self.other_agent['id']}/sessions",
            json={"name": "Wrong owner", "folder_id": folder["id"]},
        )
        self.assertEqual(cross_agent.status_code, 400)

        missing_folder = await self.client.post(
            f"/api/agents/{self.agent['id']}/sessions",
            json={"name": "No folder", "folder_id": "missing"},
        )
        self.assertEqual(missing_folder.status_code, 400)


if __name__ == "__main__":
    unittest.main()
