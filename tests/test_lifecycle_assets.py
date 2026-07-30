from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        name, PROJECT_ROOT / "scripts" / filename
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_features = _load_script("check_features", "check-features.py")
sync_skills = _load_script("sync_skills", "sync-skills.py")


class FeatureValidatorTests(unittest.TestCase):
    def _feature(self, root: Path) -> Path:
        path = root / "docs" / "features" / "F123-example" / "feature.md"
        path.parent.mkdir(parents=True)
        text = (
            PROJECT_ROOT / "server" / "assets" / "templates" / "feature.md"
        ).read_text(encoding="utf-8")
        replacements = {
            "FEATURE_ID": "F123",
            "TITLE": "Example",
            "PRIORITY": "P1",
            "OWNER": "owner",
            "ORIGIN_KIND": "test",
            "GROUP_ID": "group",
            "MESSAGE_SEQ": "1",
            "CREATED_AT": "2026-07-30T00:00:00+00:00",
            "OPERATOR_QUOTE": "Example outcome",
        }
        for key, value in replacements.items():
            text = text.replace("{{" + key + "}}", value)
        path.write_text(text, encoding="utf-8")
        return path

    def test_template_is_valid_and_role_collision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self._feature(Path(temp))
            _metadata, issues = check_features.validate_feature(path)
            self.assertEqual(issues, [])

            text = path.read_text(encoding="utf-8")
            text = text.replace('reviewer: ""', 'reviewer: "owner"')
            path.write_text(text, encoding="utf-8")
            _metadata, issues = check_features.validate_feature(path)
            self.assertTrue(
                any("owner, reviewer, and vision_guardian must differ" in issue for issue in issues)
            )

    def test_done_requires_checked_acs_and_accepted_vision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self._feature(Path(temp))
            text = path.read_text(encoding="utf-8")
            text = text.replace("stage: discovery", "stage: done")
            text = text.replace("state: active", "state: done")
            text = text.replace(
                "## Design Gate\n\n- **Verdict**: pending",
                "## Design Gate\n\n- **Verdict**: approved",
            )
            path.write_text(text, encoding="utf-8")

            _metadata, issues = check_features.validate_feature(path)
            self.assertTrue(any("unchecked AC" in issue for issue in issues))
            self.assertTrue(any("accepted Vision Gate" in issue for issue in issues))


class SkillSyncTests(unittest.TestCase):
    def test_sync_refuses_unmanaged_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            (source / "SKILL.md").write_text("source", encoding="utf-8")
            (target / "SKILL.md").write_text("user content", encoding="utf-8")

            issues = sync_skills.sync_one(source, target, check=False)

            self.assertEqual(len(issues), 1)
            self.assertIn("refusing to overwrite unmanaged", issues[0])
            self.assertEqual(
                (target / "SKILL.md").read_text(encoding="utf-8"),
                "user content",
            )

    def test_resync_removes_stale_managed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            (source / "SKILL.md").write_text("canonical", encoding="utf-8")

            self.assertEqual(sync_skills.sync_one(source, target, check=False), [])
            (target / "obsolete.md").write_text("stale", encoding="utf-8")
            self.assertNotEqual(sync_skills.sync_one(source, target, check=True), [])
            self.assertEqual(sync_skills.sync_one(source, target, check=False), [])
            self.assertFalse((target / "obsolete.md").exists())
            provenance = json.loads(
                (target / sync_skills.PROVENANCE).read_text(encoding="utf-8")
            )
            self.assertEqual(
                provenance["source_digest"], sync_skills.digest_tree(source)
            )


if __name__ == "__main__":
    unittest.main()
