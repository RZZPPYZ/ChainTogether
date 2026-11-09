import { useCallback, useState } from "react";
import {
  IconCheck,
  IconChevronDown,
  IconChevronRight,
  IconX,
} from "@tabler/icons-react";

import { cn } from "../lib/utils";
import {
  summarizeToolActivity,
  type ToolStep,
} from "../lib/toolActivity";
import { ToolStepRow } from "./ToolStepRow";

interface Props {
  steps: ToolStep[];
  sessionId: string;
  /** True once a turn-ending `result` message follows this group. */
  turnEnded: boolean;
  /** False for finished sessions, which may predate `result` badges. */
  sessionRunning: boolean;
}

/**
 * Collapsible "activity trail" group for a run of consecutive tool calls.
 *
 * Three disclosure levels: this header (one card line), one row per step, and
 * the raw input/output inside a step. The header reuses the same card chrome
 * as the chat's other tool affordances so the trail reads as part of the
 * conversation rather than a separate widget.
 *
 * Defaults are live-aware: a group in the running session starts open and
 * auto-collapses when the turn ends — unless the user has toggled it. A
 * historical group starts collapsed even when the session predates `result`
 * badges. Groups containing a failure always start open.
 */
export function ToolActivityGroup({
  steps,
  sessionId,
  turnEnded,
  sessionRunning,
}: Props) {
  const isRunning = steps.some((step) => step.status === "running");
  const hasError = steps.some((step) => step.status === "error");
  const summary = summarizeToolActivity(steps);

  // `null` = untouched; a boolean pins the user's explicit choice so later
  // streaming updates / turn-end auto-collapse can't override it.
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  const [stepOverrides, setStepOverrides] = useState<Record<string, boolean>>(
    {},
  );

  // `turnEnded` alone can't collapse legacy sessions, which predate result
  // badges — an idle session means every group in it is historical.
  const open =
    userOpen ??
    (hasError || (sessionRunning && (!turnEnded || isRunning)));

  const toggleOpen = useCallback(() => {
    setUserOpen((current) => !(current ?? open));
  }, [open]);

  const isStepOpen = useCallback(
    (step: ToolStep) => stepOverrides[step.id] ?? step.status === "error",
    [stepOverrides],
  );

  const toggleStep = useCallback((step: ToolStep) => {
    setStepOverrides((current) => ({
      ...current,
      [step.id]: !(current[step.id] ?? step.status === "error"),
    }));
  }, []);

  return (
    <div
      className={cn(
        "msg msg-activity overflow-hidden rounded-lg border bg-card",
        hasError ? "border-destructive/50" : "border-border",
      )}
      data-testid="tool-activity-group"
    >
      <button
        type="button"
        onClick={toggleOpen}
        aria-expanded={open}
        data-testid="tool-activity-toggle"
        className="tool-header w-full flex items-center gap-2 px-3 py-2 text-left text-sm hover:bg-accent/50 transition-colors"
      >
        <span className="tool-icon text-muted-foreground shrink-0">
          {open ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
        </span>
        {isRunning ? (
          <span
            className="size-1.5 shrink-0 rounded-full bg-primary animate-pulse motion-reduce:animate-none"
            title="running"
          />
        ) : hasError ? (
          <IconX
            size={14}
            className="shrink-0 text-destructive"
            title="failed"
          />
        ) : (
          <IconCheck
            size={14}
            className="shrink-0 text-green-700"
            title="succeeded"
          />
        )}
        <span
          className={cn(
            "shrink-0 font-medium",
            hasError ? "text-destructive" : "text-primary",
          )}
        >
          {summary.total} {summary.total === 1 ? "step" : "steps"}
        </span>
        <span className="tool-preview min-w-0 truncate font-mono text-xs text-muted-foreground">
          {summary.counts
            .map((count) => `${count.label} ${count.count}`)
            .join(" · ")}
        </span>
        {summary.failed > 0 && (
          <span className="ml-auto inline-flex shrink-0 items-center gap-1 text-xs font-medium tabular-nums text-destructive">
            <IconX size={12} />
            {summary.failed} failed
          </span>
        )}
      </button>

      {open && (
        <div className="border-t border-border bg-muted/30">
          {steps.map((step) => (
            <div
              key={step.id}
              className="relative border-t border-border/60 first:border-t-0"
            >
              <ToolStepRow
                step={step}
                sessionId={sessionId}
                expanded={isStepOpen(step)}
                onToggle={() => toggleStep(step)}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
