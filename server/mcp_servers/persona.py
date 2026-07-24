"""Read-only access to the active agent persona's supporting resources."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import httpx  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("chaintogether-persona")


def _context() -> tuple[str, str, dict[str, str]] | None:
    api = os.environ.get("OCTOPUS_API_BASE")
    sid = os.environ.get("OCTOPUS_SESSION_ID")
    token = os.environ.get("OCTOPUS_AUTH_TOKEN")
    if not (api and sid and token):
        return None
    return api, sid, {"Authorization": f"Bearer {token}"}


@mcp.tool(name="list_resources")
def list_resources() -> str:
    """List research and example files supplied by the active persona.

    The persona's core instructions are already active. Call this only when
    the current question would benefit from deeper source material or examples.
    """
    ctx = _context()
    if ctx is None:
        return "Error: persona resource server is misconfigured."
    api, sid, headers = ctx
    try:
        response = httpx.get(
            f"{api}/api/sessions/{sid}/persona/resources",
            headers=headers,
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        return f"Error: could not reach ChainTogether: {exc}"
    if response.status_code != 200:
        return f"Error listing persona resources ({response.status_code}): {response.text[:300]}"
    data = response.json()
    resources = data.get("resources") or []
    if not resources:
        return f"{data.get('persona_name', 'Active persona')} has no supporting resources."
    return "\n".join(
        f"- {item['path']} ({item.get('kind', 'reference')}, {item.get('size', 0)} bytes)"
        for item in resources
    )


@mcp.tool(name="read_resource")
def read_resource(path: str) -> str:
    """Read one supporting file from the active persona package.

    Args:
        path: An exact relative path returned by `list_resources`.
    """
    ctx = _context()
    if ctx is None:
        return "Error: persona resource server is misconfigured."
    api, sid, headers = ctx
    try:
        response = httpx.get(
            f"{api}/api/sessions/{sid}/persona/resource",
            params={"path": path},
            headers=headers,
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        return f"Error: could not reach ChainTogether: {exc}"
    if response.status_code != 200:
        return f"Error reading persona resource ({response.status_code}): {response.text[:300]}"
    return response.json().get("content") or ""


if __name__ == "__main__":
    mcp.run()
