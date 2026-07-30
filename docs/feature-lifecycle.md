# Group Feature Lifecycle

ChainTogether treats a feature as a durable project object, not as one agent
turn. A `FeatureRun` survives group messages, agent handoffs, worktrees,
reviews, merges, and final acceptance. Its canonical human-readable record is
`docs/features/FNNN-kebab-case/feature.md`.

This lifecycle is group-first. A group invocation owns the ball for one routed
message; the linked FeatureRun owns product progress across all invocations.

## Sources of truth

| Concern | Canonical source | Derived/runtime form |
|---|---|---|
| Feature intent, ACs, decisions, verdicts | `docs/features/FNNN-*/feature.md` | `docs/features/index.{md,json}` |
| State machine and gates | `.chaintogether/workflows/feature-lifecycle.yaml` | `feature_runs` and `feature_run_events` |
| Skill content | `.chaintogether/skills/<name>/` | `.claude/skills/` and `.codex/skills/` |
| Skill inventory and provider mounts | `.chaintogether/skills.yaml` | sync report |
| One group-message custody chain | `group_invocations` | in-memory `GroupRunState` |
| Feature ↔ invocation relation | `feature_invocation_links` | `feature_run_id` in API responses |

Do not edit `.claude/skills/` or `.codex/skills/` directly. They are generated
provider views. Claude Code and Codex therefore consume the same skill text,
while provider-only metadata such as `agents/openai.yaml` remains colocated
with the canonical skill package.

## Lifecycle

```mermaid
flowchart LR
  D["Discovery\ninterview · research · convergence"] --> G["Design Gate"]
  G --> P["Plan"]
  P --> I["Worktree + TDD"]
  I --> Q["Quality Gate"]
  Q --> R["Independent Review"]
  R --> M["Merge Gate"]
  M --> V["Vision Gate"]
  V --> C["Closure"]
  C --> X["Done"]
  G -. changes required .-> D
  Q -. failed .-> I
  R -. request changes .-> I
  V -. vision or delivery gap .-> D
```

The Discovery Loop makes the problem explicit before code:

1. `feature-discovery` interviews the operator, captures the verbatim signal,
   defines the scope unit and user journey, and turns ambiguity into questions.
2. Research records evidence and alternatives instead of filling gaps by
   intuition.
3. Discussion convergence records decisions and rejected alternatives. The
   disagreement trail is part of the artifact, not disposable chat.

The Delivery Loop turns the approved Feature Doc into accepted behavior:

1. `design-gate` checks ownership, boundaries, extension points, risks, and
   testability. The `Design Gate` section must say `Verdict: approved` before
   planning.
2. `writing-plans` decomposes work by AC and identifies verification commands.
3. `worktree` isolates the change; `tdd` drives observable behavior from a
   failing test to the smallest implementation.
4. `quality-gate` supplies test/lint/build evidence. “AC green” is necessary,
   but independent review is still pending.
5. `request-review` creates a review packet; `review-feature` produces an
   independent verdict; `receive-review` resolves findings with evidence.
6. `merge-gate` verifies the reviewed revision is still the revision being
   merged and records merge/CI evidence.
7. `vision-gate` replays the promised user journey against the merged result.
   The guardian must be independent from owner and reviewer.
8. `close-feature` reconciles the Feature Doc, events, ACs, evidence, and final
   state. Only then may the feature become `done`.

Rollback edges are part of the workflow. A failed gate moves to a named earlier
stage with a reason; it never silently edits history to look linear.

## Group operation

1. Create a FeatureRun with `POST /api/groups/{group_id}/features`. This also
   creates the next canonical `FNNN` dossier in the group's working directory.
2. Assign distinct `owner_agent_id`, `reviewer_agent_id`, and
   `vision_guardian_agent_id` with `PATCH /api/features/{run_id}/roles`.
3. Send group work with `feature_run_id` on `POST /api/groups/{group_id}/send`.
4. The controller injects the FeatureRun ID, Feature ID, stage, role, canonical
   document path, current gate, and required skill into every routed agent turn.
5. Record evidence in the repository, then request a transition through
   `POST /api/features/{run_id}/transition`. The control plane validates the
   edge, actor, role separation, evidence, and canonical document verdict.
6. Audit the immutable trail with `GET /api/features/{run_id}/events`.

An invocation may pass among several group agents without changing the feature
stage. Conversely, one feature stage may span many invocations. Agents report
evidence; only the control plane records the transition.

## Review handoff contract

When asking another agent to review, the handoff must make the review
reproducible without reconstructing intent from group history:

- FeatureRun ID, Feature ID, and canonical Feature Doc path.
- Exact review scope and the ACs/requirements it is meant to satisfy.
- Base revision and reviewed HEAD revision; state whether the worktree is clean.
- Changed paths and a short architecture/behavior summary.
- Commands run and their exact outcomes, plus links/paths to quality evidence.
- Known risks, intentional omissions, unresolved questions, and rejected
  alternatives that constrain the review.
- Requested reviewer output: findings by severity with file/line evidence,
  verdict (`approved` or `request_changes`), and residual risk.

The author cannot be the reviewer. A review verdict applies only to the named
HEAD; later changes make it stale and return the feature to review. The reviewer
updates `Review Provenance` before the control plane accepts `review -> merge`.

For direct agent delegation, use the same packet and include the FeatureRun ID.
Delegation is a transport choice, not a second lifecycle: the child agent must
read the same Feature Doc and return evidence to the parent/group control plane.

## Repository checks

```powershell
python scripts/check-features.py --write-index
python scripts/check-skills.py
python scripts/sync-skills.py
python scripts/sync-skills.py --check
python -m unittest discover -s tests -v
```

`sync-skills.py` refuses to overwrite unmanaged provider content and writes a
provenance hash into managed copies. `--check` detects drift without modifying
files. Feature validation checks schema, directory/ID consistency, required
sections, role separation, Design Gate approval, and final AC/Vision truth.
