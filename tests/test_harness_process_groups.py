from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from server.harness import run


class HarnessProcessGroupTests(unittest.TestCase):
    def test_windows_codex_prefers_spawnable_npm_native_binary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            appdata = Path(td) / "AppData" / "Roaming"
            native = (
                appdata
                / "npm"
                / "node_modules"
                / "@openai"
                / "codex"
                / "node_modules"
                / "@openai"
                / "codex-win32-x64"
                / "vendor"
                / "x86_64-pc-windows-msvc"
                / "bin"
                / "codex.exe"
            )
            native.parent.mkdir(parents=True)
            native.touch()

            with (
                patch.object(run.os, "name", "nt"),
                patch.dict(os.environ, {"APPDATA": str(appdata)}),
                patch.object(
                    run.shutil,
                    "which",
                    return_value=(
                        r"C:\Program Files\WindowsApps\OpenAI.Codex_1.0"
                        r"\app\resources\codex.exe"
                    ),
                ),
            ):
                resolved = run._which_with_fallback("codex")

        self.assertEqual(resolved, str(native))

    def test_windows_codex_rejects_store_desktop_binary(self) -> None:
        store_binary = (
            r"C:\Program Files\WindowsApps\OpenAI.Codex_1.0"
            r"\app\resources\codex.exe"
        )
        with (
            patch.object(run.os, "name", "nt"),
            patch.dict(os.environ, {"APPDATA": ""}),
            patch.object(run.shutil, "which", return_value=store_binary),
        ):
            resolved = run._which_with_fallback("codex")

        self.assertIsNone(resolved)

    def test_prepare_spawn_uses_windows_process_group_flag(self) -> None:
        with patch.object(run.os, "name", "nt"):
            _, kwargs = run.prepare_spawn(
                [sys.executable],
                {"creationflags": 0x10, "start_new_session": True},
            )

        self.assertNotIn("start_new_session", kwargs)
        self.assertEqual(
            kwargs["creationflags"], 0x10 | run._CREATE_NEW_PROCESS_GROUP
        )

    def test_windows_soft_stop_targets_tree_without_console_signal(self) -> None:
        proc = Mock(pid=1234, returncode=None)
        completed = SimpleNamespace(returncode=0)

        with (
            patch.object(run.os, "name", "nt"),
            patch.object(run.subprocess, "run", return_value=completed) as taskkill,
        ):
            sent_to_group = run._terminate_process_group(
                proc, run._SOFT_TERMINATE_SIGNAL
            )

        self.assertTrue(sent_to_group)
        command = taskkill.call_args.args[0]
        self.assertEqual(command, ["taskkill", "/PID", "1234", "/T"])
        proc.send_signal.assert_not_called()
        proc.terminate.assert_not_called()

    def test_windows_hard_stop_kills_entire_process_tree(self) -> None:
        proc = Mock(pid=5678, returncode=None)
        completed = SimpleNamespace(returncode=0)

        with (
            patch.object(run.os, "name", "nt"),
            patch.object(run.subprocess, "run", return_value=completed) as taskkill,
        ):
            sent_to_group = run._terminate_process_group(proc, run._HARD_KILL_SIGNAL)

        self.assertTrue(sent_to_group)
        command = taskkill.call_args.args[0]
        self.assertEqual(command, ["taskkill", "/PID", "5678", "/T", "/F"])
        proc.kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
