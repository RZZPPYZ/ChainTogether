import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useSessionStore, type SessionInfo } from "../stores/sessionStore";
import { ChatView } from "./ChatView";

const archivedSession = (sealed: boolean): SessionInfo =>
  ({
    id: sealed ? "sealed-session" : "ordinary-archive",
    name: sealed ? "Sealed predecessor" : "Ordinary archive",
    working_dir: "C:/workspace",
    status: "idle",
    created_at: "2026-08-22T00:00:00Z",
    message_count: 0,
    origin: sealed ? "group_member" : "user",
    backend: "codex",
    can_fork: false,
    fork_is_full_copy: false,
    archived: true,
    sealed,
  }) as SessionInfo;

const renderArchivedChat = (sealed: boolean) => {
  const session = archivedSession(sealed);
  useSessionStore.setState({
    token: "test-token",
    activeSessionId: session.id,
    activeAgentId: null,
    sessions: [],
    archivedSessions: [session],
    agents: [],
    messages: { [session.id]: [] },
    pendingQueue: {},
    pendingQuestions: {},
  });
  render(
    <ChatView
      sendMessage={vi.fn()}
      interrupt={vi.fn()}
      approveTool={vi.fn()}
      denyTool={vi.fn()}
      answerQuestion={vi.fn()}
      connected
      onToggleSidebar={vi.fn()}
      onOpenSchedules={vi.fn()}
    />,
  );
};

describe("ChatView archived session guidance", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => [] }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("explains the immutable Session Chain path for a sealed predecessor", () => {
    renderArchivedChat(true);

    expect(screen.getByText(/sealed Session Chain history/i)).toBeTruthy();
    expect(screen.getByText(/active generation/i)).toBeTruthy();
    expect(screen.queryByText(/Unarchive from the sidebar/i)).toBeNull();
  });

  it("keeps ordinary archived sessions recoverable", () => {
    renderArchivedChat(false);

    expect(screen.getByText(/Unarchive from the sidebar/i)).toBeTruthy();
  });
});
