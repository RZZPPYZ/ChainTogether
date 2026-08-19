import { beforeEach, describe, expect, it } from "vitest";

import { handleWsMessage } from "./useWebSocket";
import { useSessionStore } from "../stores/sessionStore";


describe("group member session chain events", () => {
  beforeEach(() => {
    useSessionStore.setState({
      groups: [{
        id: "group-1",
        name: "Team",
        agentIds: ["agent-1"],
        createdAt: "2026-08-19T00:00:00Z",
        sessionId: "group-root",
        workingDir: "C:/workspace",
        memberSessions: [{
          agentId: "agent-1",
          sessionId: "session-1",
          generation: 1,
          chainLength: 1,
          contextUsage: {
            context_window: 200000,
            remaining_ratio: 0.05,
            source: "reported",
          },
        }],
      }],
    });
  });

  it("applies a durable rotation projection from the websocket", () => {
    handleWsMessage({
      type: "group_member_session_chain",
      event_type: "warning",
      group_id: "group-1",
      agent_id: "agent-1",
      session_id: "session-1",
    });
    expect(useSessionStore.getState().groups[0].memberSessions?.[0]).toMatchObject({
      sessionId: "session-1",
      chainStatus: "warning",
      chainEventType: "warning",
    });

    handleWsMessage({
      type: "group_member_session_chain",
      event_type: "summary_degraded",
      group_id: "group-1",
      agent_id: "agent-1",
      session_id: "session-1",
    });
    expect(useSessionStore.getState().groups[0].memberSessions?.[0]).toMatchObject({
      chainStatus: "degraded",
      summaryDegraded: true,
    });

    handleWsMessage({
      type: "group_member_session_chain",
      event_type: "successor_created",
      group_id: "group-1",
      agent_id: "agent-1",
      previous_session_id: "session-1",
      session_id: "session-2",
      generation: 2,
      chain_length: 2,
      chain_status: "active",
    });

    expect(useSessionStore.getState().groups[0].memberSessions?.[0]).toMatchObject({
      sessionId: "session-2",
      generation: 2,
      chainLength: 2,
      contextUsage: null,
      chainStatus: "active",
      summaryDegraded: true,
    });

    handleWsMessage({
      type: "group_member_session_chain",
      event_type: "bootstrap_consumed",
      group_id: "group-1",
      agent_id: "agent-1",
      session_id: "session-2",
      generation: 2,
    });
    expect(useSessionStore.getState().groups[0].memberSessions?.[0]).toMatchObject({
      chainEventType: "bootstrap_consumed",
      chainStatus: "active",
    });
  });
});
