# F002 TDD Evidence - Task 2 Atomic Start

## Red

Command:

```text
..\..\.venv\Scripts\python.exe -m unittest tests.test_feature_delivery_start -v
```

The suite failed to import because `server.feature_delivery` did not exist.
The committed behavior tests already define the required boundary: zero-side-
effect roster rejection, deterministic three-role assignment, one atomic
checkpoint, same-key replay, distinct-key active-pointer arbitration, policy-
bounded authorization, and create-only document recovery.

## Green

Implemented:

- stable live-member ordering and valid-default owner selection;
- complete, distinct per-run owner/reviewer/guardian assignments;
- one `BEGIN IMMEDIATE` transaction for request, run, roles, event, active
  pointer, create-only document image, authorization, and initial dispatch;
- request-key replay/mismatch handling and one-active-run arbitration;
- crash-safe create-only document publication and checkpoint recovery;
- policy-bounded run authorization that explicitly denies force push, policy
  bypass, deployment, and unrelated external effects.

Focused verification: `5` behavior tests passed, including concurrent same-key
and different-key starts plus injected document delivery failure.

Regression verification: `31` Feature/lifecycle tests and `compileall` passed.
