import { describe, expect, it } from "vitest";

import {
  getAgentSidebarSessions,
  reorderSessionIds,
  sortSessionsByOrder,
} from "../lib/sessionOrder";
import type { SessionInfo } from "../stores/sessionStore";

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

  it("splits top-level sessions from folder sessions", () => {
    const withFolder = (id: string, folderId: string | null): SessionInfo =>
      ({ ...session(id, "user"), folder_id: folderId }) as SessionInfo;
    const all = [
      withFolder("top-level", null),
      withFolder("folder-a-1", "folder-a"),
      withFolder("folder-a-2", "folder-a"),
      withFolder("folder-b-1", "folder-b"),
    ];

    expect(
      getAgentSidebarSessions(all, "agent-1").map((item) => item.id),
    ).toEqual(["top-level"]);
    expect(
      getAgentSidebarSessions(all, "agent-1", "folder-a").map(
        (item) => item.id,
      ),
    ).toEqual(["folder-a-1", "folder-a-2"]);
  });

  it("sorts by manual order and falls back to creation time", () => {
    const ordered = [
      { ...session("newer-tie", "user"), sort_order: 1, created_at: "2026-02-01" },
      { ...session("second", "user"), sort_order: 1, created_at: "2026-01-01" },
      { ...session("first", "user"), sort_order: 0, created_at: "2026-03-01" },
    ] as SessionInfo[];

    expect(sortSessionsByOrder(ordered).map((item) => item.id)).toEqual([
      "first",
      "second",
      "newer-tie",
    ]);
  });
});

describe("Session drag reorder", () => {
  it("moves an id before or after its drop target", () => {
    expect(reorderSessionIds(["a", "b", "c"], "a", "c", "after")).toEqual([
      "b",
      "c",
      "a",
    ]);
    expect(reorderSessionIds(["a", "b", "c"], "c", "a", "before")).toEqual([
      "c",
      "a",
      "b",
    ]);
    expect(reorderSessionIds(["a", "b", "c"], "c", "b", "before")).toEqual([
      "a",
      "c",
      "b",
    ]);
  });

  it("ignores no-op and unknown-id moves", () => {
    expect(reorderSessionIds(["a", "b"], "a", "a", "before")).toBeNull();
    expect(reorderSessionIds(["a", "b"], "missing", "b", "before")).toBeNull();
    expect(reorderSessionIds(["a", "b"], "a", "missing", "after")).toBeNull();
  });
});
