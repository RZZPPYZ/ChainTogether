"""AgentManager — stateless CRUD + business rules over the `agents` table.

Agents are the durable definition of an assistant (agent-refactor.md §5.1):
pure DB rows, no in-memory subprocess. This layer enforces name uniqueness,
`is_system` protection, and the delete/archive guards for the routes.
SessionManager reads agent rows directly through the Database at spawn time
(so editing an agent affects its open sessions on their next turn); it does
not go through this manager.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from . import agent_memory
from .database import Database


_ALIAS_RE = re.compile(r"^[\w-]+$", re.UNICODE)


class AgentError(Exception):
    """Agent business-rule violation. Routes map this to a 400/409."""


class AgentManager:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def list_agents(
        self, *, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        return await self.db.load_agents(include_archived=include_archived)

    async def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        return await self.db.get_agent(agent_id)

    async def get_default_agent(self) -> dict[str, Any] | None:
        """The protected Default Agent (is_system=1), created by migration."""
        return await self.db.get_system_agent()

    @staticmethod
    def _normalize_alias(alias: str | None) -> str:
        value = (alias or "").strip()
        if not value:
            return ""
        if len(value) > 64 or not _ALIAS_RE.fullmatch(value):
            raise AgentError(
                "Agent alias may contain only letters, numbers, underscores, "
                "and hyphens (maximum 64 characters)"
            )
        if value.lower() == "user":
            raise AgentError("Agent alias cannot be 'user'")
        return value

    async def _validate_identity(
        self, agent_id: str | None, name: str, alias: str
    ) -> None:
        if alias and alias.casefold() == name.casefold():
            raise AgentError("Agent alias must differ from its name")
        for label, handle in (("name", name), ("alias", alias)):
            if not handle:
                continue
            clash = await self.db.get_agent_by_handle(handle)
            if clash is not None and clash["id"] != agent_id:
                raise AgentError(
                    f"Agent {label} {handle!r} conflicts with "
                    f"{clash['name']!r}"
                )

    async def create_agent(
        self,
        *,
        name: str,
        alias: str = "",
        description: str = "",
        avatar: str | None = None,
        system_prompt: str = "",
        model: str | None = None,
        credential_id: str | None = None,
        backend: str = "claude-code",
        mcp_servers: list[str] | None = None,
        tool_allow: str = "",
        tool_deny: str = "",
        persona_ids: list[str] | None = None,
        active_persona_id: str | None = None,
    ) -> dict[str, Any]:
        name = (name or "").strip()
        if not name:
            raise AgentError("Agent name is required")
        alias = self._normalize_alias(alias)
        await self._validate_identity(None, name, alias)
        persona_ids = list(persona_ids or [])
        if active_persona_id is not None and active_persona_id not in persona_ids:
            raise AgentError("Active persona must be assigned to the agent")
        available = {p["id"] for p in await self.db.list_personas()}
        missing = [pid for pid in persona_ids if pid not in available]
        if missing:
            raise AgentError(f"Persona not found: {missing[0]}")
        agent_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        await self.db.save_agent(
            agent_id=agent_id,
            name=name,
            alias=alias,
            created_at=now,
            updated_at=now,
            description=description,
            avatar=avatar,
            system_prompt=system_prompt,
            model=model,
            credential_id=credential_id,
            backend=backend,
            mcp_servers=mcp_servers,
            tool_allow=tool_allow,
            tool_deny=tool_deny,
            is_system=False,
        )
        try:
            await self.db.set_agent_personas(
                agent_id, persona_ids, active_persona_id
            )
        except ValueError as e:
            await self.db.delete_agent(agent_id)
            raise AgentError(str(e)) from e
        agent = await self.db.get_agent(agent_id)
        assert agent is not None
        # Provision the agent's canonical memory/ dir up front; also ensured
        # lazily per turn.
        agent_memory.ensure_agent_dirs(agent_id)
        return agent

    async def update_agent(self, agent_id: str, **fields: Any) -> dict[str, Any]:
        agent = await self.db.get_agent(agent_id)
        if agent is None:
            raise AgentError("Agent not found")
        persona_ids_provided = "persona_ids" in fields
        active_persona_provided = "active_persona_id" in fields
        persona_ids = fields.pop("persona_ids", None)
        active_persona_id = fields.pop("active_persona_id", None)

        if "name" in fields or "alias" in fields:
            new_name = (
                fields["name"].strip()
                if fields.get("name") is not None
                else agent["name"]
            )
            if not new_name:
                raise AgentError("Agent name cannot be empty")
            new_alias = (
                self._normalize_alias(fields.get("alias"))
                if "alias" in fields
                else agent.get("alias", "")
            )
            await self._validate_identity(agent_id, new_name, new_alias)
            if fields.get("name") is not None:
                fields["name"] = new_name
            if "alias" in fields:
                fields["alias"] = new_alias
        if persona_ids_provided or active_persona_provided:
            current_ids = list(agent.get("persona_ids") or [])
            current_active = agent.get("active_persona_id")
            resolved_ids = list(persona_ids or []) if persona_ids_provided else current_ids
            resolved_active = (
                active_persona_id if active_persona_provided else current_active
            )
            if resolved_active not in resolved_ids:
                resolved_active = None
            try:
                await self.db.set_agent_personas(
                    agent_id, resolved_ids, resolved_active
                )
            except ValueError as e:
                raise AgentError(str(e)) from e
        await self.db.update_agent(agent_id, **fields)
        updated = await self.db.get_agent(agent_id)
        assert updated is not None
        return updated

    async def archive_agent(self, agent_id: str) -> None:
        agent = await self.db.get_agent(agent_id)
        if agent is None:
            raise AgentError("Agent not found")
        if agent["is_system"]:
            raise AgentError("The Default Agent cannot be archived")
        await self.db.archive_agent(agent_id)

    async def delete_agent(self, agent_id: str) -> None:
        agent = await self.db.get_agent(agent_id)
        if agent is None:
            raise AgentError("Agent not found")
        if agent["is_system"]:
            raise AgentError("The Default Agent cannot be deleted")
        if await self.db.count_sessions_for_agent(agent_id) > 0:
            raise AgentError(
                "Agent still has sessions; archive it instead of deleting"
            )
        await self.db.delete_agent(agent_id)
        # Hard delete also removes the agent's memory dir. Archiving keeps it,
        # mirroring archived-session history.
        agent_memory.remove_agent_dir(agent_id)
