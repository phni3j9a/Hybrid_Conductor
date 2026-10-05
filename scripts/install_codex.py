#!/usr/bin/env python3
"""Link the two shared skills into Codex's local discovery directory; never overwrite."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("conduct", "herdr-adapter")


def install(target: Path, root: Path = ROOT) -> list[Path]:
    target = target.expanduser().resolve()
    planned: list[tuple[Path, Path]] = []
    # Check all collisions before making any changes.
    for name in SKILLS:
        source = (root / "skills" / name).resolve()
        if not (source / "SKILL.md").is_file():
            raise ValueError(f"Missing skill: {source}")
        destination = target / name
        if destination.is_symlink() and destination.resolve() == source:
            continue
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"Refusing to overwrite {destination}; choose another scope or resolve the conflict.")
        planned.append((source, destination))
    target.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        for source, destination in planned:
            destination.symlink_to(source, target_is_directory=True)
            created.append(destination)
    except OSError:
        for destination in reversed(created):
            destination.unlink()
        raise
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path.home() / ".agents" / "skills",
                        help="Default: ~/.agents/skills; pass <repo>/.agents/skills for repo scope")
    args = parser.parse_args(argv)
    try:
        paths = install(args.target)
    except (OSError, ValueError) as exc:
        print(f"hybrid-conductor: {exc}", file=sys.stderr)
        return 2
    if paths:
        for path in paths:
            print(f"Linked {path} -> {path.resolve()}")
    else:
        print("The two skills are already linked to this package.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
