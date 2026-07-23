"""Shared parent-chain walker for delegation and group-A2A guards.

Both `delegations._check_chain` (agent-collaboration.md §5.9) and
`group_manager._check_a2a_chain` need to walk the `parent_session_id`
chain upward from some starting session, collecting:

  - the set of agent_ids that appear on the chain (for cycle detection)
  - a hop count for each spawn-origin kind (``delegation`` and
    ``group_reply``), so each caller can apply its own depth cap
    without the two counts polluting each other
  - the visited session ids (fail-closed against session-id pointer
    cycles in the DB)

The walk is factored into this module so the two callers can share the
identical traversal + archived-DB fallback behaviour without one
silently rewriting the other's depth semantics. Policy (what to
reject, what status code to raise) belongs to the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .database import Database
    from .session_manager import SessionManager


# Bound on how many hops we'll.walk before declaring the chain
# corrupted. Real chains are shallow (delegations cap at 3, group A2A
# caps at 3); a chain longer than this is a pointer-corruption bug, not
# a legitimate call graph. Fail-closed: callers raise on the returned
# `exceeded_safety_cap` flag rather than guessing.
_SAFETY_CAP = 64


@dataclass(frozen=True)
class ChainWalk:
    """Result of walking a session's parent chain.

    - ``agent_ids``: every agent_id seen on the chain (excluding the
      starting session's own agent_id when the caller has already
      added it — callers add the spawning agent separately so cycle
      detection includes it). Callers test membership to reject
      cycles.
    - ``delegation_hops``: number of chain rows whose origin is
      ``'delegation'``. Used by ``delegations._check_chain``.
    - ``group_reply_hops``: number of chain rows whose origin is
      ``'group_reply'``. Used by ``group_manager._check_a2a_chain``.
    - ``visited_session_ids``: the set of session ids visited, for
      symmetry with the legacy code; mainly useful for tests.
    - ``exceeded_safety_cap``: True if the walk hit ``_SAFETY_CAP``
      without terminating. Callers MUST fail-closed when this is set.
    - ``broken_pointer``: True if a non-null ``parent_session_id``
      pointed at a session row that exists in neither memory nor the
      DB. Callers MUST fail-closed when this is set.
    - ``session_id_cycle``: True if the same session id appeared twice
      on the chain (a real pointer cycle, distinct from the agent_id
      cycle the caller checks for via ``agent_ids``). Callers MUST
      fail-closed when this is set.
    """

    agent_ids: frozenset[str]
    delegation_hops: int
    group_reply_hops: int
    visited_session_ids: frozenset[str]
    exceeded_safety_cap: bool = False
    broken_pointer: bool = False
    session_id_cycle: bool = False


class ChainWalkError(Exception):
    """Raised by ``walk_parent_chain`` for fail-closed conditions.

    The three fail-closed conditions (safety cap exceeded, broken
    pointer, session-id cycle) all surface as this exception so
    callers cannot silently treat a corrupted chain as a valid
    short one. Callers translate this into their own public error
    type (``DelegationError`` for delegations, swallowed for
    group-A2A cycle/depth handling).
    """

    def __init__(self, kind: str) -> None:
        super().__init__(f"ChainWalkError: {kind}")
        self.kind = kind


async def walk_parent_chain(
    session_mgr: "SessionManager",
    db: "Database",
    start_session_id: str,
) -> ChainWalk:
    """Walk the ``parent_session_id`` chain upward from
    ``start_session_id`` and return a ``ChainWalk`` summary.

    The starting session's own ``agent_id`` is included in
    ``agent_ids`` (callers rely on this for cycle detection: if you
    spawn from a session whose agent is Alice, and the target is
    Alice, ``agent_ids`` already contains her).

    Memory-resident sessions are read via ``session_mgr.get_session``;
    on a miss we fall back to a single bulk DB load
    (``load_sessions(include_archived=True)``) so a legitimately
    archived ancestor still contributes its agent_id and origin to
    the walk. This matches the original delegations behaviour: an
    archived delegation parent must still count toward the depth cap.

    Raises:
        ChainWalkError: if the chain is corrupted (cycle in session
            ids, a pointer to a session that exists nowhere, or a
            chain longer than ``_SAFETY_CAP``).
    """
    agent_ids: set[str] = set()
    visited_session_ids: set[str] = set()
    delegation_hops = 0
    group_reply_hops = 0

    archived_rows_by_id: dict[str, dict] | None = None

    async def _load_archived_index() -> dict[str, dict]:
        rows = await db.load_sessions(include_archived=True)
        return {r["id"]: r for r in rows}

    sid: str | None = start_session_id
    for _ in range(_SAFETY_CAP):
        if sid is None:
            break
        if sid in visited_session_ids:
            raise ChainWalkError("session_id_cycle")
        visited_session_ids.add(sid)
        session = session_mgr.get_session(sid)
        if session is not None:
            agent_id = session.agent_id
            origin = session.origin
            next_sid: str | None = session.parent_session_id
        else:
            if archived_rows_by_id is None:
                archived_rows_by_id = await _load_archived_index()
            row = archived_rows_by_id.get(sid)
            if row is None:
                raise ChainWalkError("broken_pointer")
            agent_id = row.get("agent_id")
            origin = row.get("origin") or "user"
            next_sid = row.get("parent_session_id")
        if agent_id:
            agent_ids.add(agent_id)
        if origin == "delegation":
            delegation_hops += 1
        elif origin == "group_reply":
            group_reply_hops += 1
        sid = next_sid
    else:
        # for/else: exhausted the safety cap without a None terminator.
        raise ChainWalkError("exceeded_safety_cap")

    return ChainWalk(
        agent_ids=frozenset(agent_ids),
        delegation_hops=delegation_hops,
        group_reply_hops=group_reply_hops,
        visited_session_ids=frozenset(visited_session_ids),
    )
