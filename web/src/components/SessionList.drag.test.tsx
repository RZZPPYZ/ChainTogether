import { fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  useSessionStore,
  type Agent,
  type SessionInfo,
} from "../stores/sessionStore";
import { SessionList } from "./SessionList";

const agent = {
  id: "agent-1",
  name: "Builder",
  backend: "claude-code",
  archived: false,
} as Agent;

const session = (
  id: string,
  name: string,
  sortOrder: number,
  createdAt: string,
): SessionInfo =>
  ({
    id,
    name,
    status: "idle",
    origin: "user",
    agent_id: agent.id,
    folder_id: null,
    sort_order: sortOrder,
    created_at: createdAt,
    working_dir: "F:\\work",
    backend: "claude-code",
  }) as SessionInfo;

describe("SessionList drag reorder", () => {
  beforeEach(() => {
    useSessionStore.setState({
      token: "token",
      agents: [agent],
      sessions: [
        session("a", "Alpha", 0, "2026-01-01"),
        session("b", "Bravo", 1, "2026-01-02"),
        session("c", "Charlie", 2, "2026-01-03"),
      ],
      credentials: [],
      availableBackends: ["claude-code"],
      showDelegations: false,
      activeSessionId: null,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("persists the moved order for the agent's group", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(
      <SessionList
        agentId={agent.id}
        formOpen={false}
        onCloseForm={() => {}}
      />,
    );

    const source = container.querySelector(
      '[data-session-id="a"]',
    ) as HTMLElement;
    const target = container.querySelector(
      '[data-session-id="c"]',
    ) as HTMLElement;
    expect(source).toBeTruthy();
    expect(target).toBeTruthy();

    vi.spyOn(target, "getBoundingClientRect").mockReturnValue({
      top: 100,
      height: 20,
    } as DOMRect);
    const originalElementFromPoint = document.elementFromPoint;
    document.elementFromPoint = (() => target) as typeof document.elementFromPoint;

    fireEvent.pointerDown(source, {
      button: 0,
      clientX: 100,
      clientY: 100,
      pointerId: 1,
    });
    // Bottom half of the target -> insert AFTER Charlie.
    fireEvent.pointerMove(window, {
      clientX: 110,
      clientY: 115,
      pointerId: 1,
      cancelable: true,
    });
    fireEvent.pointerUp(window, {
      clientX: 110,
      clientY: 115,
      pointerId: 1,
    });
    document.elementFromPoint = originalElementFromPoint;

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain(`/api/agents/${agent.id}/sessions/order`);
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({
      folder_id: null,
      session_ids: ["b", "c", "a"],
    });

    const orders = Object.fromEntries(
      useSessionStore
        .getState()
        .sessions.map((item) => [item.id, item.sort_order]),
    );
    expect(orders).toEqual({ b: 0, c: 1, a: 2 });
  });
});
