from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_PATHS = (
    ".chaintogether/agents.toml",
    "chaintogether.agents.toml",
)

GROUP_RULE_PATHS = (
    ".chaintogether/rules.md",
    "configs/rules.md",
)


def _load_config(working_dir: str) -> dict[str, Any]:
    root = Path(working_dir).expanduser()
    for rel in CONFIG_PATHS:
        path = root / rel
        if not path.is_file():
            continue
        try:
            with path.open("rb") as f:
                data = tomllib.load(f)
        except Exception:
            logger.exception("Failed to load project agent config: %s", path)
            return {}
        if isinstance(data, dict):
            return data
    return {}


def _prompt_from_table(table: Any) -> str | None:
    if not isinstance(table, dict):
        return None
    value = table.get("system_prompt")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _load_first_markdown(working_dir: str, rel_paths: tuple[str, ...]) -> str | None:
    root = Path(working_dir).expanduser()
    for rel in rel_paths:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8").strip()
        except Exception:
            logger.exception("Failed to load project rules file: %s", path)
            return None
        if text:
            return text
    return None


def project_system_prompts(
    working_dir: str,
    agent: dict[str, Any] | None,
    backend: str,
    *,
    group_member: bool = False,
) -> list[str]:
    """Load project-local prompt fragments for the current turn.

    Supported TOML:

    [common]
    system_prompt = "..."

    [backends."claude-code"]
    system_prompt = "..."

    [agents."Agent Name"]
    system_prompt = "..."

    [group]
    system_prompt = "..."
    """
    cfg = _load_config(working_dir)
    if not cfg:
        return []

    prompts: list[str] = []
    for section in (
        cfg.get("common"),
        (cfg.get("backends") or {}).get(backend)
        if isinstance(cfg.get("backends"), dict)
        else None,
    ):
        prompt = _prompt_from_table(section)
        if prompt:
            prompts.append(prompt)

    if agent and isinstance(cfg.get("agents"), dict):
        agents = cfg["agents"]
        names = [agent.get("name"), agent.get("id")]
        for name in names:
            if isinstance(name, str) and name in agents:
                prompt = _prompt_from_table(agents[name])
                if prompt:
                    prompts.append(prompt)
                    break

    if group_member:
        prompt = _prompt_from_table(cfg.get("group"))
        if prompt:
            prompts.append(prompt)
        rules = _load_first_markdown(working_dir, GROUP_RULE_PATHS)
        if rules:
            prompts.append(f"== Project group rules ==\n\n{rules}")

    return prompts
