from __future__ import annotations

import unittest

from server.group_manager import GroupManager, analyze_agent_routing, parse_agent_mentions


class GroupRoutingTests(unittest.TestCase):
    def test_group_prompt_ends_with_dynamic_pre_send_exit_check(self) -> None:
        manager = GroupManager()
        prompt = manager._build_augmented_prompt(
            "Builder",
            "Delivery",
            [
                {
                    "id": "builder-id",
                    "name": "Builder",
                    "alias": "Maker",
                    "backend": "codex",
                },
                {
                    "id": "reviewer-id",
                    "name": "Reviewer",
                    "alias": "Checker",
                    "backend": "claude-code",
                },
            ],
            "[User]: implement the change",
        )

        exit_check_at = prompt.index("== Required pre-send exit check ==")
        self.assertGreater(exit_check_at, prompt.index("</group_transcript>"))
        self.assertIn('First ask: "Does the workflow truly end with me?"', prompt)
        self.assertIn("do not let Q2 or Q3 veto this route", prompt)
        self.assertIn("Valid handles for this turn: @Builder, @Maker, @Reviewer, @Checker", prompt)
        self.assertIn(
            "Your own handle(s), which must not be routed: @Builder / @Maker",
            prompt,
        )
        self.assertTrue(prompt.rstrip().endswith("or a documented hold action."))

    def test_separator_before_final_handoff_is_ignored(self) -> None:
        reply = "Work is complete.\n\n---\n@Builder please continue."
        self.assertEqual(parse_agent_mentions(reply), ["builder"])

    def test_handoff_accepts_continuation_lines(self) -> None:
        reply = (
            "I finished the API.\n\n"
            "@Builder please update the frontend.\n"
            "Reuse the new response fields and run the UI tests."
        )
        self.assertEqual(parse_agent_mentions(reply), ["builder"])

    def test_alias_is_valid_in_final_handoff(self) -> None:
        analysis = analyze_agent_routing(
            "Done.\n\n@Feng take the next step.",
            ["Panghu", "Feng"],
        )
        self.assertEqual(analysis.line_start_mentions, ("feng",))
        self.assertEqual(analysis.invalid_inline_mentions, ())

    def test_prose_before_handoff_in_final_block_stays_non_executable(self) -> None:
        reply = "Done.\n\nPlease continue this work.\n@Builder take over."
        analysis = analyze_agent_routing(reply, ["Builder"])
        self.assertEqual(analysis.line_start_mentions, ())
        self.assertEqual(analysis.invalid_inline_mentions, ("builder",))

    def test_ordinary_mention_outside_final_block_does_not_route(self) -> None:
        reply = "I checked the plan with @Builder.\n\nThe implementation is done."
        analysis = analyze_agent_routing(reply, ["Builder"])
        self.assertEqual(analysis.line_start_mentions, ())
        self.assertEqual(analysis.invalid_inline_mentions, ())


if __name__ == "__main__":
    unittest.main()
