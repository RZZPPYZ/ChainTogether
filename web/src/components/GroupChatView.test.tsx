import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import {
  GroupAgentRunBlock,
  GroupChatView,
  GroupMarkdown,
  buildGroupTimeline,
  highlightMentions,
} from "./GroupChatView";
import {
  useSessionStore,
  type GroupInvocation,
  type Message,
} from "../stores/sessionStore";

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
      activity("result", {
        timestamp_ms: 1450,
        duration_ms: 450,
        cost: 0.01,
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
    expect(timeline.hiddenIndices).toEqual(new Set([1, 2, 3, 4, 5, 6, 7]));
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
      activity("result", {
        timestamp_ms: 1450,
        duration_ms: 450,
        cost: 0.01,
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
    expect(screen.getByText("Cost ≈1.0¢")).toBeTruthy();
    expect(screen.queryByText("npm test")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Expand execution details" }));
    expect(screen.getByText("npm test")).toBeTruthy();
    expect(screen.getByText("Tests passed")).toBeTruthy();
  });
});

describe("group execution controls", () => {
  beforeEach(() => {
    const invocation: GroupInvocation = {
      id: "invocation-1",
      group_id: "group-1",
      root_content: "Build it",
      status: "running",
      custody_state: "active",
      current_agent_id: null,
      depth: 0,
      held_until: null,
      hold_reason: null,
      created_at: "2026-07-26T00:00:00Z",
      updated_at: "2026-07-26T00:00:00Z",
      completed_at: null,
    };
    useSessionStore.setState({
      token: "",
      agents: [],
      activeGroupId: "group-1",
      groups: [
        {
          id: "group-1",
          name: "Build Team",
          agentIds: [],
          createdAt: "2026-07-26T00:00:00Z",
          sessionId: "group-session-1",
          defaultAgentId: null,
          workingDir: "F:/workspace",
        },
      ],
      messages: { "group-session-1": [] },
      groupInvocations: { "group-1": [invocation] },
      groupTypingAgents: {},
      groupStreamingReplies: {},
    });
  });

  it("places the stop control beside the composer send control", () => {
    render(<GroupChatView onToggleSidebar={() => {}} />);

    const stop = screen.getByRole("button", { name: "Stop group run" });
    const send = screen.getByRole("button", { name: "Send message" });
    expect(stop.closest(".chat-composer")).not.toBeNull();
    expect(send.closest(".chat-composer")).toBe(stop.closest(".chat-composer"));
  });
});
