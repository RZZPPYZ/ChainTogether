import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  GroupAgentRunBlock,
  GroupMarkdown,
  buildGroupTimeline,
  highlightMentions,
} from "./GroupChatView";
import type { Message } from "../stores/sessionStore";

describe("group mention highlighting", () => {
  it("highlights canonical and alias handles without changing message text", () => {
    const { container } = render(
      <div>{highlightMentions("@Builder, ask @FENG.", ["Builder", "Feng"])}</div>,
    );

    expect(container.textContent).toBe("@Builder, ask @FENG.");
    expect(
      [...container.querySelectorAll(".mention-highlight")].map(
        (element) => element.textContent,
      ),
    ).toEqual(["@Builder", "@FENG"]);
  });

  it("highlights mentions inside Markdown but leaves code unchanged", () => {
    const { container } = render(
      <GroupMarkdown
        text={"**@Builder** continue, but keep `@Builder` literal."}
        memberNames={["Builder"]}
      />,
    );

    expect(container.querySelectorAll(".mention-highlight")).toHaveLength(1);
    expect(container.querySelector("strong .mention-highlight")?.textContent).toBe(
      "@Builder",
    );
    expect(container.querySelector("code")?.textContent).toBe("@Builder");
  });
});

describe("group execution timeline", () => {
  const activity = (
    phase: string,
    extra: Record<string, unknown> = {},
  ): Message => ({
    role: "system",
    type: "group_agent_activity",
    content: JSON.stringify({
      run_id: "run-1",
      invocation_id: "invocation-1",
      agent_name: "Builder",
      phase,
      timestamp_ms: 1000,
      ...extra,
    }),
  });

  it("rebuilds one run and absorbs its committed reply after reload", () => {
    const messages: Message[] = [
      activity("started"),
      activity("thinking", { timestamp_ms: 1100 }),
      activity("tool_started", {
        timestamp_ms: 1200,
        tool_name: "Bash",
        tool_use_id: "tool-1",
        tool_input: { command: "npm test" },
      }),
      activity("tool_finished", {
        timestamp_ms: 1400,
        tool_use_id: "tool-1",
        output: "Tests passed",
      }),
      activity("text", { timestamp_ms: 1500, content: "All checks passed." }),
      activity("completed", { timestamp_ms: 1600 }),
      {
        role: "user",
        type: "text",
        content: "[agent-reply:Builder]\n\nAll checks passed.",
      },
    ];

    const timeline = buildGroupTimeline(messages);
    const item = timeline.runsByFirstIndex.get(0);
    expect(timeline.runsByFirstIndex.size).toBe(1);
    expect(item?.run.status).toBe("completed");
    expect(item?.finalText).toBe("All checks passed.");
    expect(timeline.hiddenIndices).toEqual(new Set([1, 2, 3, 4, 5, 6]));
    expect(item?.run.blocks.find((block) => block.kind === "tool")).toMatchObject({
      toolName: "Bash",
      output: "Tests passed",
    });
  });

  it("keeps tool details collapsed while leaving the final response visible", () => {
    const timeline = buildGroupTimeline([
      activity("started"),
      activity("tool_started", {
        timestamp_ms: 1200,
        tool_name: "Bash",
        tool_use_id: "tool-1",
        tool_input: { command: "npm test" },
      }),
      activity("tool_finished", {
        timestamp_ms: 1400,
        tool_use_id: "tool-1",
        output: "Tests passed",
      }),
      activity("text", { timestamp_ms: 1500, content: "All checks passed." }),
      activity("completed", { timestamp_ms: 1600 }),
    ]);
    const item = timeline.runsByFirstIndex.get(0)!;

    render(
      <GroupAgentRunBlock
        run={item.run}
        avatar="B"
        finalText="All checks passed."
      />,
    );

    expect(screen.getByText("All checks passed.")).toBeTruthy();
    expect(screen.queryByText("npm test")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Expand execution details" }));
    expect(screen.getByText("npm test")).toBeTruthy();
    expect(screen.getByText("Tests passed")).toBeTruthy();
  });
});
