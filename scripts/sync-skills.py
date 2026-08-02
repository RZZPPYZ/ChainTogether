#!/usr/bin/env python3
"""Materialize canonical project skills for Claude Code and Codex."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


PROVENANCE = ".chaintogether-source.json"


def load_catalog(root: Path) -> dict[str, Any]:
    path = root / ".chaintogether" / "skills.yaml"
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(item for item in path.rglob("*") if item.is_file()):
        if file.name == PROVENANCE:
            continue
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def safe_target(root: Path, relative: str, source: Path) -> Path:
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"provider target escapes repository: {target}") from exc
    if target == source or source in target.parents or target in source.parents:
        raise ValueError(f"provider target overlaps canonical source: {target}")
    return target


def sync_one(source: Path, target: Path, *, check: bool) -> list[str]:
    expected = digest_tree(source)
    provenance_path = target / PROVENANCE
    if check:
        if not target.is_dir():
            return [f"missing {target}"]
        if not provenance_path.is_file():
            return [f"unmanaged provider skill {target}"]
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return [f"invalid provenance {provenance_path}"]
        actual = digest_tree(target)
        if provenance.get("source_digest") != expected or actual != expected:
            return [f"stale provider skill {target}"]
        return []

    if target.exists() and not provenance_path.is_file():
        return [f"refusing to overwrite unmanaged provider skill {target}"]
    if target.exists():
        # A managed mount is a mirror, not an overlay. Recreating it removes
        # files deleted or renamed in the canonical package and prevents stale
        # provider-only instructions from surviving a successful sync.
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)
    provenance_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": source.as_posix(),
                "source_digest": expected,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider", action="append", choices=("claude", "codex")
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    root = args.root.resolve()
    catalog = load_catalog(root)
    source_root = (root / str(catalog["source_root"])).resolve()
    providers = args.provider or ["claude", "codex"]
    targets = catalog.get("provider_targets", {})
    issues: list[str] = []
    count = 0
    for provider in providers:
        target_root = safe_target(root, str(targets[provider]), source_root)
        for name in sorted(catalog["skills"]):
            count += 1
            issues.extend(
                sync_one(
                    source_root / name,
                    target_root / name,
                    check=args.check,
                )
            )
    if issues:
        action = "check" if args.check else "sync"
        print(f"FAIL skill {action}: {len(issues)} issue(s)", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1
    action = "checked" if args.check else "synced"
    print(f"PASS skills {action}: {count} provider skill mount(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
