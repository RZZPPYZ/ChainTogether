import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useSessionStore } from "../stores/sessionStore";
import { GroupList } from "./GroupList";

describe("Group sidebar visibility", () => {
  beforeEach(() => {
    useSessionStore.setState({
      token: "",
      agents: [],
      activeGroupId: null,
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
    });
  });

  it("shows existing groups without requiring the section to be opened", () => {
    render(<GroupList onCreateGroup={() => {}} />);

    expect(screen.getByText("Build Team")).toBeTruthy();
  });
});
