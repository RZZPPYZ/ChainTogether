# A2A circuit dynamic prompt quality report

Verdict: **pass**

Operator intent: keep A2A circuit-breaker enforcement in code, move its Agent-facing
prompt text into the dynamic Markdown layer, and inject that directive on the next
relevant Agent turn.

## Evidence

| Requirement | Evidence |
|---|---|
| Circuit text is a registered dynamic asset | `test_a2a_pingpong_block_is_a_registered_dynamic_template` |
| Hard breaker renders the Markdown instead of embedding prose | `test_pingpong_breaker_uses_dynamic_template_content` |
| A persisted ping-pong block resumes through trusted template rendering | `test_persisted_pingpong_block_resumes_with_trusted_dynamic` |
| Plain blocked errors are never promoted to controller directives | `test_blocked_resume_does_not_promote_plain_error` |
| Existing routing and feature behavior remains intact | Full `unittest` discovery: 101 passed, 1 skipped |

## Commands

- `..\..\.venv\Scripts\python.exe -m unittest tests.test_prompt_governance tests.test_group_routing -v` — 18 passed.
- `..\..\.venv\Scripts\python.exe -m unittest discover -s tests -q` — 101 passed, 1 skipped.
- `..\..\.venv\Scripts\python.exe -m compileall -q server tests` — passed.
- `git diff --check` — passed.

## Residual risk

The visible group transcript notice still uses the existing controller-message
transport for frontend compatibility. Its body now comes from the same trusted
dynamic Markdown. Persisted recovery stores only an allowlisted template key and
validated values; the next Agent receives a freshly rendered trusted directive,
never the generic invocation error text.
