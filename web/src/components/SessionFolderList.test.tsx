import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  useSessionStore,
  type Agent,
  type SessionFolder,
  type SessionInfo,
} from "../stores/sessionStore";
import { SessionFolderList } from "./SessionFolderList";

const agent = {
  id: "agent-1",
  name: "Builder",
  backend: "claude-code",
  archived: false,
} as Agent;

const folder: SessionFolder = {
  id: "folder-1",
  agent_id: "agent-1",
  name: "Frontend",
  working_dir: "F:\\work\\frontend",
  session_count: 0,
  created_at: "2026-11-10T00:00:00Z",
  updated_at: "2026-11-10T00:00:00Z",
};

const session = {
  id: "session-1",
  name: "Build UI",
  working_dir: folder.working_dir,
  status: "idle",
  created_at: "2026-11-10T00:00:00Z",
  agent_id: agent.id,
  folder_id: folder.id,
  origin: "user",
  backend: "claude-code",
} as SessionInfo;

const response = (data: unknown) => ({
  ok: true,
  status: 200,
  json: async () => data,
});

describe("SessionFolderList", () => {
  beforeEach(() => {
    useSessionStore.setState({
      token: "token",
      agents: [agent],
      sessions: [],
      sessionFolders: [],
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("creates a folder session without asking for a path", async () => {
    const fetchMock = vi.fn(
      async (url: string, init?: RequestInit) => {
        if (String(url).includes("/folders")) return response([folder]);
        if (
          String(url).endsWith("/api/agents/agent-1/sessions") &&
          init?.method === "POST"
        ) {
          return response(session);
        }
        return response({});
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <SessionFolderList
        agentId={agent.id}
        formOpen={false}
        onCloseForm={() => {}}
      />,
    );

    await waitFor(() => expect(screen.getByText("Frontend")).toBeVisible());
    fireEvent.click(screen.getByText("Frontend"));
    fireEvent.click(screen.getByLabelText("New session in Frontend"));

    expect(
      screen.queryByPlaceholderText("Working directory (optional)"),
    ).toBeNull();
    expect(screen.getByText(folder.working_dir)).toBeVisible();

    fireEvent.change(screen.getByPlaceholderText("Session name"), {
      target: { value: "Build UI" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).endsWith("/api/agents/agent-1/sessions") &&
          (init as RequestInit)?.method === "POST",
      );
      expect(call).toBeTruthy();
      const body = JSON.parse(
        (call![1] as RequestInit).body as string,
      ) as Record<string, unknown>;
      expect(body).toMatchObject({
        name: "Build UI",
        folder_id: folder.id,
        working_dir: null,
      });
    });
    expect(useSessionStore.getState().sessions).toHaveLength(1);
  });

  it("creates a folder with its working directory and opens its first session form", async () => {
    const created = {
      ...folder,
      name: "Backend",
      working_dir: "F:\\work\\backend",
    };
    const fetchMock = vi.fn(
      async (url: string, init?: RequestInit) => {
        if (String(url).includes("/folders") && init?.method === "POST") {
          return response(created);
        }
        if (String(url).includes("/folders")) return response([]);
        return response({});
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const onCloseForm = vi.fn();

    render(
      <SessionFolderList
        agentId={agent.id}
        formOpen
        onCloseForm={onCloseForm}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("Folder name"), {
      target: { value: "Backend" },
    });
    fireEvent.change(screen.getByPlaceholderText("Working directory"), {
      target: { value: "F:\\work\\backend" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(onCloseForm).toHaveBeenCalled());
    expect(useSessionStore.getState().sessionFolders).toHaveLength(1);
    const call = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/api/agents/agent-1/folders") &&
        (init as RequestInit)?.method === "POST",
    );
    expect(
      JSON.parse((call![1] as RequestInit).body as string),
    ).toMatchObject({
      name: "Backend",
      working_dir: "F:\\work\\backend",
    });
    // The new folder is expanded with its first-session form ready.
    expect(screen.getByPlaceholderText("Session name")).toBeVisible();
  });

  it("detaches sessions locally when a folder is deleted", async () => {
    const existing = { ...session, folder_id: folder.id } as SessionInfo;
    useSessionStore.setState({
      sessions: [existing],
      sessionFolders: [folder],
    });
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).includes("/folders") && init?.method === "DELETE") {
        return { ...response(null), status: 204 };
      }
      if (String(url).includes("/folders")) return response([folder]);
      return response({});
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <SessionFolderList
        agentId={agent.id}
        formOpen={false}
        onCloseForm={() => {}}
      />,
    );

    await waitFor(() => expect(screen.getByText("Frontend")).toBeVisible());
    fireEvent.click(screen.getByLabelText("Delete Frontend"));

    await waitFor(() =>
      expect(useSessionStore.getState().sessionFolders).toHaveLength(0),
    );
    const stored = useSessionStore.getState().sessions;
    expect(stored).toHaveLength(1);
    expect(stored[0].folder_id).toBeNull();
    expect(stored[0].working_dir).toBe(folder.working_dir);
  });
});
