from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from server.harness import RunConfig, get_harness
from server.harness.assembly import build_callback_env, select_mcp_servers
from server.mcp_servers import feature


class FeatureMcpTests(unittest.TestCase):
    def _env(self) -> dict[str, str]:
        return {
            "OCTOPUS_API_BASE": "http://127.0.0.1:8000",
            "OCTOPUS_AUTH_TOKEN": "auth-secret",
            "OCTOPUS_SESSION_ID": "session-1",
            "OCTOPUS_SESSION_CAPABILITY": "session-secret",
            "OCTOPUS_FEATURE_RUN_ID": "run-1",
            "OCTOPUS_FEATURE_DISPATCH_ID": "dispatch-1",
            "OCTOPUS_FEATURE_DISPATCH_CAPABILITY": "dispatch-secret",
        }

    def test_missing_env_fails_closed(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIn("misconfigured", feature.feature_status().lower())
            self.assertIn(
                "misconfigured",
                feature.feature_transition(to_stage="design").lower(),
            )
            self.assertIn(
                "misconfigured",
                feature.feature_request_review(evidence_refs=[]).lower(),
            )

    def test_status_uses_session_identity_without_consuming_dispatch(self) -> None:
        response = mock.Mock(status_code=200)
        response.json.return_value = {
            "feature_id": "F002",
            "stage": "implementation",
            "role": "owner",
            "suggested_skills": ["tdd"],
            "next_step": "Implement the next AC",
        }
        with mock.patch.dict(os.environ, self._env(), clear=True), mock.patch.object(
            feature.httpx, "get", return_value=response
        ) as get:
            result = feature.feature_status()
        self.assertIn("F002", result)
        _url, kwargs = get.call_args
        self.assertEqual(
            "session-secret",
            kwargs["headers"]["X-Octopus-Session-Capability"],
        )
        self.assertNotIn("X-Octopus-Dispatch-Capability", kwargs["headers"])

    def test_mutations_send_exact_dispatch_headers(self) -> None:
        response = mock.Mock(status_code=200)
        response.json.return_value = {
            "feature_id": "F002",
            "stage": "design",
            "successor_role": "owner",
            "suggested_skills": ["design-gate"],
        }
        with mock.patch.dict(os.environ, self._env(), clear=True), mock.patch.object(
            feature.httpx, "post", return_value=response
        ) as post:
            transitioned = feature.feature_transition(
                to_stage="design", reason="Discovery complete"
            )
            requested = feature.feature_request_review(
                evidence_refs=["evidence/quality.md"], revision="abc1234"
            )
        self.assertIn("end this turn", transitioned.lower())
        self.assertIn("end this turn", requested.lower())
        for call in post.call_args_list:
            headers = call.kwargs["headers"]
            self.assertEqual(
                "session-secret", headers["X-Octopus-Session-Capability"]
            )
            self.assertEqual("dispatch-1", headers["X-Octopus-Feature-Dispatch"])
            self.assertEqual(
                "dispatch-secret", headers["X-Octopus-Dispatch-Capability"]
            )

    def test_api_errors_are_returned_without_secret_echo(self) -> None:
        response = mock.Mock(status_code=409, text="stale dispatch")
        with mock.patch.dict(os.environ, self._env(), clear=True), mock.patch.object(
            feature.httpx, "post", return_value=response
        ):
            result = feature.feature_transition(to_stage="design")
        self.assertIn("stale dispatch", result)
        self.assertNotIn("session-secret", result)
        self.assertNotIn("dispatch-secret", result)


class FeatureMcpHarnessTests(unittest.TestCase):
    def test_feature_is_mandatory_when_optional_selection_is_empty(self) -> None:
        entries = select_mcp_servers([], [], {})
        self.assertEqual(
            ["feature", "session_chain"],
            [entry.key for entry in entries],
        )

    def test_callback_env_carries_dispatch_authority(self) -> None:
        env = build_callback_env(
            "session-1",
            "session-secret",
            feature_run_id="run-1",
            feature_dispatch_id="dispatch-1",
            feature_dispatch_capability="dispatch-secret",
        )
        self.assertEqual("run-1", env["OCTOPUS_FEATURE_RUN_ID"])
        self.assertEqual("dispatch-1", env["OCTOPUS_FEATURE_DISPATCH_ID"])
        self.assertEqual(
            "dispatch-secret", env["OCTOPUS_FEATURE_DISPATCH_CAPABILITY"]
        )

    def test_claude_and_codex_keep_capabilities_out_of_argv_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as working_dir:
            for backend in ("claude-code", "codex"):
                run = get_harness(backend).create_run(
                    RunConfig(
                        session_id="session-1",
                        session_capability="session-secret",
                        feature_run_id="run-1",
                        feature_dispatch_id="dispatch-1",
                        feature_dispatch_capability="dispatch-secret",
                        mcp_servers=[],
                    )
                )
                argv, kwargs = run.build_argv("feature turn", working_dir)
                rendered = "\0".join(argv)
                self.assertIn("server.mcp_servers.feature", rendered)
                self.assertNotIn("session-secret", rendered)
                self.assertNotIn("dispatch-secret", rendered)
                self.assertEqual(
                    "session-secret",
                    kwargs["env"]["OCTOPUS_SESSION_CAPABILITY"],
                )
                self.assertEqual(
                    "dispatch-secret",
                    kwargs["env"]["OCTOPUS_FEATURE_DISPATCH_CAPABILITY"],
                )


if __name__ == "__main__":
    unittest.main()
