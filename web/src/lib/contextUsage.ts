export interface ContextUsage {
  input_tokens?: number | null;
  output_tokens?: number | null;
  cached_input_tokens?: number | null;
  cache_creation_input_tokens?: number | null;
  total_tokens?: number | null;
  // Tokens consumed by the reporting turn (cache reads included); the
  // "Done · N tokens" badge reads this — `total_tokens` is context size.
  turn_tokens?: number | null;
  context_window?: number | null;
  remaining_tokens?: number | null;
  remaining_ratio?: number | null;
  model?: string | null;
  backend?: string | null;
  source?: "reported" | "estimated" | string;
  observed_at?: string | null;
}

function formatTokenCount(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`;
  if (tokens >= 1_000) return `${Math.round(tokens / 1_000)}k`;
  return `${tokens}`;
}

export function formatContextUsageLabel(
  usage?: ContextUsage | null,
): string | null {
  if (!usage) return null;
  if (typeof usage.remaining_ratio === "number") {
    return `${Math.round(usage.remaining_ratio * 100)}% ctx`;
  }
  if (typeof usage.remaining_tokens === "number") {
    return `${formatTokenCount(usage.remaining_tokens)} ctx`;
  }
  if (typeof usage.total_tokens === "number") {
    return `${formatTokenCount(usage.total_tokens)} used`;
  }
  return null;
}

export function contextUsageTitle(usage?: ContextUsage | null): string {
  if (!usage) return "Context usage unavailable";
  const lines: string[] = [];
  if (typeof usage.remaining_ratio === "number") {
    lines.push(`Context remaining: ${Math.round(usage.remaining_ratio * 100)}%`);
  }
  if (
    typeof usage.remaining_tokens === "number" &&
    typeof usage.context_window === "number"
  ) {
    lines.push(
      `${formatTokenCount(usage.remaining_tokens)} of ${formatTokenCount(
        usage.context_window,
      )} tokens left`,
    );
  } else if (typeof usage.total_tokens === "number") {
    lines.push(`${formatTokenCount(usage.total_tokens)} tokens used`);
  }
  if (usage.model) lines.push(`Model: ${usage.model}`);
  if (usage.backend) lines.push(`Backend: ${usage.backend}`);
  if (usage.source) lines.push(`Source: ${usage.source}`);
  return lines.join("\n") || "Context usage unavailable";
}

export function contextUsageTone(usage?: ContextUsage | null): string {
  const ratio = usage?.remaining_ratio;
  if (typeof ratio !== "number") return "border-border bg-muted text-muted-foreground";
  if (ratio <= 0.05) return "border-destructive/40 bg-destructive/10 text-destructive";
  if (ratio <= 0.15) return "border-amber-500/50 bg-amber-500/10 text-amber-700";
  if (ratio <= 0.3) return "border-yellow-500/40 bg-yellow-500/10 text-yellow-700";
  return "border-emerald-500/35 bg-emerald-500/10 text-emerald-700";
}
