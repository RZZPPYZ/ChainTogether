"""Mandatory MCP control plane for one autonomous FeatureRun turn.

This stdio child never touches the database. It derives all identity and
generation authority from host-injected environment variables and calls the
Session-bound FastAPI surface.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import httpx  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s feature-mcp %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)
mcp = FastMCP("chaintogether-feature")


def _required(name: str) -> str | None:
    value = os.environ.get(name)
    if not value:
        logger.error("Required env var %s is not set", name)
    return value


def _base_context() -> tuple[str, str, str, dict[str, str]] | None:
    api = _required("OCTOPUS_API_BASE")
    auth = _required("OCTOPUS_AUTH_TOKEN")
    session_id = _required("OCTOPUS_SESSION_ID")
    session_capability = _required("OCTOPUS_SESSION_CAPABILITY")
    run_id = _required("OCTOPUS_FEATURE_RUN_ID")
    if not all((api, auth, session_id, session_capability, run_id)):
        return None
    headers = {
        "Authorization": f"Bearer {auth}",
        "X-Octopus-Session-Capability": session_capability,
    }
    return api, session_id, run_id, headers


def _mutation_context() -> tuple[str, str, str, dict[str, str]] | None:
    context = _base_context()
    dispatch_id = _required("OCTOPUS_FEATURE_DISPATCH_ID")
    dispatch_capability = _required("OCTOPUS_FEATURE_DISPATCH_CAPABILITY")
    if context is None or not dispatch_id or not dispatch_capability:
        return None
    api, session_id, run_id, headers = context
    headers.update(
        {
            "X-Octopus-Feature-Dispatch": dispatch_id,
            "X-Octopus-Dispatch-Capability": dispatch_capability,
        }
    )
    return api, session_id, run_id, headers


def _result(response: httpx.Response, *, mutation: bool = False) -> str:
    if response.status_code != 200:
        return f"Error: Feature control plane rejected the request ({response.status_code}): {response.text[:500]}"
    try:
        payload: Any = response.json()
    except ValueError:
        return "Error: Feature control plane returned invalid JSON."
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if mutation:
        return (
            f"Handoff committed: {rendered}. End this turn now; the control "
            "plane will launch the exact successor actor."
        )
    return rendered


@mcp.tool(name="status")
def feature_status() -> str:
    """Inspect this turn's FeatureRun, role, stage, Skill and next gate."""
    context = _base_context()
    if context is None:
        return "Error: Feature MCP is misconfigured; required turn env is missing."
    api, session_id, run_id, headers = context
    try:
        response = httpx.get(
            f"{api}/api/sessions/{session_id}/features/{run_id}/status",
            headers=headers,
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        return f"Error: failed to reach Feature control plane: {exc}"
    return _result(response)


@mcp.tool(name="transition")
def feature_transition(
    to_stage: str,
    result: str = "",
    reason: str = "",
    evidence_refs: list[str] | None = None,
    revision: str = "",
) -> str:
    """Commit one permitted Feature lifecycle edge and hand off the turn."""
    context = _mutation_context()
    if context is None:
        return "Error: Feature MCP is misconfigured; mutation authority is missing."
    api, session_id, run_id, headers = context
    body = {
        "to_stage": to_stage,
        "result": result,
        "reason": reason,
        "evidence_refs": evidence_refs or [],
        "revision": revision,
    }
    try:
        response = httpx.post(
            f"{api}/api/sessions/{session_id}/features/{run_id}/dispatch/transition",
            headers=headers,
            json=body,
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        return f"Error: failed to reach Feature control plane: {exc}"
    return _result(response, mutation=True)


@mcp.tool(name="request_review")
def feature_request_review(
    evidence_refs: list[str] | None = None,
    revision: str = "",
    reason: str = "SHA-bound review packet is ready for independent review",
) -> str:
    """In Review, hand a SHA-bound packet from owner to assigned reviewer."""
    context = _mutation_context()
    if context is None:
        return "Error: Feature MCP is misconfigured; mutation authority is missing."
    api, session_id, run_id, headers = context
    try:
        response = httpx.post(
            f"{api}/api/sessions/{session_id}/features/{run_id}/dispatch/request-review",
            headers=headers,
            json={
                "reason": reason,
                "evidence_refs": evidence_refs or [],
                "revision": revision,
            },
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        return f"Error: failed to reach Feature control plane: {exc}"
    return _result(response, mutation=True)


if __name__ == "__main__":
    mcp.run(transport="stdio")
