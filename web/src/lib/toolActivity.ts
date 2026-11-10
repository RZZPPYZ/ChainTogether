import type { Message } from "../stores/sessionStore";

/**
 * Pure derivation layer for the chat "activity trail".
 *
 * The backend streams a tool call as two separate messages (a `tool_use`
 * followed by the matching `tool_result`, joined by `tool_use_id`). Rendering
 * each one as its own card makes a long agent turn read like a pile of
 * machinery. This module folds consecutive tool messages into grouped
 * "steps" so the chat can show a quiet, collapsible trail instead — without
 * touching the store shape or the wire protocol.
 */

export type ToolStepStatus = "running" | "ok" | "error";

export interface ToolStep {
  /** Stable key: the tool_use_id when present, else a message-index fallback. */
  id: string;
  toolName: string;
  input: Record<string, unknown>;
  result?: string;
  isError: boolean;
  status: ToolStepStatus;
  toolUseId?: string;
  /** Original message indices composing this step (use + first result). */
  messageIndexes: number[];
}

export interface ToolActivityRenderItem {
  kind: "activity";
  /** Stable group key — the first step's tool_use_id when available. */
  id: string;
  steps: ToolStep[];
  /** Original index of the first message in the group. */
  messageIndex: number;
  /** True once a `result` message appears after this group (turn ended). */
  turnEnded: boolean;
}

export interface MessageRenderItem {
  kind: "message";
  id: string;
  message: Message;
  messageIndex: number;
}

export type ChatRenderItem = MessageRenderItem | ToolActivityRenderItem;

export interface ChatRenderResult {
  items: ChatRenderItem[];
  /**
   * Original message index → render item index (-1 for messages that produce
   * no render item, e.g. empty `thinking` rows).
   */
  messageToItemIndex: number[];
}

export function isToolActivityMessage(message: Message): boolean {
  return message.type === "tool_use" || message.type === "tool_result";
}

/**
 * Messages that are persisted in the transcript but produce no render item.
 * Only EMPTY thinking rows are hidden: they carry no content (a redacted or
 * blank thought) and must not split a run of tool calls. Non-empty thinking
 * rows render as their own collapsible blocks.
 */
function isHiddenMessage(message: Message): boolean {
  return message.type === "thinking" && !messageContent(message).trim();
}

function messageContent(message: Message): string {
  const content: unknown = message.content;
  if (typeof content === "string") return content;
  return content == null ? "" : String(content);
}

function messageRenderId(message: Message, index: number): string {
  return typeof message.seq === "number" ? `msg-${message.seq}` : `msg-idx-${index}`;
}

function createUseStep(message: Message, index: number): ToolStep {
  const toolUseId = message.tool_use_id;
  return {
    id: toolUseId ? `use-${toolUseId}` : `use-idx-${index}`,
    toolName: message.tool_name || "Tool",
    input: message.tool_input ?? {},
    status: "running",
    isError: false,
    toolUseId,
    messageIndexes: [index],
  };
}

function createOrphanResultStep(message: Message, index: number): ToolStep {
  const toolUseId = message.tool_use_id;
  const isError = !!message.is_error;
  return {
    id: `result-${toolUseId ?? `idx-${index}`}`,
    toolName: message.tool_name || "Result",
    input: {},
    result: messageContent(message),
    isError,
    status: isError ? "error" : "ok",
    toolUseId,
    messageIndexes: [index],
  };
}

/**
 * Turn a flat message list into render items: conversational messages stay
 * one-per-item; consecutive tool_use/tool_result messages collapse into one
 * activity item. Hidden `thinking` rows are skipped without breaking the
 * group. Anything visible that is not a tool message (text, notice, error,
 * approval request, question, result badge, …) breaks the group and renders
 * inline as before.
 */
export function buildChatRenderItems(
  messages: readonly Message[],
): ChatRenderResult {
  const items: ChatRenderItem[] = [];
  const messageToItemIndex = new Array<number>(messages.length).fill(-1);

  let groupSteps: ToolStep[] | null = null;
  let groupMessageIndexes: number[] = [];
  let groupFirstIndex = -1;
  let pendingByToolUseId = new Map<string, ToolStep>();

  const flushGroup = () => {
    if (!groupSteps || groupSteps.length === 0) {
      groupSteps = null;
      groupMessageIndexes = [];
      groupFirstIndex = -1;
      pendingByToolUseId = new Map();
      return;
    }
    const itemIndex = items.length;
    const first = groupSteps[0];
    items.push({
      kind: "activity",
      id: `activity-${first.toolUseId ?? `idx-${groupFirstIndex}`}`,
      steps: groupSteps,
      messageIndex: groupFirstIndex,
      turnEnded: false,
    });
    for (const messageIndex of groupMessageIndexes) {
      messageToItemIndex[messageIndex] = itemIndex;
    }
    groupSteps = null;
    groupMessageIndexes = [];
    groupFirstIndex = -1;
    pendingByToolUseId = new Map();
  };

  for (let index = 0; index < messages.length; index++) {
    const message = messages[index];

    // Empty thinking rows render nothing — skip them without breaking the
    // current tool group. Visible thinking (non-empty) flushes below.
    if (isHiddenMessage(message)) continue;

    if (!isToolActivityMessage(message)) {
      flushGroup();
      messageToItemIndex[index] = items.length;
      items.push({
        kind: "message",
        id: messageRenderId(message, index),
        message,
        messageIndex: index,
      });
      continue;
    }

    if (!groupSteps) {
      groupSteps = [];
      groupMessageIndexes = [];
      groupFirstIndex = index;
      pendingByToolUseId = new Map();
    }
    groupMessageIndexes.push(index);

    if (message.type === "tool_use") {
      const step = createUseStep(message, index);
      groupSteps.push(step);
      // Keep the FIRST step for an id — a duplicated id must not steal the
      // result from the original call.
      if (step.toolUseId && !pendingByToolUseId.has(step.toolUseId)) {
        pendingByToolUseId.set(step.toolUseId, step);
      }
      continue;
    }

    const matched = message.tool_use_id
      ? pendingByToolUseId.get(message.tool_use_id)
      : undefined;
    if (!matched) {
      // A result with no use in this group still renders as its own step.
      groupSteps.push(createOrphanResultStep(message, index));
      continue;
    }
    // First result wins; duplicates are ignored (and never crash).
    if (matched.result === undefined) {
      matched.result = messageContent(message);
      matched.isError = !!message.is_error;
      matched.status = matched.isError ? "error" : "ok";
      matched.messageIndexes.push(index);
    }
  }
  flushGroup();

  // A group belongs to a finished turn once a `result` badge appears after it.
  let sawResult = false;
  for (let index = items.length - 1; index >= 0; index--) {
    const item = items[index];
    if (item.kind === "message") {
      if (item.message.type === "result") sawResult = true;
    } else {
      item.turnEnded = sawResult;
    }
  }

  return { items, messageToItemIndex };
}

export type ToolIconKind =
  | "terminal"
  | "file"
  | "edit"
  | "search"
  | "world"
  | "tool";

export interface ToolStepDescription {
  icon: ToolIconKind;
  /** Compact label used in group headers ("Bash 3"). */
  label: string;
  /** Verb on the primary line ("Ran", "Read", …). */
  verb: string;
  /** Mono target rendered after the verb. */
  target: string;
  /** Right-aligned hint ("exit 0", "3 lines", …). */
  hint: string;
  hintTone: "default" | "running" | "error";
}

export interface ToolActivitySummary {
  total: number;
  counts: Array<{ label: string; count: number }>;
  failed: number;
}

export function toolLabel(toolName: string): string {
  switch (toolName) {
    case "Bash":
    case "command_execution":
      return "Bash";
    case "Read":
    case "file_read":
      return "Read";
    case "Edit":
    case "file_edit":
      return "Edit";
    case "Write":
    case "file_write":
      return "Write";
    case "Grep":
      return "Grep";
    case "Glob":
      return "Glob";
    case "WebFetch":
      return "Fetch";
    case "WebSearch":
      return "Search";
    case "mcp__bg__run":
      return "bg";
    case "mcp__ask_agent__ask":
      return "Ask";
    default:
      return toolName || "Tool";
  }
}

export function summarizeToolActivity(
  steps: readonly ToolStep[],
): ToolActivitySummary {
  const counts = new Map<string, number>();
  let failed = 0;
  for (const step of steps) {
    const label = toolLabel(step.toolName);
    counts.set(label, (counts.get(label) ?? 0) + 1);
    if (step.status === "error") failed++;
  }
  return {
    total: steps.length,
    counts: [...counts].map(([label, count]) => ({ label, count })),
    failed,
  };
}

function firstString(
  input: Record<string, unknown>,
  keys: readonly string[],
): string | undefined {
  for (const key of keys) {
    const value = input[key];
    if (typeof value === "string" && value.length > 0) return value;
  }
  return undefined;
}

function compactLine(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(1, maxLength - 1))}…`;
}

function lineCount(text: string): number {
  const trimmed = text.replace(/[\r\n]+$/, "");
  return trimmed.length === 0 ? 0 : trimmed.split(/\r?\n/).length;
}

function countNonEmptyLines(text: string): number {
  return text.split(/\r?\n/).filter((line) => line.trim().length > 0).length;
}

function parseExitCode(text: string): number | null {
  const match = text.match(/\bexit(?:\s+code)?[:\s]+(\d+)\b/i);
  return match ? Number(match[1]) : null;
}

function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

/**
 * First-line preview of a tool result. JSON payloads are compacted first;
 * unparseable text falls back to its raw first line. Always truncated.
 */
export function cleanToolResultPreview(
  text: string | undefined,
  maxLength = 100,
): string {
  const raw = (text ?? "").trim();
  if (!raw) return "";
  let candidate = raw.split(/\r?\n/, 1)[0] ?? "";
  try {
    const parsed: unknown = JSON.parse(raw);
    if (parsed !== null && typeof parsed === "object") {
      candidate = JSON.stringify(parsed);
    } else if (typeof parsed === "string") {
      candidate = parsed.split(/\r?\n/, 1)[0] ?? "";
    }
  } catch {
    // Not JSON — keep the raw first line.
  }
  return truncateText(candidate.trim(), maxLength);
}

function editDiffHint(input: Record<string, unknown>): string | null {
  const oldText = firstString(input, [
    "old_string",
    "old_text",
    "old_str",
    "before",
  ]);
  const newText = firstString(input, [
    "new_string",
    "new_text",
    "new_str",
    "content",
    "after",
  ]);
  if (oldText === undefined && newText === undefined) return null;
  const added = newText === undefined ? 0 : lineCount(newText);
  const removed = oldText === undefined ? 0 : lineCount(oldText);
  if (added === 0 && removed === 0) return "edit";
  return `+${added} −${removed}`;
}

/**
 * Rule-based, single-line description of a tool step. Never calls a model and
 * never loads extra data — the hint is derived from the messages we already
 * have. Unknown shapes degrade to the tool name + cleaned result preview.
 */
export function describeToolStep(step: ToolStep): ToolStepDescription {
  const input = step.input;
  const name = step.toolName || "Tool";
  const lower = name.toLowerCase();
  const result = step.result ?? "";
  const running = step.status === "running";
  const hintTone: ToolStepDescription["hintTone"] =
    step.status === "error" ? "error" : running ? "running" : "default";

  if (name === "mcp__bg__run") {
    const command = firstString(input, ["command"]) ?? "";
    const description = firstString(input, ["description"]);
    return {
      icon: "terminal",
      label: toolLabel(name),
      verb: "Started bg task",
      target: truncateText(compactLine(description ?? command), 60),
      hint: running ? "running" : "bg",
      hintTone,
    };
  }

  if (name === "mcp__ask_agent__ask") {
    return {
      icon: "tool",
      label: toolLabel(name),
      verb: "Asked",
      target: firstString(input, ["name"]) ?? "agent",
      hint: running ? "running" : step.status === "error" ? "failed" : "replied",
      hintTone,
    };
  }

  if (name === "Bash" || lower === "command_execution" || lower === "bash") {
    const command = firstString(input, ["command", "cmd"]) ?? "";
    const exitCode = parseExitCode(result);
    return {
      icon: "terminal",
      label: "Bash",
      verb: "Ran",
      target: truncateText(compactLine(command), 60),
      hint: running
        ? "running"
        : exitCode !== null
          ? `exit ${exitCode}`
          : step.status === "error"
            ? "failed"
            : "exit 0",
      hintTone,
    };
  }

  if (name === "Read" || lower === "file_read") {
    const lines = lineCount(result);
    return {
      icon: "file",
      label: "Read",
      verb: "Read",
      target: firstString(input, ["file_path", "path", "file"]) ?? "",
      hint: running
        ? "running"
        : `${lines} ${lines === 1 ? "line" : "lines"}`,
      hintTone,
    };
  }

  if (
    name === "Edit" ||
    name === "Write" ||
    lower === "file_edit" ||
    lower === "file_write"
  ) {
    const diff = editDiffHint(input);
    return {
      icon: "edit",
      label: name === "Write" ? "Write" : "Edit",
      verb: "Edited",
      target: firstString(input, ["file_path", "path", "file"]) ?? "",
      hint: running ? "running" : diff ?? "edit",
      hintTone,
    };
  }

  if (name === "Grep" || name === "Glob") {
    const pattern = firstString(input, ["pattern", "query"]) ?? "";
    const matches = countNonEmptyLines(result);
    return {
      icon: "search",
      label: name,
      verb: "Searched",
      target: pattern ? `"${pattern}"` : "",
      hint: running
        ? "running"
        : `${matches} ${matches === 1 ? "match" : "matches"}`,
      hintTone,
    };
  }

  if (name === "WebFetch" || name === "WebSearch") {
    const url = firstString(input, ["url", "uri"]);
    const query = firstString(input, ["query"]);
    const preview = cleanToolResultPreview(result, 60);
    return {
      icon: "world",
      label: toolLabel(name),
      verb: url ? "Fetched" : "Searched",
      target: url
        ? hostOf(url)
        : query
          ? `"${truncateText(compactLine(query), 60)}"`
          : "",
      hint: running ? "running" : preview,
      hintTone,
    };
  }

  return {
    icon: "tool",
    label: toolLabel(name),
    verb: name,
    target: step.result === undefined ? "" : cleanToolResultPreview(result, 100),
    hint: running ? "running" : "",
    hintTone,
  };
}

export function toolStepInputText(step: ToolStep): string {
  if (Object.keys(step.input).length === 0) return "";
  try {
    return JSON.stringify(step.input, null, 2);
  } catch {
    return String(step.input);
  }
}

export function toolStepOutputText(step: ToolStep): string {
  return step.result ?? "";
}
