import type { ContextUsage } from "./contextUsage";

/**
 * Compact token counts for badges: `950`, `25.1k`, `1.2M`.
 * Returns null for missing/invalid values so callers can omit the badge.
 */
export function formatTokenCount(
  tokens: number | null | undefined,
): string | null {
  if (tokens == null || !Number.isFinite(tokens) || tokens < 0) return null;
  const n = Math.round(tokens);
  if (n < 1_000) return `${n}`;

  const scaled = (value: number, unit: "k" | "M"): string => {
    const rounded = Math.round(value * 10) / 10;
    if (rounded >= 1_000) return scaled(value / 1_000, "M");
    return `${Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1)}${unit}`;
  };
  return n < 1_000_000
    ? scaled(n / 1_000, "k")
    : scaled(n / 1_000_000, "M");
}

/**
 * Tokens consumed by one turn. Prefers the backend-normalized `turn_tokens`
 * (summed across every API request the turn made). Falls back to deriving it
 * from the raw counters for payloads persisted before that field existed:
 * Claude's `input_tokens` excludes cache reads/writes while Codex's already
 * includes the cached input, so only the Claude shape adds them.
 */
export function turnTokenCount(
  usage: ContextUsage | null | undefined,
): number | null {
  if (!usage) return null;
  const reported = usage.turn_tokens;
  if (
    typeof reported === "number" &&
    Number.isFinite(reported) &&
    reported >= 0
  ) {
    return reported;
  }

  const add = (...values: Array<number | null | undefined>): number =>
    values.reduce<number>(
      (total, value) =>
        typeof value === "number" && Number.isFinite(value) && value > 0
          ? total + value
          : total,
      0,
    );
  const total =
    usage.backend === "claude-code"
      ? add(
          usage.input_tokens,
          usage.cached_input_tokens,
          usage.cache_creation_input_tokens,
          usage.output_tokens,
        )
      : add(usage.input_tokens, usage.output_tokens);
  return total > 0 ? total : null;
}

/** Tooltip breakdown for the per-turn token badge. */
export function turnTokenTitle(
  usage: ContextUsage | null | undefined,
): string | undefined {
  const total = turnTokenCount(usage);
  if (!usage || total == null) return undefined;

  const format = (value: number) => value.toLocaleString("en-US");
  const parts: string[] = [];
  if (typeof usage.input_tokens === "number") {
    parts.push(`${format(usage.input_tokens)} input`);
  }
  if (
    typeof usage.cached_input_tokens === "number" &&
    usage.cached_input_tokens > 0
  ) {
    parts.push(
      usage.backend === "codex"
        ? `${format(usage.cached_input_tokens)} cached (included in input)`
        : `${format(usage.cached_input_tokens)} cached`,
    );
  }
  if (
    typeof usage.cache_creation_input_tokens === "number" &&
    usage.cache_creation_input_tokens > 0
  ) {
    parts.push(`${format(usage.cache_creation_input_tokens)} cache write`);
  }
  if (typeof usage.output_tokens === "number") {
    parts.push(`${format(usage.output_tokens)} output`);
  }

  const totalLabel = `${format(total)} tokens`;
  return parts.length > 0
    ? `This turn: ${totalLabel} (${parts.join(" · ")})`
    : `This turn: ${totalLabel}`;
}
