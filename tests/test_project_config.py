from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server.project_config import project_system_prompts


class ProjectConfigTests(unittest.TestCase):
    def test_group_rules_are_reloaded_for_each_group_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_dir = root / ".chaintogether"
            config_dir.mkdir()
            (config_dir / "agents.toml").write_text(
                '[group]\nsystem_prompt = "group prompt"\n',
                encoding="utf-8",
            )
            rules_path = config_dir / "rules.md"
            rules_path.write_text("first pre-send rule", encoding="utf-8")

            first = project_system_prompts(
                str(root), None, "codex", group_member=True
            )
            rules_path.write_text("updated pre-send rule", encoding="utf-8")
            second = project_system_prompts(
                str(root), None, "codex", group_member=True
            )

            self.assertIn("first pre-send rule", "\n".join(first))
            self.assertNotIn("first pre-send rule", "\n".join(second))
            self.assertIn("updated pre-send rule", "\n".join(second))


if __name__ == "__main__":
    unittest.main()
