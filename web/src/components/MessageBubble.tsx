import { useState } from "react";
import {
  IconChevronDown,
  IconChevronRight,
  IconFile,
  IconGitFork,
  IconRobot,
} from "@tabler/icons-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import {
  useSessionStore,
  type AttachmentMetadata,
  type Message,
} from "../stores/sessionStore";
import {
  formatTokenCount,
  turnTokenCount,
  turnTokenTitle,
} from "../lib/tokens";
import {
  AgentDelegationEventCard,
  parseDelegationEvent,
} from "./AgentDelegationEventCard";

// Marker the backend prepends to the synthesized user message it
// injects when a bg task completes. Used to render those messages
// with a distinct "auto" badge so the user knows they didn't type it.
// Source of truth: server/bg_tasks.py render_delivery_prompt.
const BG_TASK_RESULT_PREFIX = "[bg-task-result]";

interface MessageBubbleProps {
  message: Message;
  sessionId: string;
  // Name + avatar of the agent that owns this session, used to label
  // assistant turns. Falls back to a harness-neutral "Assistant" when the
  // session has no owning agent.
  agentName?: string;
  agentAvatar?: string | null;
  // "Fork from here" affordance (session-rewind.md §6.1): rendered on
  // user messages when set + the message has a known seq. Called with the
  // rewind target seq.
  onFork?: (seq: number) => void;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function AttachmentList({
  attachments,
  sessionId,
}: {
  attachments: AttachmentMetadata[];
  sessionId: string;
}) {
  const token = useSessionStore((s) => s.token);
  return (
    <div className="msg-attachments mt-2 flex flex-wrap gap-2">
      {attachments.map((a) => {
        // Token is appended as a query param because <img src> and
        // <a download> can't carry custom headers. Same auth value as the
        // bearer header — the server accepts either.
        const url = `${window.location.origin}/api/sessions/${encodeURIComponent(
          sessionId
        )}/attachments/${encodeURIComponent(a.id)}?token=${encodeURIComponent(token)}`;
        const isImage = a.mime_type.startsWith("image/");
        if (isImage) {
          return (
            <a
              key={a.id}
              href={url}
              target="_blank"
              rel="noreferrer"
              className="attachment-thumb block rounded-md border border-border overflow-hidden bg-muted/40 hover:border-primary/60 transition-colors"
              title={`${a.filename} (${formatBytes(a.size)})`}
            >
              <img
                src={url}
                alt={a.filename}
                className="block max-h-40 max-w-[16rem] object-contain"
              />
            </a>
          );
        }
        return (
          <a
            key={a.id}
            href={url}
            download={a.filename}
            target="_blank"
            rel="noreferrer"
            className="attachment-chip inline-flex items-center gap-2 rounded-md border border-border bg-muted/40 px-2.5 py-1.5 text-xs text-foreground hover:border-primary/60 transition-colors"
          >
            <IconFile size={14} className="text-muted-foreground shrink-0" />
            <span className="font-medium truncate max-w-[12rem]">{a.filename}</span>
            <span className="text-muted-foreground">{formatBytes(a.size)}</span>
          </a>
        );
      })}
    </div>
  );
}

export function MessageBubble({
  message,
  sessionId,
  agentName,
  agentAvatar,
  onFork,
}: MessageBubbleProps) {
  const assistantLabel = agentName || "Assistant";
  // Mirror the header's avatar treatment: show the agent's emoji, falling
  // back to the default octopus when an agent exists but set no avatar.
  const assistantAvatar = agentName ? agentAvatar || "🐙" : null;
  switch (message.type) {
    case "text":
      if (message.role === "user") {
        const isBgResult =
          typeof message.content === "string" &&
          message.content.startsWith(BG_TASK_RESULT_PREFIX);
        if (isBgResult) {
          return <BgTaskResultMessage content={message.content as string} />;
        }
        // Agent-to-agent delegation injection (reply / question /
        // error). The DelegationManager injects these as user-message
        // turns starting with a `[agent-…:<name> delegation=…]` prefix.
        const delegationEvent = parseDelegationEvent(
          typeof message.content === "string" ? message.content : undefined
        );
        if (delegationEvent) {
          return <AgentDelegationEventCard event={delegationEvent} />;
        }
        return (
          <div className="msg msg-user group flex justify-end">
            <div className="max-w-[85%] space-y-1">
              <div className="msg-label flex items-center justify-end gap-2 text-xs font-semibold text-muted-foreground">
                {onFork && typeof message.seq === "number" && (
                  <button
                    type="button"
                    data-testid="fork-from-here"
                    className="fork-from-here inline-flex items-center gap-1 font-normal text-muted-foreground/70 opacity-0 transition-opacity hover:text-primary group-hover:opacity-100"
                    title="Rewind to this message and redo it"
                    onClick={() => onFork(message.seq as number)}
                  >
                    <IconGitFork size={12} />
                    Rewind to here
                  </button>
                )}
                <span>You</span>
              </div>
              <div className="msg-content inline-block rounded-lg border border-primary/60 bg-card px-4 py-3 text-sm text-foreground whitespace-pre-wrap break-words">
                {message.content}
              </div>
              {message.attachments && message.attachments.length > 0 && (
                <AttachmentList
                  attachments={message.attachments}
                  sessionId={sessionId}
                />
              )}
            </div>
          </div>
        );
      }
      return (
        <div className="msg msg-assistant space-y-1">
          <div className="msg-label flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
            {assistantAvatar && (
              <span aria-hidden className="text-sm leading-none">
                {assistantAvatar}
              </span>
            )}
            <span>{assistantLabel}</span>
          </div>
          <div className="msg-content markdown rounded-lg border border-border bg-card px-4 py-3 text-sm leading-relaxed">
            <Markdown
              remarkPlugins={[remarkGfm, remarkMath]}
              rehypePlugins={[rehypeKatex]}
            >
              {message.content || ""}
            </Markdown>
          </div>
        </div>
      );

    // Tool calls no longer render as standalone cards — ChatView folds them
    // into ToolActivityGroup before they reach this component.
    case "tool_use":
    case "tool_result":
      return null;

    case "tool_approval_request":
    case "question_request":
      return null; // handled by ToolApproval / QuestionPrompt component

    case "question_answer":
      return (
        <div className="msg msg-user flex justify-end">
          <div className="max-w-[85%] space-y-1">
            <div className="msg-label text-xs font-semibold text-muted-foreground text-right">
              You
            </div>
            <div className="msg-content msg-question-answer inline-block rounded-lg border border-primary/60 bg-card px-4 py-3 text-sm text-foreground italic whitespace-pre-wrap break-words">
              {message.content}
            </div>
          </div>
        </div>
      );

    case "result": {
      const usage = message.context_usage;
      const tokenLabel = formatTokenCount(turnTokenCount(usage));
      return (
        <div className="msg msg-system flex justify-center py-1">
          <span
            className="result-badge text-[11px] font-medium text-muted-foreground bg-muted px-2.5 py-1 rounded-full"
            title={turnTokenTitle(usage)}
          >
            Done{tokenLabel ? ` · ${tokenLabel} tokens` : ""}
          </span>
        </div>
      );
    }

    // Ephemeral, client-side system note (e.g. the /schedule command's
    // confirmation or a parse-error hint). Centered pill, not attributed to
    // the user or to Claude. Not persisted — clears on reload.
    case "notice":
      return (
        <div className="msg msg-notice flex justify-center py-1">
          <span
            className={`notice-pill max-w-[85%] rounded-full border px-3 py-1 text-xs ${
              message.is_error
                ? "border-destructive/30 bg-destructive/10 text-destructive"
                : "border-border bg-muted text-muted-foreground"
            }`}
          >
            {message.content}
          </span>
        </div>
      );

    case "error":
      return (
        <div className="msg msg-error space-y-1">
          <div className="msg-label text-xs font-semibold text-destructive">
            Error
          </div>
          <div className="msg-content rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive whitespace-pre-wrap break-words">
            {message.content}
          </div>
        </div>
      );

    default:
      return null;
  }
}

function BgTaskResultMessage({ content }: { content: string }) {
  const [expanded, setExpanded] = useState(false);
  // Strip the marker for display — it's only a routing hint, not part
  // of the human-facing text.
  const stripped = content.startsWith(BG_TASK_RESULT_PREFIX)
    ? content.slice(BG_TASK_RESULT_PREFIX.length).trimStart()
    : content;
  // Show only the first line collapsed; that line is the "finished
  // with status …" summary which is the most-important info.
  const firstLine = stripped.split("\n", 1)[0];
  return (
    <div className="msg msg-bg-result flex justify-end">
      <div className="max-w-[85%] space-y-1">
        <div className="msg-label text-xs font-semibold text-muted-foreground text-right flex items-center justify-end gap-1.5">
          <IconRobot size={12} className="text-muted-foreground" />
          <span>Auto · bg-task result</span>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="msg-content w-full text-left inline-block rounded-lg border border-dashed border-border bg-muted/30 px-4 py-3 text-sm text-foreground hover:bg-muted/50 transition-colors"
          title={expanded ? "Collapse" : "Expand full result"}
          aria-expanded={expanded}
        >
          <div className="flex items-start gap-2">
            <span className="text-muted-foreground shrink-0 mt-0.5">
              {expanded ? <IconChevronDown size={12} /> : <IconChevronRight size={12} />}
            </span>
            {expanded ? (
              <pre className="m-0 flex-1 font-mono text-xs whitespace-pre-wrap break-words">
                {stripped}
              </pre>
            ) : (
              <span className="flex-1">{firstLine}</span>
            )}
          </div>
        </button>
      </div>
    </div>
  );
}
