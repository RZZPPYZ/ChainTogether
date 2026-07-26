import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useSessionStore, type Agent } from "../stores/sessionStore";
import { CreateGroupDialog } from "./CreateGroupDialog";

const agent = (id: string, name: string): Agent =>
  ({ id, name, backend: "claude-code", archived: false }) as Agent;

describe("CreateGroupDialog working directory", () => {
  beforeEach(() => {
    useSessionStore.setState({
      token: "token",
      agents: [agent("agent-1", "Builder"), agent("agent-2", "Reviewer")],
      groups: [],
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends and stores the selected Group working directory", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "group-1",
        name: "Build Team",
        agent_ids: ["agent-1", "agent-2"],
        created_at: "2026-07-26T00:00:00Z",
        session_id: "group-session-1",
        default_agent_id: null,
        working_dir: "F:\\projects\\chain",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<CreateGroupDialog open onOpenChange={() => {}} />);
    fireEvent.change(screen.getByLabelText("Group name"), {
      target: { value: "Build Team" },
    });
    fireEvent.change(screen.getByLabelText("Working directory"), {
      target: { value: "F:\\projects\\chain" },
    });
    screen.getAllByRole("checkbox").forEach((checkbox) => {
      fireEvent.click(checkbox);
    });
    fireEvent.click(screen.getByRole("button", { name: "Create group" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(request.body as string)).toMatchObject({
      working_dir: "F:\\projects\\chain",
    });
    expect(useSessionStore.getState().groups[0].workingDir).toBe(
      "F:\\projects\\chain",
    );
  });
});
