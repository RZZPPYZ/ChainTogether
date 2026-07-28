import {
  useState,
  useRef,
  useMemo,
  useCallback,
  useEffect,
} from "react";
import {
  IconArrowUp,
  IconAlertCircle,
  IconAt,
  IconCheck,
  IconChevronDown,
  IconChevronRight,
  IconClock,
  IconLoader2,
  IconMenu2,
  IconMessageCircle,
  IconPlayerPlay,
  IconPlayerStop,
  IconTerminal2,
  IconUsers,
} from "@tabler/icons-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { exactTurnCostTitle, formatTurnCost } from "../lib/cost";
import {
  useSessionStore,
  reduceGroupAgentRun,
  type GroupAgentActivityEvent,
  type GroupAgentRun,
  type GroupInvocation,
  type Message,
} from "../stores/sessionStore";
import { Button } from "./ui/button";
import { MessageNavigator } from "./MessageNavigator";
import { buildUserMessageMarkers } from "../lib/messageNavigation";

const API = window.location.origin;

/** @-mention input detection. Unicode-aware so non-ASCII agent names
 * (中文, éàü, …) trigger + complete the same way ASCII ones do — JS's
 * bare `\w` is ASCII-only by default, which previously meant the
 * autocomplete dropdown never opened while typing `@悟空` and the
 * `@Alice ` inserted via insertMention couldn't be re-typed for a
 * Unicode name. `\p{L}` + `\p{N}` cover letters and digits across
 * scripts; `-` and `_` keep `Agent-1` / `Agent_2` working. `u` flag
 * required for `\p{…}`.
 *
 * Two surfaces share this:
 *   - handleInputChange: detect "user is typing a @-mention now"
 *   - insertMention: replace the partial `@…` portion with `@Name `
 * The exact pattern is a `const` so both stay in lock-step. */
const MENTION_PARTIAL_RE = /@([\p{L}\p{N}_-]*)$/u;

/** Build a regex that matches @-mentions of known group members.
 * Longest-first so `@Alice-Wonder` is tried before `@Alice`.
 * Boundary chars mirror the backend's `_TOKEN_BOUNDARY`. */
function buildMentionHighlightRe(
  names: string[],
): RegExp | null {
  if (names.length === 0) return null;
  const escaped = names
    .map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .sort((a, b) => b.length - a.length);
  // `\b` is ASCII-only so we use a custom left-boundary that also
  // catches CJK / Unicode: (?:^|[\s,.:;!?()\[\]{}<>,。！？、：；（）【】《》「」『』〈〉])
  const leftBoundary = "(^|[\\s,.:;!?()\\[\\]{}<>,\\u3000\\u3001\\u3002\\uFF01\\uFF1A\\uFF1B\\uFF08\\uFF09\\u3010\\u3011\\u300A\\u300B\\u300C\\u300D\\u300E\\u300F\\u3008\\u3009])";
  const rightBoundary = "(?=$|[\\s,.:;!?()\\[\\]{}<>,\\u3000\\u3001\\u3002\\uFF01\\uFF1A\\uFF1B\\uFF08\\uFF09\\u3010\\u3011\\u300A\\u300B\\u300C\\u300D\\u300E\\u300F\\u3008\\u3009])";
  return new RegExp(
    `${leftBoundary}@(${escaped.join("|")})${rightBoundary}`,
    "giu",
  );
}

/** Highlight @-mentions in a message body string, returning an
 * array of React nodes with mentions rendered as styled spans. */
export function highlightMentions(
  text: string,
  memberNames: string[],
): React.ReactNode[] {
  const re = buildMentionHighlightRe(memberNames);
  if (!re) return [text];

  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  // Reset regex state for each call (global flag retains lastIndex).
  re.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    // Text before the match, followed by the captured boundary character.
    if (m.index > lastIndex) {
      parts.push(text.slice(lastIndex, m.index));
    }
    if (m[1]) parts.push(m[1]);
    parts.push(
      <span
        key={`m-${key++}`}
        className="mention-highlight inline-flex items-center rounded-sm bg-primary/15 px-0.5 font-semibold text-primary ring-1 ring-primary/20"
      >
        @{m[2]}
      </span>,
    );
    lastIndex = re.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts.length > 0 ? parts : [text];
}

function normalizeGroupMarkdown(text: string): string {
  return text.replace(/\*\*\s+([^*\n][\s\S]*?[^*\n])\s+\*\*/g, "**$1**");
}

interface MentionTreeNode {
  type: string;
  value?: string;
  tagName?: string;
  properties?: Record<string, unknown>;
  children?: MentionTreeNode[];
}

function rehypeMentionHighlights(options: { names: string[] }) {
  return (tree: MentionTreeNode) => {
    const transform = (node: MentionTreeNode, skip = false) => {
      const shouldSkip =
        skip ||
        (node.type === "element" &&
          (node.tagName === "code" ||
            node.tagName === "pre" ||
            node.tagName === "a"));
      if (shouldSkip || !node.children) return;

      const children: MentionTreeNode[] = [];
      for (const child of node.children) {
        if (child.type !== "text" || !child.value) {
          transform(child);
          children.push(child);
          continue;
        }

        const re = buildMentionHighlightRe(options.names);
        if (!re) {
          children.push(child);
          continue;
        }
        let lastIndex = 0;
        let match: RegExpExecArray | null;
        while ((match = re.exec(child.value)) !== null) {
          const prefix = child.value.slice(lastIndex, match.index) + match[1];
          if (prefix) children.push({ type: "text", value: prefix });
          children.push({
            type: "element",
            tagName: "span",
            properties: {
              className: [
                "mention-highlight",
                "inline-flex",
                "items-center",
                "rounded-sm",
                "bg-primary/15",
                "px-0.5",
                "font-semibold",
                "text-primary",
                "ring-1",
                "ring-primary/20",
              ],
            },
            children: [{ type: "text", value: `@${match[2]}` }],
          });
          lastIndex = re.lastIndex;
        }
        if (lastIndex === 0) {
          children.push(child);
        } else if (lastIndex < child.value.length) {
          children.push({ type: "text", value: child.value.slice(lastIndex) });
        }
      }
      node.children = children;
    };
    transform(tree);
  };
}

export function GroupMarkdown({
  text,
  memberNames = [],
}: {
  text: string;
  memberNames?: string[];
}) {
  return (
    <div className="markdown group-markdown">
      <Markdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[
          rehypeKatex,
          [rehypeMentionHighlights, { names: memberNames }],
        ]}
      >
        {normalizeGroupMarkdown(text)}
      </Markdown>
    </div>
  );
}

function formatElapsed(milliseconds: number): string {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function formatToolName(name: string): string {
  const parts = name.split("__").filter(Boolean);
  if (parts.length >= 3 && parts[0] === "mcp") {
    return `${parts[1]} · ${parts.slice(2).join(" ").replaceAll("_", " ")}`;
  }
  return name.replaceAll("_", " ");
}

function summarizeToolInput(input: Record<string, unknown>): string {
  const keys = [
    "description",
    "command",
    "file_path",
    "path",
    "query",
    "pattern",
    "url",
    "request",
    "prompt",
    "preview",
  ];
  for (const key of keys) {
    const value = input[key];
    if (value === undefined || value === null) continue;
    const text = typeof value === "string" ? value : JSON.stringify(value);
    const singleLine = text.replace(/\s+/g, " ").trim();
    return singleLine.length > 150
      ? `${singleLine.slice(0, 150)}...`
      : singleLine;
  }
  const fallback = JSON.stringify(input);
  return fallback.length > 150 ? `${fallback.slice(0, 150)}...` : fallback;
}

export function parseGroupAgentMessage(content: string): {
  name?: string;
  body: string;
  isError: boolean;
  isInvocation: boolean;
} {
  const reply = content.match(/^\[agent-reply:(.+?)\]\s*\n\n([\s\S]*)$/);
  if (reply) {
    return {
      name: reply[1],
      body: reply[2],
      isError: false,
      isInvocation: false,
    };
  }
  const error = content.match(/^\[agent-error:(.+?)\]\s*\n\n([\s\S]*)$/);
  if (error) {
    return {
      name: error[1],
      body: error[2],
      isError: true,
      isInvocation: false,
    };
  }
  const invocation = content.match(
    /^\[group-invocation:[^:]+:[^\]]+\]\s*\n\n([\s\S]*)$/,
  );
  if (invocation) {
    return {
      body: invocation[1],
      isError: false,
      isInvocation: true,
    };
  }
  return { body: content, isError: false, isInvocation: false };
}

export interface GroupTimelineRun {
  run: GroupAgentRun;
  firstIndex: number;
  finalText?: string;
  isError: boolean;
  finalMessageIndex?: number;
}

export interface GroupTimeline {
  runsByFirstIndex: Map<number, GroupTimelineRun>;
  hiddenIndices: Set<number>;
}

function parseActivityMessage(message: Message): GroupAgentActivityEvent | null {
  if (message.type !== "group_agent_activity" || !message.content) return null;
  try {
    const event = JSON.parse(message.content) as GroupAgentActivityEvent;
    if (!event.run_id || !event.agent_name || !event.phase) return null;
    return event;
  } catch {
    return null;
  }
}

export function buildGroupTimeline(messages: Message[]): GroupTimeline {
  const byRunId = new Map<string, GroupTimelineRun>();
  const hiddenIndices = new Set<number>();

  messages.forEach((message, index) => {
    const event = parseActivityMessage(message);
    if (!event || !event.run_id) return;
    const existing = byRunId.get(event.run_id);
    const run = reduceGroupAgentRun(existing?.run, event);
    byRunId.set(event.run_id, {
      run,
      firstIndex: existing?.firstIndex ?? index,
      finalText: existing?.finalText,
      isError: existing?.isError ?? false,
      finalMessageIndex: existing?.finalMessageIndex,
    });
    hiddenIndices.add(index);
  });

  messages.forEach((message, index) => {
    if (message.type !== "text") return;
    const parsed = parseGroupAgentMessage(message.content || "");
    if (!parsed.name || parsed.isInvocation) return;
    const candidate = [...byRunId.values()]
      .filter(
        (item) =>
          item.run.agentName === parsed.name &&
          item.firstIndex < index &&
          item.finalMessageIndex === undefined,
      )
      .sort((a, b) => b.firstIndex - a.firstIndex)[0];
    if (!candidate) return;

    candidate.finalText = parsed.body;
    candidate.isError = parsed.isError;
    candidate.finalMessageIndex = index;
    if (parsed.isError) {
      candidate.run = {
        ...candidate.run,
        status: "failed",
        error: parsed.body,
        finishedAt: candidate.run.finishedAt ?? Date.now(),
      };
    }
    hiddenIndices.add(index);
  });

  const runsByFirstIndex = new Map<number, GroupTimelineRun>();
  byRunId.forEach((item) => {
    hiddenIndices.delete(item.firstIndex);
    runsByFirstIndex.set(item.firstIndex, item);
  });
  return { runsByFirstIndex, hiddenIndices };
}

export function GroupAgentRunBlock({
  run,
  avatar,
  finalText,
  isError = false,
  memberNames = [],
}: {
  run: GroupAgentRun;
  avatar: string;
  finalText?: string;
  isError?: boolean;
  memberNames?: string[];
}) {
  const [now, setNow] = useState(Date.now());
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (run.status !== "running") return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [run.status]);

  const elapsed =
    run.durationMs ?? (run.finishedAt ?? now) - run.startedAt;
  const activeBlock = [...run.blocks]
    .reverse()
    .find((block) => block.status === "running");
  const statusText =
    run.status === "failed"
      ? "Execution failed"
      : run.status === "completed"
        ? "Completed"
        : activeBlock?.kind === "tool"
          ? `Using ${formatToolName(activeBlock.toolName)}`
          : activeBlock?.kind === "stage"
            ? activeBlock.label
            : activeBlock?.kind === "response"
              ? "Writing response"
              : "Waiting for CLI activity";
  const toolCount = run.blocks.filter((block) => block.kind === "tool").length;
  const costLabel = formatTurnCost(run.cost);
  const responseBlock = run.blocks.find((block) => block.kind === "response");
  const responseText =
    finalText ||
    (responseBlock?.kind === "response" ? responseBlock.content : "") ||
    (isError ? run.error || "" : "");

  return (
    <div className="group-agent-run mb-3 flex w-full max-w-2xl flex-col items-start">
      <div className="mb-1 flex items-center gap-1.5 px-1">
        <span className="text-sm">{avatar}</span>
        <span className="text-xs font-medium text-muted-foreground">
          @{run.agentName}
        </span>
      </div>
      <div className="w-full overflow-hidden rounded-lg border border-border bg-card text-sm shadow-sm">
        <button
          type="button"
          className="flex min-h-11 w-full items-center gap-2.5 px-3 py-2 text-left hover:bg-muted/40"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
          aria-label={expanded ? "Collapse execution details" : "Expand execution details"}
        >
          {run.status === "failed" ? (
            <IconAlertCircle size={17} className="shrink-0 text-destructive" />
          ) : run.status === "completed" ? (
            <IconCheck size={17} className="shrink-0 text-emerald-500" />
          ) : (
            <IconLoader2
              size={17}
              className="shrink-0 animate-spin text-primary"
            />
          )}
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium text-foreground">
              {statusText}
            </div>
            <div className="text-xs text-muted-foreground">
              {run.blocks.length} {run.blocks.length === 1 ? "block" : "blocks"}
              {toolCount > 0
                ? ` · ${toolCount} tool ${toolCount === 1 ? "call" : "calls"}`
                : ""}
            </div>
          </div>
          {costLabel && run.cost != null && (
            <span
              className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground"
              title={exactTurnCostTitle(run.cost)}
            >
              Cost {costLabel}
            </span>
          )}
          <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
            {formatElapsed(elapsed)}
          </span>
          {expanded ? (
            <IconChevronDown size={16} className="shrink-0 text-muted-foreground" />
          ) : (
            <IconChevronRight size={16} className="shrink-0 text-muted-foreground" />
          )}
        </button>

        {expanded && run.blocks.length > 0 && (
          <div className="border-t border-border">
            {run.blocks.map((block) => {
              if (block.kind === "stage") {
                return (
                  <div
                    key={block.id}
                    className="flex min-h-9 items-center gap-2 border-b border-border px-3 py-2 last:border-b-0"
                  >
                    {block.status === "running" ? (
                      <IconLoader2
                        size={14}
                        className="shrink-0 animate-spin text-primary"
                      />
                    ) : block.status === "failed" ? (
                      <IconAlertCircle
                        size={14}
                        className="shrink-0 text-destructive"
                      />
                    ) : (
                      <IconCheck
                        size={14}
                        className="shrink-0 text-emerald-500"
                      />
                    )}
                    <IconClock
                      size={14}
                      className="shrink-0 text-muted-foreground"
                    />
                    <span className="text-xs font-medium text-foreground">
                      {block.label}
                    </span>
                    {block.finishedAt && block.finishedAt > block.startedAt && (
                      <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">
                        {formatElapsed(block.finishedAt - block.startedAt)}
                      </span>
                    )}
                  </div>
                );
              }

              if (block.kind === "response") {
                return null;
              }

              if (block.kind === "error") {
                return (
                  <div
                    key={block.id}
                    className="flex items-start gap-2 border-b border-destructive/20 bg-destructive/5 px-3 py-2 text-xs text-destructive last:border-b-0"
                  >
                    <IconAlertCircle size={14} className="mt-0.5 shrink-0" />
                    <span className="whitespace-pre-wrap break-words">
                      {block.content}
                    </span>
                  </div>
                );
              }

              const hasDetails =
                Object.keys(block.input).length > 0 || Boolean(block.output);
              return (
                <details
                  key={block.id}
                  className="group/tool border-b border-border last:border-b-0"
                >
                  <summary
                    className={`flex min-h-10 list-none items-center gap-2 px-3 py-2 ${
                      hasDetails ? "cursor-pointer hover:bg-accent/40" : ""
                    }`}
                  >
                    {block.status === "running" ? (
                      <IconLoader2
                        size={14}
                        className="shrink-0 animate-spin text-primary"
                      />
                    ) : block.status === "failed" ? (
                      <IconAlertCircle
                        size={14}
                        className="shrink-0 text-destructive"
                      />
                    ) : (
                      <IconCheck
                        size={14}
                        className="shrink-0 text-emerald-500"
                      />
                    )}
                    <IconTerminal2
                      size={14}
                      className="shrink-0 text-muted-foreground"
                    />
                    <span className="shrink-0 text-xs font-medium text-foreground">
                      {formatToolName(block.toolName)}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                      {summarizeToolInput(block.input)}
                    </span>
                    {block.finishedAt && (
                      <span className="shrink-0 text-[10px] text-muted-foreground">
                        {formatElapsed(block.finishedAt - block.startedAt)}
                      </span>
                    )}
                  </summary>
                  {hasDetails && (
                    <div className="space-y-2 border-t border-border bg-muted/30 px-3 py-2">
                      {Object.keys(block.input).length > 0 && (
                        <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] leading-relaxed text-muted-foreground">
                          {JSON.stringify(block.input, null, 2)}
                        </pre>
                      )}
                      {block.output && (
                        <pre
                          className={`max-h-48 overflow-auto whitespace-pre-wrap break-words border-t border-border pt-2 font-mono text-[11px] leading-relaxed ${
                            block.status === "failed"
                              ? "text-destructive"
                              : "text-muted-foreground"
                          }`}
                        >
                          {block.output}
                        </pre>
                      )}
                    </div>
                  )}
                </details>
              );
            })}
          </div>
        )}

        {responseText && (
          <div
            className={`border-t px-3 py-2.5 leading-relaxed ${
              isError
                ? "border-destructive/20 bg-destructive/5 text-destructive"
                : "border-border text-foreground"
            }`}
          >
            <div className="mb-1.5 flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <IconMessageCircle size={14} />
              <span>Response</span>
            </div>
            {isError ? (
              <div className="whitespace-pre-wrap break-words">{responseText}</div>
            ) : (
              <GroupMarkdown text={responseText} memberNames={memberNames} />
            )}
            {run.status === "running" && (
              <span className="inline-block h-4 w-1.5 animate-pulse bg-foreground/50 align-text-bottom" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** The main chat area for a group session. Renders messages from the backing
 * group session (messages[group.sessionId]), detects [agent-reply:Name] and
 * [agent-error:Name] prefixes to style agent bubbles, and provides an
 * @-mention autocomplete in the composer. Messages are sent via POST
 * /api/groups/{id}/send; the backend injects the user message + spawns child
 * sessions for @-mentioned agents, whose replies arrive later as injected
 * user_message WS events. */
export function GroupChatView({
  onToggleSidebar,
}: {
  onToggleSidebar: () => void;
}) {
  const activeGroupId = useSessionStore((s) => s.activeGroupId);
  const groups = useSessionStore((s) => s.groups);
  const agents = useSessionStore((s) => s.agents);
  const token = useSessionStore((s) => s.token);
  const messages = useSessionStore((s) => s.messages);
  const upsertGroup = useSessionStore((s) => s.upsertGroup);
  const groupInvocations = useSessionStore((s) => s.groupInvocations);
  const setGroupInvocations = useSessionStore((s) => s.setGroupInvocations);
  const upsertGroupInvocation = useSessionStore(
    (s) => s.upsertGroupInvocation,
  );

  const group = useMemo(
    () => groups.find((g) => g.id === activeGroupId) ?? null,
    [groups, activeGroupId],
  );
  const sessionId = group?.sessionId ?? null;
  const sessionMessages = useMemo<Message[]>(
    () => (sessionId ? messages[sessionId] ?? [] : []),
    [sessionId, messages],
  );

  const members = useMemo(
    () =>
      group
        ? group.agentIds
            .map((id) => agents.find((a) => a.id === id))
            .filter(Boolean)
        : [],
    [group, agents],
  );

  const memberHandles = useMemo(
    () =>
      members.flatMap((agent) => {
        if (!agent) return [];
        const handles = [agent.name];
        if (agent.alias && agent.alias.toLowerCase() !== agent.name.toLowerCase()) {
          handles.push(agent.alias);
        }
        return handles;
      }),
    [members],
  );

  const agentByName = useMemo(() => {
    const m = new Map<string, { avatar?: string | null }>();
    for (const a of agents) m.set(a.name, { avatar: a.avatar });
    return m;
  }, [agents]);

  const groupTimeline = useMemo(
    () => buildGroupTimeline(sessionMessages),
    [sessionMessages],
  );
  const activeRunAgentNames = useMemo(() => {
    const names = new Set<string>();
    groupTimeline.runsByFirstIndex.forEach((item) => {
      if (item.run.status === "running" && item.finalMessageIndex === undefined) {
        names.add(item.run.agentName);
      }
    });
    return names;
  }, [groupTimeline]);

  const groupTypingAgents = useSessionStore((s) => s.groupTypingAgents);
  const typingNames = useMemo(() => {
    if (!sessionId) return [] as string[];
    const set = groupTypingAgents[sessionId];
    return set ? [...set] : [];
  }, [sessionId, groupTypingAgents]);

  const groupStreamingReplies = useSessionStore((s) => s.groupStreamingReplies);
  const streamingReplies = useMemo(() => {
    if (!sessionId) return {} as Record<string, string>;
    return groupStreamingReplies[sessionId] ?? {};
  }, [sessionId, groupStreamingReplies]);

  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [mentionIndex, setMentionIndex] = useState(-1);
  const [mentionSearch, setMentionSearch] = useState("");
  const [showMentions, setShowMentions] = useState(false);
  const [invocationAction, setInvocationAction] = useState<string | null>(null);
  const [defaultSaving, setDefaultSaving] = useState(false);
  const [activeUserMessageIndex, setActiveUserMessageIndex] = useState<
    number | null
  >(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeMessageFrameRef = useRef<number | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const userMessageMarkers = useMemo(
    () => buildUserMessageMarkers(sessionMessages),
    [sessionMessages],
  );

  const updateActiveUserMessage = useCallback(() => {
    const container = scrollRef.current;
    if (!container || userMessageMarkers.length === 0) {
      setActiveUserMessageIndex(null);
      return;
    }

    const containerRect = container.getBoundingClientRect();
    const viewportCenter = containerRect.top + containerRect.height / 2;
    let closestIndex: number | null = null;
    let closestDistance = Number.POSITIVE_INFINITY;
    for (const marker of userMessageMarkers) {
      const element = container.querySelector<HTMLElement>(
        `[data-message-index="${marker.index}"]`,
      );
      if (!element) continue;
      const rect = element.getBoundingClientRect();
      const distance = Math.abs(rect.top + rect.height / 2 - viewportCenter);
      if (distance < closestDistance) {
        closestDistance = distance;
        closestIndex = marker.index;
      }
    }
    setActiveUserMessageIndex((current) =>
      current === closestIndex ? current : closestIndex,
    );
  }, [userMessageMarkers]);

  const scheduleActiveUserMessageUpdate = useCallback(() => {
    if (activeMessageFrameRef.current !== null) return;
    activeMessageFrameRef.current = requestAnimationFrame(() => {
      activeMessageFrameRef.current = null;
      updateActiveUserMessage();
    });
  }, [updateActiveUserMessage]);

  const navigateToUserMessage = useCallback((index: number) => {
    const target = scrollRef.current?.querySelector<HTMLElement>(
      `[data-message-index="${index}"]`,
    );
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
    setActiveUserMessageIndex(index);
  }, []);

  const visibleInvocations = useMemo(
    () => (activeGroupId ? groupInvocations[activeGroupId] ?? [] : []).filter(
      (item) =>
        item.status === "running" ||
        item.status === "held" ||
        item.custody_state === "blocked" ||
        item.custody_state === "void",
    ),
    [activeGroupId, groupInvocations],
  );
  const stoppableInvocation = useMemo(
    () =>
      visibleInvocations.find((item) => item.status === "running") ??
      visibleInvocations.find((item) => item.status === "held") ??
      null,
    [visibleInvocations],
  );

  useEffect(() => {
    if (!activeGroupId || !token) return;
    const controller = new AbortController();
    fetch(`${API}/api/groups/${activeGroupId}/invocations`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then((response) => (response.ok ? response.json() : []))
      .then((rows: GroupInvocation[]) => {
        if (!controller.signal.aborted) {
          setGroupInvocations(activeGroupId, rows);
        }
      })
      .catch(() => {});
    return () => controller.abort();
  }, [activeGroupId, token, setGroupInvocations]);

  const mentionOptions = useMemo(() => {
    const handles = members.flatMap((agent) => {
      if (!agent) return [];
      const rows = [{ agent, handle: agent.name, isAlias: false }];
      if (agent.alias && agent.alias.toLowerCase() !== agent.name.toLowerCase()) {
        rows.push({ agent, handle: agent.alias, isAlias: true });
      }
      return rows;
    });
    if (!showMentions) return handles;
    const q = mentionSearch.toLowerCase();
    return handles.filter(
      ({ agent, handle }) =>
        handle.toLowerCase().includes(q) || agent.name.toLowerCase().includes(q),
    );
  }, [showMentions, mentionSearch, members]);

  // Auto-scroll to bottom on new messages or streaming text.
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    if (typeof container.scrollTo === "function") {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: "smooth",
      });
    } else {
      container.scrollTop = container.scrollHeight;
    }
  }, [sessionMessages.length, typingNames.length, streamingReplies]);

  useEffect(() => {
    scheduleActiveUserMessageUpdate();
    return () => {
      if (activeMessageFrameRef.current !== null) {
        cancelAnimationFrame(activeMessageFrameRef.current);
        activeMessageFrameRef.current = null;
      }
    };
  }, [scheduleActiveUserMessageUpdate]);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const v = e.target.value;
      setInput(v);
      const pos = e.target.selectionStart;
      const before = v.slice(0, pos);
      const m = before.match(MENTION_PARTIAL_RE);
      if (m) {
        setShowMentions(true);
        setMentionSearch(m[1]);
        setMentionIndex(0);
      } else {
        setShowMentions(false);
        setMentionSearch("");
        setMentionIndex(-1);
      }
    },
    [],
  );

  const insertMention = useCallback(
    (agentName: string) => {
      const pos = inputRef.current?.selectionStart ?? input.length;
      const before = input.slice(0, pos);
      const after = input.slice(pos);
      const newBefore = before.replace(MENTION_PARTIAL_RE, `@${agentName} `);
      setInput(newBefore + after);
      setShowMentions(false);
      setMentionSearch("");
      setMentionIndex(-1);
      setTimeout(() => {
        const np = newBefore.length;
        inputRef.current?.focus();
        inputRef.current?.setSelectionRange(np, np);
      }, 0);
    },
    [input],
  );

  const handleSend = async () => {
    const content = input.trim();
    if (!content || !activeGroupId || sending) return;
    setSending(true);
    setInput("");
    setShowMentions(false);
    try {
      const response = await fetch(`${API}/api/groups/${activeGroupId}/send`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ content }),
      });
      if (response.ok) {
        const payload = await response.json();
        if (payload.invocation) {
          upsertGroupInvocation(payload.invocation as GroupInvocation);
        }
      }
    } catch {
      // best-effort; the WS handler still renders whatever the server emits
    } finally {
      setSending(false);
    }
  };

  const runInvocationAction = useCallback(
    async (invocation: GroupInvocation, action: "cancel" | "resume") => {
      if (!activeGroupId || invocationAction) return;
      setInvocationAction(invocation.id);
      try {
        const response = await fetch(
          `${API}/api/groups/${activeGroupId}/invocations/${invocation.id}/${action}`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: action === "resume" ? JSON.stringify({ reason: "" }) : undefined,
          },
        );
        if (response.ok) {
          upsertGroupInvocation(await response.json());
        }
      } finally {
        setInvocationAction(null);
      }
    },
    [activeGroupId, invocationAction, token, upsertGroupInvocation],
  );

  const updateDefaultAgent = useCallback(
    async (agentId: string) => {
      if (!group || defaultSaving) return;
      setDefaultSaving(true);
      try {
        const response = await fetch(`${API}/api/groups/${group.id}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ default_agent_id: agentId || "" }),
        });
        if (response.ok) {
          const updated = await response.json();
          upsertGroup({
            id: updated.id,
            name: updated.name,
            agentIds: updated.agent_ids,
            createdAt: updated.created_at,
            sessionId: updated.session_id ?? null,
            defaultAgentId: updated.default_agent_id ?? null,
            workingDir: updated.working_dir,
          });
        }
      } finally {
        setDefaultSaving(false);
      }
    },
    [group, defaultSaving, token, upsertGroup],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (showMentions && mentionOptions.length > 0) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setMentionIndex((i) =>
            i < mentionOptions.length - 1 ? i + 1 : 0,
          );
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          setMentionIndex((i) =>
            i > 0 ? i - 1 : mentionOptions.length - 1,
          );
          return;
        }
        if (e.key === "Tab" || e.key === "Enter") {
          e.preventDefault();
          const sel = mentionOptions[mentionIndex] || mentionOptions[0];
          if (sel) insertMention(sel.handle);
          return;
        }
        if (e.key === "Escape") {
          e.preventDefault();
          setShowMentions(false);
          return;
        }
      }
      if (e.key === "Enter" && !e.shiftKey && !showMentions) {
        e.preventDefault();
        void handleSend();
      }
    },
    [showMentions, mentionOptions, mentionIndex, insertMention],
  );

  const renderMessage = useCallback(
    (msg: Message, idx: number) => {
      const timelineRun = groupTimeline.runsByFirstIndex.get(idx);
      if (timelineRun) {
        const avatar =
          agentByName.get(timelineRun.run.agentName)?.avatar || "\u{1F419}";
        return (
          <GroupAgentRunBlock
            key={timelineRun.run.runId}
            run={timelineRun.run}
            avatar={avatar}
            finalText={timelineRun.finalText}
            isError={timelineRun.isError}
            memberNames={memberHandles}
          />
        );
      }
      if (groupTimeline.hiddenIndices.has(idx)) return null;
      if (msg.type !== "text") return null;
      const content = msg.content || "";
      const { name, body, isError, isInvocation } =
        parseGroupAgentMessage(content);
      if (isInvocation) {
        return (
          <div key={idx} className="my-3 flex justify-center px-4">
            <div className="max-w-[85%] border-l-2 border-border px-3 py-1 text-xs text-muted-foreground">
              {body}
            </div>
          </div>
        );
      }
      const isUser = !name;
      const avatar = name ? agentByName.get(name)?.avatar || "\u{1F419}" : null;

      return (
        <div
          key={idx}
          className={`flex flex-col mb-3 ${isUser ? "items-end" : "items-start"}`}
        >
          {name && (
            <div className="flex items-center gap-1.5 mb-1 px-1">
              <span className="text-sm">{avatar}</span>
              <span className="text-xs font-medium text-muted-foreground">
                @{name}
              </span>
            </div>
          )}
          <div
            className={`max-w-[75%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
              isError
                ? "bg-destructive/10 text-destructive border border-destructive/20"
                : isUser
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted"
            }`}
          >
            {isError ? (
              body
            ) : (
              <GroupMarkdown
                text={body}
                memberNames={isUser ? [] : memberHandles}
              />
            )}
          </div>
        </div>
      );
    },
    [groupTimeline, agentByName, memberHandles],
  );

  if (!activeGroupId || !group) {
    return (
      <div className="chat-view flex-1 flex flex-col min-h-0">
        <div className="chat-header flex items-center gap-3 px-4 h-12 shrink-0 border-b border-border bg-sidebar">
          <button
            className="btn btn-menu inline-flex items-center justify-center size-9 rounded-lg text-foreground hover:bg-accent md:hidden"
            onClick={onToggleSidebar}
            aria-label="Toggle sidebar"
          >
            <IconMenu2 size={18} />
          </button>
        </div>
        <div className="chat-empty flex-1 flex items-center justify-center text-muted-foreground">
          <p className="text-sm">No group selected.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-view flex-1 flex flex-col min-h-0">
      {/* Header */}
      <div className="chat-header flex items-center gap-3 px-4 h-12 shrink-0 border-b border-border bg-sidebar">
        <button
          className="btn btn-menu inline-flex items-center justify-center size-9 rounded-lg text-foreground hover:bg-accent md:hidden"
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
        >
          <IconMenu2 size={18} />
        </button>
        <IconUsers size={18} className="text-muted-foreground shrink-0" />
        <h3 className="text-[15px] font-semibold text-foreground truncate">
          {group.name}
        </h3>
        <div
          className="ml-auto flex shrink-0 items-center gap-1.5 rounded-md border border-border bg-background px-2 py-1"
          title="不带 @ 的消息会按最近回复者、最近 @ 过、默认回复 agent 的顺序选择接话人"
        >
          <span className="text-[11px] font-medium text-muted-foreground">
            默认回复
          </span>
          <select
            value={group.defaultAgentId ?? ""}
            onChange={(e) => void updateDefaultAgent(e.target.value)}
            disabled={defaultSaving}
            className="h-6 max-w-36 bg-transparent text-xs text-foreground outline-none"
            aria-label="默认回复 agent"
          >
            <option value="">不设置</option>
            {members.map((a) => (
              <option key={a!.id} value={a!.id}>
                {a!.name}
              </option>
            ))}
          </select>
        </div>
        <span className="flex items-center gap-1 shrink-0">
          {members.map((a) => (
            <span
              key={a!.id}
              className="text-base leading-none"
              title={a!.name}
            >
              {a!.avatar || "\u{1F419}"}
            </span>
          ))}
        </span>
      </div>

      {visibleInvocations.length > 0 && (
        <div className="shrink-0 border-b border-border bg-muted/35 px-4 py-2 space-y-1.5">
          {visibleInvocations.map((invocation) => {
            const currentAgent = agents.find(
              (agent) => agent.id === invocation.current_agent_id,
            );
            const canResume = ["held", "blocked", "void"].includes(
              invocation.custody_state,
            );
            return (
              <div
                key={invocation.id}
                className="flex min-w-0 items-center gap-2 text-xs"
              >
                <IconClock size={14} className="shrink-0 text-muted-foreground" />
                <span className="font-medium text-foreground shrink-0">
                  {invocation.custody_state}
                </span>
                <span className="truncate text-muted-foreground">
                  {currentAgent ? `@${currentAgent.name}` : "Routing chain"}
                  {invocation.hold_reason ? `: ${invocation.hold_reason}` : ""}
                </span>
                <span className="ml-auto shrink-0 text-muted-foreground">
                  depth {invocation.depth}
                </span>
                {canResume && (
                  <button
                    type="button"
                    className="inline-flex size-7 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50"
                    onClick={() => void runInvocationAction(invocation, "resume")}
                    disabled={invocationAction === invocation.id}
                    title="Resume this chain"
                    aria-label="Resume this chain"
                  >
                    <IconPlayerPlay size={15} />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Messages */}
      <div className="message-pane relative flex-1 min-h-0">
        <div
          ref={scrollRef}
          className="group-messages h-full min-h-0 overflow-y-auto px-4 py-3"
          onScroll={scheduleActiveUserMessageUpdate}
        >
        {sessionMessages.length === 0 && (
          <div className="mx-4 mt-3 shrink-0 rounded-lg border border-dashed border-border bg-accent/40 px-4 py-3">
            <p className="text-sm text-muted-foreground leading-relaxed">
              @mention an agent to start a conversation. For example:{" "}
              <span className="font-mono text-xs bg-muted px-1 rounded">
                @{members[0]?.name || "Agent"} help me with this
              </span>
            </p>
          </div>
        )}
        {sessionMessages.map((msg, i) => {
          const rendered = renderMessage(msg, i);
          return rendered ? (
            <div
              key={`group-message-${msg.seq ?? i}`}
              className="group-message-anchor"
              data-message-index={i}
            >
              {rendered}
            </div>
          ) : null;
        })}

        {/* Streaming agent replies — live bubbles that grow as the
         * backend streams chunks. Cleared when the final
         * [agent-reply:Name] user_message replaces them. */}
        {Object.entries(streamingReplies)
          .filter(([name]) => !activeRunAgentNames.has(name))
          .map(([name, text]) => {
            const avatar = agentByName.get(name)?.avatar || "\u{1F419}";
            return (
              <div key={`stream-${name}`} className="mb-3 flex flex-col items-start">
                <div className="mb-1 flex items-center gap-1.5 px-1">
                  <span className="text-sm">{avatar}</span>
                  <span className="text-xs font-medium text-muted-foreground">
                    @{name}
                  </span>
                </div>
                <div className="max-w-[75%] rounded-lg bg-muted px-3 py-2 text-sm leading-relaxed">
                  <GroupMarkdown text={text} memberNames={memberHandles} />
                  <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-foreground/50 align-text-bottom" />
                </div>
              </div>
            );
          })}

        {/* Typing indicator — only shown when the agent is typing but
         * hasn't produced any text yet (streamingReplies takes over
         * once text starts flowing). */}
        {typingNames.some(
          (name) => !streamingReplies[name] && !activeRunAgentNames.has(name),
        ) && (
          <div className="flex items-center gap-1.5 px-1 py-1 text-xs text-muted-foreground">
            {typingNames
              .filter(
                (name) =>
                  !streamingReplies[name] && !activeRunAgentNames.has(name),
              )
              .map((name) => {
                const a = agentByName.get(name);
                return (
                  <span key={name} className="flex items-center gap-1">
                    <span className="text-sm">{a?.avatar || "\u{1F419}"}</span>
                    <span>@{name}</span>
                  </span>
                );
              })}
            <span className="animate-pulse">is typing…</span>
          </div>
        )}
        </div>
        <MessageNavigator
          markers={userMessageMarkers}
          totalItems={sessionMessages.length}
          activeIndex={activeUserMessageIndex}
          onNavigate={navigateToUserMessage}
        />
      </div>

      {/* Composer with @-mention autocomplete */}
      <div className="chat-composer shrink-0 border-t border-border bg-background px-3 py-2 relative">
        {showMentions && mentionOptions.length > 0 && (
          <div className="absolute bottom-full left-3 right-3 mb-1 bg-popover border border-border rounded-lg shadow-lg overflow-hidden z-50">
            {mentionOptions.map(({ agent, handle, isAlias }, i) => (
              <button
                key={`${agent.id}-${handle}`}
                className={`flex items-center gap-2 w-full px-3 py-2 text-sm text-left transition-colors ${
                  i === mentionIndex ? "bg-accent" : "hover:bg-accent/50"
                }`}
                onClick={() => insertMention(handle)}
                onMouseEnter={() => setMentionIndex(i)}
              >
                <span className="text-base">{agent.avatar || "\u{1F419}"}</span>
                <span className="min-w-0 flex-1 truncate">
                  @{handle}
                  {isAlias && (
                    <span className="ml-1.5 text-xs text-muted-foreground">
                      {agent.name}
                    </span>
                  )}
                </span>
                <span className="text-xs text-muted-foreground">
                  {agent.backend === "codex" ? "Codex" : "Claude"}
                </span>
              </button>
            ))}
          </div>
        )}
        <div className="flex items-end gap-2">
          <button
            className="shrink-0 h-8 w-8 rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors inline-flex items-center justify-center"
            onClick={() => {
              setInput((p) => p + "@");
              setShowMentions(true);
              setMentionSearch("");
              inputRef.current?.focus();
            }}
            title="Mention an agent"
            aria-label="Mention an agent"
          >
            <IconAt size={16} />
          </button>
          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Send a message... @mention a specific agent when needed"
            rows={1}
            className="flex-1 resize-none field-sizing-content bg-transparent px-2 py-1.5 text-sm text-foreground placeholder:text-muted-foreground/50 border-0 outline-none focus:outline-none max-h-48"
          />
          {stoppableInvocation && (
            <Button
              type="button"
              variant="destructive"
              size="sm"
              className="btn btn-stop rounded-lg h-8 w-8 p-0 shrink-0"
              onClick={() =>
                void runInvocationAction(stoppableInvocation, "cancel")
              }
              disabled={invocationAction === stoppableInvocation.id}
              aria-label="Stop group run"
              title="Stop current group run"
            >
              <IconPlayerStop size={14} />
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            className="btn btn-send rounded-lg h-8 w-8 p-0 shrink-0"
            onClick={() => void handleSend()}
            disabled={!input.trim() || sending}
            aria-label="Send message"
          >
            <IconArrowUp size={14} />
          </Button>
        </div>
      </div>
    </div>
  );
}
