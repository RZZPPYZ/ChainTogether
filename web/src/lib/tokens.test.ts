import { describe, expect, it } from "vitest";

import {
  formatTokenCount,
  turnTokenCount,
  turnTokenTitle,
} from "./tokens";

describe("token count formatting", () => {
  it("keeps small counts exact and compacts larger ones", () => {
    expect(formatTokenCount(950)).toBe("950");
    expect(formatTokenCount(25_084)).toBe("25.1k");
    expect(formatTokenCount(100_000)).toBe("100k");
    expect(formatTokenCount(999_999)).toBe("1M");
    expect(formatTokenCount(1_234_567)).toBe("1.2M");
  });

  it("rejects missing or invalid values", () => {
    expect(formatTokenCount(null)).toBeNull();
    expect(formatTokenCount(Number.NaN)).toBeNull();
    expect(formatTokenCount(-1)).toBeNull();
  });
});

describe("per-turn token totals", () => {
  it("prefers the backend-normalized turn total", () => {
    expect(
      turnTokenCount({ turn_tokens: 50_287, input_tokens: 25_268 }),
    ).toBe(50_287);
  });

  it("adds Claude cache reads when deriving the total", () => {
    expect(
      turnTokenCount({
        backend: "claude-code",
        input_tokens: 250,
        cached_input_tokens: 24_832,
        cache_creation_input_tokens: 100,
        output_tokens: 2,
      }),
    ).toBe(25_184);
  });

  it("does not double-count Codex cached input", () => {
    expect(
      turnTokenCount({
        backend: "codex",
        input_tokens: 90_000,
        cached_input_tokens: 20_000,
        output_tokens: 10_000,
      }),
    ).toBe(100_000);
  });
});

describe("per-turn token tooltip", () => {
  it("breaks the total down by usage bucket", () => {
    expect(
      turnTokenTitle({
        backend: "claude-code",
        input_tokens: 250,
        cached_input_tokens: 24_832,
        output_tokens: 2,
        turn_tokens: 25_084,
      }),
    ).toBe(
      "This turn: 25,084 tokens (250 input · 24,832 cached · 2 output)",
    );
  });

  it("marks Codex cached tokens as included in input", () => {
    expect(
      turnTokenTitle({
        backend: "codex",
        input_tokens: 90_000,
        cached_input_tokens: 20_000,
        output_tokens: 10_000,
        turn_tokens: 100_000,
      }),
    ).toBe(
      "This turn: 100,000 tokens (90,000 input · 20,000 cached (included in input) · 10,000 output)",
    );
  });
});
