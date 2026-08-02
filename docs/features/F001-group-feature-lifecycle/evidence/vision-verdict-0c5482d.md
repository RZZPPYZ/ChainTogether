# F001 independent Vision Gate verdict

- Guardian: `f001_vision_guardian`
- Merged revision: `0c5482d95fc56ec6ab3b63382134c3e55d370905`
- Verdict: `accepted`
- Independence: guardian differs from author `codex` and reviewer
  `f001_reviewer`

## Journey evidence

1. Creating a FeatureRun persists it as the group's active Feature. Later group
   messages inherit that Feature without resupplying its ID, and each actual
   Agent turn rerenders D14 from durable state.
2. D14 supplies FeatureRun, Feature, stage, state, role, canonical doc,
   suggested Skill, current gate, and next step. Review routes owner and
   reviewer differently; Acceptance routes `vision-gate` only to the guardian.
3. Role collisions, author self-review, invalid Session capability, missing
   evidence, wrong Git revision, and inconsistent canonical provenance all fail
   closed without advancing the protected state.
4. FeatureRun CAS, immutable event, and Feature Doc outbox share one control
   path. Workflow, 13 canonical Skills, 26 provider mounts, and the Feature
   validator agree on the lifecycle.
5. The merged behavior is a group-first, cross-message, cross-Agent durable
   lifecycle control plane rather than a single-Agent delegation wrapper.

No vision deviation requires return. `/feature <requirement>`, automatic role
assignment, Agent-callable transition MCP, automated @handoff, and one-sentence
continuous orchestration are explicitly separated into F002.

## Verification and residual risks

- Four core Feature/group/gate/capability journeys passed.
- Two Skill contract and next-step tests passed.
- Skill, provider mount, Feature, and whitespace validators passed.
- The protocol is single-control-plane-process rather than a distributed file
  transaction; capability secrecy depends on process environment isolation;
  slow disk can extend the Feature write lock; full external Claude/Codex
  product E2E remains future evidence.
