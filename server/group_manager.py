from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from .group_protocol import GROUP_PRE_SEND_EXIT_CHECK
from .session_manager import resolve_working_dir

if TYPE_CHECKING:
    from .database import Database
    from .session_manager import SessionManager

logger = logging.getLogger(__name__)

# Characters that can appear after a valid @handle without being part of it.
_TOKEN_BOUNDARY = re.compile(r"""[\s,.:;!?()\[\]{}<>,.：；！？、（）【】《》]|\Z""")

# A @-handle name. Unicode-aware so non-ASCII agent names (中文, éàü, …)
# route the same way ASCII ones do — without this the user can type
# `@悟空 帮帮我` and the backend silently never wakes the agent. `\w`
# in Python 3 defaults to Unicode; we keep `-` and `_` so names like
# `Agent-1` / `Agent_2` continue to work.
_HANDLE_RE = re.compile(r"[\w-]+")

# Markdown prefix before a line-start mention: leading whitespace + optional
# quote ("> "), list marker ("- ", "* ", "1. "), possibly nested.
_MD_PREFIX_RE = re.compile(r"^\s*(?:(?:>\s*)|(?:[-*+]\s+)|(?:\d+[.)]\s+))*")

# Fenced code block — stripped before parsing so mentions inside code never route.
_FENCED_CODE_RE = re.compile(r"```[\s\S]*?```")
_MARKDOWN_RULE_RE = re.compile(r"^\s*[-*_]{3,}\s*$")
_MARKDOWN_RULE_MENTION_PREFIX_RE = re.compile(r"^\s*[-*_]{3,}\s+(?=@)")

# Max distinct @-targets per message (safety limit from clowder-ai).
MAX_MENTION_TARGETS = 4

# Max group-context messages sent to a member on its first group turn.
MAX_GROUP_CONTEXT_MESSAGES = 40

# Group activity is persisted in the transcript. Keep verbose CLI payloads
# useful for inspection without allowing one tool event to dominate storage.
_GROUP_ACTIVITY_INPUT_LIMIT = 4000
_GROUP_ACTIVITY_OUTPUT_LIMIT = 12000

# Maximum A2A @-mention hops below the initial user @: user→A is hop 0,
# A@-B is hop 1, B@-C is hop 2, C@-D is hop 3 — D would exceed the cap.
# This cap is deliberately generous; normal runaway prevention lives in
# self/active/pending guards plus the same-pair ping-pong breaker below.
#
# Counted in-memory via the `depth` parameter passed through
# `_dispatch_a2a_mentions` → `_run_mentioned_agent` recursion (no DB
# chain walk). Each A2A hop strictly +1; reaching `depth + 1 > CAP`
# triggers a visible `[agent-error:Target]` injection so the user sees
# the bounce.
# Effective cap used by routing.
GROUP_A2A_DEPTH_CAP = 15
PINGPONG_WARN_THRESHOLD = 2
PINGPONG_BLOCK_THRESHOLD = 4
PINGPONG_OUTPUT_LEN_THRESHOLD = 200
NON_SUBSTANTIVE_TOOL_PATTERNS = (
    "cat_cafe_post_message",
    "cat_cafe_multi_mention",
    "cat_cafe_hold_ball",
    "mcp__ask_agent__ask",
)

_GROUP_HOLD_RE = re.compile(
    r"^\s*\[group-hold:(\d{1,4})\]\s*(.*)$", re.IGNORECASE | re.MULTILINE
)
GROUP_HOLD_MIN_SECONDS = 5
GROUP_HOLD_MAX_SECONDS = 3600

CustodyState = Literal[
    "new", "active", "held", "blocked", "void", "dead", "resolved",
    "cancelled",
]
CustodyEvent = Literal[
    "invocation_started", "ball_handed", "ball_held", "hold_expired",
    "routing_blocked", "routing_void", "task_done", "task_cancelled",
    "task_resumed", "invocation_died",
]

_CUSTODY_TRANSITIONS: dict[CustodyEvent, dict[CustodyState, CustodyState]] = {
    "invocation_started": {"new": "active"},
    "ball_handed": {"active": "active"},
    "ball_held": {"active": "held"},
    "hold_expired": {"held": "dead"},
    "routing_blocked": {"active": "blocked"},
    "routing_void": {"active": "void"},
    "task_done": {"active": "resolved"},
    "task_cancelled": {
        "new": "cancelled", "active": "cancelled", "held": "cancelled",
        "blocked": "cancelled", "void": "cancelled",
    },
    "task_resumed": {"held": "active", "blocked": "active", "void": "active"},
    "invocation_died": {"new": "dead", "active": "dead", "held": "dead"},
}


def transition_custody(state: CustodyState, event: CustodyEvent) -> CustodyState:
    """Apply one explicit group ball-custody transition."""
    target = _CUSTODY_TRANSITIONS.get(event, {}).get(state)
    if target is None:
        raise ValueError(f"Invalid group custody transition: {state} + {event}")
    return target


class GroupError(Exception):
    """Surface-level error for the REST layer."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class _BackendError(Exception):
    """Internal: the reuse session's backend run returned an error event.

    Raised by ``_collect_agent_reply`` so ``_run_mentioned_agent``'s
    ``except Exception`` clause can surface the real backend failure
    text (e.g. ``claude CLI not found on PATH``, ``Session … is busy``)
    in the injected ``[agent-error:Name]`` message instead of the
    generic "Agent produced no reply." that otherwise masks it.
    """


def _compact_activity_value(value: Any, limit: int) -> Any:
    """Return a JSON-safe value, truncating only oversized serialized data."""
    try:
        serialized = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        serialized = str(value)
    if len(serialized) <= limit:
        try:
            return json.loads(serialized)
        except (TypeError, ValueError, json.JSONDecodeError):
            return serialized
    return f"{serialized[:limit]}\n... [truncated]"


def _compact_activity_input(value: Any) -> dict[str, Any]:
    compact = _compact_activity_value(value, _GROUP_ACTIVITY_INPUT_LIMIT)
    return compact if isinstance(compact, dict) else {"value": compact}


def _compact_activity_output(value: Any) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= _GROUP_ACTIVITY_OUTPUT_LIMIT:
        return text
    return f"{text[:_GROUP_ACTIVITY_OUTPUT_LIMIT]}\n... [truncated]"


@dataclass
class WorklistEntry:
    """A currently-active @-mention invocation within a group."""
    agent_id: str
    agent_name: str
    session_id: str          # the (group × agent) reuse session running the turn
    started_at: str


@dataclass
class MentionWorkItem:
    """One queued @-mention target for a group worklist runner."""
    agent: dict[str, Any]
    spawner_agent_ids: frozenset[str] = frozenset()
    spawner_agent_name: str | None = None
    depth: int = 1
    prompt_override: str | None = None


@dataclass
class PingPongStreak:
    from_agent_id: str
    to_agent_id: str
    count: int
    blocked: bool = False


@dataclass(frozen=True)
class AgentTurnResult:
    text: str
    tool_names: tuple[str, ...] = ()

    @property
    def output_length(self) -> int:
        return len(self.text.strip())

    @property
    def had_substantive_activity(self) -> bool:
        if self.output_length > PINGPONG_OUTPUT_LEN_THRESHOLD:
            return True
        return any(is_substantive_tool(name) for name in self.tool_names)


@dataclass(frozen=True)
class AgentRoutingAnalysis:
    """Mechanical routing signals extracted from one agent reply."""

    line_start_mentions: tuple[str, ...]
    invalid_inline_mentions: tuple[str, ...]


@dataclass
class GroupRunState:
    """One isolated, cancellable group invocation."""
    group_id: str
    group_session_id: str    # the backing group session (origin='group')
    invocation_id: str = ""
    root_content: str = ""
    worklist: list[WorklistEntry] = field(default_factory=list)
    pending: list[MentionWorkItem] = field(default_factory=list)
    runner_task: asyncio.Task[None] | None = None
    pingpong_streak: PingPongStreak | None = None
    status: str = "running"
    custody_state: CustodyState = "new"
    current_agent_id: str | None = None
    depth: int = 0
    held_until: str | None = None
    hold_reason: str | None = None
    hold_task: asyncio.Task[None] | None = None
    error: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None


def parse_mentions(text: str) -> list[str]:
    """Extract @-mentioned names from a message string.

    Any @handle in the text is a routing directive. Code blocks are
    stripped before parsing. Handles must be followed by a token
    boundary (whitespace, punctuation, or end-of-string) so that
    email addresses and the like are not treated as mentions.

    Line-start @handles that follow markdown prefixes (quotes, list
    markers) are also routed — the prefix is stripped so that
    ``> @Alice`` and ``- @Bob`` still work.

    Returns deduplicated names in order of first mention, lowercased.
    """
    stripped = _FENCED_CODE_RE.sub("", text)
    seen: set[str] = set()
    result: list[str] = []

    for raw_line in stripped.split("\n"):
        cleaned = _MD_PREFIX_RE.sub("", raw_line.lstrip())
        pos = 0
        while pos < len(cleaned) and len(result) < MAX_MENTION_TARGETS:
            if cleaned[pos] != "@":
                pos += 1
                continue
            # Check what's before the @ — it must be at the start of the
            # line or preceded by a token boundary so that email@domain
            # and other non-mention @-symbols are not treated as routing.
            if pos > 0:
                char_before = cleaned[pos - 1]
                if not _TOKEN_BOUNDARY.match(char_before):
                    pos += 1
                    continue
            pos += 1  # skip the @
            m = _HANDLE_RE.match(cleaned[pos:])
            if not m:
                continue
            name = m.group(0).lower()
            end = pos + m.end()
            # Token boundary check after the name.
            char_after = cleaned[end] if end < len(cleaned) else ""
            if not char_after or _TOKEN_BOUNDARY.match(char_after):
                if name not in seen:
                    seen.add(name)
                    result.append(name)
            pos = end

    return result


def _parse_line_start_mentions(text: str) -> list[str]:
    """Extract line-start handles from the supplied text fragment."""
    stripped = _FENCED_CODE_RE.sub("", text)
    seen: set[str] = set()
    result: list[str] = []
    for raw_line in stripped.split("\n"):
        cleaned = _MD_PREFIX_RE.sub("", raw_line.lstrip())
        if not cleaned.startswith("@"):
            continue
        m = _HANDLE_RE.match(cleaned[1:])
        if not m:
            continue
        name = m.group(0).lower()
        end = 1 + m.end()
        char_after = cleaned[end] if end < len(cleaned) else ""
        if char_after and not _TOKEN_BOUNDARY.match(char_after):
            continue
        if name == "user":
            continue
        if name not in seen:
            seen.add(name)
            result.append(name)
            if len(result) >= MAX_MENTION_TARGETS:
                break
    return result


def parse_agent_mentions(text: str) -> list[str]:
    """Extract valid routing handoffs from an agent reply.

    User messages may route mid-sentence mentions. Agent replies obey the
    mandatory group protocol: only line-start handles in the final non-empty
    paragraph are executable handoffs. A line-start handle earlier in the
    reply is diagnostic input for one-shot correction, not a route.
    """
    slot = _strip_markdown_rules(_final_routing_slot(text))
    mentions = _parse_line_start_mentions(slot)
    if not mentions:
        return []
    # A routing block must begin with a line-start handle. Once established,
    # later lines may continue the handoff instructions without repeating the
    # handle. This keeps ordinary prose non-executable while accepting natural
    # multi-line task descriptions.
    first_content_line = next(
        (line for line in slot.splitlines() if line.strip()), ""
    )
    if not _parse_line_start_mentions(first_content_line):
        return []
    return mentions


def _final_routing_slot(text: str) -> str:
    """Return the final non-empty paragraph after removing fenced code."""
    lines = _FENCED_CODE_RE.sub("", text).splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    start = len(lines)
    while start > 0 and lines[start - 1].strip():
        start -= 1
    return "\n".join(lines[start:])


def _strip_markdown_rules(text: str) -> str:
    """Remove standalone Markdown separator lines from a routing slot."""
    lines: list[str] = []
    for line in text.splitlines():
        if _MARKDOWN_RULE_RE.match(line):
            continue
        lines.append(_MARKDOWN_RULE_MENTION_PREFIX_RE.sub("", line))
    return "\n".join(lines).strip()


def _resolve_roster_handle(
    name: str, roster_names: tuple[str, ...],
) -> str | None:
    """Resolve an exact or unambiguous prefix handle to its roster name."""
    lowered = name.lower()
    exact = [candidate for candidate in roster_names if candidate == lowered]
    if len(exact) == 1:
        return exact[0]
    prefixes = [
        candidate for candidate in roster_names if candidate.startswith(lowered)
    ]
    return prefixes[0] if len(prefixes) == 1 else None


def analyze_agent_routing(
    text: str, member_names: list[str] | tuple[str, ...],
) -> AgentRoutingAnalysis:
    """Find valid routes and known-member inline routing mistakes.

    Inline feedback is deliberately narrow: only handles resolving to a
    current group member in the final non-empty paragraph are reported. This
    avoids treating ordinary references earlier in a substantive reply as a
    failed handoff.
    """
    line_start = tuple(parse_agent_mentions(text))
    if line_start:
        return AgentRoutingAnalysis(line_start, ())

    roster_names = tuple(
        name.lower() for name in member_names if name.lower() != "user"
    )
    invalid: list[str] = []
    final_slot = _strip_markdown_rules(_final_routing_slot(text))
    candidates = [
        *_parse_line_start_mentions(text),
        *parse_mentions(final_slot),
    ]
    for name in candidates:
        resolved = _resolve_roster_handle(name, roster_names)
        if resolved is not None and resolved not in invalid:
            invalid.append(resolved)
    return AgentRoutingAnalysis(line_start, tuple(invalid))


def parse_group_hold(text: str) -> tuple[int, str] | None:
    """Parse a final-slot ``[group-hold:seconds] reason`` action."""
    match = _GROUP_HOLD_RE.search(_strip_markdown_rules(_final_routing_slot(text)))
    if match is None:
        return None
    seconds = max(
        GROUP_HOLD_MIN_SECONDS,
        min(int(match.group(1)), GROUP_HOLD_MAX_SECONDS),
    )
    reason = match.group(2).strip() or "Waiting for an external condition."
    return seconds, reason


def is_substantive_tool(tool_name: str) -> bool:
    """Return True when a tool call indicates real work, not pure routing."""
    lowered = tool_name.lower()
    return not any(pattern in lowered for pattern in NON_SUBSTANTIVE_TOOL_PATTERNS)


def agent_routing_handles(agent: dict[str, Any]) -> tuple[str, ...]:
    """Return the canonical @handle followed by its optional alias."""
    handles = [str(agent["name"])]
    alias = str(agent.get("alias") or "").strip()
    if alias and alias.casefold() != handles[0].casefold():
        handles.append(alias)
    return tuple(handles)


def member_routing_handles(
    member_agents: list[dict[str, Any]],
) -> list[str]:
    """Return handles accepted from user-authored group messages."""
    return [
        handle
        for agent in member_agents
        for handle in agent_routing_handles(agent)
    ]


def member_canonical_handles(
    member_agents: list[dict[str, Any]],
) -> list[str]:
    """Return the canonical handles Agents may use for A2A handoffs."""
    return [str(agent["name"]) for agent in member_agents]


class GroupManager:
    """Multi-agent group chat: CRUD for groups + @-mention routing.

    A group owns ONE backing Session (origin='group', agent_id=system-agent)
    that stores the entire transcript. The system agent never runs a turn on
    it — every message is injected via SessionManager.inject_message (persist
    + broadcast, no backend spawn).

    Each (group × agent) pair owns ONE long-lived reuse Session
    (origin='group_member'). It's created lazily on the first @-mention of
    that agent in that group, and **reused on every subsequent @** so the
    agent keeps its private `--resume` JSONL transcript across turns — it
    remembers what it analyzed last time without needing the group transcript
    to act as its memory. Never auto-archived (only `schedule` and
    `group_reply` origin sessions are); hard-deleted by `delete_group` /
    `remove_member`.

    When a user @-mentions a member agent:

    1. Get-or-create the (group × agent) reuse session (lazy on first @).
    2. Augment the prompt with the recent group transcript as context so the
       agent sees what came before it — this is the message-boundary answer:
       the agent reads up-to-and-including the @-mention, and nothing after.
       (The agent's own prior turns are already in its `--resume` transcript;
       the augmented prompt only carries the group-wide context.)
    3. start_message(reuse_session, augmented) — kicks off the real backend
       turn. If the session is already running another turn (busy),
       start_message queues this prompt behind it (SessionManager's built-in
       busy→queue mechanism serializes naturally — no need for a separate
       worklist-based skip path).
    4. Poll the reuse session until it goes idle, then extract its assistant
       text.
    5. inject_message(group_session, "user", "[agent-reply:Name]\\n\\n<reply>",
       agent_id=agent_id) — the reply lands in the group transcript and the
       frontend renders it as an agent bubble.

    A2A (agent-to-agent) passing: parse the spawned agent's reply for
    @-mentions of other members and append them to the same group worklist
    runner used for user @-mentions. Re-mentioning an earlier agent in the
    chain is allowed (A→B→A is a normal conversation); self-mentions,
    already-active/pending targets, the generous depth cap, and the short
    same-pair ping-pong breaker prevent runaway loops.

    The worklist tracks in-flight turns so the UI can show "Alice is typing…"
    and so a re-@ of an already-typing agent goes through start_message's
    queue (we still broadcast typing only for the first concurrent @ of a
    given agent; subsequent ones just enqueue).
    """

    def __init__(self) -> None:
        self.db: Database | None = None
        self.session_manager: SessionManager | None = None
        self._runs: dict[str, GroupRunState] = {}
        self._invocations: dict[str, GroupRunState] = {}

    def bind(self, session_mgr: "SessionManager", db: "Database") -> None:
        self.db = db
        self.session_manager = session_mgr

    # ------------------------------------------------------------------
    # Group CRUD
    # ------------------------------------------------------------------

    async def create_group(
        self, name: str, agent_ids: list[str],
        default_agent_id: str | None = None,
        working_dir: str | None = None,
    ) -> dict[str, Any]:
        if not self.db or not self.session_manager:
            raise RuntimeError("GroupManager not initialized")
        if len(agent_ids) < 2:
            raise GroupError("A group must have at least 2 agents")
        for aid in agent_ids:
            if await self.db.get_agent(aid) is None:
                raise GroupError(f"Agent {aid} not found", status_code=404)
        if default_agent_id is not None and default_agent_id not in agent_ids:
            raise GroupError("Default reply agent must be a group member")
        requested_working_dir = working_dir.strip() if working_dir else None
        resolved_working_dir = resolve_working_dir(requested_working_dir)
        if not Path(resolved_working_dir).is_dir():
            raise GroupError(
                f"Working directory does not exist: {resolved_working_dir}"
            )

        sys_agent = await self.db.get_system_agent()
        if sys_agent is None:
            raise GroupError("System agent not initialized", status_code=500)

        group_id = uuid.uuid4().hex[:12]
        created_at = datetime.now(timezone.utc).isoformat()
        session = await self.session_manager.create_session(
            agent_id=sys_agent["id"],
            name=f"group:{group_id}",
            working_dir=resolved_working_dir,
            origin="group",
        )
        await self.db.create_group(
            group_id, name, session.id, created_at, agent_ids,
            default_agent_id=default_agent_id,
            working_dir=resolved_working_dir,
        )

        self._runs[group_id] = GroupRunState(
            group_id=group_id, group_session_id=session.id
        )
        return {
            "id": group_id,
            "name": name,
            "agent_ids": list(agent_ids),
            "default_agent_id": default_agent_id,
            "working_dir": resolved_working_dir,
            "created_at": created_at,
            "session_id": session.id,
        }

    async def update_group(
        self,
        group_id: str,
        *,
        name: str | None = None,
        default_agent_id: str | None = None,
    ) -> dict[str, Any] | None:
        if not self.db:
            return None
        group = await self.db.get_group(group_id)
        if group is None:
            return None
        fields: dict[str, Any] = {}
        if name is not None:
            name = name.strip()
            if not name:
                raise GroupError("Group name cannot be empty")
            fields["name"] = name
        if default_agent_id is not None:
            if default_agent_id and default_agent_id not in group["agent_ids"]:
                raise GroupError("Default reply agent must be a group member")
            fields["default_agent_id"] = default_agent_id or None
        updated = await self.db.update_group(group_id, **fields)
        if updated is not None:
            self._populate_session_id(updated)
        return updated

    async def list_groups(self) -> list[dict[str, Any]]:
        if not self.db:
            return []
        groups = await self.db.list_groups()
        for g in groups:
            self._populate_session_id(g)
        return groups

    async def get_group(self, group_id: str) -> dict[str, Any] | None:
        if not self.db:
            return None
        group = await self.db.get_group(group_id)
        if group is None:
            return None
        self._populate_session_id(group)
        return group

    async def delete_group(self, group_id: str) -> bool:
        """Hard-delete a group + its backing session + all (group × agent)
        reuse sessions. Refuses if any agent turn is in-flight.

        Returns False if the group_id doesn't exist (matches the original
        no-op contract for the not-found case). Also returns False if
        GroupManager was never bound to a DB / SessionManager — matches
        ``list_groups`` / ``get_group`` defensive no-DB behaviour for
        callers that hit a non-initialized GroupManager.

        Unlike archived=True, this physically removes the session rows and
        their messages — these sessions are an implementation detail, not
        user-visible conversation history. The user-visible transcript
        lives in the backing session's messages which get CASCADE-deleted
        with the session row.
        """
        if not self.db or not self.session_manager:
            return False
        active_runs = self._group_invocation_runs(group_id)
        if any(self._run_has_active_turns(run) or run.status == "held"
               for run in active_runs):
            raise GroupError("Cannot delete group with active agent turns")

        group = await self.db.get_group(group_id)
        if group is None:
            return False

        # Hard-delete (group × agent) reuse sessions first.
        member_sessions = await self.db.list_group_agent_sessions(group_id)
        result = await self.db.delete_group(group_id)
        for ms in member_sessions:
            await self._hard_delete_session(ms["session_id"])

        # Then the backing group session.
        if group.get("session_id"):
            await self._hard_delete_session(group["session_id"])

        self._runs.pop(group_id, None)
        for invocation_id in [
            iid for iid, run in self._invocations.items()
            if run.group_id == group_id
        ]:
            self._invocations.pop(invocation_id, None)
        return result

    async def add_member(self, group_id: str, agent_id: str) -> None:
        if not self.db:
            raise RuntimeError("GroupManager not initialized")
        group = await self.db.get_group(group_id)
        if group is None:
            raise GroupError("Group not found", status_code=404)
        if await self.db.get_agent(agent_id) is None:
            raise GroupError(f"Agent {agent_id} not found", status_code=404)
        await self.db.add_group_member(
            group_id, agent_id, datetime.now(timezone.utc).isoformat()
        )

    async def remove_member(self, group_id: str, agent_id: str) -> None:
        """Remove a member from the group and hard-delete its (group × agent)
        reuse session. Refuses if the agent has an in-flight turn."""
        if not self.db or not self.session_manager:
            raise RuntimeError("GroupManager not initialized")
        group = await self.db.get_group(group_id)
        if group is None:
            raise GroupError("Group not found", status_code=404)
        if len(group["agent_ids"]) <= 2:
            raise GroupError("A group must have at least 2 agents")
        for run in self._group_invocation_runs(group_id):
            if run.runner_task is not None and not run.runner_task.done():
                raise GroupError("Cannot remove an agent while group turns are active")
            for entry in run.worklist:
                if entry.agent_id == agent_id:
                    raise GroupError("Cannot remove an agent with an active turn")
            for item in run.pending:
                if item.agent["id"] == agent_id:
                    raise GroupError("Cannot remove an agent with a pending turn")

        # Hard-delete the (group × agent) reuse session if it exists.
        reuse_sid = await self.db.get_group_agent_session(group_id, agent_id)
        if reuse_sid:
            await self._hard_delete_session(reuse_sid)
            # CASCADE on session_id FK also clears the row, but be explicit.
            await self.db.delete_group_agent_session(group_id, agent_id)

        await self.db.remove_group_member(group_id, agent_id)

    # ------------------------------------------------------------------
    # @-mention routing
    # ------------------------------------------------------------------

    async def send_message(
        self, group_id: str, content: str,
        attachment_ids: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Process a user message in the group.

        1. Inject the user message into the group session (no system-agent
           turn — inject_message persists + broadcasts only).
        2. Parse @-mentions. If none, the message is stored but no agent wakes.
        3. For each mentioned agent, fire a background task that runs its turn
           in its (group × agent) reuse session and injects the reply back.
        """
        if not self.db or not self.session_manager:
            raise RuntimeError("GroupManager not initialized")

        group = await self.db.get_group(group_id)
        if group is None:
            raise GroupError("Group not found", status_code=404)

        group_session_id = group.get("session_id")
        if not group_session_id:
            base_run = await self._ensure_run_state(group_id)
            group_session_id = base_run.group_session_id

        # 1. Inject the user message. No agent turn is spawned — the system
        #    agent owns the group session but never responds. (attachment_ids
        #    are ignored for now; group attachments are a follow-up.)
        await self.session_manager.inject_message(
            group_session_id, "user", content
        )

        # 2. Load members and parse @-mentions.
        member_agents: list[dict[str, Any]] = []
        for aid in group["agent_ids"]:
            agent = await self.db.get_agent(aid)
            if isinstance(agent, dict):
                member_agents.append(agent)

        mentioned = parse_mentions(content)
        targets: list[dict[str, Any]] = []
        if mentioned:
            for name in mentioned:
                target = self._resolve_agent_by_name(name, member_agents)
                if target is None:
                    logger.warning(
                        "Group %s: @%s matched no member agent", group_id, name,
                    )
                    continue
                targets.append(target)
        else:
            inferred = self._infer_default_reply_agent(
                group,
                await self.db.load_messages(group_session_id),
                member_agents,
            )
            if inferred is not None:
                logger.info(
                    "Group %s: no @mention; inferred @%s as responder",
                    group_id, inferred["name"],
                )
                targets.append(inferred)
        if not targets:
            return None

        invocation_id = uuid.uuid4().hex[:12]
        created_at = datetime.now(timezone.utc).isoformat()
        await self.db.create_group_invocation(
            invocation_id, group_id, content, created_at
        )
        run = GroupRunState(
            group_id=group_id,
            group_session_id=group_session_id,
            invocation_id=invocation_id,
            root_content=content,
            created_at=created_at,
            updated_at=created_at,
            pending=[MentionWorkItem(agent=target) for target in targets],
        )
        await self._transition_invocation(run, "invocation_started")
        self._runs[group_id] = run
        self._invocations[invocation_id] = run
        self._ensure_worklist_runner(run, group)
        return self._invocation_view(run)

    def _ensure_worklist_runner(
        self, run: GroupRunState, group: dict[str, Any],
    ) -> None:
        """Start the group's single @-mention runner if it is not active."""
        task = run.runner_task
        if task is not None and not task.done():
            return
        run.runner_task = asyncio.create_task(
            self._drain_worklist(run, group)
        )

    async def _drain_worklist(
        self, run: GroupRunState, group: dict[str, Any],
    ) -> None:
        """Serially drain queued @-mention targets for one group.

        User mentions and agent-to-agent mentions append to this same queue.
        That keeps routing on one cancellable, depth-checked path instead of
        spawning an independent execution branch per mention.
        """
        try:
            while run.pending and self._invocation_accepts_work(run):
                item = run.pending.pop(0)
                await self._run_mentioned_agent(
                    run,
                    item.agent,
                    group,
                    spawner_agent_ids=item.spawner_agent_ids,
                    spawner_agent_name=item.spawner_agent_name,
                    depth=item.depth,
                    prompt_override=item.prompt_override,
                )
        except asyncio.CancelledError:
            logger.info("Group %s: @-mention worklist cancelled", run.group_id)
            raise
        except Exception:
            logger.exception(
                "Group %s: @-mention worklist failed", run.group_id
            )
        finally:
            current = asyncio.current_task()
            if run.runner_task is current:
                run.runner_task = None
            if run.invocation_id and run.status == "running":
                if run.custody_state == "active" and not run.pending:
                    await self._transition_invocation(run, "task_done")

    async def _run_mentioned_agent(
        self,
        run: GroupRunState,
        agent: dict[str, Any],
        group: dict[str, Any],
        *,
        spawner_agent_ids: frozenset[str] = frozenset(),
        spawner_agent_name: str | None = None,
        depth: int = 1,
        prompt_override: str | None = None,
    ) -> None:
        """Run one agent turn in response to an @-mention.

        Gets-or-creates the (group × agent) reuse session, augments the
        prompt with group context, runs the backend turn via
        ``send_message`` (awaited directly so there is no race with
        fire-and-forget task scheduling), injects the reply back into
        the group transcript, then — if the reply itself @-mentions
        another member agent — recursively dispatches that agent's turn,
        **serially**: the next A2A target only starts after this turn's
        reply has been fully injected (and any A2A chain it spawned has
        drained).

        ``spawner_agent_ids`` is the in-memory snapshot of the agents
        already on this A2A chain. It is carried for attribution and future
        routing policy, but repeated agents are allowed within the depth cap;
        the initial user-@-mention path passes an empty set.

        ``spawner_agent_name`` carries the name of the agent whose reply
        triggered this A2A hop (the ``directMessageFrom`` field from
        clowder-ai). When set, the augmented prompt tells the target
        agent who @-mentioned it so it can respond directly.

        ``depth`` is the number of agents woken up on this chain so far
        (including the current agent). The initial user @-mention starts at
        ``depth=1``; each A2A hop increments.  When ``depth + 1 > CAP`` the
        next target's dispatch is rejected.  This matches the old
        ``group_reply_hops`` logic: user→A=hop 0, A→B=hop 1, B→C=hop 2,
        C→D=hop 3 → D exceeds the cap (= 4th agent, ``depth`` from C is 3,
        ``3 + 1 = 4 > 3``).
        """
        agent_id = agent["id"]
        agent_name = agent["name"]
        if not self._invocation_accepts_work(run):
            return
        run.current_agent_id = agent_id
        run.depth = max(run.depth, depth)
        if run.invocation_id:
            await self._transition_invocation(
                run, "ball_handed", current_agent_id=agent_id, depth=run.depth
            )

        # If this agent is already in-flight in the group, we still proceed:
        # start_message will queue this turn behind the running one. We only
        # skip the typing broadcast (the worklist already shows them typing).
        already_typing = any(
            e.agent_id == agent_id for e in run.worklist
        )

        # Get-or-create the long-lived (group × agent) reuse session.
        reuse_session_id = await self._get_or_create_member_session(
            run, agent, group
        )

        # Build group context up to the message boundary. First turn gets
        # recent history; resumed member turns get only the group delta since
        # this agent's previous committed group reply.
        group_messages = await self.db.load_messages(run.group_session_id)
        member_agents: list[dict[str, Any]] = []
        for aid in group["agent_ids"]:
            a = await self.db.get_agent(aid)
            if isinstance(a, dict):
                member_agents.append(a)
        context = self._format_group_context(
            group_messages, agent_name, member_agents,
            current_agent_id=agent_id,
        )
        group_name = group["name"]
        augmented = self._build_augmented_prompt(
            agent_name, group_name, member_agents, context,
            direct_message_from=spawner_agent_name,
        )
        if prompt_override:
            augmented = f"{augmented}\n\n{prompt_override}"

        agent_backend = agent.get("backend") or "claude-code"
        logger.info(
            "Group %s: @%s -> reuse session %s (backend=%s, depth=%d, spawner=%s)",
            run.group_id, agent_name, reuse_session_id, agent_backend,
            depth, spawner_agent_name or "(user)",
        )

        entry: WorklistEntry | None = None
        if not already_typing:
            entry = WorklistEntry(
                agent_id=agent_id,
                agent_name=agent_name,
                session_id=reuse_session_id,
                started_at=datetime.now(timezone.utc).isoformat(),
            )
            run.worklist.append(entry)
            await self._broadcast_typing(run, agent_name, started=True)

        try:
            # SessionManager owns the configurable idle/overall watchdog. Do
            # not layer a shorter group-only wall-clock cap over an active turn.
            turn = await self._collect_agent_reply(
                reuse_session_id, augmented,
                group_session_id=run.group_session_id,
                agent_id=agent_id,
                agent_name=agent_name,
                invocation_id=run.invocation_id or None,
            )
            reply_text = self._strip_completion_token(turn.text)
            routing_text = reply_text
            routing_turn = AgentTurnResult(
                text=reply_text,
                tool_names=turn.tool_names,
            )

            if not self._invocation_accepts_work(run):
                return

            if reply_text:
                logger.info(
                    "Group %s: injecting %d-char reply from %s",
                    run.group_id, len(reply_text), agent_name,
                )
                await self._inject_agent_reply(
                    run.group_session_id, agent_id, agent_name, reply_text
                )
                hold = parse_group_hold(reply_text)
                if hold is not None:
                    seconds, reason = hold
                    await self._hold_invocation(
                        run, agent_name=agent_name, seconds=seconds, reason=reason
                    )
                    return
                analysis = analyze_agent_routing(
                    reply_text, member_canonical_handles(member_agents)
                )
                if analysis.invalid_inline_mentions:
                    remedial = await self._run_routing_remedial(
                        run=run,
                        reuse_session_id=reuse_session_id,
                        agent_id=agent_id,
                        agent_name=agent_name,
                        invalid_mentions=analysis.invalid_inline_mentions,
                    )
                    if remedial is not None:
                        corrected = analyze_agent_routing(
                            self._strip_completion_token(remedial.text),
                            member_canonical_handles(member_agents),
                        )
                        if corrected.line_start_mentions:
                            remedial_text = self._strip_completion_token(
                                remedial.text
                            )
                            await self._inject_agent_reply(
                                run.group_session_id,
                                agent_id,
                                agent_name,
                                remedial_text,
                            )
                            routing_text = remedial_text
                            routing_turn = AgentTurnResult(
                                text=f"{reply_text}\n\n{remedial_text}",
                                tool_names=turn.tool_names + remedial.tool_names,
                            )
                        else:
                            await self._inject_routing_warning(
                                run.group_session_id,
                                agent_name,
                                "The one-time routing correction still did "
                                "not contain a valid line-start @Agent "
                                "handoff. Automatic correction has stopped.",
                            )
                            routing_text = ""
                            if run.invocation_id:
                                await self._transition_invocation(
                                    run, "routing_void",
                                    error="Routing correction failed.",
                                )
            else:
                await self._inject_agent_error(
                    run.group_session_id, agent_name,
                    "Agent produced no reply.",
                )

            # A2A: parse @-mentions in the reply we just injected and
            # dispatch each new target serially.
            await self._dispatch_a2a_mentions(
                run=run,
                group=group,
                member_agents=member_agents,
                spawner_agent_id=agent_id,
                spawner_agent_name=agent_name,
                spawner_agent_ids=spawner_agent_ids,
                depth=depth,
                reply_text=routing_text or "",
                turn=routing_turn,
            )
        except asyncio.CancelledError:
            logger.info(
                "Group %s: agent %s turn cancelled", run.group_id, agent_name,
            )
        except _BackendError as exc:
            # ``_collect_agent_reply`` raised this because the backend
            # returned an error event (e.g. CLI not installed, or the
            # session was busy). Surface the real reason so the user can
            # act on it instead of seeing the generic "Agent produced no
            # reply." that masks the underlying failure.
            logger.warning(
                "Group %s: agent %s backend error: %s",
                run.group_id, agent_name, exc,
            )
            await self._inject_agent_error(
                run.group_session_id, agent_name, str(exc),
            )
        except Exception as exc:
            logger.exception(
                "Group %s: agent %s turn failed", run.group_id, agent_name
            )
            try:
                await self._inject_agent_error(
                    run.group_session_id, agent_name,
                    f"Agent turn failed unexpectedly: {exc}",
                )
            except Exception:
                logger.exception(
                    "Group %s: also failed to inject error for %s",
                    run.group_id, agent_name,
                )
        finally:
            if entry is not None and entry in run.worklist:
                run.worklist.remove(entry)
            if entry is not None:
                await self._broadcast_typing(run, agent_name, started=False)

    @staticmethod
    def _same_pingpong_pair(
        streak: PingPongStreak, from_agent_id: str, to_agent_id: str
    ) -> bool:
        return (
            {streak.from_agent_id, streak.to_agent_id}
            == {from_agent_id, to_agent_id}
        )

    def _predict_pingpong_count(
        self,
        run: GroupRunState,
        from_agent_id: str,
        to_agent_id: str,
        turn: AgentTurnResult,
    ) -> int:
        if turn.had_substantive_activity:
            return 1
        streak = run.pingpong_streak
        if streak and self._same_pingpong_pair(streak, from_agent_id, to_agent_id):
            return streak.count + 1
        return 1

    def _would_block_pingpong(
        self,
        run: GroupRunState,
        from_agent_id: str,
        to_agent_id: str,
        turn: AgentTurnResult,
    ) -> bool:
        return (
            self._predict_pingpong_count(
                run, from_agent_id, to_agent_id, turn
            )
            >= PINGPONG_BLOCK_THRESHOLD
        )

    def _should_warn_pingpong(
        self,
        run: GroupRunState,
        from_agent_id: str,
        to_agent_id: str,
        turn: AgentTurnResult,
    ) -> bool:
        predicted = self._predict_pingpong_count(
            run, from_agent_id, to_agent_id, turn
        )
        return PINGPONG_WARN_THRESHOLD <= predicted < PINGPONG_BLOCK_THRESHOLD

    def _record_pingpong_enqueue(
        self,
        run: GroupRunState,
        from_agent_id: str,
        to_agent_id: str,
        turn: AgentTurnResult,
    ) -> None:
        predicted = self._predict_pingpong_count(
            run, from_agent_id, to_agent_id, turn
        )
        run.pingpong_streak = PingPongStreak(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            count=predicted,
        )

    def _record_pingpong_block(
        self,
        run: GroupRunState,
        from_agent_id: str,
        to_agent_id: str,
        turn: AgentTurnResult,
    ) -> int:
        predicted = self._predict_pingpong_count(
            run, from_agent_id, to_agent_id, turn
        )
        run.pingpong_streak = PingPongStreak(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            count=predicted,
            blocked=True,
        )
        return predicted

    async def _dispatch_a2a_mentions(
        self,
        *,
        run: GroupRunState,
        group: dict[str, Any],
        member_agents: list[dict[str, Any]],
        spawner_agent_id: str,
        spawner_agent_name: str,
        spawner_agent_ids: frozenset[str],
        depth: int,
        reply_text: str,
        turn: AgentTurnResult | None = None,
    ) -> None:
        """Parse the spawned agent's reply for @-mentions of other
        member agents and dispatch each one serially.

        Order of guards per parsed name:
        1. Unknown member → log + skip.
        2. Self-mention (``@Alice`` by Alice) → skip.
        3. Already typing/busy in this group → skip (start_message would
           queue behind the running turn, but A2A fan-out shouldn't pile
           up turns on a busy agent — let the user re-@ if they want).
        4. Depth cap exceeded (``depth + 1 > GROUP_A2A_DEPTH_CAP``) →
           inject ``[agent-error:Target]`` so the user sees the bounce,
           then continue with the next name.

        Each surviving target is awaited serially, so the next one only
        starts after this one's reply has been injected and its own A2A
        chain has fully drained.
        """
        mentioned = parse_agent_mentions(reply_text)
        if not mentioned:
            return
        if not self._invocation_accepts_work(run):
            return

        turn = turn or AgentTurnResult(reply_text)
        chain_agent_ids = spawner_agent_ids | {spawner_agent_id}
        count_pingpong = len(mentioned) == 1
        if not count_pingpong or turn.had_substantive_activity:
            run.pingpong_streak = None

        has_viable_target = False
        for name in mentioned:
            target = self._resolve_agent_by_name(
                name, member_agents, allow_prefix=False, allow_alias=False
            )
            if target is None:
                logger.info(
                    "Group %s: @%s in %s's reply matched no member; skipping",
                    run.group_id, name, spawner_agent_name,
                )
                await self._inject_routing_warning(
                    run.group_session_id,
                    spawner_agent_name,
                    f"@{name} was not dispatched because it does not "
                    "uniquely match a current group member.",
                )
                continue
            target_id = target["id"]
            if target_id == spawner_agent_id:
                logger.info(
                    "Group %s: @%s self-mention in own reply; skipping",
                    run.group_id, spawner_agent_name,
                )
                await self._inject_routing_warning(
                    run.group_session_id,
                    spawner_agent_name,
                    "A self-mention cannot create a new handoff and was "
                    "ignored.",
                )
                continue
            if any(e.agent_id == target_id for e in run.worklist):
                has_viable_target = True
                logger.info(
                    "Group %s: @%s already active; skipping A2A from %s",
                    run.group_id, target["name"], spawner_agent_name,
                )
                await self._inject_routing_warning(
                    run.group_session_id,
                    spawner_agent_name,
                    f"@{target['name']} is already processing a group turn; "
                    "this duplicate handoff was ignored.",
                )
                continue
            if any(item.agent["id"] == target_id for item in run.pending):
                has_viable_target = True
                logger.info(
                    "Group %s: @%s already pending; skipping A2A from %s",
                    run.group_id, target["name"], spawner_agent_name,
                )
                await self._inject_routing_warning(
                    run.group_session_id,
                    spawner_agent_name,
                    f"@{target['name']} is already queued for this group; "
                    "this duplicate handoff was ignored.",
                )
                continue
            if depth + 1 > GROUP_A2A_DEPTH_CAP:
                msg = (
                    f"Group A2A depth would exceed "
                    f"{GROUP_A2A_DEPTH_CAP} hops"
                )
                logger.warning(
                    "Group %s: @%s A2A rejected (depth > %d)",
                    run.group_id, target["name"], GROUP_A2A_DEPTH_CAP,
                )
                await self._inject_agent_error(
                    run.group_session_id, target["name"], msg,
                )
                if run.invocation_id:
                    await self._transition_invocation(
                        run, "routing_blocked", error=msg
                    )
                continue
            if count_pingpong and self._would_block_pingpong(
                run, spawner_agent_id, target_id, turn
            ):
                pair_count = self._record_pingpong_block(
                    run, spawner_agent_id, target_id, turn
                )
                logger.warning(
                    "Group %s: @%s A2A rejected "
                    "(ping-pong breaker from %s, count=%d)",
                    run.group_id, target["name"], spawner_agent_name, pair_count,
                )
                await self._inject_agent_error(
                    run.group_session_id,
                    target["name"],
                    "Group A2A ping-pong terminated after repeated short "
                    "handoffs between the same two agents. A user message, "
                    "a different target, or substantive work will reset this "
                    "routing streak.",
                )
                if run.invocation_id:
                    await self._transition_invocation(
                        run,
                        "routing_blocked",
                        error="Ping-pong breaker terminated the invocation.",
                    )
                continue
            if count_pingpong and self._should_warn_pingpong(
                run, spawner_agent_id, target_id, turn
            ):
                pair_count = self._predict_pingpong_count(
                    run, spawner_agent_id, target_id, turn
                )
                await self._inject_routing_warning(
                    run.group_session_id,
                    target["name"],
                    "You and the previous agent have handed off short "
                    f"messages {pair_count} times in a row. Continue only "
                    "if you are adding new substance; otherwise summarize, "
                    "choose a different target, or stop passing the task back.",
                )

            item = MentionWorkItem(
                agent=target,
                spawner_agent_ids=chain_agent_ids,
                spawner_agent_name=spawner_agent_name,
                depth=depth + 1,
            )
            has_viable_target = True
            if count_pingpong:
                self._record_pingpong_enqueue(
                    run, spawner_agent_id, target_id, turn
                )
            if run.runner_task is asyncio.current_task():
                run.pending.append(item)
                continue

            # Direct-call fallback for tests and recovery paths that invoke a
            # single agent turn without the group runner.
            await self._run_mentioned_agent(
                run, target, group,
                spawner_agent_ids=item.spawner_agent_ids,
                spawner_agent_name=item.spawner_agent_name,
                depth=item.depth,
                prompt_override=item.prompt_override,
            )
        if (
            run.invocation_id
            and not has_viable_target
            and run.custody_state == "active"
        ):
            await self._transition_invocation(
                run, "routing_void", error="No valid routing target remained."
            )

    async def _collect_agent_reply(
        self, reuse_session_id: str, prompt: str, *,
        group_session_id: str,
        agent_id: str | None = None,
        agent_name: str,
        invocation_id: str | None = None,
    ) -> AgentTurnResult:
        """Drive one member turn and persist its execution timeline."""
        reply_parts: list[str] = []
        error_messages: list[str] = []
        tool_names: list[str] = []
        error_recorded = False
        run_id = uuid.uuid4().hex[:12]

        async def record(phase: str, **details: Any) -> None:
            if not self.session_manager:
                return
            await self.session_manager.inject_group_agent_activity(
                group_session_id,
                {
                    "run_id": run_id,
                    "invocation_id": invocation_id,
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "phase": phase,
                    "timestamp_ms": int(time.time() * 1000),
                    **details,
                },
                agent_id=agent_id,
            )

        await record("started")
        try:
            async for event in self.session_manager.send_message(
                reuse_session_id, prompt
            ):
                etype = event.get("type")
                if etype == "thinking":
                    await record("thinking")
                elif (
                    etype == "assistant_text"
                    and event.get("content", "").strip()
                ):
                    chunk = event["content"].strip()
                    reply_parts.append(chunk)
                    await record("text", content=chunk)
                elif etype == "tool_use":
                    tool_name = (
                        event.get("tool_name")
                        or event.get("tool")
                        or event.get("name")
                        or "Tool"
                    )
                    tool_names.append(str(tool_name))
                    await record(
                        "tool_started",
                        tool_name=str(tool_name),
                        tool_use_id=event.get("tool_use_id"),
                        tool_input=_compact_activity_input(
                            event.get("input") or event.get("tool_input") or {},
                        ),
                    )
                elif etype == "tool_result":
                    await record(
                        "tool_finished",
                        tool_name=event.get("tool_name") or event.get("tool"),
                        tool_use_id=event.get("tool_use_id"),
                        output=_compact_activity_output(
                            event.get("output") or event.get("content") or "",
                        ),
                        is_error=bool(event.get("is_error")),
                    )
                elif etype == "result":
                    is_error = bool(event.get("is_error"))
                    await record(
                        "result",
                        duration_ms=event.get("duration_ms"),
                        cost=event.get("cost"),
                        is_error=is_error,
                    )
                    if is_error:
                        detail = (
                            event.get("message")
                            or "The CLI reported that this turn failed."
                        )
                        error_messages.append(str(detail))
                elif etype == "error" and event.get("message", "").strip():
                    detail = event["message"].strip()
                    error_messages.append(detail)
                    await record("error", detail=detail)
                    error_recorded = True
        except asyncio.CancelledError:
            await record("error", detail="Agent execution was cancelled.")
            raise
        except Exception as exc:
            await record("error", detail=str(exc))
            raise

        if reply_parts:
            await record("completed")
            return AgentTurnResult(
                text="\n\n".join(reply_parts),
                tool_names=tuple(tool_names),
            )
        # No assistant text — surface whatever the backend reported so the
        # user sees the real failure instead of a generic "Agent produced
        # no reply." when the backend in fact errored.
        if error_messages:
            if not error_recorded:
                await record("error", detail="\n".join(error_messages))
            raise _BackendError("\n".join(error_messages))
        await record("completed")
        return AgentTurnResult(text="", tool_names=tuple(tool_names))

    async def _run_routing_remedial(
        self,
        *,
        run: GroupRunState,
        reuse_session_id: str,
        agent_id: str | None,
        agent_name: str,
        invalid_mentions: tuple[str, ...],
    ) -> AgentTurnResult | None:
        """Run one syntax-only correction turn for a failed inline handoff."""
        handles = ", ".join(f"@{name}" for name in invalid_mentions)
        await self._inject_routing_warning(
            run.group_session_id,
            agent_name,
            f"Inline routing mention(s) {handles} were not dispatched. "
            "Agent handoffs must put each @Agent at the start of its own line. "
            "A one-time automatic routing correction is being requested.",
        )
        prompt = (
            "[Routing guard] Your previous reply attempted an inline handoff "
            f"to {handles}, which does not route in group chat.\n"
            "Reply with only the corrected handoff line or lines. Put each "
            "@Agent at the start of its own line. Do not repeat your analysis "
            "or any completed work."
        )
        try:
            remedial = await self._collect_agent_reply(
                reuse_session_id,
                prompt,
                group_session_id=run.group_session_id,
                agent_id=agent_id,
                agent_name=agent_name,
                invocation_id=run.invocation_id or None,
            )
        except _BackendError as exc:
            detail = f"The one-time routing correction failed: {exc}"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception(
                "Group %s: routing correction failed for %s",
                run.group_id,
                agent_name,
            )
            detail = f"The one-time routing correction failed: {exc}"
        else:
            if remedial.text:
                return remedial
            detail = "The one-time routing correction produced no reply."

        logger.warning(
            "Group %s: %s routing correction did not complete: %s",
            run.group_id,
            agent_name,
            detail,
        )
        await self._inject_routing_warning(
            run.group_session_id,
            agent_name,
            f"{detail} Automatic correction has stopped.",
        )
        return None

    async def _broadcast_typing(
        self, run: GroupRunState, agent_name: str, *, started: bool,
    ) -> None:
        """Broadcast a group_typing / group_typing_done event."""
        if not self.session_manager:
            return
        event_type = "group_typing" if started else "group_typing_done"
        await self.session_manager._broadcast({
            "type": event_type,
            "group_id": run.group_id,
            "invocation_id": run.invocation_id or None,
            "agent_name": agent_name,
            "session_id": run.group_session_id,
        })

    # ------------------------------------------------------------------
    # (group × agent) reuse session management
    # ------------------------------------------------------------------

    async def _get_or_create_member_session(
        self, run: GroupRunState, agent: dict[str, Any],
        group: dict[str, Any],
    ) -> str:
        """Return the (group × agent) reuse session id, lazily creating it
        on first @-mention.

        The session is ``origin='group_member'``, parented to the backing
        group session so it shows in the session tree. Never auto-archived
        (only ``schedule`` and ``group_reply`` origins are), so it survives
        server restarts — ``SessionManager.initialize`` re-loads all
        non-archived sessions into ``self.sessions`` automatically.

        On subsequent @-mentions we look up the existing row in
        ``group_agent_sessions``. If the in-memory ``sessions`` map doesn't
        have it (e.g. the server crashed mid-turn and the row was re-loaded
        later), the lookup still returns the right id; ``send_message``
        will rebuild the Session object on demand if needed.
        """
        assert self.db is not None
        assert self.session_manager is not None
        aid = agent["id"]
        existing = await self.db.get_group_agent_session(run.group_id, aid)
        if existing:
            return existing

        child = await self.session_manager.create_session(
            agent_id=aid,
            name=f"{agent['name']} @ {group['name']}",
            working_dir=group["working_dir"],
            origin="group_member",
            parent_session_id=run.group_session_id,
            backend=agent.get("backend") or "claude-code",
            credential_id=agent.get("credential_id"),
        )
        await self.db.upsert_group_agent_session(
            run.group_id, aid, child.id,
            datetime.now(timezone.utc).isoformat(),
        )
        return child.id

    async def _hard_delete_session(self, session_id: str) -> None:
        """Physically remove a session: cancel any in-flight task, pop from
        memory, delete the DB row (messages CASCADE).

        Used by ``delete_group`` (backing + member sessions) and
        ``remove_member`` (the one (group × agent) session). Nothing
        here archives — these sessions are implementation detail, not
        user-visible conversation history.
        """
        assert self.session_manager is not None
        assert self.db is not None
        session = self.session_manager.get_session(session_id)
        if session is not None:
            # Cancel any running turn. The worklist check in callers should
            # have already prevented this, but be defensive.
            if session._active_task and not session._active_task.done():
                session._active_task.cancel()
            session._pending_queue.clear()
            self.session_manager.sessions.pop(session_id, None)
        await self.db.delete_session(session_id)

    # ------------------------------------------------------------------
    # Prompt assembly
    # ------------------------------------------------------------------

    def _build_augmented_prompt(
        self,
        agent_name: str,
        group_name: str,
        member_agents: list[dict[str, Any]],
        context: str,
        *,
        direct_message_from: str | None = None,
    ) -> str:
        """Build the augmented prompt sent to the mentioned agent.

        Includes identity injection, a teammate roster, the relevant group
        transcript window as context, and clear instructions. This follows
        clowder-ai patterns:
        mechanical routing + identity context so the agent knows who it is
        and who its teammates are.

        The agent's own prior turns are carried by its `--resume` JSONL
        transcript (since the (group × agent) session is reused). The
        augmented prompt's role is reduced to *group-wide* context: who the
        other members are and what's happening in the group right now.

        ``direct_message_from`` is the name of the agent whose reply
        @-mentioned this target (the ``directMessageFrom`` field from
        clowder-ai). When set, the prompt includes "You were @-mentioned
        by @{name}" so the agent knows who specifically called on it.
        """
        roster = self._format_roster(member_agents)
        exact_handles = ", ".join(
            f"@{handle}" for handle in member_canonical_handles(member_agents)
        )
        identity_handles = f"@{agent_name}"
        exit_check = GROUP_PRE_SEND_EXIT_CHECK.format(
            valid_handles=exact_handles,
            self_handles=identity_handles,
        )
        origin_line = (
            f"You were @-mentioned by @{direct_message_from} — respond "
            f"to their message. You may @mention another listed agent by "
            f"name to include them."
            if direct_message_from
            else "You were @-mentioned — respond to the message that "
            "mentions you. You may @mention another listed agent by name "
            "to include them."
        )
        return (
            f"You are {identity_handles}, responding in the group chat "
            f"\"{group_name}\".\n\n"
            f"Group members: {roster}\n\n"
            f"Valid routing handles for this turn: {exact_handles}\n\n"
            f"Use canonical Agent names for identity, conversation, and A2A "
            f"handoffs. Aliases are user-only input shortcuts and are not "
            f"Agent names. Ignore any former aliases remembered from earlier "
            f"resumed turns; the canonical roster above is authoritative.\n\n"
            f"Below is the relevant group transcript window. {origin_line}\n\n"
            f"<group_transcript>\n{context}\n</group_transcript>\n\n"
            f"Respond now under the mandatory group routing protocol already "
            f"present in your system instructions. If no teammate meets the "
            f"pre-send exit-check conditions, end naturally with no @handle "
            f"and no completion token. If a teammate must be routed, use a "
            f"final paragraph whose lines begin with exact handles from the "
            f"list above and explain the action, awareness, or work impact. "
            f"If progress must pause, use "
            f"[group-hold:SECONDS] reason. Do not @User, do not @ yourself, "
            f"and use teammate names without @ in explanatory prose. HOLD "
            f"seconds must be between {GROUP_HOLD_MIN_SECONDS} and "
            f"{GROUP_HOLD_MAX_SECONDS}.\n\n"
            f"{exit_check}"
        )

    def _format_roster(
        self, member_agents: list[dict[str, Any]],
    ) -> str:
        """Format the teammate roster for the augmented prompt."""
        parts: list[str] = []
        for a in member_agents:
            backend_label = "Codex" if a.get("backend") == "codex" else "Claude"
            parts.append(f"@{a['name']} ({backend_label})")
        return ", ".join(parts)

    # ------------------------------------------------------------------
    # Injection helpers
    # ------------------------------------------------------------------

    async def _inject_agent_reply(
        self, group_session_id: str, agent_id: str,
        agent_name: str, text: str,
    ) -> None:
        if not self.session_manager:
            return
        prompt = f"[agent-reply:{agent_name}]\n\n{text}"
        try:
            await self.session_manager.inject_message(
                group_session_id, "user", prompt, agent_id=agent_id
            )
        except Exception:
            logger.exception(
                "Failed to inject %s reply into group %s",
                agent_name, group_session_id,
            )

    async def _inject_agent_error(
        self, group_session_id: str, agent_name: str, error_msg: str,
    ) -> None:
        if not self.session_manager:
            return
        prompt = f"[agent-error:{agent_name}]\n\n{error_msg}"
        try:
            await self.session_manager.inject_message(
                group_session_id, "user", prompt
            )
        except Exception:
            logger.exception(
                "Failed to inject %s error into group %s",
                agent_name, group_session_id,
            )

    async def _inject_routing_warning(
        self, group_session_id: str, agent_name: str, warning_msg: str,
    ) -> None:
        if not self.session_manager:
            return
        prompt = f"[agent-routing-warning:{agent_name}]\n\n{warning_msg}"
        try:
            await self.session_manager.inject_message(
                group_session_id, "user", prompt
            )
        except Exception:
            logger.exception(
                "Failed to inject %s routing warning into group %s",
                agent_name, group_session_id,
            )

    async def _inject_invocation_notice(
        self, run: GroupRunState, message: str,
    ) -> None:
        if not self.session_manager or not run.invocation_id:
            return
        prompt = (
            f"[group-invocation:{run.invocation_id}:{run.custody_state}]\n\n"
            f"{message}"
        )
        await self.session_manager.inject_message(
            run.group_session_id, "user", prompt
        )

    # ------------------------------------------------------------------
    # Invocation lifecycle and ball custody
    # ------------------------------------------------------------------

    @staticmethod
    def _status_for_custody(state: CustodyState) -> str:
        return {
            "new": "running",
            "active": "running",
            "held": "held",
            "blocked": "blocked",
            "void": "failed",
            "dead": "failed",
            "resolved": "completed",
            "cancelled": "cancelled",
        }[state]

    def _invocation_view(self, run: GroupRunState) -> dict[str, Any]:
        return {
            "id": run.invocation_id,
            "group_id": run.group_id,
            "root_content": run.root_content,
            "status": run.status,
            "custody_state": run.custody_state,
            "current_agent_id": run.current_agent_id,
            "depth": run.depth,
            "held_until": run.held_until,
            "hold_reason": run.hold_reason,
            "error": run.error,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "completed_at": run.completed_at,
        }

    async def _transition_invocation(
        self,
        run: GroupRunState,
        event: CustodyEvent,
        *,
        current_agent_id: str | None = None,
        depth: int | None = None,
        held_until: str | None = None,
        hold_reason: str | None = None,
        error: str | None = None,
    ) -> None:
        run.custody_state = transition_custody(run.custody_state, event)
        run.status = self._status_for_custody(run.custody_state)
        if current_agent_id is not None:
            run.current_agent_id = current_agent_id
        if depth is not None:
            run.depth = depth
        run.held_until = held_until
        run.hold_reason = hold_reason
        now = datetime.now(timezone.utc).isoformat()
        terminal = run.status in {"completed", "blocked", "failed", "cancelled"}
        run.error = error
        run.updated_at = now
        run.completed_at = now if terminal else None
        if run.invocation_id and self.db:
            await self.db.update_group_invocation(
                run.invocation_id,
                status=run.status,
                custody_state=run.custody_state,
                current_agent_id=run.current_agent_id,
                depth=run.depth,
                held_until=run.held_until,
                hold_reason=run.hold_reason,
                error=error,
                updated_at=now,
                completed_at=now if terminal else None,
            )
            await self._broadcast_invocation(run)

    async def _broadcast_invocation(self, run: GroupRunState) -> None:
        if not self.session_manager or not run.invocation_id:
            return
        await self.session_manager._broadcast({
            "type": "group_invocation",
            "session_id": run.group_session_id,
            "invocation": self._invocation_view(run),
        })

    def _invocation_accepts_work(self, run: GroupRunState) -> bool:
        if not run.invocation_id:
            return True
        return run.status == "running" and run.custody_state in {"new", "active"}

    async def _hold_invocation(
        self,
        run: GroupRunState,
        *,
        agent_name: str,
        seconds: int,
        reason: str,
    ) -> None:
        held_until = (
            datetime.now(timezone.utc) + timedelta(seconds=seconds)
        ).isoformat()
        await self._transition_invocation(
            run,
            "ball_held",
            held_until=held_until,
            hold_reason=reason,
        )
        await self._inject_invocation_notice(
            run,
            f"@{agent_name} paused this chain for up to {seconds} seconds: "
            f"{reason}",
        )
        self._schedule_hold_expiry(run)

    def _schedule_hold_expiry(self, run: GroupRunState) -> None:
        if run.hold_task and not run.hold_task.done():
            run.hold_task.cancel()
        run.hold_task = asyncio.create_task(
            self._expire_hold(run),
            name=f"group-hold-{run.invocation_id}",
        )

    async def _expire_hold(self, run: GroupRunState) -> None:
        if not run.held_until:
            return
        try:
            deadline = datetime.fromisoformat(run.held_until)
            delay = max(
                0.0, (deadline - datetime.now(timezone.utc)).total_seconds()
            )
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        if run.custody_state != "held":
            return
        await self._transition_invocation(
            run,
            "hold_expired",
            error="The group hold expired before the chain was resumed.",
        )
        await self._inject_invocation_notice(
            run, "The hold expired. This chain is now dead and will not resume."
        )

    async def list_invocations(
        self, group_id: str, *, active_only: bool = False,
    ) -> list[dict[str, Any]]:
        if not self.db:
            return []
        if await self.db.get_group(group_id) is None:
            raise GroupError("Group not found", status_code=404)
        return await self.db.list_group_invocations(
            group_id, active_only=active_only
        )

    async def cancel_invocation(
        self, group_id: str, invocation_id: str,
    ) -> dict[str, Any]:
        if not self.db or not self.session_manager:
            raise RuntimeError("GroupManager not initialized")
        row = await self.db.get_group_invocation(invocation_id)
        if row is None or row["group_id"] != group_id:
            raise GroupError("Group invocation not found", status_code=404)
        if row["status"] not in {"running", "held"}:
            raise GroupError("Group invocation is already terminal", status_code=409)
        run = self._invocations.get(invocation_id)
        if run is None:
            group = await self.db.get_group(group_id)
            assert group is not None
            run = self._run_from_row(row, group["session_id"])
            self._invocations[invocation_id] = run
        run.pending.clear()
        if run.hold_task and not run.hold_task.done():
            run.hold_task.cancel()
        await self._transition_invocation(run, "task_cancelled")
        active_sessions = [entry.session_id for entry in run.worklist]
        for session_id in active_sessions:
            await self.session_manager.interrupt(session_id)
        if run.runner_task and not run.runner_task.done():
            run.runner_task.cancel()
        await self._inject_invocation_notice(
            run, "This group chain was cancelled by the user."
        )
        return self._invocation_view(run)

    async def resume_invocation(
        self, group_id: str, invocation_id: str, reason: str = "",
    ) -> dict[str, Any]:
        if not self.db:
            raise RuntimeError("GroupManager not initialized")
        row = await self.db.get_group_invocation(invocation_id)
        if row is None or row["group_id"] != group_id:
            raise GroupError("Group invocation not found", status_code=404)
        if row["custody_state"] not in {"held", "blocked", "void"}:
            raise GroupError("Group invocation cannot be resumed", status_code=409)
        group = await self.db.get_group(group_id)
        if group is None:
            raise GroupError("Group not found", status_code=404)
        run = self._invocations.get(invocation_id)
        if run is None:
            run = self._run_from_row(row, group["session_id"])
            self._invocations[invocation_id] = run
        if not run.current_agent_id:
            raise GroupError("Invocation has no agent to resume", status_code=409)
        agent = await self.db.get_agent(run.current_agent_id)
        if not isinstance(agent, dict):
            raise GroupError("Invocation agent no longer exists", status_code=409)
        if run.hold_task and not run.hold_task.done():
            run.hold_task.cancel()
        await self._transition_invocation(run, "task_resumed")
        run.pending.insert(0, MentionWorkItem(
            agent=agent,
            depth=max(1, run.depth),
            prompt_override=(
                "[Group invocation resumed by the user] Continue the held "
                f"work now. User note: {reason or 'No additional note.'}"
            ),
        ))
        self._runs[group_id] = run
        self._ensure_worklist_runner(run, group)
        await self._inject_invocation_notice(run, "This group chain was resumed.")
        return self._invocation_view(run)

    async def reconcile_zombies(self) -> None:
        """Restore held timers and fail running invocations after a restart."""
        if not self.db:
            return
        rows = await self.db.list_recoverable_group_invocations()
        for row in rows:
            group = await self.db.get_group(row["group_id"])
            if group is None:
                continue
            run = self._run_from_row(row, group["session_id"])
            self._invocations[run.invocation_id] = run
            self._runs[run.group_id] = run
            if run.status == "held" and run.held_until:
                deadline = datetime.fromisoformat(run.held_until)
                if deadline > datetime.now(timezone.utc):
                    self._schedule_hold_expiry(run)
                    await self._broadcast_invocation(run)
                    continue
                await self._transition_invocation(
                    run, "hold_expired", error="Hold expired while server was offline."
                )
                await self._inject_invocation_notice(
                    run, "The hold expired while the server was offline."
                )
                continue
            await self._transition_invocation(
                run,
                "invocation_died",
                error="Server restarted while this invocation was running.",
            )
            await self._inject_invocation_notice(
                run,
                "The server restarted during this chain. It was marked dead "
                "instead of replaying a possibly completed agent turn.",
            )

    def shutdown(self) -> None:
        """Stop local runners; durable rows are reconciled on next startup."""
        for run in self._invocations.values():
            if run.runner_task and not run.runner_task.done():
                run.runner_task.cancel()
            if run.hold_task and not run.hold_task.done():
                run.hold_task.cancel()

    @staticmethod
    def _run_from_row(row: dict[str, Any], session_id: str) -> GroupRunState:
        return GroupRunState(
            group_id=row["group_id"],
            group_session_id=session_id,
            invocation_id=row["id"],
            root_content=row["root_content"],
            status=row["status"],
            custody_state=row["custody_state"],
            current_agent_id=row["current_agent_id"],
            depth=row["depth"],
            held_until=row["held_until"],
            hold_reason=row["hold_reason"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_agent_by_name(
        self,
        name: str,
        member_agents: list[dict[str, Any]],
        *,
        allow_prefix: bool = True,
        allow_alias: bool = True,
    ) -> dict[str, Any] | None:
        name_lower = name.casefold()
        exact = [
            agent
            for agent in member_agents
            if any(
                handle.casefold() == name_lower
                for handle in (
                    agent_routing_handles(agent)
                    if allow_alias
                    else (str(agent["name"]),)
                )
            )
        ]
        exact = list({agent["id"]: agent for agent in exact}.values())
        if len(exact) == 1:
            return exact[0]
        if not allow_prefix:
            return None
        prefix = [
            agent
            for agent in member_agents
            if any(
                handle.casefold().startswith(name_lower)
                for handle in (
                    agent_routing_handles(agent)
                    if allow_alias
                    else (str(agent["name"]),)
                )
            )
        ]
        prefix = list({agent["id"]: agent for agent in prefix}.values())
        if len(prefix) == 1:
            return prefix[0]
        return None

    def _infer_default_reply_agent(
        self,
        group: dict[str, Any],
        messages: list[dict[str, Any]],
        member_agents: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        by_id = {agent["id"]: agent for agent in member_agents}

        # 1. Prefer the most recent agent that replied in the group, if idle.
        for msg in reversed(messages):
            agent_id = msg.get("agent_id")
            if (
                isinstance(agent_id, str)
                and agent_id in by_id
                and msg.get("role") == "user"
                and self._parse_reply_prefix(msg.get("content", "") or "")
                is not None
                and self._agent_idle_for_group(group["id"], agent_id)
            ):
                return by_id[agent_id]

        # 2. Then the most recently @mentioned member in a user-authored
        # message (agent replies/errors are synthetic user rows, so skip them).
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "") or ""
            if (
                self._parse_reply_prefix(content) is not None
                or self._parse_error_prefix(content) is not None
                or content.startswith("[group-invocation:")
            ):
                continue
            for name in reversed(parse_mentions(content)):
                target = self._resolve_agent_by_name(name, member_agents)
                if (
                    target is not None
                    and self._agent_idle_for_group(group["id"], target["id"])
                ):
                    return target

        # 3. Finally use the group's configured fallback agent. This can queue
        # if the fallback is busy; it is the explicit "someone should answer"
        # policy for otherwise ambiguous messages.
        default_agent_id = group.get("default_agent_id")
        if isinstance(default_agent_id, str) and default_agent_id in by_id:
            return by_id[default_agent_id]
        return None

    def _agent_idle_for_group(self, group_id: str, agent_id: str) -> bool:
        return not any(
            entry.agent_id == agent_id
            for run in self._group_invocation_runs(group_id)
            for entry in run.worklist
        )

    def _format_group_context(
        self, messages: list[dict[str, Any]], current_agent_name: str,
        member_agents: list[dict[str, Any]] | None = None,
        *,
        current_agent_id: str | None = None,
    ) -> str:
        text_msgs = [
            m for m in messages
            if m.get("type") == "text" and m.get("role") in ("user", "assistant")
        ]
        last_own_reply_idx: int | None = None
        if current_agent_id:
            for idx in range(len(text_msgs) - 1, -1, -1):
                msg = text_msgs[idx]
                if (
                    msg.get("agent_id") == current_agent_id
                    and msg.get("role") == "user"
                    and self._parse_reply_prefix(msg.get("content", "") or "")
                    is not None
                ):
                    last_own_reply_idx = idx
                    break
        if last_own_reply_idx is None:
            recent = text_msgs[-MAX_GROUP_CONTEXT_MESSAGES:]
        else:
            recent = text_msgs[last_own_reply_idx + 1:]
        # Build agent_id -> name lookup for attribution.
        agent_names: dict[str, str] = {}
        if member_agents:
            for a in member_agents:
                agent_names[a["id"]] = a["name"]
        lines: list[str] = []
        for m in recent:
            role = m.get("role", "unknown")
            content = m.get("content", "") or ""
            agent_id = m.get("agent_id")
            if role == "user":
                reply = self._parse_reply_prefix(content)
                err = self._parse_error_prefix(content)
                if reply is not None:
                    rname, rtext = reply
                    lines.append(f"[Agent {rname}]: {rtext}")
                elif err is not None:
                    ename, etext = err
                    lines.append(f"[Agent {ename}] (error): {etext}")
                else:
                    lines.append(f"[User]: {content}")
            elif agent_id and agent_id in agent_names:
                lines.append(f"[Agent {agent_names[agent_id]}]: {content}")
            elif agent_id:
                lines.append(f"[Agent {agent_id}]: {content}")
            else:
                lines.append(f"[Assistant]: {content}")
        if not lines:
            return (
                f"No new group messages since @{current_agent_name}'s previous "
                "turn. Continue from your resumed private context."
            )
        return "\n".join(lines)

    @staticmethod
    def _strip_completion_token(text: str) -> str:
        """Remove accidental standalone STOP/DONE tokens from group replies."""
        stripped = text.strip()
        if stripped.upper() in {"STOP", "DONE"}:
            return ""
        lines = stripped.splitlines()
        while lines and lines[-1].strip().upper() in {"STOP", "DONE"}:
            lines.pop()
            while lines and not lines[-1].strip():
                lines.pop()
        return "\n".join(lines).strip()

    @staticmethod
    def _parse_reply_prefix(content: str) -> tuple[str, str] | None:
        """If `content` is an injected [agent-reply:Name] message, return
        (name, body); otherwise None."""
        if not content.startswith("[agent-reply:"):
            return None
        end = content.find("]")
        if end < 0:
            return None
        name = content[len("[agent-reply:"):end]
        body = content[end + 1:].lstrip("\n").strip()
        return name, body

    @staticmethod
    def _parse_error_prefix(content: str) -> tuple[str, str] | None:
        """If `content` is an injected [agent-error:Name] message, return
        (name, body); otherwise None."""
        if not content.startswith("[agent-error:"):
            return None
        end = content.find("]")
        if end < 0:
            return None
        name = content[len("[agent-error:"):end]
        body = content[end + 1:].lstrip("\n").strip()
        return name, body

    def _populate_session_id(self, group: dict[str, Any]) -> None:
        """The DB row already carries session_id; keep the in-memory run
        state's copy authoritative if it differs (defensive)."""
        run = self._runs.get(group["id"])
        if run:
            group["session_id"] = run.group_session_id

    @staticmethod
    def _run_has_active_turns(run: GroupRunState) -> bool:
        if run.worklist or run.pending:
            return True
        return run.runner_task is not None and not run.runner_task.done()

    def _group_invocation_runs(self, group_id: str) -> list[GroupRunState]:
        runs = [
            run for run in self._invocations.values()
            if run.group_id == group_id
        ]
        if runs:
            return runs
        fallback = self._runs.get(group_id)
        return [fallback] if fallback is not None else []

    async def _ensure_run_state(
        self, group_id: str
    ) -> GroupRunState:
        if not self.db or not self.session_manager:
            raise RuntimeError("GroupManager not initialized")
        group = await self.db.get_group(group_id)
        if group and group.get("session_id"):
            return GroupRunState(
                group_id=group_id, group_session_id=group["session_id"]
            )
        # No backing session row — create one (recovery path).
        sys_agent = await self.db.get_system_agent()
        session = await self.session_manager.create_session(
            agent_id=sys_agent["id"],
            name=f"group:{group_id}",
            origin="group",
        )
        return GroupRunState(group_id=group_id, group_session_id=session.id)

    def get_worklist(self, group_id: str) -> list[dict[str, Any]]:
        return [
            {
                "invocation_id": run.invocation_id or None,
                "agent_id": e.agent_id,
                "agent_name": e.agent_name,
                "session_id": e.session_id,
                "started_at": e.started_at,
            }
            for run in self._group_invocation_runs(group_id)
            for e in run.worklist
        ]


# Module-level singleton (same pattern as delegation_manager).
group_manager = GroupManager()
