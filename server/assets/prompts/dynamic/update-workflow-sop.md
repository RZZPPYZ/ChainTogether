<!-- D14 — update-workflow-sop -->
== Active Feature Workflow (D14 — update-workflow-sop) ==

FeatureRun: $feature_run_id | Feature: $feature_id
Stage: $stage | State: $state | Role: $role
Canonical doc: $canonical_doc
Suggested skill(s): $suggested_skills
Current gate: $current_gate
Next step: $next_step

Read the canonical Feature Doc before acting and load the suggested skill that
matches your assigned role. This D14 block is refreshed from durable workflow
state on every routed agent turn. GroupInvocation custody is separate from the
FeatureRun stage. Return evidence to the control plane; do not claim or perform
a stage transition in chat. Only the assigned reviewer or vision guardian may
issue that gate's verdict.

For this autonomous FeatureRun, a successful Feature MCP mutation is the only
role-handoff mechanism. It durably schedules the required actor in a fresh
GroupInvocation. After the mutation commits, end naturally without an @handle;
do not also use the ordinary L0 HANDOFF route for the same lifecycle step.
