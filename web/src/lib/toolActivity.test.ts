import { describe, expect, it } from "vitest";

import type { Message } from "../stores/sessionStore";
import {
  buildChatRenderItems,
  cleanToolResultPreview,
  describeToolStep,
  summarizeToolActivity,
  type ToolStep,
} from "./toolActivity";

function toolUse(
  id: string,
  toolName: string,
  input: Record<string, unknown> = {},
): Message {
  return {
    role: "assistant",
    type: "tool_use",
    tool_name: toolName,
    tool_input: input,
    tool_use_id: id,
  };
}

function toolResult(
  id: string,
  content: string,
  isError = false,
): Message {
  return {
    role: "tool",
    type: "tool_result",
    content,
    tool_use_id: id,
    is_error: isError,
  };
}

function textMessage(
  role: Message["role"],
  type: string,
  content: string,
): Message {
  return { role, type, content };
}

function thinkingMessage(content = ""): Message {
  return { role: "assistant", type: "thinking", content };
}

function activityItem(messages: Message[]) {
  const item = buildChatRenderItems(messages).items[0];
  if (item.kind !== "activity") throw new Error("expected an activity item");
  return item;
}

function step(overrides: Partial<ToolStep> = {}): ToolStep {
  return {
    id: "use-1",
    toolName: "Bash",
    input: { command: "bun run test" },
    result: "ok",
    isError: false,
    status: "ok",
    toolUseId: "tool-1",
    messageIndexes: [0, 1],
    ...overrides,
  };
}

describe("buildChatRenderItems pairing", () => {
  it("pairs a tool_use with its tool_result into one step", () => {
    const item = activityItem([
      toolUse("t1", "Bash", { command: "ls" }),
      toolResult("t1", "a\nb\n"),
    ]);

    expect(item.id).toBe("activity-t1");
    expect(item.steps).toHaveLength(1);
    expect(item.steps[0]).toMatchObject({
      toolName: "Bash",
      status: "ok",
      result: "a\nb\n",
      isError: false,
    });
    expect(item.steps[0]?.messageIndexes).toEqual([0, 1]);
  });

  it("marks a use without a result as running", () => {
    const item = activityItem([toolUse("t1", "Read", { file_path: "a.ts" })]);
    expect(item.steps[0]?.status).toBe("running");
    expect(item.steps[0]?.result).toBeUndefined();
    expect(item.turnEnded).toBe(false);
  });

  it("renders an orphan result as its own step", () => {
    const item = activityItem([toolResult("orphan", "boom", true)]);
    expect(item.steps).toHaveLength(1);
    expect(item.steps[0]).toMatchObject({
      id: "result-orphan",
      toolName: "Result",
      status: "error",
      isError: true,
      result: "boom",
    });
  });

  it("keeps the first result when duplicates arrive", () => {
    const item = activityItem([
      toolUse("t1", "Bash", { command: "ls" }),
      toolResult("t1", "first"),
      toolResult("t1", "second"),
    ]);
    expect(item.steps).toHaveLength(1);
    expect(item.steps[0]?.result).toBe("first");
    expect(item.steps[0]?.messageIndexes).toEqual([0, 1]);
  });

  it("keeps parallel calls independent and returns results to the right step", () => {
    const item = activityItem([
      toolUse("a", "Read", { file_path: "a.ts" }),
      toolUse("b", "Read", { file_path: "b.ts" }),
      toolResult("b", "B\n"),
      toolResult("a", "A\n"),
    ]);
    expect(item.steps.map((s) => s.toolUseId)).toEqual(["a", "b"]);
    expect(item.steps[0]?.result).toBe("A\n");
    expect(item.steps[1]?.result).toBe("B\n");
    expect(item.steps.every((s) => s.status === "ok")).toBe(true);
  });

  it("marks the group as turn-ended once a result badge follows it", () => {
    const before = activityItem([
      toolUse("t1", "Bash", { command: "ls" }),
      toolResult("t1", "ok"),
    ]);
    expect(before.turnEnded).toBe(false);

    const after = activityItem([
      toolUse("t1", "Bash", { command: "ls" }),
      toolResult("t1", "ok"),
      textMessage("system", "result", ""),
    ]);
    expect(after.turnEnded).toBe(true);
  });
});

describe("buildChatRenderItems grouping boundaries", () => {
  it("breaks groups on text, approvals, questions, notices and result badges", () => {
    const messages: Message[] = [
      toolUse("a", "Read", { file_path: "a.ts" }),
      toolResult("a", "one\n"),
      textMessage("assistant", "text", "Thinking"),
      { ...toolUse("approval", "Bash", { command: "rm" }), type: "tool_approval_request" },
      toolUse("b", "Read", { file_path: "b.ts" }),
      toolResult("b", "two\n"),
      { ...toolUse("q", "AskUserQuestion", {}), type: "question_request" },
      textMessage("system", "notice", "hello"),
      textMessage("system", "result", ""),
    ];

    const { items, messageToItemIndex } = buildChatRenderItems(messages);

    expect(items.map((item) => item.kind)).toEqual([
      "activity",
      "message",
      "message",
      "activity",
      "message",
      "message",
      "message",
    ]);
    expect(messageToItemIndex).toEqual([0, 0, 1, 2, 3, 3, 4, 5, 6]);

    const [first, , , second] = items;
    expect(first?.kind === "activity" && first.steps).toHaveLength(1);
    expect(second?.kind === "activity" && second.steps).toHaveLength(1);
    expect(first?.kind === "activity" && first.turnEnded).toBe(true);
    expect(second?.kind === "activity" && second.turnEnded).toBe(true);
  });

  it("keeps a stable group id as the group grows", () => {
    const initial = buildChatRenderItems([
      toolUse("t1", "Read", { file_path: "a.ts" }),
    ]).items[0];
    const grown = buildChatRenderItems([
      toolUse("t1", "Read", { file_path: "a.ts" }),
      toolResult("t1", "done"),
      toolUse("t2", "Bash", { command: "ls" }),
    ]).items[0];

    expect(initial?.kind === "activity" && initial.id).toBe("activity-t1");
    expect(grown?.kind === "activity" && grown.id).toBe("activity-t1");
    expect(grown?.kind === "activity" && grown.steps).toHaveLength(2);
  });

  it("renders non-empty thinking and keeps groups across empty thinking rows", () => {
    const messages: Message[] = [
      toolUse("a", "Read", { file_path: "a.ts" }),
      toolResult("a", "one\n"),
      thinkingMessage("Now check the callers"),
      toolUse("b", "Grep", { pattern: "foo" }),
      toolResult("b", "x.ts:1: foo\n"),
      thinkingMessage(""),
      toolUse("c", "Bash", { command: "ls" }),
      toolResult("c", "a.ts\n"),
    ];

    const { items, messageToItemIndex } = buildChatRenderItems(messages);

    // Visible thinking splits the run; the EMPTY thinking after Grep is
    // invisible and must not split Grep+Bash into separate groups.
    expect(items.map((item) => item.kind)).toEqual([
      "activity",
      "message",
      "activity",
    ]);
    const first = items[0];
    const thinking = items[1];
    const second = items[2];
    expect(first?.kind === "activity" && first.steps.map((s) => s.toolName)).toEqual(
      ["Read"],
    );
    expect(thinking?.kind === "message" && thinking.message.type).toBe(
      "thinking",
    );
    expect(second?.kind === "activity" && second.steps.map((s) => s.toolName)).toEqual(
      ["Grep", "Bash"],
    );
    expect(messageToItemIndex).toEqual([0, 0, 1, 2, 2, -1, 2, 2]);
  });

  it("maps every original message to a render item", () => {
    const messages: Message[] = [
      textMessage("user", "text", "hello"),
      toolUse("t1", "Bash", { command: "ls" }),
      toolResult("t1", "ok"),
      textMessage("assistant", "text", "done"),
    ];
    const { items, messageToItemIndex } = buildChatRenderItems(messages);
    expect(items).toHaveLength(3);
    expect(messageToItemIndex).toEqual([0, 1, 1, 2]);
  });
});

describe("summarizeToolActivity", () => {
  it("counts steps per tool and total failures in first-seen order", () => {
    const summary = summarizeToolActivity([
      step({ id: "a" }),
      step({ id: "b", status: "error", isError: true }),
      step({ id: "c", toolName: "Read", input: { file_path: "a.ts" } }),
    ]);

    expect(summary.total).toBe(3);
    expect(summary.counts).toEqual([
      { label: "Bash", count: 2 },
      { label: "Read", count: 1 },
    ]);
    expect(summary.failed).toBe(1);
  });
});

describe("describeToolStep", () => {
  it("describes Bash by command and exit status", () => {
    const done = describeToolStep(
      step({ input: { command: "bun   run test" }, result: "ok" }),
    );
    expect(done).toMatchObject({
      icon: "terminal",
      verb: "Ran",
      target: "bun run test",
      hint: "exit 0",
      hintTone: "default",
    });

    const failed = describeToolStep(
      step({
        status: "error",
        isError: true,
        result: "Command failed (exit code 2)",
      }),
    );
    expect(failed.hint).toBe("exit 2");
    expect(failed.hintTone).toBe("error");

    const running = describeToolStep(
      step({ status: "running", result: undefined }),
    );
    expect(running.hint).toBe("running");
    expect(running.hintTone).toBe("running");
  });

  it("truncates long commands", () => {
    const description = describeToolStep(
      step({ input: { command: "x".repeat(120) } }),
    );
    expect(description.target).toHaveLength(60);
    expect(description.target.endsWith("…")).toBe(true);
  });

  it("describes Read by path and line count", () => {
    const description = describeToolStep(
      step({
        toolName: "Read",
        input: { file_path: "src/a.ts" },
        result: "one\ntwo\nthree\n",
      }),
    );
    expect(description).toMatchObject({
      icon: "file",
      verb: "Read",
      target: "src/a.ts",
      hint: "3 lines",
    });
  });

  it("computes Edit line deltas from the tool input", () => {
    const edit = describeToolStep(
      step({
        toolName: "Edit",
        input: {
          file_path: "src/a.ts",
          old_string: "a\nb",
          new_string: "a\nb\nc",
        },
      }),
    );
    expect(edit).toMatchObject({
      icon: "edit",
      verb: "Edited",
      target: "src/a.ts",
      hint: "+3 −2",
    });

    const write = describeToolStep(
      step({
        toolName: "Write",
        input: { file_path: "src/b.ts", content: "x\ny" },
      }),
    );
    expect(write.hint).toBe("+2 −0");

    const unknown = describeToolStep(
      step({
        toolName: "Edit",
        input: { file_path: "src/c.ts" },
      }),
    );
    expect(unknown.hint).toBe("edit");
  });

  it("describes Grep by pattern and rough match count", () => {
    const description = describeToolStep(
      step({
        toolName: "Grep",
        input: { pattern: "foo" },
        result: "a.ts:1: foo\nb.ts:2: foo\n\n",
      }),
    );
    expect(description).toMatchObject({
      icon: "search",
      verb: "Searched",
      target: '"foo"',
      hint: "2 matches",
    });
  });

  it("describes WebFetch by host and WebSearch by query", () => {
    const fetched = describeToolStep(
      step({
        toolName: "WebFetch",
        input: { url: "https://example.com/docs" },
        result: "Docs title\nmore",
      }),
    );
    expect(fetched).toMatchObject({
      icon: "world",
      verb: "Fetched",
      target: "example.com",
      hint: "Docs title",
    });

    const searched = describeToolStep(
      step({
        toolName: "WebSearch",
        input: { query: "claude   code" },
        result: "Result line",
      }),
    );
    expect(searched).toMatchObject({
      verb: "Searched",
      target: '"claude code"',
      hint: "Result line",
    });
  });

  it("keeps bg tasks and delegations recognizable", () => {
    const bg = describeToolStep(
      step({
        toolName: "mcp__bg__run",
        input: { command: "bun run dev", description: "Start dev server" },
        result: "Started bg task abc",
      }),
    );
    expect(bg).toMatchObject({
      icon: "terminal",
      label: "bg",
      verb: "Started bg task",
      target: "Start dev server",
    });

    const asked = describeToolStep(
      step({
        toolName: "mcp__ask_agent__ask",
        input: { name: "Vera", request: "Review this" },
        result: "Started delegation abc",
      }),
    );
    expect(asked).toMatchObject({
      verb: "Asked",
      target: "Vera",
      hint: "replied",
    });
  });

  it("falls back to the tool name and a cleaned result preview", () => {
    const json = describeToolStep(
      step({
        toolName: "mcp__foo__bar",
        input: {},
        result: '{\n  "ok": true\n}',
      }),
    );
    expect(json.verb).toBe("mcp__foo__bar");
    expect(json.target).toBe('{"ok":true}');

    const plain = describeToolStep(
      step({
        toolName: "mcp__foo__baz",
        input: {},
        result: `${"a".repeat(120)}\nsecond line`,
      }),
    );
    expect(plain.target).toHaveLength(100);
    expect(plain.target.endsWith("…")).toBe(true);
    expect(plain.target.includes("second line")).toBe(false);
  });
});

describe("cleanToolResultPreview", () => {
  it("falls back to the raw first line when the payload is not JSON", () => {
    expect(cleanToolResultPreview("  first line\nsecond  ")).toBe("first line");
  });

  it("compacts JSON payloads", () => {
    expect(cleanToolResultPreview('{"a": 1, "b": [2, 3]}')).toBe(
      '{"a":1,"b":[2,3]}',
    );
  });

  it("returns an empty string for empty output", () => {
    expect(cleanToolResultPreview(undefined)).toBe("");
    expect(cleanToolResultPreview("   ")).toBe("");
  });
});
