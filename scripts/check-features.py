#!/usr/bin/env python3
"""Validate canonical Feature dossiers and optionally regenerate indexes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


STAGES = (
    "discovery",
    "design",
    "planning",
    "implementation",
    "quality",
    "review",
    "merge",
    "acceptance",
    "closure",
    "done",
)
STATES = {"active", "blocked", "done"}
REQUIRED_FIELDS = {
    "schema_version",
    "id",
    "title",
    "stage",
    "state",
    "priority",
    "owner",
    "reviewer",
    "vision_guardian",
    "origin_kind",
    "created_at",
    "updated_at",
}
REQUIRED_HEADINGS = (
    "Why",
    "Current State",
    "Scope",
    "User Journey",
    "Requirements",
    "Acceptance Criteria",
    "Research and Decisions",
    "Architecture Ownership",
    "Design Gate",
    "Delivery",
    "Review Provenance",
    "Vision Gate",
    "Risks and Open Questions",
    "Timeline",
)
FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
FEATURE_DIR_RE = re.compile(r"^(F\d{3,})-[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def parse_frontmatter(text: str) -> dict[str, Any]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("missing YAML frontmatter")
    parsed: dict[str, Any] = {}
    for number, line in enumerate(match.group(1).splitlines(), start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace() or ":" not in line:
            raise ValueError(
                f"unsupported frontmatter syntax at line {number}; "
                "use flat key/value fields and inline JSON lists"
            )
        key, raw = line.split(":", 1)
        key = key.strip()
        if key in parsed:
            raise ValueError(f"duplicate frontmatter key: {key}")
        parsed[key] = parse_scalar(raw)
    return parsed


def section_body(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*$\r?\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def validate_feature(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    issues: list[str] = []
    text = path.read_text(encoding="utf-8-sig")
    try:
        metadata = parse_frontmatter(text)
    except ValueError as exc:
        return None, [f"{path}: {exc}"]

    missing = sorted(REQUIRED_FIELDS - metadata.keys())
    if missing:
        issues.append(f"{path}: missing frontmatter fields: {', '.join(missing)}")

    feature_id = str(metadata.get("id", ""))
    if not re.fullmatch(r"F\d{3,}", feature_id):
        issues.append(f"{path}: invalid id {feature_id!r}")
    if not FEATURE_DIR_RE.fullmatch(path.parent.name):
        issues.append(f"{path}: parent directory must be FNNN-kebab-case")
    elif not path.parent.name.startswith(f"{feature_id}-"):
        issues.append(f"{path}: directory ID does not match frontmatter id")

    stage = metadata.get("stage")
    state = metadata.get("state")
    if stage not in STAGES:
        issues.append(f"{path}: invalid stage {stage!r}")
    if state not in STATES:
        issues.append(f"{path}: invalid state {state!r}")
    if stage == "done" and state != "done":
        issues.append(f"{path}: stage=done requires state=done")
    if state == "done" and stage != "done":
        issues.append(f"{path}: state=done requires stage=done")

    for heading in REQUIRED_HEADINGS:
        if not section_body(text, heading):
            issues.append(f"{path}: missing or empty section '## {heading}'")

    roles = {
        key: str(metadata.get(key, "") or "").strip()
        for key in ("owner", "reviewer", "vision_guardian")
    }
    assigned = [value.casefold() for value in roles.values() if value]
    if len(assigned) != len(set(assigned)):
        issues.append(f"{path}: owner, reviewer, and vision_guardian must differ")

    if re.search(r"^>\s*\*\*Status\*\*:", text, re.MULTILINE):
        issues.append(f"{path}: status must live only in frontmatter")

    if stage in STAGES[2:]:
        design = section_body(text, "Design Gate")
        if not re.search(r"\*\*Verdict\*\*:\s*approved\b", design, re.IGNORECASE):
            issues.append(f"{path}: stage {stage} requires approved Design Gate")

    if stage == "done":
        unchecked = re.findall(r"^-\s*\[ \]\s+AC-", text, re.MULTILINE)
        if unchecked:
            issues.append(f"{path}: done feature has {len(unchecked)} unchecked AC(s)")
        vision = section_body(text, "Vision Gate")
        if not re.search(r"\*\*Verdict\*\*:\s*accepted\b", vision, re.IGNORECASE):
            issues.append(f"{path}: done feature requires accepted Vision Gate")

    return metadata, issues


def collect_features(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    docs_root = root / "docs" / "features"
    records: list[dict[str, Any]] = []
    issues: list[str] = []
    seen: dict[str, Path] = {}
    if not docs_root.is_dir():
        return [], [f"{docs_root}: feature directory not found"]
    for path in sorted(docs_root.glob("F*-*/feature.md")):
        metadata, file_issues = validate_feature(path)
        issues.extend(file_issues)
        if metadata is None:
            continue
        feature_id = str(metadata.get("id", ""))
        if feature_id in seen:
            issues.append(f"{path}: duplicate id also used by {seen[feature_id]}")
        else:
            seen[feature_id] = path
        records.append(
            {
                "id": feature_id,
                "title": metadata.get("title", ""),
                "stage": metadata.get("stage", ""),
                "state": metadata.get("state", ""),
                "priority": metadata.get("priority", ""),
                "file": path.relative_to(root).as_posix(),
            }
        )
    records.sort(key=lambda item: int(str(item["id"])[1:] or 0))
    return records, issues


def write_indexes(root: Path, records: list[dict[str, Any]]) -> None:
    target = root / "docs" / "features"
    (target / "index.json").write_text(
        json.dumps({"schema_version": 1, "features": records}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Feature Index",
        "",
        "> Generated by `python scripts/check-features.py --write-index`.",
        "",
        "| ID | Feature | Stage | State | Priority |",
        "|---|---|---|---|---|",
    ]
    for item in records:
        rel = Path(str(item["file"])).relative_to("docs/features").as_posix()
        lines.append(
            f"| {item['id']} | [{item['title']}]({rel}) | "
            f"{item['stage']} | {item['state']} | {item['priority']} |"
        )
    (target / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--write-index", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    records, issues = collect_features(root)
    if issues:
        print(f"FAIL feature validation: {len(issues)} issue(s)", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1
    if args.write_index:
        write_indexes(root, records)
    print(f"PASS feature validation: {len(records)} feature(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
