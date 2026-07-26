import { useState, useEffect } from "react";
import { useSessionStore, type Group } from "../stores/sessionStore";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

const API = window.location.origin;

/** Modal for creating a multi-agent group. Picks a name + 2+ agents; the
 * backend provisions a backing session (origin='group') and returns the
 * GroupInfo, which we upsert into the store. */
export function CreateGroupDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const agents = useSessionStore((s) => s.agents);
  const upsertGroup = useSessionStore((s) => s.upsertGroup);
  const token = useSessionStore((s) => s.token);

  const [name, setName] = useState("");
  const [workingDir, setWorkingDir] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [defaultAgentId, setDefaultAgentId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (open) {
      setName("");
      setWorkingDir("");
      setSelected(new Set());
      setDefaultAgentId("");
      setError(null);
      setCreating(false);
    }
  }, [open]);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      if (defaultAgentId && !next.has(defaultAgentId)) {
        setDefaultAgentId("");
      }
      return next;
    });
    setError(null);
  };

  const handleCreate = async () => {
    if (!name.trim()) {
      setError("Group name is required.");
      return;
    }
    if (selected.size < 2) {
      setError("Select at least 2 agents.");
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/groups`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: name.trim(),
          agent_ids: [...selected],
          default_agent_id: defaultAgentId || null,
          working_dir: workingDir.trim() || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Failed to create group");
        return;
      }
      const g = await res.json();
      upsertGroup({
        id: g.id,
        name: g.name,
        agentIds: g.agent_ids,
        createdAt: g.created_at,
        sessionId: g.session_id ?? null,
        defaultAgentId: g.default_agent_id ?? null,
        workingDir: g.working_dir,
      } as Group);
      onOpenChange(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Network error");
    } finally {
      setCreating(false);
    }
  };

  const avatar = (a: { avatar?: string | null }) => a.avatar || "\u{1F419}";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Create group</DialogTitle>
          <DialogDescription>
            A group lets 2+ agents share one chat. @mention an agent to get
            its reply.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="group-name">Group name</Label>
            <Input
              id="group-name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setError(null);
              }}
              placeholder="e.g. Brainstorming circle"
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="group-working-dir">Working directory</Label>
            <Input
              id="group-working-dir"
              value={workingDir}
              onChange={(e) => {
                setWorkingDir(e.target.value);
                setError(null);
              }}
              placeholder="Default server working directory"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Members</Label>
            <p className="text-xs text-muted-foreground">
              Choose 2+ agents. {selected.size} selected.
            </p>
            <div className="flex flex-col gap-1 mt-1 max-h-48 overflow-y-auto">
              {agents
                .filter((a) => !a.archived)
                .map((a) => {
                  const checked = selected.has(a.id);
                  return (
                    <label
                      key={a.id}
                      className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm cursor-pointer transition-colors ${
                        checked ? "bg-accent" : "hover:bg-accent/50"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggle(a.id)}
                        className="rounded"
                      />
                      <span className="text-base leading-none">{avatar(a)}</span>
                      <span className="truncate flex-1">{a.name}</span>
                      <span className="text-[10px] text-muted-foreground uppercase">
                        {a.backend === "codex" ? "Codex" : "Claude"}
                      </span>
                    </label>
                  );
                })}
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="group-default-agent">默认回复 agent</Label>
            <select
              id="group-default-agent"
              value={defaultAgentId}
              onChange={(e) => setDefaultAgentId(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">不设置兜底</option>
              {agents
                .filter((a) => selected.has(a.id))
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
            </select>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={!name.trim() || selected.size < 2 || creating}
          >
            {creating ? "Creating\u2026" : "Create group"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
