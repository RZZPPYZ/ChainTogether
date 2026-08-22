import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  useSessionStore,
  type Agent,
  type SessionInfo,
} from "../stores/sessionStore";
import { ArchivedSessionsDialog } from "./ArchivedSessionsDialog";

const agent = {
  id: "agent-1",
  name: "Builder",
  avatar: "🛠️",
} as Agent;

const archivedSession = (
  id: string,
  name: string,
  sealed: boolean,
): SessionInfo =>
  ({
    id,
    name,
    agent_id: agent.id,
    archived: true,
    sealed,
  }) as SessionInfo;

describe("ArchivedSessionsDialog sealed generations", () => {
  beforeEach(() => {
    useSessionStore.setState({
      token: "test-token",
      agents: [agent],
      sessions: [],
      archivedSessions: [],
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps a sealed predecessor read-only while ordinary archives stay recoverable", async () => {
    const archived = [
      archivedSession("sealed-1", "Sealed predecessor", true),
      archivedSession("archive-1", "Ordinary archive", false),
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => archived,
      }),
    );

    render(<ArchivedSessionsDialog open onOpenChange={() => {}} />);

    const sealedName = await screen.findByText("Sealed predecessor");
    const sealedRow = sealedName.closest(".archived-session-row");
    const ordinaryRow = screen
      .getByText("Ordinary archive")
      .closest(".archived-session-row");
    expect(sealedRow).not.toBeNull();
    expect(ordinaryRow).not.toBeNull();

    expect(
      within(sealedRow as HTMLElement).queryByRole("button", {
        name: /Unarchive/,
      }),
    ).toBeNull();
    expect(
      within(ordinaryRow as HTMLElement).getByRole("button", {
        name: /Unarchive/,
      }),
    ).toBeTruthy();
    await waitFor(() => {
      expect(
        within(sealedRow as HTMLElement).getByText(/Session Chain/),
      ).toBeTruthy();
    });
  });
});
