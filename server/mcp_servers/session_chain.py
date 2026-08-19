"""Mandatory, read-only recall tools for the current group session chain."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import httpx  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402


mcp = FastMCP("chaintogether-session-chain")
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _context() -> tuple[str, str, dict[str, str]] | None:
    api = os.environ.get("OCTOPUS_API_BASE")
    auth = os.environ.get("OCTOPUS_AUTH_TOKEN")
    session_id = os.environ.get("OCTOPUS_SESSION_ID")
    capability = os.environ.get("OCTOPUS_SESSION_CAPABILITY")
    if not all((api, auth, session_id, capability)):
        return None
    return api, session_id, {
        "Authorization": f"Bearer {auth}",
        "X-Octopus-Session-Capability": capability,
    }


def _get(path: str, *, params: dict[str, Any] | None = None) -> str:
    context = _context()
    if context is None:
        return "Error: Session Chain MCP is unavailable outside a bound turn."
    api, _, headers = context
    try:
        response = httpx.get(
            f"{api}{path}", headers=headers, params=params, timeout=15.0
        )
    except httpx.HTTPError as exc:
        return f"Error: could not reach Session Chain control plane: {exc}"
    if response.status_code != 200:
        return f"Error: Session Chain request rejected ({response.status_code}): {response.text[:400]}"
    return json.dumps(response.json(), ensure_ascii=False, sort_keys=True)


def _valid_session_id(value: str) -> bool:
    """Session ids are opaque single path segments, never URL fragments."""
    return bool(_SESSION_ID_RE.fullmatch(value))


@mcp.tool(name="list_chain")
def list_chain() -> str:
    """List this group member's generations and sealed predecessors."""
    context = _context()
    if context is None:
        return "Error: Session Chain MCP is unavailable outside a bound turn."
    _, session_id, _ = context
    return _get(f"/api/sessions/{session_id}/session-chain")


@mcp.tool(name="read_events")
def read_events(
    predecessor_session_id: str,
    view: str = "chat",
    offset: int = 0,
    limit: int = 50,
) -> str:
    """Read a page from one sealed predecessor (view: raw/chat/handoff)."""
    if not _valid_session_id(predecessor_session_id):
        return "Error: invalid predecessor session id."
    context = _context()
    if context is None:
        return "Error: Session Chain MCP is unavailable outside a bound turn."
    _, session_id, _ = context
    return _get(
        f"/api/sessions/{session_id}/session-chain/{predecessor_session_id}/events",
        params={"view": view, "offset": offset, "limit": limit},
    )


@mcp.tool(name="read_invocation")
def read_invocation(predecessor_session_id: str, seq: int) -> str:
    """Read one full invocation from its starting user-message sequence."""
    if not _valid_session_id(predecessor_session_id):
        return "Error: invalid predecessor session id."
    context = _context()
    if context is None:
        return "Error: Session Chain MCP is unavailable outside a bound turn."
    _, session_id, _ = context
    return _get(
        f"/api/sessions/{session_id}/session-chain/"
        f"{predecessor_session_id}/invocations/{seq}"
    )


@mcp.tool(name="search")
def search(query: str, limit: int = 20) -> str:
    """Search sealed predecessors and return bounded snippets plus locations."""
    if not query.strip() or len(query) > 256:
        return "Error: search query must contain 1 to 256 characters."
    context = _context()
    if context is None:
        return "Error: Session Chain MCP is unavailable outside a bound turn."
    _, session_id, _ = context
    return _get(
        f"/api/sessions/{session_id}/session-chain/search",
        params={"q": query, "limit": limit},
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
