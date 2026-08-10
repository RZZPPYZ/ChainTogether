from __future__ import annotations

import unittest

from server.context_usage import normalize_context_usage


class ContextUsageTests(unittest.TestCase):
    def test_codex_usage_derives_remaining_context(self) -> None:
        usage = normalize_context_usage(
            backend="codex",
            model="gpt-5-codex",
            raw={"usage": {"input_tokens": 90000, "output_tokens": 10000}},
        )

        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage["input_tokens"], 90000)
        self.assertEqual(usage["output_tokens"], 10000)
        self.assertEqual(usage["total_tokens"], 100000)
        self.assertEqual(usage["context_window"], 400000)
        self.assertEqual(usage["remaining_tokens"], 300000)
        self.assertAlmostEqual(usage["remaining_ratio"], 0.75)
        self.assertEqual(usage["backend"], "codex")
        self.assertEqual(usage["model"], "gpt-5-codex")
        self.assertEqual(usage["source"], "estimated")

    def test_reported_remaining_context_wins_over_estimate(self) -> None:
        usage = normalize_context_usage(
            backend="claude-code",
            model="claude-sonnet-4-5",
            raw={
                "usage": {
                    "input_tokens": 123,
                    "output_tokens": 77,
                    "context_window": 200000,
                    "remaining_tokens": 199800,
                }
            },
        )

        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage["total_tokens"], 200)
        self.assertEqual(usage["remaining_tokens"], 199800)
        self.assertAlmostEqual(usage["remaining_ratio"], 0.999)
        self.assertEqual(usage["source"], "reported")


if __name__ == "__main__":
    unittest.main()
