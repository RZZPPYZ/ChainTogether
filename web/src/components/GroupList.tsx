import { useEffect, useState } from "react";
import { IconPlus, IconUsers, IconTrash } from "@tabler/icons-react";
import { useSessionStore } from "../stores/sessionStore";

const API = window.location.origin;

/** The "Groups" section of the sidebar. Lists multi-agent groups; clicking
 * one switches the main area to GroupChatView. A "+" button opens the
 * create-group dialog (owned by App). */
export function GroupList({ onCreateGroup }: { onCreateGroup: () => void }) {
  const groups = useSessionStore((s) => s.groups);
  const setGroups = useSessionStore((s) => s.setGroups);
  const removeGroup = useSessionStore((s) => s.removeGroup);
  const agents = useSessionStore((s) => s.agents);
  const token = useSessionStore((s) => s.token);
  const activeGroupId = useSessionStore((s) => s.activeGroupId);
  const setActiveGroupId = useSessionStore((s) => s.setActiveGroupId);
  const setActiveAgentId = useSessionStore((s) => s.setActiveAgentId);
  const setActiveSessionId = useSessionStore((s) => s.setActiveSessionId);
  const setMessages = useSessionStore((s) => s.setMessages);
  const setLastAppliedSeq = useSessionStore((s) => s.setLastAppliedSeq);
  const [expanded, setExpanded] = useState(false);

  // Fetch groups once when we have a token.
  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/groups`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((data: Array<{ id: string; name: string; agent_ids: string[]; created_at: string; session_id?: string | null; default_agent_id?: string | null }>) => {
        setGroups(
          data.map((g) => ({
            id: g.id,
            name: g.name,
            agentIds: g.agent_ids,
            createdAt: g.created_at,
            sessionId: g.session_id ?? null,
            defaultAgentId: g.default_agent_id ?? null,
          })),
        );
      })
      .catch(() => {});
  }, [token, setGroups]);

  const agentById = (id: string) => agents.find((a) => a.id === id);

  const handleSelect = (groupId: string) => {
    const g = groups.find((x) => x.id === groupId);
    if (!g) return;
    setActiveGroupId(groupId);
    setActiveAgentId(null);
    setActiveSessionId(null);
    if (g.sessionId) {
      // Load the backing session's messages so GroupChatView renders history.
      fetch(`${API}/api/sessions/${g.sessionId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data?.messages) setMessages(g.sessionId!, data.messages);
          if (typeof data?.next_message_seq === "number") {
            setLastAppliedSeq(g.sessionId!, data.next_message_seq - 1);
          }
        })
        .catch(() => {});
    }
  };

  const handleDelete = async (groupId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const res = await fetch(`${API}/api/groups/${groupId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      removeGroup(groupId);
      if (activeGroupId === groupId) setActiveGroupId(null);
    }
  };

  return (
    <div className="shrink-0">
      <div
        className="group flex h-8 items-center justify-between rounded-lg px-2 hover:bg-sidebar-accent transition-colors cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
      >
        <h2 className="text-[13px] font-medium leading-4 text-sidebar-foreground/50 group-hover:text-sidebar-foreground transition-colors uppercase tracking-wide">
          Groups
        </h2>
        <span className="flex items-center gap-0.5">
          <button
            className="inline-flex h-6 w-6 items-center justify-center rounded-md text-sidebar-foreground/70 hover:bg-sidebar-accent-foreground/10 hover:text-sidebar-foreground transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              onCreateGroup();
            }}
            title="New group"
            aria-label="New group"
          >
            <IconPlus size={14} />
          </button>
        </span>
      </div>

      {expanded && (
        <div className="flex flex-col gap-0 mt-1">
          {groups.map((g) => {
            const isActive = g.id === activeGroupId;
            return (
              <div
                key={g.id}
                className={`group flex items-center gap-2 rounded-lg px-2 py-1.5 cursor-pointer transition-colors ${
                  isActive
                    ? "bg-sidebar-accent text-sidebar-foreground"
                    : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50"
                }`}
                onClick={() => handleSelect(g.id)}
              >
                <IconUsers size={15} className="shrink-0 opacity-60" />
                <span className="truncate text-sm flex-1">{g.name}</span>
                <span className="flex items-center gap-0.5 shrink-0">
                  {g.agentIds.slice(0, 3).map((aid) => {
                    const a = agentById(aid);
                    return (
                      <span
                        key={aid}
                        className="text-xs leading-none"
                        title={a?.name ?? "Unknown"}
                      >
                        {a?.avatar || "\u{1F419}"}
                      </span>
                    );
                  })}
                  {g.agentIds.length > 3 && (
                    <span className="text-[10px] text-sidebar-foreground/40 ml-0.5">
                      +{g.agentIds.length - 3}
                    </span>
                  )}
                </span>
                <button
                  className="opacity-0 group-hover:opacity-60 hover:!opacity-100 ml-1 text-sidebar-foreground/50"
                  onClick={(e) => handleDelete(g.id, e)}
                  title="Delete group"
                  aria-label="Delete group"
                >
                  <IconTrash size={12} />
                </button>
              </div>
            );
          })}
          {groups.length === 0 && (
            <p className="text-xs text-sidebar-foreground/40 px-2 py-1">
              No groups yet
            </p>
          )}
        </div>
      )}
    </div>
  );
}
