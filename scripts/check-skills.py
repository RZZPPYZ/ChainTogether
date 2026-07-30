#!/usr/bin/env python3
"""Validate the canonical ChainTogether skill catalog and workflow."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)


def load_json_yaml(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: expected JSON-compatible YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top level must be an object")
    return value


def parse_skill_metadata(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"{path}: missing frontmatter")
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"{path}: invalid frontmatter line {line!r}")
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    extras = sorted(set(metadata) - {"name", "description"})
    if extras:
        raise ValueError(f"{path}: unsupported frontmatter keys: {', '.join(extras)}")
    if not metadata.get("name") or not metadata.get("description"):
        raise ValueError(f"{path}: name and description are required")
    if "[TODO" in text or "TODO:" in text:
        raise ValueError(f"{path}: unresolved TODO")
    if len(text.splitlines()) >= 500:
        raise ValueError(f"{path}: SKILL.md must stay under 500 lines")
    return metadata


def main() -> int:
    root = Path.cwd().resolve()
    issues: list[str] = []
    try:
        catalog = load_json_yaml(root / ".chaintogether" / "skills.yaml")
        workflow = load_json_yaml(
            root / ".chaintogether" / "workflows" / "feature-lifecycle.yaml"
        )
    except ValueError as exc:
        print(f"FAIL skill validation: {exc}", file=sys.stderr)
        return 1

    skills_root = root / str(catalog.get("source_root", ""))
    catalog_skills = catalog.get("skills")
    if not isinstance(catalog_skills, dict):
        issues.append("skills.yaml: skills must be an object")
        catalog_skills = {}
    filesystem_skills = {
        path.parent.name
        for path in skills_root.glob("*/SKILL.md")
        if path.is_file()
    }
    if filesystem_skills != set(catalog_skills):
        missing = sorted(set(catalog_skills) - filesystem_skills)
        extra = sorted(filesystem_skills - set(catalog_skills))
        if missing:
            issues.append(f"catalog skills missing on disk: {', '.join(missing)}")
        if extra:
            issues.append(f"disk skills missing in catalog: {', '.join(extra)}")

    for name in sorted(filesystem_skills):
        skill_dir = skills_root / name
        try:
            metadata = parse_skill_metadata(skill_dir / "SKILL.md")
            if metadata["name"] != name:
                issues.append(f"{name}: frontmatter name is {metadata['name']!r}")
        except ValueError as exc:
            issues.append(str(exc))
        openai_yaml = skill_dir / "agents" / "openai.yaml"
        if not openai_yaml.is_file():
            issues.append(f"{name}: missing agents/openai.yaml")
        else:
            contents = openai_yaml.read_text(encoding="utf-8-sig")
            token = "$" + name
            if token not in contents:
                issues.append(
                    f"{name}: default_prompt must explicitly mention {token}"
                )

    stages = workflow.get("stages")
    transitions = workflow.get("transitions")
    if not isinstance(stages, dict):
        issues.append("workflow: stages must be an object")
        stages = {}
    if not isinstance(transitions, list):
        issues.append("workflow: transitions must be an array")
        transitions = []
    for stage, spec in stages.items():
        if not isinstance(spec, dict):
            issues.append(f"workflow stage {stage}: spec must be an object")
            continue
        referenced: list[str] = []
        if isinstance(spec.get("skill"), str):
            referenced.append(spec["skill"])
        if isinstance(spec.get("skills"), list):
            referenced.extend(spec["skills"])
        for skill in referenced:
            if skill not in catalog_skills:
                issues.append(f"workflow stage {stage}: unknown skill {skill}")
    for transition in transitions:
        if not isinstance(transition, dict):
            issues.append("workflow transition must be an object")
            continue
        if transition.get("from") not in stages:
            issues.append(f"workflow transition has unknown from={transition.get('from')}")
        if transition.get("to") not in stages:
            issues.append(f"workflow transition has unknown to={transition.get('to')}")

    if issues:
        print(f"FAIL skill validation: {len(issues)} issue(s)", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1
    print(
        f"PASS skill validation: {len(filesystem_skills)} skills, "
        f"{len(stages)} stages, {len(transitions)} transitions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
