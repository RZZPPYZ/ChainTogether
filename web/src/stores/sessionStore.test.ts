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
  });
});
