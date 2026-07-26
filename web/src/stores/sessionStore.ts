import { create } from "zustand";
import type {
  AgentRead as ApiAgentRead,
  AttachmentMetadata as ApiAttachmentMetadata,
  BackendKind as ApiBackendKind,
  ConnectorCatalogEntry as ApiConnectorCatalogEntry,
  ConnectorInstallationInfo as ApiConnectorInstallationInfo,
  CredentialInfo as ApiCredentialInfo,
  ScheduleInfo,
  SessionInfo as ApiSessionInfo,
  SessionStatus as ApiSessionStatus,
} from "../api";

// Re-export contract types under the names the rest of the frontend
// already uses. Source of truth is `web/src/api/contracts.ts`, regenerated
// from FastAPI's openapi.json via `bun run generate:contracts`.
export type SessionStatus = ApiSessionStatus;
export type SessionInfo = ApiSessionInfo;
export type Agent = ApiAgentRead;
export type BackendKind = ApiBackendKind;
export type CredentialInfo = ApiCredentialInfo;
export type ConnectorCatalogEntry = ApiConnectorCatalogEntry;
export type ConnectorInstallationInfo = ApiConnectorInstallationInfo;
export type Schedule = ScheduleInfo;
export type AttachmentMetadata = ApiAttachmentMetadata;

// `Message` is a UI-only shape: it's how WS events are normalized for
// rendering, not 1-to-1 with `MessageContent` from the contract (which has
// `content: unknown` because tool_result can carry arbitrary JSON). Leave
// hand-rolled.
export interface Message {
  role: "user" | "assistant" | "system" | "tool";
  type: string;
  content?: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_use_id?: string;
  is_error?: boolean;
  session_id?: string;
  cost?: number;
  // User-uploaded files attached to this message. Present on user
  // messages that the user attached files to (image, PDF, anything).
  // The chat UI renders thumbnails / file chips below the message text.
  attachments?: AttachmentMetadata[];
  // Per-session sequence number, present on messages loaded from the
  // session detail snapshot. Used as the rewind target for "Fork from here"
  // (session-rewind.md §6.1). Absent on freshly-streamed messages until
  // the next detail reload.
  seq?: number;
}

export interface QuestionOption {
  label: string;
  description?: string;
}

export interface QuestionItem {
  question: string;
  header?: string;
  multiSelect?: boolean;
  options: QuestionOption[];
}

export interface PendingQuestion {
  question_id: string;
  questions: QuestionItem[];
}

interface SessionStore {
  token: string;
  setToken: (t: string) => void;

  // Agents own sessions/schedules/bridges (agent-refactor.md). The sidebar
  // is two-pane: pick an agent, then see its sessions. `activeAgentId`
  // drives the session/schedule filters.
  agents: Agent[];
  setAgents: (a: Agent[]) => void;
  upsertAgent: (a: Agent) => void;
  removeAgent: (id: string) => void;
  activeAgentId: string | null;
  setActiveAgentId: (id: string | null) => void;

  // Which AI backends this host can run (GET /api/backends). 'claude-code'
  // is always present; 'codex' only when the binary resolves. Drives the
  // backend selector in the session-create form (codex-backend.md §6).
  availableBackends: string[];
  setAvailableBackends: (b: string[]) => void;

  sessions: SessionInfo[];
  setSessions: (s: SessionInfo[]) => void;
  updateSessionStatus: (id: string, status: SessionStatus) => void;

  // Mirror of `archived=true` rows from `GET /api/sessions?include_archived=true`.
  // SessionList fetches into this lazily when the user expands the
  // archived section; ChatView reads it so it can detect when the
  // active session is archived (show read-only banner, hide input).
  archivedSessions: SessionInfo[];
  setArchivedSessions: (s: SessionInfo[]) => void;

  activeSessionId: string | null;
  setActiveSessionId: (id: string | null) => void;

  messages: Record<string, Message[]>;
  addMessage: (sessionId: string, msg: Message) => void;
  setMessages: (sessionId: string, msgs: Message[]) => void;

  // Per-session WS-event dedup baseline. Set when a snapshot is loaded
  // (`/api/sessions/{id}` returns `next_message_seq`); the WS handler
  // drops any event whose `seq <= lastAppliedSeq[sessionId]` so a
  // reconnect-refetch can't stomp an event that arrived between the
  // snapshot's SQL and `setMessages` (the original race).
  lastAppliedSeq: Record<string, number>;
  setLastAppliedSeq: (sessionId: string, seq: number) => void;

  schedules: Schedule[];
  setSchedules: (s: Schedule[]) => void;

  credentials: CredentialInfo[];
  setCredentials: (c: CredentialInfo[]) => void;

  // Connectors (connectors.md). Installations are global; the catalog lists
  // installable kinds. Per-agent enablement (which installations an agent may
  // call) is keyed by agentId → installation ids.
  connectorCatalog: ConnectorCatalogEntry[];
  setConnectorCatalog: (c: ConnectorCatalogEntry[]) => void;
  connectorInstallations: ConnectorInstallationInfo[];
  setConnectorInstallations: (c: ConnectorInstallationInfo[]) => void;
  upsertConnectorInstallation: (c: ConnectorInstallationInfo) => void;
  removeConnectorInstallation: (id: string) => void;
  agentConnectorIds: Record<string, string[]>;
  setAgentConnectorIds: (agentId: string, ids: string[]) => void;

  // Per-session queue of messages waiting for the current run to finish.
  // Mirrored from server `queued` / `dequeued` events; not persisted.
  pendingQueue: Record<string, string[]>;
  setPendingQueue: (sessionId: string, queue: string[]) => void;
  enqueuePending: (sessionId: string, content: string) => void;
  dequeuePending: (sessionId: string) => void;
  clearPending: (sessionId: string) => void;

  // Deferred /fork requests (session-fork.md). When `/fork` is typed
  // while a session is busy, we record the intent here instead of erroring;
  // a watcher fires the duplicate once the session goes idle + drained.
  // Keyed by the PARENT session id → the requested label (null = default
  // name). Tab-scoped (not persisted) — closing the tab drops it.
  pendingForks: Record<string, { label: string | null }>;
  setPendingFork: (sessionId: string, label: string | null) => void;
  clearPendingFork: (sessionId: string) => void;

  // Active AskUserQuestion prompts waiting for the user's answer.
  pendingQuestions: Record<string, PendingQuestion[]>;
  setPendingQuestions: (sessionId: string, qs: PendingQuestion[]) => void;
  addPendingQuestion: (sessionId: string, q: PendingQuestion) => void;
  removePendingQuestion: (sessionId: string, questionId: string) => void;

  connected: boolean;
  setConnected: (c: boolean) => void;

  // FileViewerDialog is mounted at the App level and reads this slot.
  // null = closed; non-null = open and fetching the named file. Set
  // by ChatView when the `/showme` resolver returns a concrete path.
  viewer: { sessionId: string; path: string } | null;
  openViewer: (sessionId: string, path: string) => void;
  closeViewer: () => void;

  // Cross-turn background tasks. Keyed by sessionId → list of tasks
  // (most-recent last as they arrive over WS / from snapshot fetch).
  // The BgTaskChip in chat looks each task up by id; it lives next
  // to the `mcp__bg__run` tool_use block that started it.
  bgTasks: Record<string, BgTask[]>;
  upsertBgTask: (sessionId: string, task: BgTask) => void;
  setBgTasks: (sessionId: string, tasks: BgTask[]) => void;

  // Agent-to-agent delegations spawned by a parent session.
  // Keyed by parent sessionId → list of delegation records. The
  // request and event cards in chat resolve their live state by
  // looking up the delegation_id in this map.
  // (agent-collaboration.md §6)
  delegations: Record<string, Delegation[]>;
  upsertDelegation: (parentSessionId: string, d: Delegation) => void;
  setDelegations: (parentSessionId: string, ds: Delegation[]) => void;

  // Sidebar visibility toggle for `origin === "delegation"` sessions.
  // Hidden by default so heavy fan-out doesn't flood the agent list;
  // toggle persists in localStorage so the user's preference sticks
  // across reloads.
  showDelegations: boolean;
  setShowDelegations: (v: boolean) => void;

  // Multi-agent group chat (groups.md). A group is a set of 2+ agents
  // sharing ONE backing session; @-mention routing wakes a specific
  // agent. `activeGroupId` drives whether ChatView or GroupChatView is
  // mounted in the main area.
  groups: Group[];
  setGroups: (g: Group[]) => void;
  upsertGroup: (g: Group) => void;
  removeGroup: (id: string) => void;
  activeGroupId: string | null;
  setActiveGroupId: (id: string | null) => void;

  groupInvocations: Record<string, GroupInvocation[]>;
  setGroupInvocations: (groupId: string, rows: GroupInvocation[]) => void;
  upsertGroupInvocation: (row: GroupInvocation) => void;

  // Group typing indicators: session_id → set of agent names currently typing.
  groupTypingAgents: Record<string, Set<string>>;
  addGroupTypingAgent: (sessionId: string, agentName: string) => void;
  removeGroupTypingAgent: (sessionId: string, agentName: string) => void;

  // Compatibility path for older servers that emit group_agent_text instead
  // of text blocks. New servers put response chunks in group_agent_activity.
  groupStreamingReplies: Record<string, Record<string, string>>;
  appendGroupStreamingReply: (sessionId: string, agentName: string, chunk: string) => void;
  clearGroupStreamingReply: (sessionId: string, agentName: string) => void;

  // Live index of group-member turns. The same events are also persisted as
  // messages, so GroupChatView can rebuild these runs after a reload.
  groupAgentRuns: Record<string, Record<string, GroupAgentRun>>;
  applyGroupAgentActivity: (
    sessionId: string,
    event: GroupAgentActivityEvent,
  ) => void;
  clearGroupAgentRun: (sessionId: string, runId: string) => void;

  // Native deep-research jobs, keyed by sessionId → list (native-deep-research.md
  // §7). The ResearchCard renders live phase/progress; the final report arrives
  // as a normal injected turn.
  research: Record<string, ResearchJob[]>;
  upsertResearch: (sessionId: string, job: Partial<ResearchJob> & { id: string }) => void;
  setResearch: (sessionId: string, jobs: ResearchJob[]) => void;
}

export interface ResearchJob {
  id: string;
  session_id: string;
  question: string;
  status: "running" | "completed" | "failed" | "cancelled" | "interrupted";
  phase: string | null;        // scope | search | verify | synthesize | done
  detail?: string;
  counts?: Record<string, number>;
  sources?: string[];
  verified?: number;
  error?: string | null;
}

export interface BgTask {
  id: string;
  session_id: string;
  command: string;
  description: string | null;
  working_dir: string;
  status:
    | "running"
    | "completed"
    | "failed"
    | "cancelled"
    | "interrupted"
    | "pending";
  exit_code: number | null;
  stdout: string;
  stderr: string;
  truncated: boolean;
  started_at: string;
  completed_at: string | null;
}

// Live record of an agent-to-agent delegation, mirrored from
// `GET /api/sessions/{parent}/delegations`. Used by the delegation
// request/event cards in chat and by the sidebar inbound badge.
// (agent-collaboration.md §6)
export interface Delegation {
  delegation_id: string;
  sub_session_id: string;
  parent_session_id: string;
  target_agent_id: string;
  target_agent_name: string;
  request: string;
  state: "running" | "completed" | "failed" | "cancelled";
  created_at: string;
  finished_at: string | null;
  error: string | null;
}

// Multi-agent group chat (groups.md). Mirrors the backend GroupInfo
// contract: `sessionId` is the backing group session (1:1).
export interface Group {
  id: string;
  name: string;
  agentIds: string[];
  createdAt: string;
  sessionId: string | null;
  defaultAgentId?: string | null;
}

export interface GroupInvocation {
  id: string;
  group_id: string;
  root_content: string;
  status: "running" | "held" | "completed" | "blocked" | "failed" | "cancelled";
  custody_state: "new" | "active" | "held" | "blocked" | "void" | "dead" | "resolved" | "cancelled";
  current_agent_id: string | null;
  depth: number;
  held_until: string | null;
  hold_reason: string | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

interface GroupAgentBlockBase {
  id: string;
  startedAt: number;
  finishedAt?: number;
  status: "running" | "completed" | "failed";
}

export interface GroupAgentStageBlock extends GroupAgentBlockBase {
  kind: "stage";
  label: string;
}

export interface GroupAgentToolBlock extends GroupAgentBlockBase {
  kind: "tool";
  toolName: string;
  input: Record<string, unknown>;
  output?: string;
}

export interface GroupAgentResponseBlock extends GroupAgentBlockBase {
  kind: "response";
  content: string;
}

export interface GroupAgentErrorBlock extends GroupAgentBlockBase {
  kind: "error";
  content: string;
}

export type GroupAgentActivityBlock =
  | GroupAgentStageBlock
  | GroupAgentToolBlock
  | GroupAgentResponseBlock
  | GroupAgentErrorBlock;

export interface GroupAgentRun {
  runId: string;
  invocationId: string | null;
  agentName: string;
  status: "running" | "completed" | "failed";
  startedAt: number;
  finishedAt?: number;
  durationMs?: number;
  cost?: number;
  error?: string;
  blocks: GroupAgentActivityBlock[];
}

export interface GroupAgentActivityEvent {
  run_id?: string;
  invocation_id?: string | null;
  agent_id?: string | null;
  agent_name: string;
  timestamp_ms?: number;
  phase:
    | "started"
    | "thinking"
    | "text"
    | "tool_started"
    | "tool_finished"
    | "result"
    | "completed"
    | "error";
  tool_name?: string;
  tool_use_id?: string | null;
  tool_input?: Record<string, unknown>;
  output?: string;
  content?: string;
  is_error?: boolean;
  duration_ms?: number | null;
  cost?: number | null;
  detail?: string;
}

function finishRunningPhaseBlocks(
  blocks: GroupAgentActivityBlock[],
  finishedAt: number,
): GroupAgentActivityBlock[] {
  return blocks.map((block) =>
    (block.kind === "stage" || block.kind === "response") &&
    block.status === "running"
      ? { ...block, status: "completed", finishedAt }
      : block,
  );
}

export function reduceGroupAgentRun(
  existing: GroupAgentRun | undefined,
  event: GroupAgentActivityEvent,
): GroupAgentRun {
  const now = event.timestamp_ms ?? Date.now();
  const runId = event.run_id || `${event.agent_name}-${event.invocation_id || "turn"}`;
  let run: GroupAgentRun =
    event.phase === "started" || !existing
      ? {
          runId,
          invocationId: event.invocation_id ?? null,
          agentName: event.agent_name,
          status: "running",
          startedAt: now,
          blocks: [
            {
              id: "started",
              kind: "stage",
              label: "Agent started",
              status: "completed",
              startedAt: now,
              finishedAt: now,
            },
          ],
        }
      : { ...existing, blocks: existing.blocks.map((block) => ({ ...block })) };

  if (event.phase === "thinking") {
    if (
      !run.blocks.some(
        (block) =>
          block.kind === "stage" &&
          block.label === "Reasoning" &&
          block.status === "running",
      )
    ) {
      run.blocks = finishRunningPhaseBlocks(run.blocks, now);
      run.blocks.push({
        id: `thinking-${now}-${run.blocks.length}`,
        kind: "stage",
        label: "Reasoning",
        status: "running",
        startedAt: now,
      });
    }
  } else if (event.phase === "tool_started") {
    run.blocks = finishRunningPhaseBlocks(run.blocks, now);
    const id = event.tool_use_id || `tool-${now}-${run.blocks.length}`;
    const index = run.blocks.findIndex(
      (block) => block.kind === "tool" && block.id === id,
    );
    const tool: GroupAgentToolBlock = {
      id,
      kind: "tool",
      toolName: event.tool_name || "Tool",
      input: event.tool_input || {},
      status: "running",
      startedAt: now,
    };
    run.blocks =
      index >= 0
        ? [
            ...run.blocks.slice(0, index),
            tool,
            ...run.blocks.slice(index + 1),
          ]
        : [...run.blocks, tool];
  } else if (event.phase === "tool_finished") {
    run.blocks = finishRunningPhaseBlocks(run.blocks, now);
    const index = event.tool_use_id
      ? run.blocks.findIndex(
          (block) => block.kind === "tool" && block.id === event.tool_use_id,
        )
      : -1;
    if (index >= 0) {
      const current = run.blocks[index] as GroupAgentToolBlock;
      run.blocks[index] = {
        ...current,
        output: event.output,
        status: event.is_error ? "failed" : "completed",
        finishedAt: now,
      };
    } else {
      run.blocks.push({
        id: event.tool_use_id || `tool-result-${now}-${run.blocks.length}`,
        kind: "tool",
        toolName: event.tool_name || "Tool",
        input: {},
        output: event.output,
        status: event.is_error ? "failed" : "completed",
        startedAt: now,
        finishedAt: now,
      });
    }
  } else if (event.phase === "text" && event.content) {
    run.blocks = finishRunningPhaseBlocks(run.blocks, now);
    const index = run.blocks.findIndex((block) => block.kind === "response");
    const previous =
      index >= 0 ? (run.blocks[index] as GroupAgentResponseBlock) : null;
    const response: GroupAgentResponseBlock = {
      id: "response",
      kind: "response",
      content: previous?.content
        ? `${previous.content}\n\n${event.content}`
        : event.content,
      status: "running",
      startedAt: previous?.startedAt ?? now,
    };
    run.blocks = [
      ...run.blocks.filter((block) => block.kind !== "response"),
      response,
    ];
  } else if (event.phase === "result") {
    run.blocks = finishRunningPhaseBlocks(run.blocks, now);
    run.durationMs = event.duration_ms ?? run.durationMs;
    run.cost = event.cost ?? run.cost;
    if (event.is_error) run.status = "failed";
  } else if (event.phase === "completed") {
    run.blocks = run.blocks.map((block) =>
      block.status === "running"
        ? { ...block, status: "completed", finishedAt: now }
        : block,
    );
    if (run.status !== "failed") run.status = "completed";
    run.finishedAt = now;
    if (!run.blocks.some((block) => block.id === "completed")) {
      run.blocks.push({
        id: "completed",
        kind: "stage",
        label: run.status === "failed" ? "Finished with errors" : "Completed",
        status: run.status === "failed" ? "failed" : "completed",
        startedAt: now,
        finishedAt: now,
      });
    }
  } else if (event.phase === "error") {
    run.blocks = run.blocks.map((block) =>
      block.status === "running"
        ? { ...block, status: "failed", finishedAt: now }
        : block,
    );
    run.status = "failed";
    run.error = event.detail || "Agent execution failed";
    run.finishedAt = now;
    if (
      !run.blocks.some(
        (block) => block.kind === "error" && block.content === run.error,
      )
    ) {
      run.blocks.push({
        id: `error-${now}-${run.blocks.length}`,
        kind: "error",
        content: run.error,
        status: "failed",
        startedAt: now,
        finishedAt: now,
      });
    }
  }

  return run;
}

interface StorageLike {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
  removeItem: (key: string) => void;
}

const memoryStorage = new Map<string, string>();
const storage: StorageLike = (
  typeof globalThis.localStorage !== "undefined" &&
  typeof globalThis.localStorage.getItem === "function" &&
  typeof globalThis.localStorage.setItem === "function" &&
  typeof globalThis.localStorage.removeItem === "function"
)
  ? globalThis.localStorage
  : {
      getItem: (key) => memoryStorage.get(key) ?? null,
      setItem: (key, value) => memoryStorage.set(key, value),
      removeItem: (key) => {
        memoryStorage.delete(key);
      },
    };


export const useSessionStore = create<SessionStore>((set) => ({
  token: storage.getItem("octopus_token") || "",
  setToken: (t) => {
    storage.setItem("octopus_token", t);
    set({ token: t });
  },

  agents: [],
  setAgents: (agents) => set({ agents }),
  upsertAgent: (agent) =>
    set((s) => {
      const idx = s.agents.findIndex((a) => a.id === agent.id);
      const agents =
        idx >= 0
          ? [...s.agents.slice(0, idx), agent, ...s.agents.slice(idx + 1)]
          : [...s.agents, agent];
      return { agents };
    }),
  removeAgent: (id) =>
    set((s) => ({ agents: s.agents.filter((a) => a.id !== id) })),
  activeAgentId: null,
  setActiveAgentId: (activeAgentId) => set({ activeAgentId }),

  availableBackends: ["claude-code"],
  setAvailableBackends: (availableBackends) => set({ availableBackends }),

  sessions: [],
  setSessions: (sessions) => set({ sessions }),
  archivedSessions: [],
  setArchivedSessions: (archivedSessions) => set({ archivedSessions }),
  updateSessionStatus: (id, status) =>
    set((s) => ({
      sessions: s.sessions.map((sess) =>
        sess.id === id ? { ...sess, status } : sess
      ),
    })),

  activeSessionId: null,
  setActiveSessionId: (id) => set({ activeSessionId: id }),

  lastAppliedSeq: {},
  setLastAppliedSeq: (sessionId, seq) =>
    set((s) => {
      const current = s.lastAppliedSeq[sessionId] ?? -1;
      if (seq <= current) return s;
      return { lastAppliedSeq: { ...s.lastAppliedSeq, [sessionId]: seq } };
    }),

  messages: {},
  addMessage: (sessionId, msg) =>
    set((s) => ({
      messages: {
        ...s.messages,
        [sessionId]: [...(s.messages[sessionId] || []), msg],
      },
    })),
  setMessages: (sessionId, msgs) =>
    set((s) => ({
      messages: { ...s.messages, [sessionId]: msgs },
    })),

  schedules: [],
  setSchedules: (schedules) => set({ schedules }),

  credentials: [],
  setCredentials: (credentials) => set({ credentials }),

  connectorCatalog: [],
  setConnectorCatalog: (connectorCatalog) => set({ connectorCatalog }),
  connectorInstallations: [],
  setConnectorInstallations: (connectorInstallations) =>
    set({ connectorInstallations }),
  upsertConnectorInstallation: (c) =>
    set((s) => {
      const idx = s.connectorInstallations.findIndex((i) => i.id === c.id);
      const connectorInstallations =
        idx >= 0
          ? [
              ...s.connectorInstallations.slice(0, idx),
              c,
              ...s.connectorInstallations.slice(idx + 1),
            ]
          : [...s.connectorInstallations, c];
      return { connectorInstallations };
    }),
  removeConnectorInstallation: (id) =>
    set((s) => ({
      connectorInstallations: s.connectorInstallations.filter(
        (i) => i.id !== id
      ),
      // Also drop it from every agent's enabled set so the UI stays consistent.
      agentConnectorIds: Object.fromEntries(
        Object.entries(s.agentConnectorIds).map(([aid, ids]) => [
          aid,
          ids.filter((x) => x !== id),
        ])
      ),
    })),
  agentConnectorIds: {},
  setAgentConnectorIds: (agentId, ids) =>
    set((s) => ({
      agentConnectorIds: { ...s.agentConnectorIds, [agentId]: ids },
    })),

  pendingQueue: {},
  setPendingQueue: (sessionId, queue) =>
    set((s) => {
      const next = { ...s.pendingQueue };
      if (queue.length === 0) delete next[sessionId];
      else next[sessionId] = queue;
      return { pendingQueue: next };
    }),
  enqueuePending: (sessionId, content) =>
    set((s) => ({
      pendingQueue: {
        ...s.pendingQueue,
        [sessionId]: [...(s.pendingQueue[sessionId] || []), content],
      },
    })),
  dequeuePending: (sessionId) =>
    set((s) => {
      const cur = s.pendingQueue[sessionId] || [];
      if (cur.length === 0) return s;
      return {
        pendingQueue: { ...s.pendingQueue, [sessionId]: cur.slice(1) },
      };
    }),
  clearPending: (sessionId) =>
    set((s) => {
      if (!s.pendingQueue[sessionId]) return s;
      const next = { ...s.pendingQueue };
      delete next[sessionId];
      return { pendingQueue: next };
    }),

  pendingForks: {},
  setPendingFork: (sessionId, label) =>
    set((s) => ({
      pendingForks: { ...s.pendingForks, [sessionId]: { label } },
    })),
  clearPendingFork: (sessionId) =>
    set((s) => {
      if (!s.pendingForks[sessionId]) return s;
      const next = { ...s.pendingForks };
      delete next[sessionId];
      return { pendingForks: next };
    }),

  pendingQuestions: {},
  setPendingQuestions: (sessionId, qs) =>
    set((s) => {
      const next = { ...s.pendingQuestions };
      if (qs.length === 0) delete next[sessionId];
      else next[sessionId] = qs;
      return { pendingQuestions: next };
    }),
  addPendingQuestion: (sessionId, q) =>
    set((s) => ({
      pendingQuestions: {
        ...s.pendingQuestions,
        [sessionId]: [...(s.pendingQuestions[sessionId] || []), q],
      },
    })),
  removePendingQuestion: (sessionId, questionId) =>
    set((s) => {
      const cur = s.pendingQuestions[sessionId] || [];
      const filtered = cur.filter((q) => q.question_id !== questionId);
      const next = { ...s.pendingQuestions };
      if (filtered.length === 0) delete next[sessionId];
      else next[sessionId] = filtered;
      return { pendingQuestions: next };
    }),

  connected: false,
  setConnected: (c) => set({ connected: c }),

  viewer: null,
  openViewer: (sessionId, path) => set({ viewer: { sessionId, path } }),
  closeViewer: () => set({ viewer: null }),

  bgTasks: {},
  upsertBgTask: (sessionId, task) =>
    set((s) => {
      const current = s.bgTasks[sessionId] || [];
      const idx = current.findIndex((t) => t.id === task.id);
      const next = idx >= 0
        ? [...current.slice(0, idx), { ...current[idx], ...task }, ...current.slice(idx + 1)]
        : [...current, task];
      return { bgTasks: { ...s.bgTasks, [sessionId]: next } };
    }),
  setBgTasks: (sessionId, tasks) =>
    set((s) => ({ bgTasks: { ...s.bgTasks, [sessionId]: tasks } })),

  research: {},
  upsertResearch: (sessionId, job) =>
    set((s) => {
      const current = s.research[sessionId] || [];
      const idx = current.findIndex((j) => j.id === job.id);
      if (idx < 0) {
        // Inserting a NEW card: only do so from a full payload (started /
        // snapshot). A bare progress/completed/failed patch for an unknown id
        // (missed `research_started` after reconnect or in a 2nd tab) would
        // render a card with no question/status — skip it; the /research
        // snapshot fetch on session load seeds those properly (Vera review).
        if (!job.question || !job.status) return {};
        return { research: { ...s.research, [sessionId]: [...current, job as ResearchJob] } };
      }
      const next = [
        ...current.slice(0, idx),
        { ...current[idx], ...job },
        ...current.slice(idx + 1),
      ];
      return { research: { ...s.research, [sessionId]: next } };
    }),
  setResearch: (sessionId, jobs) =>
    set((s) => ({ research: { ...s.research, [sessionId]: jobs } })),

  delegations: {},
  upsertDelegation: (parentSessionId, d) =>
    set((s) => {
      const current = s.delegations[parentSessionId] || [];
      const idx = current.findIndex((x) => x.delegation_id === d.delegation_id);
      const next =
        idx >= 0
          ? [
              ...current.slice(0, idx),
              { ...current[idx], ...d },
              ...current.slice(idx + 1),
            ]
          : [...current, d];
      return {
        delegations: { ...s.delegations, [parentSessionId]: next },
      };
    }),
  setDelegations: (parentSessionId, ds) =>
    set((s) => ({
      delegations: { ...s.delegations, [parentSessionId]: ds },
    })),

  showDelegations: storage.getItem("octopus_show_delegations") === "true",
  setShowDelegations: (v) => {
    if (v) storage.setItem("octopus_show_delegations", "true");
    else storage.removeItem("octopus_show_delegations");
    set({ showDelegations: v });
  },

  groups: [],
  setGroups: (groups) => set({ groups }),
  upsertGroup: (g) =>
    set((s) => {
      const idx = s.groups.findIndex((x) => x.id === g.id);
      const groups =
        idx >= 0
          ? [...s.groups.slice(0, idx), g, ...s.groups.slice(idx + 1)]
          : [...s.groups, g];
      return { groups };
    }),
  removeGroup: (id) =>
    set((s) => ({ groups: s.groups.filter((g) => g.id !== id) })),
  activeGroupId: null,
  setActiveGroupId: (activeGroupId) => set({ activeGroupId }),

  groupInvocations: {},
  setGroupInvocations: (groupId, rows) =>
    set((s) => ({
      groupInvocations: { ...s.groupInvocations, [groupId]: rows },
    })),
  upsertGroupInvocation: (row) =>
    set((s) => {
      const current = s.groupInvocations[row.group_id] ?? [];
      const index = current.findIndex((item) => item.id === row.id);
      const next = index >= 0
        ? [
            ...current.slice(0, index),
            { ...current[index], ...row },
            ...current.slice(index + 1),
          ]
        : [row, ...current];
      return {
        groupInvocations: {
          ...s.groupInvocations,
          [row.group_id]: next,
        },
      };
    }),

  groupTypingAgents: {},
  addGroupTypingAgent: (sessionId, agentName) =>
    set((s) => {
      const current = s.groupTypingAgents[sessionId] ?? new Set<string>();
      if (current.has(agentName)) return s;
      const next = new Set(current);
      next.add(agentName);
      return { groupTypingAgents: { ...s.groupTypingAgents, [sessionId]: next } };
    }),
  removeGroupTypingAgent: (sessionId, agentName) =>
    set((s) => {
      const current = s.groupTypingAgents[sessionId];
      if (!current || !current.has(agentName)) return s;
      const next = new Set(current);
      next.delete(agentName);
      const copy = { ...s.groupTypingAgents };
      if (next.size > 0) {
        copy[sessionId] = next;
      } else {
        delete copy[sessionId];
      }
      return { groupTypingAgents: copy };
    }),

  groupStreamingReplies: {},
  appendGroupStreamingReply: (sessionId, agentName, chunk) =>
    set((s) => {
      const sessionReplies = s.groupStreamingReplies[sessionId] ?? {};
      const prev = sessionReplies[agentName] ?? "";
      return {
        groupStreamingReplies: {
          ...s.groupStreamingReplies,
          [sessionId]: {
            ...sessionReplies,
            [agentName]: prev + chunk,
          },
        },
      };
    }),
  clearGroupStreamingReply: (sessionId, agentName) =>
    set((s) => {
      const sessionReplies = s.groupStreamingReplies[sessionId];
      if (!sessionReplies || !(agentName in sessionReplies)) return s;
      const copy = { ...s.groupStreamingReplies };
      const updated = { ...copy[sessionId] };
      delete updated[agentName];
      if (Object.keys(updated).length > 0) {
        copy[sessionId] = updated;
      } else {
        delete copy[sessionId];
      }
      return { groupStreamingReplies: copy };
    }),

  groupAgentRuns: {},
  applyGroupAgentActivity: (sessionId, event) =>
    set((s) => {
      const byRun = s.groupAgentRuns[sessionId] ?? {};
      const runId = event.run_id || `${event.agent_name}-${event.invocation_id || "turn"}`;
      const run = reduceGroupAgentRun(byRun[runId], event);

      return {
        groupAgentRuns: {
          ...s.groupAgentRuns,
          [sessionId]: { ...byRun, [runId]: run },
        },
      };
    }),
  clearGroupAgentRun: (sessionId, runId) =>
    set((s) => {
      const byRun = s.groupAgentRuns[sessionId];
      if (!byRun || !(runId in byRun)) return s;
      const nextByRun = { ...byRun };
      delete nextByRun[runId];
      const next = { ...s.groupAgentRuns };
      if (Object.keys(nextByRun).length > 0) {
        next[sessionId] = nextByRun;
      } else {
        delete next[sessionId];
      }
      return { groupAgentRuns: next };
    }),
}));
