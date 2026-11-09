import { useEffect, useRef, useState } from "react";
import type { ComponentType } from "react";
import {
  IconCheck,
  IconChevronDown,
  IconChevronRight,
  IconCopy,
  IconFileText,
  IconPencil,
  IconSearch,
  IconTerminal2,
  IconTool,
  IconWorld,
  IconX,
} from "@tabler/icons-react";

import { useSessionStore } from "../stores/sessionStore";
import { cn } from "../lib/utils";
import {
  describeToolStep,
  toolStepInputText,
  toolStepOutputText,
  type ToolIconKind,
  type ToolStep,
} from "../lib/toolActivity";
import { BgTaskChip } from "./BgTaskChip";
import { AgentDelegationRequestCard } from "./AgentDelegationRequestCard";

const STEP_ICONS: Record<
  ToolIconKind,
  ComponentType<{ size?: number; className?: string }>
> = {
  terminal: IconTerminal2,
  file: IconFileText,
  edit: IconPencil,
  search: IconSearch,
  world: IconWorld,
  tool: IconTool,
};

interface Props {
  step: ToolStep;
  sessionId: string;
  expanded: boolean;
  onToggle: () => void;
}

/**
 * One line of the activity trail. Collapsed it is a quiet row inside the
 * group card (verb + mono target + right-side status hint); expanded it
 * reveals the raw tool input/output plus the live bg-task chip / delegation
 * card the tool's call produced, using the same detail treatment as the
 * chat's other tool surfaces.
 */
export function ToolStepRow({ step, sessionId, expanded, onToggle }: Props) {
  const description = describeToolStep(step);
  const Icon = STEP_ICONS[description.icon];
  const inputText = toolStepInputText(step);
  const outputText = toolStepOutputText(step);

  const isBgRun = step.toolName === "mcp__bg__run";
  const isAskAgent = step.toolName === "mcp__ask_agent__ask";
  const askAgentName =
    typeof step.input.name === "string" ? step.input.name : "";
  const askAgentRequest =
    typeof step.input.request === "string" ? step.input.request : "";
  const askAgentFiles = Array.isArray(step.input.files)
    ? (step.input.files as unknown[]).filter(
        (file): file is string => typeof file === "string",
      )
    : undefined;

  return (
    <div className="relative" data-testid="tool-step">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className={cn(
          "tool-header w-full flex items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-accent/50 transition-colors",
          step.status === "error" && "text-destructive/90",
        )}
      >
        <span className="tool-icon text-muted-foreground shrink-0">
          {expanded ? (
            <IconChevronDown size={14} />
          ) : (
            <IconChevronRight size={14} />
          )}
        </span>
        <Icon
          size={14}
          className={cn(
            "shrink-0",
            step.status === "error"
              ? "text-destructive"
              : "text-muted-foreground",
          )}
        />
        <span className="shrink-0 font-medium">{description.verb}</span>
        {description.target ? (
          <code
            className="tool-preview min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground"
            title={description.target}
          >
            {description.target}
          </code>
        ) : (
          <span className="flex-1" />
        )}
        {description.hint && (
          <span
            className={cn(
              "shrink-0 truncate font-mono text-xs tabular-nums",
              description.hintTone === "error"
                ? "text-destructive"
                : description.hintTone === "running"
                  ? "text-primary"
                  : "text-muted-foreground",
            )}
          >
            {description.hint}
          </span>
        )}
        <StepStatus status={step.status} />
      </button>

      {expanded && (
        <div className="border-t border-border bg-muted/40 px-4 py-2.5 space-y-2">
          <StepDetail title="Input" text={inputText} emptyLabel="(no input)" />
          <StepDetail
            title="Output"
            text={outputText}
            emptyLabel={
              step.status === "running" ? "Waiting for output…" : "(no output)"
            }
            error={step.status === "error"}
          />
          {isBgRun && (
            <BgChipForStep sessionId={sessionId} input={step.input} />
          )}
          {isAskAgent && askAgentName && askAgentRequest && (
            <AgentDelegationRequestCard
              sessionId={sessionId}
              toolUseId={step.toolUseId}
              agentName={askAgentName}
              request={askAgentRequest}
              files={askAgentFiles}
            />
          )}
        </div>
      )}
    </div>
  );
}

function StepStatus({ status }: { status: ToolStep["status"] }) {
  if (status === "running") {
    return (
      <span
        className="size-1.5 shrink-0 rounded-full bg-primary animate-pulse motion-reduce:animate-none"
        title="running"
      />
    );
  }
  if (status === "error") {
    return (
      <IconX size={12} className="shrink-0 text-destructive" title="failed" />
    );
  }
  return (
    <IconCheck
      size={12}
      className="shrink-0 text-green-700"
      title="succeeded"
    />
  );
}

function StepDetail({
  title,
  text,
  emptyLabel,
  error = false,
}: {
  title: string;
  text: string;
  emptyLabel: string;
  error?: boolean;
}) {
  return (
    <section>
      <div className="flex items-center justify-between gap-2">
        <span
          className={cn(
            "text-xs font-semibold uppercase tracking-wider",
            error ? "text-destructive" : "text-muted-foreground",
          )}
        >
          {title}
        </span>
        {text && <CopyButton text={text} />}
      </div>
      <pre
        className={cn(
          "mt-1 overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-relaxed",
          error
            ? // Failed steps auto-expand; cap the initial view to roughly
              // three lines so one giant stderr dump can't take over the trail.
              "max-h-20 text-destructive"
            : "max-h-80 text-foreground",
        )}
      >
        {text || emptyLabel}
      </pre>
    </section>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    },
    [],
  );

  const copy = () => {
    try {
      const write = navigator.clipboard?.writeText(text);
      if (!write) return;
      void write
        .then(() => {
          setCopied(true);
          if (timerRef.current !== null) window.clearTimeout(timerRef.current);
          timerRef.current = window.setTimeout(() => setCopied(false), 1200);
        })
        .catch(() => {
          /* clipboard permission denied — leave the icon unchanged */
        });
    } catch {
      /* clipboard API unavailable */
    }
  };

  return (
    <button
      type="button"
      onClick={copy}
      className="inline-flex items-center justify-center size-5 rounded text-muted-foreground/70 hover:text-foreground hover:bg-accent/60"
      aria-label={copied ? "Copied" : "Copy"}
      title={copied ? "Copied" : "Copy"}
    >
      {copied ? <IconCheck size={12} /> : <IconCopy size={12} />}
    </button>
  );
}

/**
 * Bridges a `mcp__bg__run` step → the live BgTaskChip.
 *
 * The model's tool_use doesn't carry the task_id (we mint it server-side), so
 * we match the most recent bg task whose `command` equals the input command.
 * The bg_started WS event populates the store before this component mounts in
 * normal flow; after a snapshot rehydrate, list_bg_tasks still gives a match.
 */
function BgChipForStep({
  sessionId,
  input,
}: {
  sessionId: string;
  input: Record<string, unknown>;
}) {
  const command =
    typeof input.command === "string" ? (input.command as string) : "";
  const matchedId = useSessionStore((s) => {
    const tasks = s.bgTasks[sessionId] || [];
    const match = [...tasks].reverse().find((t) => t.command === command);
    return match?.id ?? null;
  });
  if (!matchedId) {
    return (
      <div className="octo-bgtask-chip inline-flex items-center gap-2 rounded-md border border-border bg-muted/40 px-2.5 py-1.5 text-xs text-muted-foreground">
        <span>Waiting for bg task to register…</span>
      </div>
    );
  }
  return <BgTaskChip sessionId={sessionId} taskId={matchedId} />;
}
