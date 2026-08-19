import { beforeEach, describe, expect, it } from "vitest";

import { useSessionStore, type Agent } from "./sessionStore";

describe("agent identity updates", () => {
  it("replaces a cleared alias instead of retaining the old handle", () => {
    const agent = {
      id: "agent-1",
      name: "胖虎",
      alias: "峰哥",
    } as Agent;
    useSessionStore.setState({ agents: [agent] });

    useSessionStore.getState().upsertAgent({ ...agent, alias: "" });

    expect(useSessionStore.getState().agents[0].name).toBe("胖虎");
    expect(useSessionStore.getState().agents[0].alias).toBe("");
  });
});

describe("group agent activity blocks", () => {
  beforeEach(() => {
    useSessionStore.setState({ groupAgentRuns: {} });
  });

  it("builds one ordered message from normalized CLI events", () => {
    const apply = useSessionStore.getState().applyGroupAgentActivity;
    const base = {
      run_id: "run-1",
      invocation_id: "invocation-1",
      agent_name: "Builder",
    } as const;

    apply("group-session", { ...base, phase: "started" });
    apply("group-session", { ...base, phase: "thinking" });
    apply("group-session", {
      ...base,
      phase: "tool_started",
      tool_name: "Bash",
      tool_use_id: "tool-1",
      tool_input: { command: "python -m unittest" },
    });
    apply("group-session", {
      ...base,
      phase: "tool_finished",
      tool_use_id: "tool-1",
      output: "OK",
    });
    apply("group-session", {
      ...base,
      phase: "text",
      content: "Finished the checks.",
    });
    apply("group-session", {
      ...base,
      phase: "result",
      duration_ms: 1250,
      cost: 0.01,
      context_usage: {
        input_tokens: 90000,
        output_tokens: 10000,
        total_tokens: 100000,
        context_window: 400000,
        remaining_tokens: 300000,
        remaining_ratio: 0.75,
        source: "estimated",
      },
    });
    apply("group-session", { ...base, phase: "completed" });

    const run =
      useSessionStore.getState().groupAgentRuns["group-session"]["run-1"];
    expect(run.runId).toBe("run-1");
    expect(run.status).toBe("completed");
    expect(run.blocks.map((block) => block.kind)).toEqual([
      "stage",
      "stage",
      "tool",
      "response",
      "stage",
    ]);
    expect(run.blocks.find((block) => block.kind === "tool")).toMatchObject({
      toolName: "Bash",
      output: "OK",
      status: "completed",
    });
    expect(run.blocks.find((block) => block.kind === "response")).toMatchObject({
      content: "Finished the checks.",
      status: "completed",
    });
    expect(run.durationMs).toBe(1250);
    expect(run.cost).toBe(0.01);
    expect(run.contextUsage?.remaining_ratio).toBe(0.75);
    expect(run.contextUsage?.remaining_tokens).toBe(300000);
  });
});

describe("group session chain rotation", () => {
  it("replaces the active member session and clears stale context usage", () => {
    useSessionStore.setState({
      groups: [
        {
          id: "group-1",
          name: "Team",
          agentIds: ["agent-1"],
          createdAt: "2026-08-19T00:00:00Z",
          sessionId: "group-root",
          workingDir: "C:/workspace",
          memberSessions: [
            {
              agentId: "agent-1",
              sessionId: "session-1",
              generation: 1,
              chainLength: 1,
              chainStatus: "active",
              contextUsage: {
                context_window: 200000,
                remaining_tokens: 10000,
                remaining_ratio: 0.05,
                source: "reported",
              },
            },
          ],
        },
      ],
    });

    useSessionStore.getState().applyGroupMemberSessionChain({
      eventType: "successor_created",
      groupId: "group-1",
      agentId: "agent-1",
      previousSessionId: "session-1",
      sessionId: "session-2",
      generation: 2,
      chainLength: 2,
      chainStatus: "active",
    });

    expect(useSessionStore.getState().groups[0].memberSessions?.[0]).toMatchObject({
      sessionId: "session-2",
      generation: 2,
      chainLength: 2,
      chainStatus: "active",
      contextUsage: null,
    });
  });
});
