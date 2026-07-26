from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from server.harness import run


class HarnessProcessGroupTests(unittest.TestCase):
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
