import { useCallback, useEffect, useState } from "react";
import {
  IconChevronRight,
  IconFolder,
  IconPencil,
  IconPlus,
  IconTrash,
} from "@tabler/icons-react";
import { getAgentSidebarSessions } from "../lib/sessionOrder";
import {
  useSessionStore,
  type SessionFolder,
} from "../stores/sessionStore";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { SessionList } from "./SessionList";

const API_URL = window.location.origin;

/** Folder rows for one agent. A folder owns a working directory; its nested
 * SessionList creates sessions without asking for a path, and the server
 * inherits the folder's directory. Rendering is nested under the agent row in
 * AgentList, alongside the agent's top-level SessionList. */
export function SessionFolderList({
  agentId,
  formOpen,
  onCloseForm,
}: {
  agentId: string;
  formOpen: boolean;
  onCloseForm: () => void;
}) {
  const token = useSessionStore((s) => s.token);
  const sessions = useSessionStore((s) => s.sessions);
  const setSessions = useSessionStore((s) => s.setSessions);
  const showDelegations = useSessionStore((s) => s.showDelegations);
  const sessionFolders = useSessionStore((s) => s.sessionFolders);
  const setSessionFolders = useSessionStore((s) => s.setSessionFolders);
  const upsertSessionFolder = useSessionStore((s) => s.upsertSessionFolder);
  const removeSessionFolder = useSessionStore((s) => s.removeSessionFolder);
  const setActiveAgentId = useSessionStore((s) => s.setActiveAgentId);
  const setActiveGroupId = useSessionStore((s) => s.setActiveGroupId);

  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(
    new Set(),
  );
  // Which folder's "new session" form is open (one at a time).
  const [sessionFormFolderId, setSessionFormFolderId] = useState<string | null>(
    null,
  );
  // Which folder is being edited inline (one at a time).
  const [editingFolderId, setEditingFolderId] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [newPath, setNewPath] = useState("");
  const [editName, setEditName] = useState("");
  const [editPath, setEditPath] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const fetchFolders = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_URL}/api/agents/${agentId}/folders`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const data = (await res.json()) as SessionFolder[];
      // Replace only this agent's slice; another expanded agent may already
      // have populated its own folders in the shared store.
      const others = useSessionStore
        .getState()
        .sessionFolders.filter((f) => f.agent_id !== agentId);
      setSessionFolders([...others, ...data]);
    } catch {
      // ignore
    }
  }, [token, agentId, setSessionFolders]);

  useEffect(() => {
    fetchFolders();
  }, [fetchFolders]);

  // Clear any stale error/input each time the create-folder form opens.
  useEffect(() => {
    if (formOpen) {
      setNewName("");
      setNewPath("");
      setFormError(null);
    }
  }, [formOpen]);

  const folders = sessionFolders
    .filter((f) => f.agent_id === agentId)
    .sort((a, b) => a.name.localeCompare(b.name));

  const countVisibleSessions = (folderId: string) =>
    getAgentSidebarSessions(sessions, agentId, folderId).filter(
      (s) => showDelegations || s.origin !== "delegation",
    ).length;

  const errorFrom = async (res: Response, fallback: string) => {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    return typeof detail === "string" ? detail : fallback;
  };

  const toggleFolder = (folder: SessionFolder) => {
    setActiveGroupId(null);
    setActiveAgentId(agentId);
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(folder.id)) next.delete(folder.id);
      else next.add(folder.id);
      return next;
    });
  };

  const openFolderSessionForm = (folder: SessionFolder) => {
    setActiveGroupId(null);
    setActiveAgentId(agentId);
    setExpandedFolders((prev) => new Set(prev).add(folder.id));
    setSessionFormFolderId(folder.id);
  };

  const createFolder = async () => {
    const name = newName.trim();
    const workingDir = newPath.trim();
    if (!name || !workingDir) {
      setFormError("Name and working directory are required.");
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      const res = await fetch(`${API_URL}/api/agents/${agentId}/folders`, {
        method: "POST",
        headers,
        body: JSON.stringify({ name, working_dir: workingDir }),
      });
      if (!res.ok) {
        setFormError(await errorFrom(res, "Could not create folder."));
        return;
      }
      const folder = (await res.json()) as SessionFolder;
      upsertSessionFolder(folder);
      setExpandedFolders((prev) => new Set(prev).add(folder.id));
      // Keep the flow going: the point of a folder is to hold sessions, so
      // open its first-session form right away.
      setSessionFormFolderId(folder.id);
      setActiveGroupId(null);
      setActiveAgentId(agentId);
      onCloseForm();
    } catch {
      setFormError("Could not create folder.");
    } finally {
      setBusy(false);
    }
  };

  const startEditFolder = (folder: SessionFolder) => {
    setEditingFolderId(folder.id);
    setEditName(folder.name);
    setEditPath(folder.working_dir);
    setFormError(null);
    setExpandedFolders((prev) => new Set(prev).add(folder.id));
  };

  const saveFolder = async (folder: SessionFolder) => {
    const name = editName.trim();
    const workingDir = editPath.trim();
    if (!name || !workingDir) {
      setFormError("Name and working directory are required.");
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      const res = await fetch(`${API_URL}/api/folders/${folder.id}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ name, working_dir: workingDir }),
      });
      if (!res.ok) {
        setFormError(await errorFrom(res, "Could not save folder."));
        return;
      }
      upsertSessionFolder((await res.json()) as SessionFolder);
      setEditingFolderId(null);
    } catch {
      setFormError("Could not save folder.");
    } finally {
      setBusy(false);
    }
  };

  const deleteFolder = async (folder: SessionFolder) => {
    const confirmed = window.confirm(
      `Delete folder "${folder.name}"?\n\nIts sessions are kept and moved to the agent's top level.`,
    );
    if (!confirmed) return;
    try {
      const res = await fetch(`${API_URL}/api/folders/${folder.id}`, {
        method: "DELETE",
        headers,
      });
      if (!res.ok && res.status !== 404) return;
    } catch {
      return;
    }
    removeSessionFolder(folder.id);
    // The server detaches sessions (folder_id -> NULL) without deleting
    // them. Mirror that so they immediately reappear at the top level.
    setSessions(
      useSessionStore.getState().sessions.map((s) =>
        s.folder_id === folder.id ? { ...s, folder_id: null } : s,
      ),
    );
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      next.delete(folder.id);
      return next;
    });
    setEditingFolderId((cur) => (cur === folder.id ? null : cur));
    setSessionFormFolderId((cur) => (cur === folder.id ? null : cur));
  };

  return (
    <div className="session-folder-list ml-3 mt-0.5 mb-1 pl-2 border-l border-sidebar-border/40">
      {formOpen && (
        <div className="session-create mt-2 rounded-lg border-[0.7px] border-border bg-card p-3 space-y-2">
          <Input
            type="text"
            className="h-9 text-sm"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Folder name"
            autoFocus
          />
          <Input
            type="text"
            className="h-9 text-sm"
            value={newPath}
            onChange={(e) => setNewPath(e.target.value)}
            placeholder="Working directory"
            onKeyDown={(e) => {
              if (e.key === "Enter") createFolder();
            }}
          />
          {formError && (
            <p className="text-[11px] leading-snug text-destructive">
              {formError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setNewName("");
                setNewPath("");
                setFormError(null);
                onCloseForm();
              }}
            >
              Cancel
            </Button>
            <Button
              className="btn btn-create"
              size="sm"
              onClick={createFolder}
              disabled={busy}
            >
              Create
            </Button>
          </div>
        </div>
      )}

      <div className="session-folder-items flex flex-col gap-0">
        {folders.map((folder) => {
          const isExpanded = expandedFolders.has(folder.id);
          const count = countVisibleSessions(folder.id);
          const isEditing = editingFolderId === folder.id;
          return (
            <div key={folder.id} className="session-folder-group">
              <div
                className="session-folder group flex items-center gap-1.5 rounded-lg pl-1 pr-2 py-1.5 cursor-pointer text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
                onClick={() => toggleFolder(folder)}
                title={folder.working_dir}
              >
                <IconChevronRight
                  size={13}
                  className={`session-folder-fold shrink-0 text-sidebar-foreground/40 transition-transform ${
                    isExpanded ? "rotate-90" : ""
                  }`}
                />
                <IconFolder
                  size={14}
                  className="shrink-0 text-sidebar-foreground/50"
                />
                <span className="session-folder-name truncate text-sm flex-1">
                  {folder.name}
                </span>
                {count > 0 && (
                  <span className="session-folder-count text-[11px] tabular-nums text-sidebar-foreground/40">
                    {count}
                  </span>
                )}
                <div className="session-folder-actions flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    className="btn-folder-session-add inline-flex h-6 w-6 items-center justify-center rounded-md text-sidebar-foreground/70 hover:bg-card hover:text-sidebar-foreground"
                    onClick={(e) => {
                      e.stopPropagation();
                      openFolderSessionForm(folder);
                    }}
                    title="New session in folder"
                    aria-label={`New session in ${folder.name}`}
                  >
                    <IconPlus size={14} />
                  </button>
                  <button
                    className="btn-folder-edit inline-flex h-6 w-6 items-center justify-center rounded-md text-sidebar-foreground/60 hover:bg-card hover:text-sidebar-foreground"
                    onClick={(e) => {
                      e.stopPropagation();
                      startEditFolder(folder);
                    }}
                    title="Edit folder"
                    aria-label={`Edit ${folder.name}`}
                  >
                    <IconPencil size={13} />
                  </button>
                  <button
                    className="btn-folder-delete inline-flex h-6 w-6 items-center justify-center rounded-md text-sidebar-foreground/60 hover:bg-destructive/10 hover:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteFolder(folder);
                    }}
                    title="Delete folder"
                    aria-label={`Delete ${folder.name}`}
                  >
                    <IconTrash size={13} />
                  </button>
                </div>
              </div>

              {isExpanded && isEditing && (
                <div className="session-create mt-1 ml-3 rounded-lg border-[0.7px] border-border bg-card p-3 space-y-2">
                  <Input
                    type="text"
                    className="h-9 text-sm"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    placeholder="Folder name"
                    autoFocus
                  />
                  <Input
                    type="text"
                    className="h-9 text-sm"
                    value={editPath}
                    onChange={(e) => setEditPath(e.target.value)}
                    placeholder="Working directory"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") saveFolder(folder);
                    }}
                  />
                  <p className="text-[10px] leading-snug text-muted-foreground">
                    Path changes apply to new sessions only; existing sessions
                    keep their current directory.
                  </p>
                  {formError && (
                    <p className="text-[11px] leading-snug text-destructive">
                      {formError}
                    </p>
                  )}
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setEditingFolderId(null);
                        setFormError(null);
                      }}
                    >
                      Cancel
                    </Button>
                    <Button
                      className="btn btn-create"
                      size="sm"
                      onClick={() => saveFolder(folder)}
                      disabled={busy}
                    >
                      Save
                    </Button>
                  </div>
                </div>
              )}

              {isExpanded && (
                <SessionList
                  agentId={agentId}
                  folderId={folder.id}
                  folderWorkingDir={folder.working_dir}
                  formOpen={sessionFormFolderId === folder.id}
                  onCloseForm={() =>
                    setSessionFormFolderId((cur) =>
                      cur === folder.id ? null : cur,
                    )
                  }
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
