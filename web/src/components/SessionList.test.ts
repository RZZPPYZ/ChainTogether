import { describe, expect, it } from "vitest";

import type { SessionInfo } from "../stores/sessionStore";
import { getAgentSidebarSessions } from "./SessionList";

const session = (
  id: string,
  origin: string,
  agentId = "agent-1",
): SessionInfo =>
  ({ id, origin, agent_id: agentId }) as SessionInfo;

describe("Agent sidebar session visibility", () => {
  it("keeps Group backing and member sessions out of Agent lists", () => {
    const visible = getAgentSidebarSessions(
      [
        session("user", "user"),
        session("delegation", "delegation"),
        session("group", "group"),
        session("member", "group_member"),
        session("other-agent", "user", "agent-2"),
      ],
      "agent-1",
    );

    expect(visible.map((item) => item.id)).toEqual(["user", "delegation"]);
  });
});
