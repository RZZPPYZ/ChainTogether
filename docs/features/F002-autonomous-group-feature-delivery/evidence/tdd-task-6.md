# F002 TDD Evidence - Task 6 Dispatch Runtime

## Red

`python -m unittest tests.test_feature_dispatch_runtime -v` is expected to fail
before implementation because there is no `FeatureTurnAuthority`, no exact group
dispatch launcher, and no automatic pending-dispatch driver.

## Green

`python -m unittest tests.test_feature_dispatch_runtime -v` passes five tests.
Evidence covers automatic launch, target-only ephemeral authority, original
request recording without secrets, restart lease reclaim, and a complete
multi-round Review/fix/re-review/Merge/Vision/Closure journey whose every
dispatch-linked invocation starts at depth zero.
