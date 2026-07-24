from __future__ import annotations

import io
import os
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from server.database import Database
from server.config import settings
from server.persona_manager import (
    PersonaError,
    PersonaManager,
    parse_skill_frontmatter,
    render_persona_prompt,
)


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


class PersonaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.old_personas_dir = settings.personas_dir
        settings.personas_dir = str(root / "personas")
        self.db = Database(str(root / "test.db"))
        await self.db.initialize()
        now = datetime.now(timezone.utc).isoformat()
        await self.db.save_agent(
            agent_id="agent-one",
            name="Agent One",
            created_at=now,
            updated_at=now,
        )
        self.persona_dirs: dict[str, Path] = {}
        for persona_id, name in (("direct", "Direct"), ("gentle", "Gentle")):
            package = root / persona_id
            (package / "references").mkdir(parents=True)
            (package / "references" / "notes.md").write_text(
                f"Reference for {name}", encoding="utf-8"
            )
            self.persona_dirs[persona_id] = package
            await self.db.save_persona(
                persona_id=persona_id,
                name=name,
                description=f"{name} persona",
                source_url=f"https://github.com/example/{persona_id}",
                source_commit="a" * 40,
                license_name="MIT",
                entrypoint="SKILL.md",
                package_path=str(package),
                core_prompt=f"---\nname: {name}\ndescription: test\n---\nBe {name}.",
                resources=[
                    {
                        "path": "references/notes.md",
                        "size": 20,
                        "kind": "reference",
                    }
                ],
                created_at=now,
            )

    async def asyncTearDown(self) -> None:
        await self.db.close()
        settings.personas_dir = self.old_personas_dir
        self.temp.cleanup()

    async def test_agent_can_assign_many_but_activate_one(self) -> None:
        await self.db.set_agent_personas(
            "agent-one", ["direct", "gentle"], "gentle"
        )
        agent = await self.db.get_agent("agent-one")
        self.assertEqual(agent["persona_ids"], ["direct", "gentle"])
        self.assertEqual(agent["active_persona_id"], "gentle")
        active = await self.db.get_active_persona_for_agent("agent-one")
        self.assertEqual(active["name"], "Gentle")

        await self.db.set_agent_personas(
            "agent-one", ["direct", "gentle"], "direct"
        )
        active = await self.db.get_active_persona_for_agent("agent-one")
        self.assertEqual(active["name"], "Direct")

    async def test_active_persona_must_be_assigned(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be assigned"):
            await self.db.set_agent_personas("agent-one", ["direct"], "gentle")

    async def test_resource_reader_is_allowlisted(self) -> None:
        manager = PersonaManager()
        manager.bind(self.db)
        persona = await self.db.get_persona("direct")
        content = await manager.read_resource(persona, "references/notes.md")
        self.assertEqual(content, "Reference for Direct")
        with self.assertRaises(PersonaError):
            await manager.read_resource(persona, "../gentle/references/notes.md")

    def test_frontmatter_and_prompt_rendering(self) -> None:
        metadata = parse_skill_frontmatter(
            "---\nname: persona-name\ndescription: >\n  A useful\n  perspective.\n---\nBody"
        )
        self.assertEqual(metadata["name"], "persona-name")
        self.assertEqual(metadata["description"], "A useful perspective.")
        prompt = render_persona_prompt(
            {"name": "Persona", "core_prompt": "Core instructions"}
        )
        self.assertIn("Active persona: Persona", prompt)
        self.assertIn("Core instructions", prompt)
        self.assertIn("persona` MCP", prompt)

    async def test_imports_local_zip_with_repository_wrapper(self) -> None:
        manager = PersonaManager()
        manager.bind(self.db)
        archive = _zip_bytes(
            {
                "downloaded-skill/SKILL.md": (
                    "---\nname: local-persona\ndescription: Local test\n---\n"
                    "Use this perspective."
                ),
                "downloaded-skill/references/notes.md": "Supporting notes",
                "downloaded-skill/examples/demo.md": "Example response",
            }
        )

        persona = await manager.import_zip(archive, "downloaded-skill.zip")

        self.assertEqual(persona["name"], "local-persona")
        self.assertTrue(persona["source_url"].startswith("local://sha256/"))
        self.assertEqual(persona["entrypoint"], "SKILL.md")
        self.assertTrue(Path(persona["package_path"], "SKILL.md").is_file())
        self.assertEqual(
            {item["path"] for item in persona["resources"]},
            {"examples/demo.md", "references/notes.md"},
        )
        with self.assertRaisesRegex(PersonaError, "already installed"):
            await manager.import_zip(archive, "copy.zip")

    async def test_local_zip_rejects_unsafe_paths(self) -> None:
        manager = PersonaManager()
        manager.bind(self.db)
        archive = _zip_bytes(
            {
                "persona/SKILL.md": "---\nname: unsafe\n---\nBody",
                "persona/../outside.txt": "must not escape",
            }
        )
        with self.assertRaisesRegex(PersonaError, "unsafe path"):
            await manager.import_zip(archive, "unsafe.zip")


@unittest.skipUnless(
    os.environ.get("CHAINTOGETHER_PERSONA_LIVE_TEST"),
    "set CHAINTOGETHER_PERSONA_LIVE_TEST to run the GitHub import smoke test",
)
class PersonaGitHubImportTests(unittest.IsolatedAsyncioTestCase):
    async def test_imports_complete_zhangxuefeng_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            old_dir = settings.personas_dir
            settings.personas_dir = str(Path(temp) / "personas")
            db = Database(str(Path(temp) / "test.db"))
            await db.initialize()
            try:
                manager = PersonaManager()
                manager.bind(db)
                persona = await manager.import_github(
                    "https://github.com/alchaincyf/zhangxuefeng-skill"
                )
                self.assertEqual(persona["name"], "zhangxuefeng-perspective")
                paths = {resource["path"] for resource in persona["resources"]}
                self.assertIn("references/research/01-writings.md", paths)
                self.assertIn("examples/demo-conversation.md", paths)
                self.assertTrue(Path(persona["package_path"], "SKILL.md").is_file())
            finally:
                await db.close()
                settings.personas_dir = old_dir


if __name__ == "__main__":
    unittest.main()
