from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from server.harness.assembly import compose_system_prompt
from server.prompt_governance import GroupPromptGovernance, get_prompt_registry


class PromptGovernanceTests(unittest.TestCase):
    def test_machine_policy_is_the_runtime_source(self) -> None:
        policy = get_prompt_registry().routing_policy

        self.assertEqual(policy.max_mention_targets, 4)
        self.assertLess(
            policy.pingpong_warn_threshold,
            policy.pingpong_block_threshold,
        )

    def test_roster_snapshot_is_generated_without_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            governance = GroupPromptGovernance(state_root=temp_dir)
            group = {
                "id": "group-1",
                "name": "Delivery",
                "default_agent_id": "agent-1",
            }
            members = [
                {
                    "id": "agent-1",
                    "name": "Builder",
                    "alias": "Maker",
                    "backend": "codex",
                },
                {
                    "id": "agent-2",
                    "name": "Reviewer",
                    "alias": "Checker",
                    "backend": "claude-code",
                },
            ]

            prompt = governance.render_l0(group, members[0], members)
            snapshot_path = Path(temp_dir) / "group-1" / "group-members.json"
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

            self.assertTrue(snapshot["roster_version"])
            self.assertEqual(
                [item["canonical_name"] for item in snapshot["members"]],
                ["Builder", "Reviewer"],
            )
            self.assertNotIn("alias", json.dumps(snapshot))
            self.assertNotIn("@Maker", prompt)

    def test_l0_governance_is_last_in_composed_system_prompt(self) -> None:
        prompt = compose_system_prompt(
            "persona",
            "tools",
            [],
            governance_prompt="L0 governance",
        )

        self.assertTrue(prompt.endswith("L0 governance"))

    def test_d14_workflow_sop_is_a_registered_dynamic_template(self) -> None:
        governance = GroupPromptGovernance()

        prompt = governance.render_dynamic(
            "update_workflow_sop",
            feature_run_id="run-1",
            feature_id="F001",
            stage="implementation",
            state="active",
            role="owner",
            canonical_doc="docs/features/F001-example/feature.md",
            suggested_skills="$worktree, $tdd",
            current_gate="implementation-complete",
            next_step="Create the isolated worktree, then implement AC-6.",
        )

        self.assertIn("D14 — update-workflow-sop", prompt)
        self.assertIn("FeatureRun: run-1 | Feature: F001", prompt)
        self.assertIn("Stage: implementation | State: active | Role: owner", prompt)
        self.assertIn("Suggested skill(s): $worktree, $tdd", prompt)
        self.assertIn(
            "Next step: Create the isolated worktree, then implement AC-6.",
            prompt,
        )


if __name__ == "__main__":
    unittest.main()
