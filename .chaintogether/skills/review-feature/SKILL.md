---
name: review-feature
description: Independently review a ChainTogether feature's exact branch and HEAD against original intent, approved design, acceptance criteria, tests, architecture, security, and user journey. Use when assigned as reviewer through a review packet; do not use when you authored the reviewed changes or when the target SHA is unavailable.
---

# Review Feature

1. Confirm you are not the author and the target HEAD matches the packet.
2. Read the operator quote and Feature Doc before reading the author's conclusions.
3. Inspect the full diff from `base_sha` to `head_sha`.
4. Verify critical claims independently. Run focused tests and the real user journey when feasible.
5. Sweep correctness, state transitions, failure handling, concurrency, security, compatibility, performance, maintainability, documentation, and missing tests.
6. Distinguish code defects from spec/design defects. Return design defects to the appropriate gate.
7. Do not edit the branch while acting as reviewer. A takeover requires an explicit role change and a new reviewer.

Report findings as P1/P2/P3 with evidence and tight locations. Finish with a verdict and the exact reviewed HEAD. Silence is not approval.
