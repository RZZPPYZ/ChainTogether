from __future__ import annotations

import unittest

from server.group_manager import (
    GroupManager,
    analyze_agent_routing,
    member_canonical_handles,
    member_routing_handles,
    parse_agent_mentions,
)
from server.prompt_governance import GroupPromptGovernance


class GroupRoutingTests(unittest.TestCase):
    def test_l0_owns_identity_roster_and_exit_check(self) -> None:
        governance = GroupPromptGovernance()
        members = [
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
        ]
        prompt = governance.render_l0(
            {"id": "group-id", "name": "Delivery", "default_agent_id": None},
            members[0],
            members,
            persist_snapshot=False,
        )

        self.assertIn("Your canonical identity: @Builder", prompt)
        self.assertIn("Before sending, silently apply", prompt)
        self.assertIn("Do not let Q2 or Q3 veto", prompt)
        self.assertIn("Valid routing handles: @Builder, @Reviewer", prompt)
        self.assertIn(
            "Aliases are user-only input", prompt
        )
        self.assertNotIn("@Maker", prompt)
        self.assertNotIn("@Checker", prompt)

    def test_d_layer_separates_delta_from_current_message(self) -> None:
        governance = GroupPromptGovernance()
        prompt = governance.assemble_dynamic_turn(
            directives=[],
            delta_messages=[{
                "seq": 10,
                "source": "Reviewer",
                "kind": "agent_reply",
                "content": "API is ready.",
            }],
            current_message={
                "seq": 11,
                "source": "User",
                "content": "@Builder update the UI.",
            },
            delta_from_seq=10,
            delta_to_seq=10,
        )

        self.assertEqual(prompt.count("@Builder update the UI."), 1)
        self.assertIn("API is ready.", prompt)
        self.assertIn("<current_message>", prompt)

    def test_delta_cursor_excludes_current_and_controller_notices(self) -> None:
        manager = GroupManager()
        payload, start, end, highwater = manager._build_group_delta_payload(
            [
                {"seq": 4, "type": "text", "role": "user", "content": "old"},
                {
                    "seq": 6,
                    "type": "text",
                    "role": "user",
                    "content": "[agent-reply:Reviewer]\n\nAPI ready",
                    "agent_id": "reviewer-id",
                },
                {
                    "seq": 7,
                    "type": "text",
                    "role": "user",
                    "content": "[agent-routing-warning:Reviewer]\n\nwarning",
                },
                {
                    "seq": 8,
                    "type": "text",
                    "role": "user",
                    "content": "@Builder continue",
                },
            ],
            [{"id": "reviewer-id", "name": "Reviewer"}],
            after_seq=5,
            before_seq=8,
        )

        self.assertEqual(start, 6)
        self.assertEqual(end, 7)
        self.assertEqual(highwater, 7)
        self.assertEqual([item["content"] for item in payload], ["API ready"])

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

    def test_canonical_name_is_valid_in_final_handoff(self) -> None:
        analysis = analyze_agent_routing(
            "Done.\n\n@Feng take the next step.",
            ["Panghu", "Feng"],
        )
        self.assertEqual(analysis.line_start_mentions, ("feng",))
        self.assertEqual(analysis.invalid_inline_mentions, ())

    def test_alias_is_user_only_and_not_in_agent_handoff_roster(self) -> None:
        agents = [
            {"id": "panghu", "name": "Panghu", "alias": "Feng"},
            {"id": "xiaofu", "name": "Xiaofu", "alias": ""},
        ]

        self.assertEqual(
            member_routing_handles(agents), ["Panghu", "Feng", "Xiaofu"]
        )
        self.assertEqual(member_canonical_handles(agents), ["Panghu", "Xiaofu"])

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
