import type { Message } from "../stores/sessionStore";

const AUTO_INJECTED_PREFIXES = [
  "[bg-task-result]",
  "[agent-reply:",
  "[agent-question:",
  "[agent-error:",
  "[group-invocation:",
];

export interface MessageMarker {
  index: number;
  preview: string;
}

export function isUserAuthoredMessage(
  message: Pick<Message, "role" | "type" | "content">,
): boolean {
  if (message.role !== "user" || message.type !== "text") return false;
  const content = typeof message.content === "string" ? message.content : "";
  const trimmed = content.trimStart();
  return !AUTO_INJECTED_PREFIXES.some((prefix) => trimmed.startsWith(prefix));
}

export function messagePreview(
  content: string | undefined,
  maxLength = 56,
): string {
  const compact = (content ?? "").replace(/\s+/g, " ").trim();
  if (!compact) return "Message with attachments";
  return compact.length > maxLength
    ? `${compact.slice(0, maxLength - 3)}...`
    : compact;
}

export function buildUserMessageMarkers(
  messages: readonly Message[],
): MessageMarker[] {
  return messages.flatMap((message, index) =>
    isUserAuthoredMessage(message)
      ? [{ index, preview: messagePreview(message.content) }]
      : [],
  );
}
