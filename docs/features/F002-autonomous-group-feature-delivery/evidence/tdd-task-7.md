# F002 TDD Evidence - Task 7 Group /feature UX

## Red

`npm test -- --run src/lib/featureCommand.test.ts` is expected to fail before
implementation because the group command parser, role resolver, status surface,
and `/feature` request routing do not exist.

## Green

`npm test -- --run src/lib/featureCommand.test.ts src/components/GroupChatView.test.tsx`
passes 12 tests; `npm run typecheck` passes. The command avoids ordinary group
send, uses exact role grammar, exposes status/role actions, and preserves the
operator's exact draft on roster/API failure.
