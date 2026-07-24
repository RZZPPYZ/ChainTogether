import { useEffect, useMemo, useState } from "react";
import { IconPlus } from "@tabler/icons-react";
import type { PersonaRead } from "../api";
import { fetchAgentConnectors, toggleAgentConnector } from "../api/connectors";
import { fetchPersonas } from "../api/personas";
import { useSessionStore, type Agent } from "../stores/sessionStore";
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

const API = `${window.location.origin}/api/agents`;
const BUILTIN_MCP = ["ask", "bg"] as const;
// A small role-themed palette to pick an agent icon from (the field still
// accepts any custom emoji). 🐙 is the Octopus default.
const AVATAR_CHOICES = ["🐙", "🤖", "🧠", "🔬", "🛠️", "✍️", "📊", "🦉"] as const;

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  /** Which agent to select when the dialog opens. `null` starts in
   * "new agent" mode. The dialog manages its own selection after that —
   * the left rail lets the user switch between all agents. */
  initialAgentId: string | null;
}

const textareaCls =
  "flex w-full rounded-lg border-[0.7px] border-gray-400 bg-input px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground outline-none transition-colors focus:border-primary focus:ring-[3px] focus:ring-primary/10 resize-none";

const sameSet = (a: string[], b: string[]) =>
  a.length === b.length && [...a].sort().join() === [...b].sort().join();

export function AgentSettings({ open, onOpenChange, initialAgentId }: Props) {
  const token = useSessionStore((s) => s.token);
  const agents = useSessionStore((s) => s.agents);
  const credentials = useSessionStore((s) => s.credentials);
  const upsertAgent = useSessionStore((s) => s.upsertAgent);
  const removeAgent = useSessionStore((s) => s.removeAgent);
  const setActiveAgentId = useSessionStore((s) => s.setActiveAgentId);
  const sessions = useSessionStore((s) => s.sessions);
  const setSessions = useSessionStore((s) => s.setSessions);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const setActiveSessionId = useSessionStore((s) => s.setActiveSessionId);
  const connectorInstallations = useSessionStore((s) => s.connectorInstallations);
  const agentConnectorIds = useSessionStore((s) => s.agentConnectorIds);
  const setAgentConnectorIds = useSessionStore((s) => s.setAgentConnectorIds);
  const availableBackends = useSessionStore((s) => s.availableBackends);
  const codexAvailable = availableBackends.includes("codex");

  // `null` selection = the "New agent" draft; otherwise the agent being edited.
  const [selectedId, setSelectedId] = useState<string | null>(initialAgentId);
  const selected = useMemo(
    () => (selectedId ? agents.find((a) => a.id === selectedId) ?? null : null),
    [selectedId, agents]
  );

  const [name, setName] = useState("");
  const [alias, setAlias] = useState("");
  const [description, setDescription] = useState("");
  const [avatar, setAvatar] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [model, setModel] = useState("");
  const [credentialId, setCredentialId] = useState("");
  const [backend, setBackend] = useState("claude-code");
  const [mcpServers, setMcpServers] = useState<string[]>([...BUILTIN_MCP]);
  const [toolAllow, setToolAllow] = useState("");
  const [toolDeny, setToolDeny] = useState("");
  const [personas, setPersonas] = useState<PersonaRead[]>([]);
  const [personaIds, setPersonaIds] = useState<string[]>([]);
  const [activePersonaId, setActivePersonaId] = useState<string | null>(null);
  const [personaLoadError, setPersonaLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Credentials offered in the dropdown are scoped to the chosen backend (a
  // Claude key can't authenticate a Codex session and vice-versa).
  const backendCreds = credentials.filter((c) => c.backend === backend);

  // Opening the dialog snaps the selection back to whatever the caller asked
  // for (the active agent, or `null` for the new-agent draft).
  useEffect(() => {
    if (open) setSelectedId(initialAgentId);
  }, [open, initialAgentId]);

  // (Re)seed the form whenever the dialog opens or the selected agent changes.
  // We deliberately read `agents` at run time instead of depending on it so a
  // background refresh of the agent list can't clobber in-progress edits.
  useEffect(() => {
    if (!open) return;
    setError(null);
    const a = selectedId
      ? agents.find((x) => x.id === selectedId) ?? null
      : null;
    setName(a?.name ?? "");
    setAlias(a?.alias ?? "");
    setDescription(a?.description ?? "");
    setAvatar(a?.avatar ?? "");
    setSystemPrompt(a?.system_prompt ?? "");
    setModel(a?.model ?? "");
    setCredentialId(a?.credential_id ?? "");
    setBackend(a?.backend ?? "claude-code");
    setMcpServers(a?.mcp_servers ?? [...BUILTIN_MCP]);
    setToolAllow(a?.tool_allow ?? "");
    setToolDeny(a?.tool_deny ?? "");
    setPersonaIds(a?.persona_ids ?? []);
    setActivePersonaId(a?.active_persona_id ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, selectedId]);

  useEffect(() => {
    if (!open) return;
    setPersonaLoadError(null);
    fetchPersonas(token)
      .then(setPersonas)
      .catch((reason) => {
        setPersonas([]);
        setPersonaLoadError(
          reason instanceof Error ? reason.message : "Could not load personas"
        );
      });
  }, [open, token]);

  // Load the agent's enabled connectors when editing an existing one. New
  // agents have no id yet; their connectors are managed after first save.
  useEffect(() => {
    if (!open || !selectedId) return;
    fetchAgentConnectors(token, selectedId)
      .then((ids) => setAgentConnectorIds(selectedId, ids))
      .catch(() => {});
  }, [open, selectedId, token, setAgentConnectorIds]);

  const toggleConnector = async (installationId: string, enabled: boolean) => {
    if (!selected) return;
    const cur = agentConnectorIds[selected.id] ?? [];
    // Optimistic; revert on failure.
    setAgentConnectorIds(
      selected.id,
      enabled ? [...cur, installationId] : cur.filter((x) => x !== installationId)
    );
    try {
      await toggleAgentConnector(token, selected.id, installationId, enabled);
    } catch {
      setAgentConnectorIds(selected.id, cur);
    }
  };

  // Has the form drifted from the persisted agent (or, in new mode, from an
  // empty draft)? Used to warn before discarding edits on a rail switch.
  const dirty =
    name !== (selected?.name ?? "") ||
    alias !== (selected?.alias ?? "") ||
    description !== (selected?.description ?? "") ||
    avatar !== (selected?.avatar ?? "") ||
    systemPrompt !== (selected?.system_prompt ?? "") ||
    model !== (selected?.model ?? "") ||
    credentialId !== (selected?.credential_id ?? "") ||
    backend !== (selected?.backend ?? "claude-code") ||
    toolAllow !== (selected?.tool_allow ?? "") ||
    toolDeny !== (selected?.tool_deny ?? "") ||
    activePersonaId !== (selected?.active_persona_id ?? null) ||
    !sameSet(personaIds, selected?.persona_ids ?? []) ||
    !sameSet(mcpServers, selected?.mcp_servers ?? [...BUILTIN_MCP]);

  const selectAgent = (id: string | null) => {
    if (id === selectedId) return;
    if (
      dirty &&
      !window.confirm("Discard unsaved changes to this agent?")
    )
      return;
    setSelectedId(id);
  };

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const toggleMcp = (id: string) =>
    setMcpServers((cur) =>
      cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]
    );

  const togglePersona = (id: string) => {
    setPersonaIds((current) => {
      if (current.includes(id)) {
        if (activePersonaId === id) setActivePersonaId(null);
        return current.filter((personaId) => personaId !== id);
      }
      const next = [...current, id];
      if (!activePersonaId) setActivePersonaId(id);
      return next;
    });
  };

  const detailOf = async (res: Response): Promise<string> => {
    const b = await res.json().catch(() => null);
    return (b && typeof b.detail === "string" && b.detail) || `HTTP ${res.status}`;
  };

  const save = async () => {
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setSaving(true);
    setError(null);
    const body = {
      name: name.trim(),
      alias: alias.trim(),
      description,
      avatar: avatar.trim() || null,
      system_prompt: systemPrompt,
      model: model.trim() || null,
      credential_id: credentialId || null,
      backend,
      mcp_servers: mcpServers,
      tool_allow: toolAllow,
      tool_deny: toolDeny,
      persona_ids: personaIds,
      active_persona_id: activePersonaId,
    };
    try {
      const res = selected
        ? await fetch(`${API}/${selected.id}`, {
            method: "PATCH",
            headers,
            body: JSON.stringify(body),
          })
        : await fetch(API, {
            method: "POST",
            headers,
            body: JSON.stringify(body),
          });
      if (res.ok) {
        const saved: Agent = await res.json();
        upsertAgent(saved);
        if (!selected) setActiveAgentId(saved.id);
        onOpenChange(false);
      } else {
        setError(await detailOf(res));
      }
    } catch {
      setError("Network error");
    } finally {
      setSaving(false);
    }
  };

  const archive = async () => {
    if (!selected) return;
    const res = await fetch(`${API}/${selected.id}/archive`, {
      method: "POST",
      headers,
    });
    if (res.ok) {
      // The backend cascade-archives this agent's sessions; mirror that in the
      // store so they vanish from the sidebar, and clear the active session if
      // it was one of them. Re-selecting a fallback agent (Octo) is handled by
      // AgentList's auto-select effect once activeAgentId is cleared.
      const orphaned = new Set(
        sessions.filter((s) => s.agent_id === selected.id).map((s) => s.id)
      );
      if (orphaned.size) {
        setSessions(sessions.filter((s) => !orphaned.has(s.id)));
      }
      if (activeSessionId && orphaned.has(activeSessionId)) {
        setActiveSessionId(null);
      }
      removeAgent(selected.id);
      setActiveAgentId(null);
      onOpenChange(false);
    } else {
      setError(await detailOf(res));
    }
  };

  const railItem =
    "agent-rail-item flex shrink-0 items-center gap-2 rounded-lg px-2 py-2 text-left text-sm transition-colors sm:w-full";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="agent-settings max-w-3xl">
        <DialogHeader>
          <DialogTitle>Agent settings</DialogTitle>
          <DialogDescription>
            An agent is a durable assistant: its system prompt, model, tools
            and schedules persist across sessions. Pick one to edit, or create
            a new one.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 sm:flex-row">
          {/* Agent rail — switch which agent you're editing, or start a new
           * one. Horizontal scroll strip on mobile, left column on desktop. */}
          <div className="agent-rail flex gap-1 overflow-x-auto pb-1 sm:w-44 sm:shrink-0 sm:flex-col sm:overflow-visible sm:border-r sm:border-border sm:pb-0 sm:pr-3">
            <button
              type="button"
              className={`agent-rail-new ${railItem} ${
                selectedId === null
                  ? "bg-accent text-foreground font-medium"
                  : "text-muted-foreground hover:bg-accent/60"
              }`}
              onClick={() => selectAgent(null)}
            >
              <IconPlus size={16} className="shrink-0" />
              <span className="truncate">New agent</span>
            </button>
            {agents.map((a) => (
              <button
                key={a.id}
                type="button"
                className={`${railItem} ${
                  selectedId === a.id
                    ? "bg-accent text-foreground font-medium"
                    : "text-foreground hover:bg-accent/60"
                }`}
                onClick={() => selectAgent(a.id)}
                title={a.alias ? `${a.name} (@${a.alias})` : a.name}
              >
                <span className="shrink-0 text-base leading-none">
                  {a.avatar || "🐙"}
                </span>
                <span className="truncate">{a.name}</span>
              </button>
            ))}
          </div>

          {/* Editing form for the selected agent (or a fresh draft). */}
          <div className="min-w-0 flex-1 space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="agent-name">Name</Label>
              <Input
                id="agent-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Researcher"
                className="h-9"
                autoFocus
              />
            </div>

            {/* Icon — pick a preset or type any emoji in the custom box. */}
            <div className="space-y-1.5">
              <Label>Icon</Label>
              <div className="agent-avatar-picker flex flex-wrap items-center gap-1.5">
                {AVATAR_CHOICES.map((emoji) => (
                  <button
                    key={emoji}
                    type="button"
                    aria-label={`Icon ${emoji}`}
                    aria-pressed={avatar === emoji}
                    className={`btn-avatar inline-flex h-9 w-9 items-center justify-center rounded-md border text-lg leading-none transition-colors ${
                      avatar === emoji
                        ? "border-primary bg-primary/10"
                        : "border-border hover:bg-accent"
                    }`}
                    onClick={() => setAvatar(emoji)}
                  >
                    {emoji}
                  </button>
                ))}
                <Input
                  id="agent-avatar"
                  value={avatar}
                  onChange={(e) => setAvatar(e.target.value)}
                  placeholder="🐙"
                  aria-label="Custom icon"
                  className="h-9 w-14 text-center"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="agent-desc">Description</Label>
              <Input
                id="agent-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What this agent is for (optional)"
                className="h-9"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="agent-prompt">System prompt</Label>
              <textarea
                id="agent-prompt"
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={4}
                placeholder="You are a meticulous research assistant…"
                className={textareaCls}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="agent-alias">Alias</Label>
              <Input
                id="agent-alias"
                value={alias}
                onChange={(e) => setAlias(e.target.value)}
                placeholder="Optional alternate @handle"
                maxLength={64}
                className="h-9"
              />
            </div>

            <div className="agent-personas space-y-1.5">
              <div className="flex items-center justify-between gap-2">
                <Label>Personas</Label>
                {personaIds.length > 0 && (
                  <button
                    type="button"
                    className="text-xs text-muted-foreground hover:text-foreground"
                    onClick={() => setActivePersonaId(null)}
                  >
                    Use no persona
                  </button>
                )}
              </div>
              {personas.length === 0 ? (
                <p className="text-xs leading-relaxed text-muted-foreground">
                  {personaLoadError
                    ? `Could not load personas: ${personaLoadError}`
                    : "No personas installed. Add one from Settings → Personas."}
                </p>
              ) : (
                <div className="divide-y divide-border border-y border-border">
                  {personas.map((persona) => {
                    const assigned = personaIds.includes(persona.id);
                    const active = activePersonaId === persona.id;
                    return (
                      <div
                        key={persona.id}
                        className="agent-persona-row grid grid-cols-[auto_1fr_auto] items-center gap-2 py-2"
                      >
                        <input
                          type="checkbox"
                          checked={assigned}
                          onChange={() => togglePersona(persona.id)}
                          aria-label={`Assign ${persona.name}`}
                        />
                        <button
                          type="button"
                          className="min-w-0 text-left"
                          onClick={() => {
                            if (!assigned) togglePersona(persona.id);
                            setActivePersonaId(persona.id);
                          }}
                        >
                          <span className="block truncate text-sm text-foreground">
                            {persona.name}
                          </span>
                          <span className="block truncate text-xs text-muted-foreground">
                            {persona.description || `${persona.resources.length} resources`}
                          </span>
                        </button>
                        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                          <input
                            type="radio"
                            name="active-persona"
                            checked={active}
                            disabled={!assigned}
                            onChange={() => setActivePersonaId(persona.id)}
                          />
                          Active
                        </label>
                      </div>
                    );
                  })}
                </div>
              )}
              <p className="text-xs leading-relaxed text-muted-foreground">
                Keep several personas available for this agent; only the active one
                shapes its next response.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="agent-model">Model</Label>
              <Input
                id="agent-model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="claude-opus-4-7 (blank = backend default)"
                className="h-9"
              />
            </div>

            {/* Default harness for this agent's new sessions. Shown only when
             * Codex is available (otherwise there's nothing to choose). */}
            {codexAvailable && (
              <div className="space-y-1.5">
                <Label>Harness</Label>
                <div
                  className="agent-backend-select flex gap-2"
                  role="radiogroup"
                  aria-label="Default backend"
                >
                  {[
                    { id: "claude-code", label: "Claude Code" },
                    { id: "codex", label: "Codex" },
                  ].map((b) => (
                    <button
                      key={b.id}
                      type="button"
                      role="radio"
                      aria-checked={backend === b.id}
                      className={`btn-agent-backend btn-agent-backend-${b.id} flex-1 h-9 rounded-md border text-sm transition-colors ${
                        backend === b.id
                          ? "border-primary bg-primary/10 text-foreground font-medium"
                          : "border-border text-muted-foreground hover:bg-accent"
                      }`}
                      onClick={() => {
                        setBackend(b.id);
                        setCredentialId("");
                      }}
                    >
                      {b.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {backendCreds.length > 0 && (
              <div className="space-y-1.5">
                <Label htmlFor="agent-cred">Credential</Label>
                <select
                  id="agent-cred"
                  className="agent-credential-select flex h-9 w-full rounded-md border border-border bg-input px-3 py-1 text-sm text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
                  value={credentialId}
                  onChange={(e) => setCredentialId(e.target.value)}
                >
                  <option value="">Default auth (CLI login)</option>
                  {backendCreds.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="space-y-1.5">
              <Label>Built-in tools</Label>
              <div className="flex gap-3">
                {BUILTIN_MCP.map((id) => (
                  <label
                    key={id}
                    className="flex items-center gap-1.5 text-sm text-foreground"
                  >
                    <input
                      type="checkbox"
                      checked={mcpServers.includes(id)}
                      onChange={() => toggleMcp(id)}
                    />
                    {id}
                  </label>
                ))}
              </div>
            </div>

            {/* Connectors — agent-scoped enablement (connectors.md revision).
             * Toggling here calls the agent-connectors API immediately (no
             * Save needed); new agents must be saved first to get an id. */}
            <div className="agent-connectors space-y-1.5">
              <Label>Connectors</Label>
              {!selected ? (
                <p className="text-xs text-muted-foreground">
                  Save the agent first, then enable connectors for it.
                </p>
              ) : connectorInstallations.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No connectors installed yet — add one in the sidebar's
                  Connectors section.
                </p>
              ) : (
                <div className="flex flex-col gap-1.5">
                  {connectorInstallations.map((inst) => {
                    const enabled = (
                      agentConnectorIds[selected.id] ?? []
                    ).includes(inst.id);
                    return (
                      <label
                        key={inst.id}
                        className="agent-connector-row flex items-center gap-2 text-sm text-foreground"
                      >
                        <input
                          type="checkbox"
                          className="agent-connector-toggle"
                          data-installation={inst.id}
                          checked={enabled}
                          onChange={(e) =>
                            toggleConnector(inst.id, e.target.checked)
                          }
                        />
                        <span className="truncate">
                          {inst.kind} · {inst.label}
                        </span>
                        {inst.needs_reconnect && (
                          <span className="text-xs text-destructive">
                            needs reconnect
                          </span>
                        )}
                      </label>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <Label htmlFor="agent-allow">Allow tools</Label>
                <textarea
                  id="agent-allow"
                  value={toolAllow}
                  onChange={(e) => setToolAllow(e.target.value)}
                  rows={3}
                  placeholder="one per line; blank = all"
                  className={textareaCls}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="agent-deny">Deny tools</Label>
                <textarea
                  id="agent-deny"
                  value={toolDeny}
                  onChange={(e) => setToolDeny(e.target.value)}
                  rows={3}
                  placeholder="one per line; wins over allow"
                  className={textareaCls}
                />
              </div>
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
        </div>

        <DialogFooter className="flex items-center justify-between gap-2 sm:justify-between">
          {selected && !selected.is_system ? (
            <Button variant="destructive" size="sm" onClick={archive}>
              Archive agent
            </Button>
          ) : (
            <span />
          )}
          <Button
            className="btn-agent-save"
            size="sm"
            onClick={save}
            disabled={saving}
          >
            {saving ? "Saving…" : selected ? "Save" : "Create agent"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
