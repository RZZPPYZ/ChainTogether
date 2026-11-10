# Model thinking / reasoning visibility

## 1. What

Provider-supplied reasoning is captured, persisted, and shown in a session's
chat as collapsible **Thinking** blocks.

Sources:

- **Claude Code**: `thinking` content blocks from the `assistant` stream-json
  events (`server/harness/claude_code.py`).
- **Codex**: `reasoning` items from `item.completed`
  (`server/harness/codex.py`).

What providers send is not guaranteed to be raw chain-of-thought. Claude may
return summarized or redacted thinking, and Codex exposes reasoning summaries;
whatever the provider emits is what this app can show.

## 2. Event flow

1. The harness parser emits `HarnessEvent(type="thinking", content=...)`.
2. `SessionManager._event_to_message_content` persists it as
   `messages.type = 'thinking'` (assistant role), so it survives reloads and is
   available to fork/archive snapshots.
3. `SessionManager._event_to_ws_message` broadcasts it live as:

   ```json
   { "type": "assistant_thinking", "session_id": "...", "content": "..." }
   ```

   The WS event carries the persisted row's `seq`, so the existing
   `lastAppliedSeq` dedupe works exactly like text/tool events.
4. Empty/whitespace-only thinking is dropped at both layers: it has no useful
   content and would only add empty rows and sequence churn.

## 3. UI

- `useWebSocket` appends live `assistant_thinking` events as `thinking`
  messages; `GET /api/sessions/{id}` returns persisted ones.
- `MessageBubble` renders a dashed, muted **Thinking** block with a char count.
  It is **collapsed by default**; clicking expands the reasoning (Markdown).
  Expanded text is deliberately quieter than normal assistant text: gray
  (`--muted-foreground`, applied to markdown descendants too) and `0.8rem`
  instead of the chat's `0.875rem`.
- `buildChatRenderItems` treats EMPTY thinking as invisible (it does not split
  a tool-call group), while non-empty thinking is a normal render item and
  therefore separates adjacent tool groups.
- Blank historical rows (from before this change) remain hidden.

## 4. Known limitations

- Thinking is **block-streamed, not token-streamed**: each `thinking` block is
  emitted after the CLI completes that assistant message, so the UI shows one
  block at a time rather than typing character-by-character. Token-level
  deltas would require `--include-partial-messages` and parsing
  `stream_event` deltas (plus dedupe/merge against the completed block).
- Group chat shows a **Reasoning** activity phase (from
  `GroupManager.record("thinking")`) but does not render the reasoning text in
  the group timeline yet.
- Visibility is currently per-block (expand on demand); there is no global
  "always show thinking" preference.
